#!/usr/bin/env bash
# Verify product-id binding discovery and the admin review flow on the local
# cluster.
#
# What runs for real: tracking.ensure_tracking_state against the seeded
# catalog; perform_fetch + binding_discovery.score_results + record_discovery
# inside the builder pod (Postgres, fake-gcs, quota); the admin's binding
# transitions (admin/src/lib/product-binding-transitions.ts, the code behind
# the page's buttons) against the same Postgres, including the
# one-confirmed-per-part index; the admin page rendering those rows; and the
# discovery job's dry run.
#
# What does not: SerpApi. Each search is answered by an httpx.MockTransport:
# the real 9800X3D capture from .local-seed/serpapi/ when present (raw
# responses are never committed), and small inline responses for the
# confirm/review cases. NO SerpApi quota is spent; the LOCAL quota row rises
# by 4.
#
#   ./scripts/mk-verify-product-bindings.sh
#
# Requires `tilt up` (builder, admin, fake-gcs, postgres forwarded on :5433,
# admin on :3001) and the migration at head.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

PGDB="${PALLADIUM_LOCAL_PG_DB:-palladium_local}"
ADMIN="${PALLADIUM_ADMIN:-http://localhost:3001}"
CAPTURE=".local-seed/serpapi/google_shopping_ryzen7_9800x3d_2026-10-21.json"

pass() { printf '  \033[32mPASS\033[0m  %s\n' "$*"; }
fail() { printf '  \033[31mFAIL\033[0m  %s\n' "$*" >&2; FAILED=1; }
step() { printf '\n== %s\n' "$*"; }
FAILED=0

psql_() { kubectl exec statefulset/postgres -- psql -q -U palladium_app -d "$PGDB" -tAc "$1" 2>/dev/null | tail -1; }
in_builder() { kubectl exec -i deploy/builder -- env "$@" sh -c 'cd /app && python - 2>&1'; }

# --- preflight ---------------------------------------------------------------
step "preflight"
CTX="$(kubectl config current-context)"
[ "$CTX" = "minikube" ] || { echo "refusing to run against context '$CTX'" >&2; exit 1; }
pass "kubectl context is minikube"

CPU="$(psql_ "select id from pc_parts where name = 'Ryzen 7 9800X3D' and part_type = 'cpu' and is_active and model_number is not null order by id limit 1")"
CPU2="$(psql_ "select id from pc_parts where name = 'Ryzen 9 9900X3D' and part_type = 'cpu' and is_active order by id limit 1")"
[ -n "$CPU" ] && [ -n "$CPU2" ] || { echo "seeded catalog lacks Ryzen 7 9800X3D / Ryzen 9 9900X3D" >&2; exit 1; }
PRIOR="$(psql_ "select count(*) from google_product_bindings where part_id in ('$CPU','$CPU2')")"
[ "$PRIOR" = "0" ] || { echo "test parts already have $PRIOR bindings; refusing to disturb them" >&2; exit 1; }
pass "test parts: 9800X3D $CPU, 9900X3D $CPU2 (no existing bindings)"

START="$(psql_ "select now()")"
cleanup() {
  psql_ "delete from google_product_bindings where part_id in ('$CPU','$CPU2') and created_at >= '$START'" >/dev/null || true
  psql_ "delete from price_fetches where part_id in ('$CPU','$CPU2') and fetched_at >= '$START'" >/dev/null || true
  rm -f admin/.mk-verify-bindings.tmp.mts
}
trap cleanup EXIT

if [ -f "$CAPTURE" ]; then
  SOURCE="real capture"
  kubectl exec -i deploy/builder -- sh -c 'cat > /tmp/mk-shopping.json' < "$CAPTURE"
else
  SOURCE="committed sample"
  (cd backend && uv run python -c 'import json; from tests.pricing.serpapi_samples import shopping_9800x3d; print(json.dumps(shopping_9800x3d()))') \
    | kubectl exec -i deploy/builder -- sh -c 'cat > /tmp/mk-shopping.json'
