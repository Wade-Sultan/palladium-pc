#!/usr/bin/env bash
# Verify the product-bound pricing scheduler on the local cluster.
#
# What runs for real: app.jobs.price_tracking.run inside the builder pod (the
# job's own entrypoint), against the in-cluster Postgres and fake-gcs: tracking
# state, the weekly re-rank, due selection, fetch + verify + parse, failure
# counting, stale marking, daily rows, the history backfill, and publishing to
# street_price_cents with price-drop alerts (evaluated in dry-run mode, as
# PRICE_ALERTS_ENABLED is off locally: nothing is mailed).
#
# What does not: SerpApi. A router answers by product id: the real 7800X3D
# google_product capture from .local-seed/serpapi/ (or the committed sample),
# the same response for a 9900X3D binding (so its title check fails), and an
# HTTP 500 for a GPU binding. NO SerpApi quota is spent; the LOCAL quota row
# rises by one per mocked fetch.
#
# price_tracking_state and daily_price_estimates are snapshotted first and
# restored at the end, so the run leaves local data as it found it.
#
#   ./scripts/mk-verify-price-tracking.sh
#
# Requires `tilt up`, the migration at head (f3b5d7e9a1c2), and the seeded
# catalog (Ryzen 7 7800X3D, Ryzen 9 9900X3D, at least one GPU chipset).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

PGDB="${PALLADIUM_LOCAL_PG_DB:-palladium_local}"
CAPTURE="${PALLADIUM_SERPAPI_CAPTURE:-.local-seed/serpapi/google_product_ryzen7_7800x3d_2026-10-21.json}"
ID_A="4400000000000000001"  # 7800X3D: the real capture, passes
ID_B="4400000000000000002"  # 9900X3D: same capture, wrong product
ID_C="4400000000000000003"  # GPU: HTTP 500

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
[ "$(psql_ "select count(*) from information_schema.columns where table_name = 'daily_price_estimates' and column_name = 'source'")" = "1" ] \
  || { echo "daily_price_estimates.source missing; is the migration at head?" >&2; exit 1; }
CONFIRMED_BEFORE="$(psql_ "select count(*) from google_product_bindings where status = 'confirmed'")"
[ "$CONFIRMED_BEFORE" = "0" ] || { echo "local DB has $CONFIRMED_BEFORE confirmed bindings; this script assumes none so the run touches only its own" >&2; exit 1; }
pass "migration at head; no confirmed bindings to disturb"

# Snapshot what the run will rewrite.
psql_ "drop table if exists mk_backup_state; drop table if exists mk_backup_daily;
       create table mk_backup_state as select * from price_tracking_state;
       create table mk_backup_daily as select * from daily_price_estimates" >/dev/null
START="$(psql_ "select now()")"
restore() {
  psql_ "delete from users where email = 'mk-verify-price-tracking@palladium.local'" >/dev/null || true
  psql_ "update pc_parts p set street_price_cents = b.street_price_cents, price_source = b.price_source,
         last_price_checked_at = b.last_price_checked_at
         from mk_backup_parts b where p.id = b.id; drop table if exists mk_backup_parts" >/dev/null || true
  psql_ "delete from google_product_bindings where google_product_id in ('$ID_A','$ID_B','$ID_C')" >/dev/null || true
  psql_ "delete from price_fetches where fetched_at >= '$START'" >/dev/null || true
  psql_ "truncate price_tracking_state; insert into price_tracking_state select * from mk_backup_state;
         truncate daily_price_estimates; insert into daily_price_estimates select * from mk_backup_daily;
         drop table mk_backup_state; drop table mk_backup_daily" >/dev/null || true
}
trap restore EXIT

kubectl exec deploy/builder -- sh -c 'cd /app && python -c "
import asyncio
from app.core.db import AsyncSessionLocal
from app.services.pricing_etl import tracking
async def m():
    async with AsyncSessionLocal() as db: await tracking.ensure_tracking_state(db)
