#!/usr/bin/env bash
# Verify raw SerpApi capture for product-bound pricing on the local cluster.
#
# What runs for real: pricing_etl.fetches.perform_fetch inside the builder pod,
# against the in-cluster Postgres (price_fetches, serpapi_quota) and the
# fake-gcs-server bucket, through raw_store.get_store() exactly as the job will
# call it.
#
# What does not: the HTTP call to SerpApi. It is replaced by an
# httpx.MockTransport serving a recorded-shape google_product response, so this
# spends NO SerpApi quota. It does increment the LOCAL serpapi_quota row by the
# number of fetches made here (two), because that accounting is under test.
#
#   ./scripts/mk-verify-pricing-raw.sh
#
# Requires `tilt up` with the fake-gcs resource running and the migration at
# head (d9e1f3a5b7c2 or later).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

PGDB="${PALLADIUM_LOCAL_PG_DB:-palladium_local}"
BUCKET="palladium-shopping-results"

pass() { printf '  \033[32mPASS\033[0m  %s\n' "$*"; }
fail() { printf '  \033[31mFAIL\033[0m  %s\n' "$*" >&2; FAILED=1; }
step() { printf '\n== %s\n' "$*"; }
FAILED=0

psql_() { kubectl exec statefulset/postgres -- psql -q -U palladium_app -d "$PGDB" -tAc "$1" 2>/dev/null | tail -1; }
# Runs Python from stdin inside the builder pod, from /app so `app` imports.
in_builder() { kubectl exec -i deploy/builder -- sh -c 'cd /app && python - 2>&1'; }

# --- preflight ---------------------------------------------------------------
step "preflight"
CTX="$(kubectl config current-context)"
[ "$CTX" = "minikube" ] || { echo "refusing to run against context '$CTX'" >&2; exit 1; }
pass "kubectl context is minikube"

kubectl wait --for=condition=available deploy/fake-gcs --timeout=60s >/dev/null \
  || { echo "fake-gcs is not available; check 'tilt up'" >&2; exit 1; }
pass "fake-gcs-server available"

# The ConfigMap can be right while the pod still holds the old values (see
# Tilt's config-roll), so check the environment the pod actually has.
EMU="$(kubectl exec deploy/builder -- printenv STORAGE_EMULATOR_HOST 2>/dev/null || true)"
BKT="$(kubectl exec deploy/builder -- printenv PRICING_RAW_BUCKET 2>/dev/null || true)"
[ "$EMU" = "http://fake-gcs:4443" ] || { echo "builder pod has STORAGE_EMULATOR_HOST='$EMU'; trigger config-roll in Tilt" >&2; exit 1; }
[ "$BKT" = "$BUCKET" ] || { echo "builder pod has PRICING_RAW_BUCKET='$BKT'; trigger config-roll in Tilt" >&2; exit 1; }
pass "builder pod points at the emulator, bucket $BUCKET"

TABLES="$(psql_ "select count(*) from information_schema.tables where table_name in ('google_product_bindings','price_fetches','price_offers','price_tracking_state','daily_price_estimates','price_merchant_rules')")"
[ "$TABLES" = "6" ] || { echo "expected 6 product-pricing tables, found ${TABLES:-0}; is the migration at head?" >&2; exit 1; }
pass "all six product-pricing tables exist"

RULES="$(psql_ "select count(*) from price_merchant_rules where rule = 'membership'")"
[ "${RULES:-0}" -ge 3 ] && pass "membership merchant rules seeded ($RULES)" || fail "membership merchant rules missing"

QUOTA_BEFORE="$(psql_ "select coalesce((select search_count from serpapi_quota where month = date_trunc('month', current_date)::date), 0)")"

# --- a successful fetch ------------------------------------------------------
step "a recorded google_product response is fetched, stored raw, and recorded"
OUT="$(in_builder <<'PY'
import asyncio, hashlib, json
import httpx
from app.core.db import AsyncSessionLocal
from app.services.pricing_etl import fetches, query_profile, raw_store