fi
pass "9800X3D search response: $SOURCE"
QUOTA_BEFORE="$(psql_ "select coalesce((select search_count from serpapi_quota where month = date_trunc('month', current_date)::date), 0)")"

# --- tracking state -------------------------------------------------------------
step "every active target gets exactly one tracked SKU"
EXPECTED="$(psql_ "
  select (select count(*) from pc_parts where is_active and part_type in ('cpu','motherboard','cpucooler','case','fan','system'))
       + (select count(distinct gpu_chipset_id) from gpus g join pc_parts p on p.id = g.id where p.is_active)
       + (select count(distinct psu_group_id) from psus s join pc_parts p on p.id = s.id where p.is_active and psu_group_id is not null)
       + (select count(distinct ram_group_id) from ram_kits r join pc_parts p on p.id = r.id where p.is_active and ram_group_id is not null)
       + (select count(distinct storage_group_id) from storage_drives d join pc_parts p on p.id = d.id where p.is_active and storage_group_id is not null)")"
TRACK_OUT="$(in_builder <<'PY' || true
import asyncio
from app.core.db import AsyncSessionLocal
from app.services.pricing_etl import tracking
async def main():
    async with AsyncSessionLocal() as db:
        first = await tracking.ensure_tracking_state(db)
        second = await tracking.ensure_tracking_state(db)
    print("RESULT", first, second)
asyncio.run(main())
PY
)"
SECOND="$(printf '%s\n' "$TRACK_OUT" | awk '/^RESULT/{print $3}')"
ROWS="$(psql_ "select count(*) from price_tracking_state")"
[ "$ROWS" = "$EXPECTED" ] && pass "$ROWS tracking rows, one per active target" || fail "$ROWS tracking rows, expected $EXPECTED: $TRACK_OUT"
[ "$SECOND" = "0" ] && pass "a second run changes nothing" || fail "second run changed $SECOND rows"
GPU_PICK="$(psql_ "select count(*) from price_tracking_state s join pc_parts p on p.id = s.tracked_part_id where s.target_kind = 'gpu_chipset' and p.part_type = 'gpu' and p.is_active")"
GPU_TARGETS="$(psql_ "select count(*) from price_tracking_state where target_kind = 'gpu_chipset'")"
[ "$GPU_PICK" = "$GPU_TARGETS" ] && pass "each of $GPU_TARGETS GPU chipsets is tracked through one of its own active boards" || fail "$GPU_PICK of $GPU_TARGETS chipsets track an active board"

# --- discovery: none, auto, review ----------------------------------------------
step "discovery decisions, recorded"
DISC_OUT="$(in_builder CPU="$CPU" CPU2="$CPU2" <<'PY' || true
import asyncio, json, os, uuid
import httpx
from app.core.db import AsyncSessionLocal
from app.models.pcparts import PCPart
from app.services.pricing_etl import binding_discovery as bd, fetches, raw_store, tracking
from app.services.pricing_etl.query_profile import discovery_params

CPU, CPU2 = uuid.UUID(os.environ["CPU"]), uuid.UUID(os.environ["CPU2"])
REAL = open("/tmp/mk-shopping.json", "rb").read()

def hit(pid, title, price, pos=1, multi=True):
    return {"position": pos, "title": title, "product_id": pid, "source": "Newegg.com",
            "extracted_price": price, "multiple_sources": multi}

def search(*hits):
    return json.dumps({"search_metadata": {"id": "mk"}, "shopping_results": list(hits)}).encode()

async def discover(db, store, part_id, body):
    part = await db.get(PCPart, part_id)
    ref = bd.PartRef.of(part)
    out = await fetches.perform_fetch(
        db, store, purpose="discovery", params=discovery_params(bd.discovery_query(ref)),
        part_id=part_id, transport=httpx.MockTransport(lambda r: httpx.Response(200, content=body)),
    )
    result = bd.score_results(ref, out.payload)
    written = await bd.record_discovery(db, part_id=part_id, fetch_id=out.fetch_id, result=result)
    return result, written

