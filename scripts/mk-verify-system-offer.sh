#!/usr/bin/env bash
# Verify complete-system offers (DGX Spark, Mac Studio, ...) on the local cluster.
#
# What runs for real: the fit rules against the seeded catalog, the offer store
# in the cluster's Valkey and Postgres, the select-system command through the
# DISPATCHED path (Pub/Sub, a worker pod, the Valkey event stream), the one-shot
# claim, and commerce resolving a family-level eBay listing for a system.
#
# NO LLM IS CALLED. The offer's pitch and the custom build run on load-test
# stubs (see mk-smoke.sh for how). That is also why the offer is created
# in-cluster rather than by chatting: the stubs extract a fixed gaming profile,
# which is never offered a system, so a chat turn cannot reach the offer node
# without spending on a real model. Everything after the offer exists is
# driven through /chat exactly as the browser drives it.
#
#   ./scripts/mk-verify-system-offer.sh
#
# Requires `tilt up` with its port-forwards, a migrated database, and the
# system catalog seeded (uv run python -m app.seeds.seed_systems).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

API="${PALLADIUM_API:-http://localhost:8000}"
COMMERCE="${PALLADIUM_COMMERCE:-http://localhost:8080}"
PGDB="${PALLADIUM_LOCAL_PG_DB:-palladium_local}"

pass() { printf '  \033[32mPASS\033[0m  %s\n' "$*"; }
fail() { printf '  \033[31mFAIL\033[0m  %s\n' "$*" >&2; FAILED=1; }
step() { printf '\n== %s\n' "$*"; }
FAILED=0

valkey() { kubectl exec deploy/valkey -- valkey-cli "$@" 2>/dev/null; }
# -q: without it a data-modifying statement prints its command tag ("INSERT 0 1")
# after the rows it returns, and `tail -1` would hand back the tag, not the id.
psql_()  { kubectl exec statefulset/postgres -- psql -q -U palladium_app -d "$PGDB" -tAc "$1" 2>/dev/null | tail -1; }

# --- preflight ---------------------------------------------------------------
step "preflight"
CTX="$(kubectl config current-context)"
[ "$CTX" = "minikube" ] || { echo "refusing to run against context '$CTX'" >&2; exit 1; }
pass "kubectl context is minikube"

SECRET="$(grep -E '^LOAD_TEST_SECRET=' deploy/overlays/local/.env.local | head -1 | cut -d= -f2-)"
[ -n "$SECRET" ] || { echo "LOAD_TEST_SECRET missing from deploy/overlays/local/.env.local" >&2; exit 1; }
curl -sf -m 10 -o /dev/null "$API/api/v1/healthz" || { echo "builder not reachable at $API" >&2; exit 1; }
curl -sf -m 10 -o /dev/null "$COMMERCE/healthz" || { echo "commerce not reachable at $COMMERCE" >&2; exit 1; }
[ "$(valkey ping)" = "PONG" ] || { echo "valkey not answering" >&2; exit 1; }
pass "builder, commerce and valkey answering"

SYSTEMS="$(psql_ 'select count(*) from systems')"
[ "${SYSTEMS:-0}" -gt 0 ] || { echo "no systems in $PGDB; run app.seeds.seed_systems" >&2; exit 1; }
pass "$SYSTEMS systems in the catalog"

# --- the rules, against the real catalog --------------------------------------
# A 70B model at 4-bit is ~42GB: past any single consumer card, so the rules
# should find a system cheaper than the discrete-GPU estimate. Two offers are
# saved, one to decline and one to take.
step "the rules find an offer for a 70B local-LLM profile"
OFFER="$(kubectl exec -i deploy/builder -- sh -c 'cd /app && python - 2>/dev/null' <<'PY' | tail -1
import asyncio, json
from app.schemas.chat import BuildProfile
from app.services import chat_pipeline as cp
from app.services.systems import catalog, offer

profile = BuildProfile(
    primary_use="ai", budget_tier="high", ai_workload="inference",
    ai_model_scale="large", llm_quantization="yes", llm_context_tokens="8k",
    stated_budget_usd=5000, price_sensitivity="flexible",
)

async def main():
    async def reference():
        _key, built, _cached = await cp._get_reference_build(profile, None)
        return dict(built)
    found = await catalog.assess_profile(profile, reference)
    if found is None:
        print(json.dumps({"offer": None}))
        return
    tokens = [await offer.save(None, profile, found) for _ in range(2)]
    print(json.dumps({
        "offer": True,
        "part_id": found.primary.part_id,
        "family_id": found.primary.family_id,
        "name": found.primary.name,
        "need": found.memory_need_gb,
        "tokens": tokens,
    }))