BODY = json.dumps({
    "search_metadata": {"id": "mk-verify-0001", "status": "Success"},
    "search_parameters": {"engine": "google_product", "product_id": "19637827"},
    "product_results": {
        "title": "AMD Ryzen 7 9800X3D 8-Core Processor",
        "stores": [
            {"name": "Best Buy", "price": "$479.00", "extracted_price": 479.0,
             "shipping": "Free", "total": "$515.12", "extracted_total": 515.12},
            {"name": "Costco", "price": "$449.99", "extracted_price": 449.99},
        ],
    },
}).encode()

def handler(request):
    assert request.url.params["engine"] == "google_product"
    assert request.url.params["product_id"] == "19637827"
    assert request.url.params["no_cache"] == "true"
    return httpx.Response(200, content=BODY)

async def main():
    store = raw_store.get_store()
    async with AsyncSessionLocal() as db:
        out = await fetches.perform_fetch(
            db, store, purpose="offers",
            params=query_profile.offers_params("19637827"),
            transport=httpx.MockTransport(handler),
        )
    back = await store.get(out.raw_uri)
    print(json.dumps({
        "fetch_id": str(out.fetch_id), "ok": out.ok, "raw_uri": out.raw_uri,
        "roundtrip": back == BODY,
        "sha": hashlib.sha256(BODY).hexdigest(),
        "hash": query_profile.conditions_hash("google_product"),
    }))

asyncio.run(main())
PY
)" || true
LAST="$(printf '%s\n' "$OUT" | tail -1)"
FETCH_ID="$(printf '%s' "$LAST" | python3 -c 'import json,sys;print(json.load(sys.stdin)["fetch_id"])' 2>/dev/null || true)"
if [ -z "$FETCH_ID" ]; then
  fail "fetch did not complete:"; printf '%s\n' "$OUT" >&2
else
  field() { printf '%s' "$LAST" | python3 -c "import json,sys;print(json.load(sys.stdin)['$1'])"; }
  [ "$(field ok)" = "True" ] && pass "fetch outcome ok" || fail "fetch outcome not ok"
  [ "$(field roundtrip)" = "True" ] && pass "raw body reads back byte-for-byte from GCS" || fail "raw body differs on read-back"
  case "$(field raw_uri)" in
    "gs://$BUCKET/serpapi/google_product/q1/dt="*"/$FETCH_ID.json.gz") pass "object path partitioned by engine, profile version, date; named by fetch id" ;;
    *) fail "unexpected object path: $(field raw_uri)" ;;
  esac

  ROW="$(psql_ "select raw_uri || '|' || raw_sha256 || '|' || params_hash || '|' || coalesce(serpapi_search_id,'') || '|' || (params ? 'api_key') || '|' || coalesce(error_detail,'') from price_fetches where id = '$FETCH_ID'")"
  IFS='|' read -r R_URI R_SHA R_HASH R_SID R_KEY R_ERR <<<"$ROW"
  [ "$R_URI" = "$(field raw_uri)" ] && pass "price_fetches row points at the object" || fail "row raw_uri '$R_URI'"
  [ "$R_SHA" = "$(field sha)" ] && pass "row sha256 matches the uncompressed body" || fail "row sha256 mismatch"
  [ "$R_HASH" = "$(field hash)" ] && pass "row carries the frozen conditions hash" || fail "row params_hash '$R_HASH'"
  [ "$R_SID" = "mk-verify-0001" ] && pass "SerpApi search id recorded" || fail "search id '$R_SID'"
  [ "$R_KEY" = "false" ] && pass "api key not stored in params" || fail "api key present in params"
  [ -z "$R_ERR" ] && pass "no error recorded" || fail "error_detail '$R_ERR'"
fi

# --- write-once -------------------------------------------------------------
step "an existing raw object cannot be overwritten"
if [ -n "$FETCH_ID" ]; then
  OVER="$(in_builder <<PY
import asyncio
from app.services.pricing_etl import raw_store