async def main():
    store = raw_store.get_store()
    out = {}
    async with AsyncSessionLocal() as db:
        r, w = await discover(db, store, CPU, REAL)
        out["none"] = {"decision": r.decision, "written": w, "rejected": len(r.rejected)}
        due = await tracking.parts_needing_discovery(db, 10_000)
        out["cooldown_excludes_part"] = CPU not in {p.id for p in due}

        match = hit("4300000000000000001", "AMD Ryzen 7 9800X3D 8-Core, 16-Thread Desktop Processor", 459.0)
        r, w = await discover(db, store, CPU, search(match))
        out["auto"] = {"decision": r.decision, "written": w}
        # The same answer again must not create a second row.
        r, w = await discover(db, store, CPU, search(match))
        out["repeat"] = {"decision": r.decision, "written": w}

        a = hit("4300000000000000011", "AMD Ryzen 9 9900X3D 12-Core Processor", 689.0, 1)
        b = hit("4300000000000000012", "AMD Ryzen 9 9900X3D 12-Core Desktop Processor (Tray)", 659.0, 2)
        r, w = await discover(db, store, CPU2, search(a, b))
        out["review"] = {"decision": r.decision, "written": w, "why": r.why_not_auto}
    print("RESULT " + json.dumps(out))

asyncio.run(main())
PY
)"
RES="$(printf '%s\n' "$DISC_OUT" | sed -n 's/^RESULT //p')"
[ -n "$RES" ] || { fail "discovery did not complete:"; printf '%s\n' "$DISC_OUT" >&2; exit 1; }
q() { printf '%s' "$RES" | python3 -c "import json,sys; d=json.load(sys.stdin); print($1)"; }

[ "$(q 'd["none"]["written"]')" = "none" ] && pass "9800X3D ($SOURCE): no binding, all $(q 'd["none"]["rejected"]') results rejected" || fail "9800X3D: $(q 'd["none"]')"
[ "$(q 'd["cooldown_excludes_part"]')" = "True" ] && pass "a search that found nothing puts the part on cooldown" || fail "part still due for discovery"
[ "$(q 'd["auto"]["written"]')" = "auto_confirm" ] && pass "a clear catalog match is confirmed automatically" || fail "auto: $(q 'd["auto"]')"
[ "$(q 'd["repeat"]["written"]')" = "none" ] && pass "the same match again writes nothing new" || fail "repeat: $(q 'd["repeat"]')"
[ "$(q 'd["review"]["written"]')" = "review" ] && pass "two plausible products go to review" || fail "review: $(q 'd["review"]')"

AUTO_ROW="$(psql_ "select status || '|' || confirmed_by || '|' || (match_evidence->>'decision') || '|' || (discovery_fetch_id is not null) from google_product_bindings where part_id = '$CPU'")"
[ "$AUTO_ROW" = "confirmed|auto|auto_confirm|true" ] && pass "auto binding row: confirmed by auto, evidence and discovery fetch recorded" || fail "auto row '$AUTO_ROW'"
CANDS="$(psql_ "select count(*) from google_product_bindings where part_id = '$CPU2' and status = 'candidate'")"
[ "$CANDS" = "2" ] && pass "2 candidate rows for the 9900X3D" || fail "$CANDS candidate rows"
FETCHES="$(psql_ "select count(*) from price_fetches where purpose = 'discovery' and part_id in ('$CPU','$CPU2') and fetched_at >= '$START' and raw_uri is not null")"
[ "$FETCHES" = "4" ] && pass "4 discovery fetches recorded, each with its raw response in GCS" || fail "$FETCHES discovery fetches"

# --- the admin page -------------------------------------------------------------
step "the admin page shows the review queue"
PAGE="$(curl -sf -m 30 "$ADMIN/product-bindings" || true)"
if [ -z "$PAGE" ]; then
  fail "admin page did not render at $ADMIN/product-bindings"