asyncio.run(m())"' >/dev/null 2>&1
CPU_A="$(psql_ "select id from pc_parts where name = 'Ryzen 7 7800X3D' and part_type = 'cpu' and is_active order by id limit 1")"
CPU_B="$(psql_ "select id from pc_parts where name = 'Ryzen 9 9900X3D' and part_type = 'cpu' and is_active order by id limit 1")"
GPU_ROW="$(psql_ "select target_id || '|' || tracked_part_id from price_tracking_state where target_kind = 'gpu_chipset' and tracked_part_id is not null order by target_id limit 1")"
IFS='|' read -r CHIPSET GPU <<<"$GPU_ROW"
[ -n "$CPU_A" ] && [ -n "$CPU_B" ] && [ -n "$GPU" ] || { echo "seeded catalog lacks a test part" >&2; exit 1; }
for pair in "$CPU_A:$ID_A" "$CPU_B:$ID_B" "$GPU:$ID_C"; do
  psql_ "insert into google_product_bindings (id, part_id, google_product_id, status, confirmed_by) values (gen_random_uuid(), '${pair%%:*}', '${pair##*:}', 'confirmed', 'admin')" >/dev/null
done
pass "3 confirmed test bindings: 7800X3D, 9900X3D, and the board tracking GPU chipset $CHIPSET"

psql_ "drop table if exists mk_backup_parts; create table mk_backup_parts as
       select id, street_price_cents, price_source, last_price_checked_at from pc_parts where id in ('$CPU_A','$CPU_B')" >/dev/null
A_BEFORE="$(psql_ "select coalesce(street_price_cents::text, 'null') || '|' || coalesce(price_source, 'null') from pc_parts where id = '$CPU_A'")"
A_PRICE_BEFORE="${A_BEFORE%%|*}"; [ "$A_PRICE_BEFORE" = "null" ] && A_PRICE_BEFORE="NULL"
CHIP_BEFORE="$(psql_ "select coalesce(street_price_cents::text, 'null') || '|' || coalesce(last_price_checked_at::text, 'null') from gpu_chipsets where id = '$CHIPSET'")"
USER_ID="$(psql_ "insert into users (id, email, hashed_password) values (gen_random_uuid(), 'mk-verify-price-tracking@palladium.local', 'x') returning id")"
psql_ "insert into price_subscriptions (id, user_id, target_kind, target_id, threshold_cents, baseline_price_cents)
       values (gen_random_uuid(), '$USER_ID', 'pc_part', '$CPU_A', 40000, 133166)" >/dev/null
pass "7800X3D stored price before: ${A_BEFORE/|/ via }; a subscriber waits for \$400.00"

if [ -f "$CAPTURE" ]; then SOURCE="real capture"; kubectl exec -i deploy/builder -- sh -c 'cat > /tmp/mk-offers.json' < "$CAPTURE"
else SOURCE="committed sample"; (cd backend && uv run python -c 'import json; from tests.pricing.serpapi_samples import product_7800x3d; print(json.dumps(product_7800x3d()))') | kubectl exec -i deploy/builder -- sh -c 'cat > /tmp/mk-offers.json'
fi
pass "7800X3D response: $SOURCE"

N_TARGETS="$(psql_ "select count(*) from price_tracking_state")"
quota() { psql_ "select coalesce((select search_count from serpapi_quota where month = date_trunc('month', current_date)::date), 0)"; }

# Runs the job in the pod. $1 = days after now, $2 = "dry" for a dry run.
job() {
  kubectl exec -i deploy/builder -- env OFFSET="$1" DRY="${2:-}" ID_A="$ID_A" ID_B="$ID_B" sh -c 'cd /app && python - 2>&1' <<'PY'
import asyncio, json, os
from datetime import UTC, datetime, timedelta
import httpx
from app.jobs import price_tracking

BODY = open("/tmp/mk-offers.json", "rb").read()
# From day 1 the 7800X3D gets cheaper at two of its three stores: the median
# falls from $415.99 to $389.00, under the subscriber's $400.00.
cheaper = json.loads(BODY)
for store in cheaper["product_results"]["stores"]:
    if store["name"] in ("Best Buy", "Walmart"):
        store["price"], store["extracted_price"] = "$389.00", 389.0
CHEAPER = json.dumps(cheaper).encode()
def route(request):
    pid = request.url.params.get("product_id")
    if pid == os.environ["ID_A"] and int(os.environ["OFFSET"]) >= 1:
        return httpx.Response(200, content=CHEAPER)
    if pid in (os.environ["ID_A"], os.environ["ID_B"]):
        return httpx.Response(200, content=BODY)
    return httpx.Response(500, content=b'{"error": "upstream failure"}')

now = datetime.now(UTC) + timedelta(days=int(os.environ["OFFSET"]))
counts = asyncio.run(price_tracking.run(
    dry_run=os.environ["DRY"] == "dry", now=now, transport=httpx.MockTransport(route)))
print("RESULT " + json.dumps(counts))
PY
}
result() { sed -n 's/^RESULT //p' <<<"$1"; }
c() { python3 -c "import json,sys; print(json.loads(sys.argv[1]).get('$2'))" "$1"; }

