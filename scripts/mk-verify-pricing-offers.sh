#!/usr/bin/env bash
# Verify the offer parser end to end on the local cluster.
#
# What runs for real, inside the builder pod: perform_fetch (quota, fake-gcs
# raw write, price_fetches row), the parser with merchant rules read from
# Postgres, record_parsed (price_offers, estimate, band, price_history_points),
# and reparse_fetch reading the response back from GCS, which is the whole
# reason responses are stored raw.
#
# What does not: the HTTP call to SerpApi, replaced by an httpx.MockTransport
# serving a recorded response. NO SerpApi quota is spent; the LOCAL quota row
# rises by 2. The response is the real capture in .local-seed/serpapi/ when it
# exists (raw responses are never committed), else the hand-written sample in
# backend/tests/pricing/serpapi_samples.py.
#
#   ./scripts/mk-verify-pricing-offers.sh
#
# Requires `tilt up` with fake-gcs running, the migration at head
# (e2a4c6e8f0b1 or later), and a "Ryzen 7 7800X3D" row in pc_parts.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

PGDB="${PALLADIUM_LOCAL_PG_DB:-palladium_local}"
CAPTURE="${PALLADIUM_SERPAPI_CAPTURE:-.local-seed/serpapi/google_product_ryzen7_7800x3d_2026-10-21.json}"

pass() { printf '  \033[32mPASS\033[0m  %s\n' "$*"; }
fail() { printf '  \033[31mFAIL\033[0m  %s\n' "$*" >&2; FAILED=1; }
step() { printf '\n== %s\n' "$*"; }
FAILED=0

psql_() { kubectl exec statefulset/postgres -- psql -q -U palladium_app -d "$PGDB" -tAc "$1" 2>/dev/null | tail -1; }

# --- preflight ---------------------------------------------------------------
step "preflight"
CTX="$(kubectl config current-context)"
[ "$CTX" = "minikube" ] || { echo "refusing to run against context '$CTX'" >&2; exit 1; }
pass "kubectl context is minikube"

kubectl wait --for=condition=available deploy/fake-gcs --timeout=60s >/dev/null \
  || { echo "fake-gcs is not available; check 'tilt up'" >&2; exit 1; }
EMU="$(kubectl exec deploy/builder -- printenv STORAGE_EMULATOR_HOST 2>/dev/null || true)"
[ "$EMU" = "http://fake-gcs:4443" ] || { echo "builder pod has STORAGE_EMULATOR_HOST='$EMU'; trigger config-roll in Tilt" >&2; exit 1; }
pass "fake-gcs available and the builder points at it"

HAS_HISTORY="$(psql_ "select count(*) from information_schema.tables where table_name = 'price_history_points'")"
[ "$HAS_HISTORY" = "1" ] || { echo "price_history_points missing; is the migration at head?" >&2; exit 1; }
pass "migration at head (price_history_points exists)"

PART_ID="$(psql_ "select id from pc_parts where name = 'Ryzen 7 7800X3D' and is_active order by id limit 1")"
[ -n "$PART_ID" ] || { echo "no active 'Ryzen 7 7800X3D' in pc_parts" >&2; exit 1; }
pass "catalog part $PART_ID"

if [ -f "$CAPTURE" ]; then
  SOURCE="real capture ($CAPTURE)"
  cat "$CAPTURE" | kubectl exec -i deploy/builder -- sh -c 'cat > /tmp/mk-offers.json'
else
  SOURCE="committed sample (serpapi_samples.py)"
  (cd backend && uv run python -c 'import json; from tests.pricing.serpapi_samples import product_7800x3d; print(json.dumps(product_7800x3d()))') \
    | kubectl exec -i deploy/builder -- sh -c 'cat > /tmp/mk-offers.json'
fi
pass "response source: $SOURCE"

# A throwaway binding to hang the history on. 'candidate', so it can never
# collide with a real confirmed binding for the same part.
BINDING_ID="$(psql_ "insert into google_product_bindings (id, part_id, google_product_id, status) values (gen_random_uuid(), '$PART_ID', 'mk-verify-' || substr(md5(random()::text), 1, 8), 'candidate') returning id")"
[ -n "$BINDING_ID" ] || { echo "could not create a test binding" >&2; exit 1; }
cleanup() {
  psql_ "delete from price_fetches where binding_id = '$BINDING_ID'" >/dev/null || true
  psql_ "delete from google_product_bindings where id = '$BINDING_ID'" >/dev/null || true
}
trap cleanup EXIT