else
  grep -q "Product bindings" <<<"$PAGE" && pass "page renders" || fail "page title missing"
  grep -q "9900X3D 12-Core Desktop Processor (Tray)" <<<"$PAGE" && pass "candidates listed for review" || fail "candidate not on page"
  grep -q "2 distinct products survived" <<<"$PAGE" && pass "why it was not auto-confirmed is shown" || fail "reason not on page"
fi

# --- the admin transitions, against the real database ----------------------------
step "admin actions: confirm, bind by hand, retire"
DB_URL="$(kubectl exec deploy/admin -- printenv DATABASE_URL 2>/dev/null | sed -E 's#@[^/:]+(:[0-9]+)?/#@localhost:5433/#')"
[ -n "$DB_URL" ] || { fail "could not read the admin's DATABASE_URL"; exit 1; }
CAND_A="$(psql_ "select id from google_product_bindings where part_id = '$CPU2' and google_product_id = '4300000000000000011'")"
AUTO_ID="$(psql_ "select id from google_product_bindings where part_id = '$CPU' and status = 'confirmed'")"
cat > admin/.mk-verify-bindings.tmp.mts <<'TS'
import { PrismaClient } from '@prisma/client';
import {
  bindManuallyTx, confirmCandidateTx, rejectCandidateTx, retireBindingTx, BindingError,
} from './src/lib/product-binding-transitions.ts';

const db = new PrismaClient();
const [cpu, cpu2, candA, autoId] = process.argv.slice(2);
const out: Record<string, unknown> = {};
async function status(partId: string) {
  return (await db.googleProductBinding.findMany({ where: { partId }, orderBy: { googleProductId: 'asc' } }))
    .map((b) => `${b.googleProductId}:${b.status}:${b.confirmedBy ?? '-'}`);
}
try {
  await confirmCandidateTx(db, candA);
  out.confirm = await status(cpu2);
  try { await rejectCandidateTx(db, candA); out.rejectConfirmed = 'allowed'; }
  catch (e) { out.rejectConfirmed = e instanceof BindingError ? 'refused' : String(e); }

  await bindManuallyTx(db, cpu, `https://www.google.com/search?ibp=oshop&prds=catalogid%3A4300000000000000099&udm=28`);
  out.manual = await status(cpu);
  try { await bindManuallyTx(db, cpu, 'not a product'); out.garbage = 'accepted'; }
  catch (e) { out.garbage = e instanceof BindingError ? 'refused' : String(e); }

  const confirmed = await db.googleProductBinding.findFirst({ where: { partId: cpu, status: 'confirmed' } });
  await retireBindingTx(db, confirmed!.id);
  out.retire = await status(cpu);
  out.autoId = autoId;
} finally {
  await db.$disconnect();
}
console.log('RESULT ' + JSON.stringify(out));
TS
ADMIN_OUT="$(cd admin && DATABASE_URL="$DB_URL" node --import tsx .mk-verify-bindings.tmp.mts "$CPU" "$CPU2" "$CAND_A" "$AUTO_ID" 2>&1 || true)"
ARES="$(printf '%s\n' "$ADMIN_OUT" | sed -n 's/^RESULT //p')"
[ -n "$ARES" ] || { fail "admin transitions did not run:"; printf '%s\n' "$ADMIN_OUT" >&2; exit 1; }
a() { printf '%s' "$ARES" | python3 -c "import json,sys; d=json.load(sys.stdin); print($1)"; }

[ "$(a 'd["confirm"]')" = "['4300000000000000011:confirmed:admin', '4300000000000000012:rejected:-']" ] \
  && pass "confirming a candidate rejects the part's other candidate" || fail "confirm: $(a 'd["confirm"]')"