# --- dry run -------------------------------------------------------------------
step "dry run: lists what is due, spends nothing"
Q0="$(quota)"
DRY="$(job 0 dry || true)"
[ "$(c "$(result "$DRY")" would_fetch)" = "3" ] && pass "3 targets due (the three bound ones)" || fail "dry run: $(tail -3 <<<"$DRY")"
[ "$(quota)" = "$Q0" ] && pass "quota unchanged" || fail "quota moved"
[ "$(psql_ "select count(*) from daily_price_estimates")" = "$(psql_ "select count(*) from mk_backup_daily")" ] && pass "no daily rows written by a dry run" || fail "dry run wrote daily rows"

# --- day 0 --------------------------------------------------------------------
step "day 0: fetch, verify, schedule, daily rows"
RUN0="$(job 0 || true)"
R0="$(result "$RUN0")"
[ -n "$R0" ] || { fail "job did not complete:"; printf '%s\n' "$RUN0" >&2; exit 1; }
[ "$(c "$R0" priced)|$(c "$R0" stale)|$(c "$R0" failed)" = "1|1|1" ] && pass "one priced, one stale (wrong product), one failed (HTTP 500)" || fail "counts $R0"
[ "$(c "$R0" daily_rows)" = "$N_TARGETS" ] && pass "a daily row for all $N_TARGETS targets" || fail "daily rows $(c "$R0" daily_rows)"
[ "$(( $(quota) - Q0 ))" = "3" ] && pass "3 searches counted" || fail "quota delta $(( $(quota) - Q0 ))"

A_STATE="$(psql_ "select round(extract(epoch from next_due_at - last_fetched_at) / 86400) || '|' || bin from price_tracking_state where target_kind = 'pc_part' and target_id = '$CPU_A'")"
[ "$A_STATE" = "7|medium" ] && pass "7800X3D: unranked, so medium, next fetch in 7 days" || fail "7800X3D state '$A_STATE'"
A_DAY="$(psql_ "select source || '|' || price_cents || '|' || (last_observed_at is not null) from daily_price_estimates where target_kind = 'pc_part' and target_id = '$CPU_A' and estimate_date = current_date")"
[ "$A_DAY" = "fetch|41599|true" ] && pass "7800X3D today: \$415.99, source fetch, with its observation time" || fail "7800X3D row '$A_DAY'"
A_PART="$(psql_ "select street_price_cents || '|' || price_source || '|' || (last_price_checked_at > now() - interval '1 hour') from pc_parts where id = '$CPU_A'")"
[ "$A_PART" = "41599|google_product|true" ] && pass "7800X3D published: street_price_cents \$415.99, price_source google_product" || fail "7800X3D pc_parts '$A_PART'"
if [ "${A_BEFORE#*|}" != "google_product" ] && [ "$A_PRICE_BEFORE" != "NULL" ]; then
  [ "$(c "$R0" method_changed)|$(c "$R0" alerts_dry_run)|$(c "$R0" alerts_sent)" = "1|0|0" ] \
    && pass "method change (${A_BEFORE/|/ via } -> 41599 via google_product): written as a baseline, no alert" \
    || fail "day 0 alerts: $R0"
fi
B_PART="$(psql_ "select coalesce(p.price_source, 'null') = coalesce(b.price_source, 'null') and p.street_price_cents is not distinct from b.street_price_cents from pc_parts p join mk_backup_parts b using (id) where id = '$CPU_B'")"
[ "$B_PART" = "t" ] && pass "9900X3D (stale): its street price untouched" || fail "9900X3D price changed"
[ "$(psql_ "select coalesce(street_price_cents::text, 'null') || '|' || coalesce(last_price_checked_at::text, 'null') from gpu_chipsets where id = '$CHIPSET'")" = "$CHIP_BEFORE" ] \
  && pass "GPU chipset (failed fetch): its street price untouched" || fail "GPU chipset price changed"