QUOTA_BEFORE="$(psql_ "select coalesce((select search_count from serpapi_quota where month = date_trunc('month', current_date)::date), 0)")"

# --- fetch, parse, record, re-parse ------------------------------------------
step "fetch -> raw in GCS -> parse -> Postgres, then re-parse from GCS"
OUT="$(kubectl exec -i deploy/builder -- \
  env BINDING_ID="$BINDING_ID" PART_ID="$PART_ID" sh -c 'cd /app && python - 2>&1' <<'PY' || true
import asyncio, copy, json, os, uuid
import httpx
from app.core.db import AsyncSessionLocal
from app.services.pricing_etl import fetches, offers, query_profile, raw_store

BODY = open("/tmp/mk-offers.json", "rb").read()
PAYLOAD = json.loads(BODY)
BINDING, PART = uuid.UUID(os.environ["BINDING_ID"]), uuid.UUID(os.environ["PART_ID"])

def serve(body):
    return httpx.MockTransport(lambda request: httpx.Response(200, content=body))

async def fetch_and_record(db, store, body):
    out = await fetches.perform_fetch(
        db, store, purpose="offers",
        params=query_profile.offers_params(PAYLOAD["search_parameters"]["product_id"]),
        binding_id=BINDING, part_id=PART, transport=serve(body),
    )
    parsed = offers.parse_product_response(out.payload, await offers.load_merchant_rules(db))
    await offers.record_parsed(db, fetch_id=out.fetch_id, binding_id=BINDING, parsed=parsed)
    return out, parsed

async def main():
    store = raw_store.get_store()
    async with AsyncSessionLocal() as db:
        out, parsed = await fetch_and_record(db, store, BODY)
        again = await offers.reparse_fetch(db, store, out.fetch_id)

        # Same response with the third store renamed to a membership warehouse:
        # the exclusion has to come from the price_merchant_rules TABLE.
        costco = copy.deepcopy(PAYLOAD)
        costco["product_results"]["stores"][-1]["name"] = "Costco"
        out2, parsed2 = await fetch_and_record(db, store, json.dumps(costco).encode())

    print(json.dumps({
        "fetch_id": str(out.fetch_id),
        "n_stores": len(PAYLOAD["product_results"].get("stores") or []),
        "n_used": parsed.n_used,
        "estimate": parsed.estimate_cents, "method": parsed.estimate_method,
        "band": parsed.band, "n_history": len(parsed.history),
        "reparse_same": (again.estimate_cents, again.n_used, len(again.history))
            == (parsed.estimate_cents, parsed.n_used, len(parsed.history)),
        "costco_fetch_id": str(out2.fetch_id),
        "costco_estimate": parsed2.estimate_cents, "costco_method": parsed2.estimate_method,
    }))

asyncio.run(main())
PY
)"
LAST="$(printf '%s\n' "$OUT" | tail -1)"
j() { printf '%s' "$LAST" | python3 -c "import json,sys; v=json.load(sys.stdin)['$1']; print(json.dumps(v) if isinstance(v,(list,dict)) else v)"; }
FETCH_ID="$(j fetch_id 2>/dev/null || true)"
if [ -z "$FETCH_ID" ]; then
  fail "pipeline did not complete:"; printf '%s\n' "$OUT" >&2
  exit 1
fi

N_STORES="$(j n_stores)"; N_USED="$(j n_used)"; N_HISTORY="$(j n_history)"
ROW="$(psql_ "select estimate_cents || '|' || estimate_method || '|' || n_offers_total || '|' || n_offers_used || '|' || parser_version || '|' || price_range_low_cents || '|' || price_range_high_cents || '|' || (raw_uri is not null) from price_fetches where id = '$FETCH_ID'")"
IFS='|' read -r R_EST R_METHOD R_TOTAL R_USED R_PV R_LOW R_HIGH R_RAW <<<"$ROW"