[ "$(a 'd["rejectConfirmed"]')" = "refused" ] && pass "a confirmed binding cannot be 'rejected' as a candidate" || fail "reject-confirmed: $(a 'd["rejectConfirmed"]')"
[ "$(a 'd["manual"]')" = "['4300000000000000001:retired:auto', '4300000000000000099:confirmed:admin']" ] \
  && pass "binding by hand from a Shopping URL retires the auto binding (one confirmed per part held)" || fail "manual: $(a 'd["manual"]')"
[ "$(a 'd["garbage"]')" = "refused" ] && pass "input that is not a product id is refused" || fail "garbage: $(a 'd["garbage"]')"
[ "$(a 'd["retire"]')" = "['4300000000000000001:retired:auto', '4300000000000000099:retired:admin']" ] \
  && pass "retiring leaves the part with no confirmed binding" || fail "retire: $(a 'd["retire"]')"

# --- rejected ids are never re-proposed --------------------------------------------
step "discovery does not re-propose what an admin ruled out"
RE_OUT="$(in_builder CPU2="$CPU2" <<'PY' || true
import asyncio, json, os, uuid
from app.core.db import AsyncSessionLocal
from app.models.pcparts import PCPart
from app.services.pricing_etl import binding_discovery as bd
CPU2 = uuid.UUID(os.environ["CPU2"])
async def main():
    async with AsyncSessionLocal() as db:
        ref = bd.PartRef.of(await db.get(PCPart, CPU2))
        payload = {"shopping_results": [{"position": 1, "title": "AMD Ryzen 9 9900X3D 12-Core Desktop Processor (Tray)",
                   "product_id": "4300000000000000012", "extracted_price": 659.0, "multiple_sources": True}]}
        r = bd.score_results(ref, payload)
        w = await bd.record_discovery(db, part_id=CPU2, fetch_id=uuid.uuid4(), result=r)
    print("RESULT", w)
asyncio.run(main())
PY
)"
[ "$(printf '%s\n' "$RE_OUT" | awk '/^RESULT/{print $2}')" = "none" ] && pass "the rejected Tray listing is not written again" || fail "re-proposal: $RE_OUT"
STILL="$(psql_ "select status from google_product_bindings where part_id = '$CPU2' and google_product_id = '4300000000000000012'")"
[ "$STILL" = "rejected" ] && pass "it stays rejected" || fail "status now '$STILL'"

# --- the job's dry run ------------------------------------------------------------
step "the discovery job's dry run spends nothing"
Q1="$(psql_ "select coalesce((select search_count from serpapi_quota where month = date_trunc('month', current_date)::date), 0)")"
DRY="$(kubectl exec deploy/builder -- env PRODUCT_BINDING_DRY_RUN=1 PRODUCT_BINDING_LIMIT=5 sh -c 'cd /app && python -m app.jobs.product_bindings 2>&1' || true)"
Q2="$(psql_ "select coalesce((select search_count from serpapi_quota where month = date_trunc('month', current_date)::date), 0)")"
grep -q "DRY RUN would search" <<<"$DRY" && pass "dry run lists what it would search, e.g. $(grep -m1 -o "would search: '[^']*'" <<<"$DRY")" || fail "dry run output: $(tail -3 <<<"$DRY")"
[ "$Q1" = "$Q2" ] && pass "quota unchanged by the dry run" || fail "quota moved $Q1 -> $Q2"

step "quota"
QUOTA_AFTER="$(psql_ "select coalesce((select search_count from serpapi_quota where month = date_trunc('month', current_date)::date), 0)")"
DELTA=$(( ${QUOTA_AFTER:-0} - ${QUOTA_BEFORE:-0} ))
[ "$DELTA" -eq 4 ] && pass "local quota rose by 4 (four mocked searches)" || fail "local quota rose by $DELTA, expected 4"

echo
if [ "$FAILED" -ne 0 ]; then
  printf '\033[31mFAILED\033[0m\n'; exit 1
fi
printf '\033[32mALL PASSED\033[0m\n'