B_BIND="$(psql_ "select status from google_product_bindings where google_product_id = '$ID_B'")"
B_EST="$(psql_ "select coalesce(estimate_cents::text, 'null') || '|' || estimate_method from price_fetches where part_id = '$CPU_B' and fetched_at >= '$START'")"
B_DAY="$(psql_ "select source from daily_price_estimates where target_kind = 'pc_part' and target_id = '$CPU_B' and estimate_date = current_date")"
[ "$B_BIND" = "stale" ] && pass "9900X3D: bound product came back as a 7800X3D, binding marked stale" || fail "9900X3D binding '$B_BIND'"
[ "$B_EST" = "null|product_mismatch" ] && pass "its offers are kept as evidence but price nothing" || fail "9900X3D fetch '$B_EST'"
[ "$B_DAY" = "none" ] && pass "its daily row says none, not a borrowed price" || fail "9900X3D row '$B_DAY'"

C_BIND="$(psql_ "select status || '|' || consecutive_failures from google_product_bindings where google_product_id = '$ID_C'")"
C_DUE="$(psql_ "select round(extract(epoch from next_due_at - now()) / 3600) from price_tracking_state where target_kind = 'gpu_chipset' and target_id = '$CHIPSET'")"
[ "$C_BIND" = "confirmed|1" ] && pass "GPU: one failure counted, binding still confirmed" || fail "GPU binding '$C_BIND'"
[ "${C_DUE:-0}" -ge 23 ] && [ "${C_DUE:-0}" -le 24 ] && pass "GPU: retried tomorrow" || fail "GPU next due in ${C_DUE}h"

# --- re-rank ------------------------------------------------------------------
step "re-rank from Google's history"
kubectl exec deploy/builder -- sh -c 'cd /app && python -c "
import asyncio
from datetime import UTC, datetime
from app.core.db import AsyncSessionLocal
from app.services.pricing_etl import scheduler
async def m():
    async with AsyncSessionLocal() as db: await scheduler.rerank_if_due(db, datetime.now(UTC), force=True)
asyncio.run(m())"' >/dev/null 2>&1
RANKED="$(psql_ "select bin || '|' || volatility_rank || '|' || (volatility > 0) || '|' || n_observations || '|' || round(extract(epoch from next_due_at - last_fetched_at) / 86400) from price_tracking_state where target_kind = 'pc_part' and target_id = '$CPU_A'")"
[ "$RANKED" = "high|1|true|12|1" ] && pass "7800X3D: volatility measured over 12 weekly changes, ranked 1st, moved to high, next fetch in 1 day" || fail "7800X3D ranked '$RANKED'"
GPU_RANK="$(psql_ "select bin || '|' || coalesce(volatility_rank::text, 'unranked') from price_tracking_state where target_kind = 'gpu_chipset' and target_id = '$CHIPSET'")"
[ "$GPU_RANK" = "medium|unranked" ] && pass "GPU (bound, no history yet): unknown, stays medium" || fail "GPU ranked '$GPU_RANK'"

# --- history backfill ------------------------------------------------------------
step "carried-forward days are replaced by Google's history"
psql_ "insert into daily_price_estimates (target_kind, target_id, estimate_date, price_cents, source)
       select 'pc_part', '$CPU_A', d::date, 99999, 'carried' from generate_series(date '2026-10-10', date '2026-10-18', interval '1 day') d
       on conflict do nothing" >/dev/null