asyncio.run(main())
PY
)"
field() { python3 -c "import json,sys; d=json.loads(sys.argv[1]); v=d$2; print(v if v is not None else '')" "$OFFER"; }
if [ "$(field "$OFFER" '["offer"]')" != "True" ]; then
  fail "no offer for a 70B profile: $OFFER"
  exit 1
fi
PART_ID="$(field "$OFFER" '["part_id"]')"
FAMILY_ID="$(field "$OFFER" '["family_id"]')"
DECLINE_TOKEN="$(field "$OFFER" '["tokens"][0]')"
TAKE_TOKEN="$(field "$OFFER" '["tokens"][1]')"
pass "offered $(field "$OFFER" '["name"]') for a ~$(field "$OFFER" '["need"]')GB need"
[ -n "$DECLINE_TOKEN" ] && [ -n "$TAKE_TOKEN" ] && pass "offer saved to the store" \
  || fail "offer could not be saved (both stores refused)"

# --- answering, through the dispatched path ------------------------------------
pick() {
  local token="$1" choice="$2"
  curl -sS -N -m 300 -X POST "$API/api/v1/chat" \
    -H 'Content-Type: application/json' \
    -H "X-Palladium-Load-Test: $SECRET" \
    -d "{\"conversation_id\":null,\"state\":{\"messages\":[],\"pipeline\":null},
         \"commands\":[{\"type\":\"select-system\",\"token\":\"$token\",\"choice\":\"$choice\"}]}"
}
has() { grep -Eq "$1" <<<"$2"; }

step "\"build a custom PC instead\" builds, with the system attached"
CLAIMS_BEFORE="$(valkey --scan --pattern 'chat:claim:*' | sort | tr '\n' ' ')"
RESP="$(pick "$DECLINE_TOKEN" custom)"
has '"chosen": ?"custom"' "$RESP" && pass "offer resolved as declined" || fail "offer was not resolved as declined"
has '"total_approx"' "$RESP" && pass "a custom build came back" || fail "no custom build"
has '"system_comparison"' "$RESP" && pass "the build carries the declined system for the side by side" \
  || fail "build has no system_comparison"

NEW_CLAIM=""
for key in $(valkey --scan --pattern 'chat:claim:*'); do
  case " $CLAIMS_BEFORE " in *" $key "*) continue;; esac
  NEW_CLAIM="$key"; break
done
OWNER="$( [ -n "$NEW_CLAIM" ] && valkey get "$NEW_CLAIM" || true)"
case "$OWNER" in
  worker-*) pass "the pick ran on $OWNER, not inline" ;;
  *)        fail "the pick did not reach a worker (claim owner '$OWNER')" ;;
esac

step "a second click on the same offer is refused"
RESP="$(pick "$DECLINE_TOKEN" custom)"
has 'expired' "$RESP" && pass "told the offer has expired" || fail "no expiry message on a reused token"
has '"total_approx"' "$RESP" && fail "a second build ran from one offer" || pass "no second build"

step "\"go with it\" records the system and builds nothing"
RESP="$(pick "$TAKE_TOKEN" "$PART_ID")"
has "\"chosen\": ?\"$PART_ID\"" "$RESP" && pass "offer resolved as taken" || fail "offer was not resolved as taken"
has '"total_approx"' "$RESP" && fail "a build ran after the system was taken" || pass "no build"

# --- where to buy ----------------------------------------------------------------
# One eBay search on the family covers every variant, the way one "RTX 3090"
# search covers every board. Inserted, read back through commerce, removed.
step "commerce resolves a family eBay listing for a system"
LISTING_ID="$(psql_ "with l as (
    insert into listings (id, system_family_id, listing_type, marketplace, url, is_active, created_at, updated_at)
    values (gen_random_uuid(), '$FAMILY_ID', 'ebay', 'ebay', 'https://www.ebay.com/sch/i.html?_nkw=mk-verify-system-offer', true, now(), now())
    returning id)
  insert into ebay_listings (id, ebay_item_id) select id, 'mk-verify' from l returning id")"
trap '[ -n "${LISTING_ID:-}" ] && psql_ "delete from listings where id = '"'"'$LISTING_ID'"'"'" >/dev/null' EXIT
BODY="$(curl -sS -m 10 "$COMMERCE/api/v1/listings/by-part/$PART_ID")"
has 'mk-verify-system-offer' "$BODY" && pass "by-part lookup for the system returns its family listing" \
  || fail "family listing not returned for the system: $BODY"

step "result"
if [ "$FAILED" = "0" ]; then
  printf '  \033[32mall checks passed\033[0m\n'
else
  printf '  \033[31mone or more checks failed\033[0m\n' >&2
fi
exit "$FAILED"