[ "$R_EST" = "41599" ] && pass "estimate \$415.99, the median of \$389.00 / \$415.99 / \$420.00" || fail "estimate '$R_EST'"
[ "$R_METHOD" = "median_of_3" ] && pass "estimate method recorded: $R_METHOD" || fail "method '$R_METHOD'"
[ "$R_LOW|$R_HIGH" = "34900|41600" ] && pass "Google's band stored: \$349 to \$416" || fail "band '$R_LOW|$R_HIGH'"
[ "$R_TOTAL" = "$N_STORES" ] && [ "$R_USED" = "$N_USED" ] && pass "offer counts on the fetch: $R_USED of $R_TOTAL used" || fail "counts $R_USED/$R_TOTAL vs parser $N_USED/$N_STORES"
[ "$R_PV" = "1" ] && pass "parser_version 1" || fail "parser_version '$R_PV'"
[ "$R_RAW" = "true" ] && pass "raw response stored" || fail "raw_uri missing"

OFFERS="$(psql_ "select count(*) || '|' || count(*) filter (where included) || '|' || count(*) filter (where shipping_cents = 0) || '|' || count(*) filter (where 'gift_promo' = any(flags)) from price_offers where fetch_id = '$FETCH_ID'")"
IFS='|' read -r O_ALL O_INC O_SHIP O_GIFT <<<"$OFFERS"
[ "$O_ALL" = "$N_STORES" ] && pass "one price_offers row per store, after a re-parse ($O_ALL, not doubled)" || fail "price_offers rows: $O_ALL, expected $N_STORES"
[ "$O_INC" = "$N_USED" ] && pass "$O_INC offers included" || fail "included $O_INC"
[ "$O_SHIP" = "$N_STORES" ] && pass "shipping stored separately (free on all $O_SHIP)" || fail "shipping rows $O_SHIP"
[ "${O_GIFT:-0}" -ge 1 ] && pass "free-gift line flagged, offer still included" || fail "no gift flag"

HIST="$(psql_ "select count(*) from price_history_points where binding_id = '$BINDING_ID'")"
[ "$HIST" = "$N_HISTORY" ] && pass "$HIST price history points stored once each across 3 parses (upsert, not append)" || fail "history rows $HIST, expected $N_HISTORY"
DIP="$(psql_ "select price_cents from price_history_points where binding_id = '$BINDING_ID' and merchant_name = 'Newegg.com' and price_date = '2026-10-12'")"
[ "$DIP" = "34800" ] && pass "history point Newegg 2026-10-12 = \$348.00" || fail "Newegg 2026-10-12 = '$DIP'"
[ "$(j reparse_same)" = "True" ] && pass "re-parse from GCS reproduces the same estimate, offers and history" || fail "re-parse differs"

# --- merchant rules come from the table ---------------------------------------
step "a membership warehouse is excluded by the price_merchant_rules table"
COSTCO_ID="$(j costco_fetch_id)"
CREASON="$(psql_ "select exclusion_reason from price_offers where fetch_id = '$COSTCO_ID' and merchant_name = 'Costco'")"
[ "$CREASON" = "membership_merchant" ] && pass "Costco offer excluded: $CREASON" || fail "Costco exclusion '$CREASON'"
[ "$(j costco_method)" = "median_of_2" ] && [ "$(j costco_estimate)" = "40450" ] \
  && pass "estimate falls back to the median of the other two (\$404.50)" \
  || fail "costco estimate $(j costco_estimate) $(j costco_method)"

# --- quota ------------------------------------------------------------------
step "quota"
QUOTA_AFTER="$(psql_ "select coalesce((select search_count from serpapi_quota where month = date_trunc('month', current_date)::date), 0)")"
DELTA=$(( ${QUOTA_AFTER:-0} - ${QUOTA_BEFORE:-0} ))
[ "$DELTA" -eq 2 ] && pass "local quota rose by 2; the re-parse spent nothing" || fail "local quota rose by $DELTA, expected 2"

echo
if [ "$FAILED" -ne 0 ]; then
  printf '\033[31mFAILED\033[0m\n'; exit 1
fi
printf '\033[32mALL PASSED\033[0m\n'