kubectl exec deploy/builder -- env CPU_A="$CPU_A" ID_A="$ID_A" sh -c 'cd /app && python -c "
import asyncio, os, uuid
from datetime import date
from sqlalchemy import select
from app.core.db import AsyncSessionLocal
from app.models.price_tracking import GoogleProductBinding
from app.services.pricing_etl import scheduler
async def m():
    async with AsyncSessionLocal() as db:
        b = (await db.execute(select(GoogleProductBinding).where(GoogleProductBinding.google_product_id == os.environ[\"ID_A\"]))).scalar_one()
        await scheduler.backfill_from_history(db, \"pc_part\", uuid.UUID(os.environ[\"CPU_A\"]), b.id, date(2026, 10, 21), uuid.uuid4())
asyncio.run(m())"' >/dev/null 2>&1
D13="$(psql_ "select source || '|' || price_cents from daily_price_estimates where target_kind = 'pc_part' and target_id = '$CPU_A' and estimate_date = '2026-10-13'")"
D17="$(psql_ "select source || '|' || price_cents || '|' || (last_observed_at at time zone 'UTC')::date from daily_price_estimates where target_kind = 'pc_part' and target_id = '$CPU_A' and estimate_date = '2026-10-17'")"
LEFT="$(psql_ "select count(*) from daily_price_estimates where target_kind = 'pc_part' and target_id = '$CPU_A' and price_cents = 99999")"
[ "$D13" = "history|41599" ] && pass "Oct 13: \$415.99 (Newegg 348, Best Buy 420, Walmart 415.99)" || fail "Oct 13 '$D13'"
[ "$D17" = "history|34800|2026-10-16" ] && pass "Oct 17: \$348.00 after Walmart's Oct 16 drop, last updated Oct 16" || fail "Oct 17 '$D17'"
[ "$LEFT" = "0" ] && pass "no carried-forward placeholder left" || fail "$LEFT placeholders left"

# --- same day again ---------------------------------------------------------------
step "a second run the same day fetches nothing"
Q1="$(quota)"
RUN1="$(job 0 || true)"
R1="$(result "$RUN1")"
[ "$(c "$R1" priced)$(c "$R1" failed)$(c "$R1" stale)" = "000" ] && pass "nothing due again today" || fail "second run $R1"
[ "$(quota)" = "$Q1" ] && pass "quota unchanged" || fail "quota moved"
[ "$(psql_ "select source from daily_price_estimates where target_kind = 'pc_part' and target_id = '$CPU_A' and estimate_date = current_date")" = "fetch" ] \
  && pass "today's 7800X3D row is still the fetched one" || fail "today's row changed"

# --- failures escalate --------------------------------------------------------------
step "three failures in a row mark a binding stale"
RUN_D1="$(job 1 || true)"
RUN_D2="$(job 2 || true)"
C_END="$(psql_ "select status || '|' || consecutive_failures from google_product_bindings where google_product_id = '$ID_C'")"
[ "$C_END" = "stale|3" ] && pass "GPU binding stale after 3 failed fetches" || fail "GPU binding '$C_END'"
A_FETCHES="$(psql_ "select count(*) from price_fetches where part_id = '$CPU_A' and fetched_at >= '$START' and estimate_cents is not null")"
[ "$A_FETCHES" = "3" ] && pass "7800X3D, now high, was fetched on each following day (3 fetches in 3 days)" || fail "7800X3D fetched $A_FETCHES times"

step "price-drop alerts on the new method's own prices"
D1="$(result "$RUN_D1")"; D2="$(result "$RUN_D2")"
[ "$(c "$D1" alerts_dry_run)|$(c "$D1" method_changed)" = "1|0" ] \
  && pass "day 1: \$415.99 -> \$389.00 crosses the subscriber's \$400.00: alert decided (dry run, nothing mailed)" || fail "day 1 alerts: $D1"
[ "$(psql_ "select street_price_cents from pc_parts where id = '$CPU_A'")" = "38900" ] && pass "street_price_cents now \$389.00" || fail "street price not updated"
[ "$(c "$D2" alerts_dry_run)" = "0" ] && pass "day 2: still \$389.00, already under the target: no second alert" || fail "day 2 alerts: $D2"
[ "$(psql_ "select status from price_subscriptions where user_id = '$USER_ID'")" = "active" ] \
  && pass "dry run leaves the subscription active, so enabling alerts later notifies the same person" || fail "subscription retired in dry run"
psql_ "delete from daily_price_estimates where estimate_date > current_date" >/dev/null

echo
if [ "$FAILED" -ne 0 ]; then
  printf '\033[31mFAILED\033[0m\n'; exit 1
fi
printf '\033[32mALL PASSED\033[0m\n'