async def main():
    store = raw_store.get_store()
    name = "$(field raw_uri)".split("/", 3)[3]
    try:
        await store.put(name, b"tampered", {})
        print("OVERWROTE")
    except Exception as exc:
        print("REFUSED", type(exc).__name__)
    print("INTACT" if (await store.get("$(field raw_uri)")) != b"tampered" else "TAMPERED")

asyncio.run(main())
PY
)" || true
  grep -q "REFUSED" <<<"$OVER" && pass "second write refused" || fail "second write was not refused: $OVER"
  grep -q "INTACT" <<<"$OVER" && pass "original object intact" || fail "original object changed"
fi

# --- a SerpApi error ---------------------------------------------------------
step "a SerpApi error body is counted, kept, and marked not ok"
ERR_OUT="$(in_builder <<'PY'
import asyncio, json
import httpx
from app.core.db import AsyncSessionLocal
from app.services.pricing_etl import fetches, query_profile, raw_store

def handler(request):
    return httpx.Response(429, json={"error": "Your account has run out of searches."})

async def main():
    async with AsyncSessionLocal() as db:
        out = await fetches.perform_fetch(
            db, raw_store.get_store(), purpose="offers",
            params=query_profile.offers_params("19637827"),
            transport=httpx.MockTransport(handler),
        )
    print(json.dumps({"fetch_id": str(out.fetch_id), "ok": out.ok, "raw_uri": out.raw_uri}))

asyncio.run(main())
PY
)" || true
ERR_LAST="$(printf '%s\n' "$ERR_OUT" | tail -1)"
ERR_ID="$(printf '%s' "$ERR_LAST" | python3 -c 'import json,sys;print(json.load(sys.stdin)["fetch_id"])' 2>/dev/null || true)"
if [ -z "$ERR_ID" ]; then
  fail "error fetch did not complete:"; printf '%s\n' "$ERR_OUT" >&2
else
  ERR_ROW="$(psql_ "select http_status || '|' || coalesce(error_detail,'') || '|' || (raw_uri is not null) from price_fetches where id = '$ERR_ID'")"
  IFS='|' read -r E_STATUS E_DETAIL E_STORED <<<"$ERR_ROW"
  [ "$E_STATUS" = "429" ] && pass "http status 429 recorded" || fail "http status '$E_STATUS'"
  grep -q "run out of searches" <<<"$E_DETAIL" && pass "SerpApi's error text recorded" || fail "error_detail '$E_DETAIL'"
  [ "$E_STORED" = "true" ] && pass "error body still stored raw" || fail "error body not stored"
fi

# --- quota ------------------------------------------------------------------
step "every call is counted against the monthly quota"
QUOTA_AFTER="$(psql_ "select coalesce((select search_count from serpapi_quota where month = date_trunc('month', current_date)::date), 0)")"
DELTA=$(( ${QUOTA_AFTER:-0} - ${QUOTA_BEFORE:-0} ))
[ "$DELTA" -eq 2 ] && pass "local quota rose by 2 (two fetches)" || fail "local quota rose by $DELTA, expected 2"

# --- the local guard --------------------------------------------------------
step "a local environment refuses real GCS without the emulator"
GUARD="$(kubectl exec -i deploy/builder -- sh -c 'cd /app && env -u STORAGE_EMULATOR_HOST python - 2>&1' <<'PY' || true
from app.services.pricing_etl import raw_store
try:
    raw_store.get_store()
    print("BUILT")
except raw_store.RawStoreConfigError as exc:
    print("REFUSED", exc)
PY
)"
grep -q "REFUSED" <<<"$GUARD" && pass "get_store refused without STORAGE_EMULATOR_HOST" || fail "get_store built a real client: $GUARD"

# --- cleanup ----------------------------------------------------------------
# The rows are test fixtures; the objects die with the fake-gcs pod anyway.
for id in ${FETCH_ID:-} ${ERR_ID:-}; do psql_ "delete from price_fetches where id = '$id'" >/dev/null; done

echo
if [ "$FAILED" -ne 0 ]; then
  printf '\033[31mFAILED\033[0m\n'; exit 1
fi
printf '\033[32mALL PASSED\033[0m\n'
