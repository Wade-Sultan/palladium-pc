#!/usr/bin/env bash
# Verifies the /chat rate limit (backend/app/core/ratelimit.py) against the
# local cluster's real Valkey.
#
# NO TURN RUNS AND NO LLM IS CALLED, and not via the load-test header, because
# that header is exactly what the limiter exempts. Instead every request carries
# a malformed body. FastAPI resolves a route's dependencies before it validates
# the body, so the limiter counts the request and then validation rejects it
# with a 422, before the handler (and any turn) is reached. Under the limit the
# answer is 422; over it, 429. That difference is the whole test.
#
# What the unit tests (fakeredis) cannot show and this does: the SDK's counter
# running on a real Valkey 8, which has no INCREX, so the Lua fallback is the
# path under test, and the counter key carrying a TTL, without which one burst
# would lock a caller out until someone deleted the key by hand.
#
#   ./scripts/mk-verify-chat-rate-limit.sh
#
# Requires the stack to be up (`tilt up`) with its port-forwards live. Clears
# the local /chat counters before and after, so it never leaves you locked out.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

API="${PALLADIUM_API:-http://localhost:8000}"

pass() { printf '  \033[32mPASS\033[0m  %s\n' "$*"; }
fail() { printf '  \033[31mFAIL\033[0m  %s\n' "$*" >&2; FAILED=1; }
step() { printf '\n== %s\n' "$*"; }
FAILED=0

valkey() { kubectl exec deploy/valkey -- valkey-cli "$@" 2>/dev/null; }
KEYS='redis:fastapi:ratelimit:chat:*'
clear_counters() {
  for k in $(valkey --scan --pattern "$KEYS"); do valkey del "$k" >/dev/null; done
}
# Status and Retry-After of one malformed POST, as "STATUS RETRY_AFTER".
post() {
  curl -s -m 10 -o /dev/null -D - -X POST "$API/api/v1/chat" \
    -H 'Content-Type: application/json' "$@" -d '{"commands": "not-a-list"}' |
    awk 'NR==1 {s=$2} tolower($1)=="retry-after:" {r=$2} END {gsub(/\r/,"",r); print s, r}'
}

# --- preflight ---------------------------------------------------------------
step "preflight"
CTX="$(kubectl config current-context)"
[ "$CTX" = "minikube" ] || { echo "refusing to run against context '$CTX'" >&2; exit 1; }
pass "kubectl context is minikube"
curl -sf -m 10 -o /dev/null "$API/api/v1/healthz" || { echo "builder not reachable at $API" >&2; exit 1; }
pass "builder answering at $API"
[ "$(valkey ping)" = "PONG" ] || { echo "valkey not answering" >&2; exit 1; }
pass "valkey answering"

SECRET="$(grep -E '^LOAD_TEST_SECRET=' deploy/overlays/local/.env.local | head -1 | cut -d= -f2- || true)"

# The limit the running pod actually enforces, read from the code rather than
# assumed, so a changed CHAT_RATE_LIMITS does not turn this into a false fail.
LIMIT="$(kubectl exec deploy/builder -- sh -c \
  'cd /app && python -c "from app.core.ratelimit import CHAT_RATES as r; print(r[0].limit if r else 0)"' \
  2>/dev/null | tail -1)"
[ "${LIMIT:-0}" -gt 0 ] || { echo "CHAT_RATE_LIMITS is empty in the pod; nothing to verify" >&2; exit 1; }
pass "shortest-window limit in the pod is $LIMIT"

STREAMS_BEFORE="$(valkey --scan --pattern 'chat:evt:*' | wc -l)"
clear_counters
trap clear_counters EXIT

# --- under the limit ---------------------------------------------------------
step "first $LIMIT requests are counted, then fail validation"
for i in $(seq 1 "$LIMIT"); do
  read -r status _ <<<"$(post)"
  [ "$status" = "422" ] || { fail "request $i returned $status, expected 422"; break; }
done
[ "$FAILED" = 0 ] && pass "$LIMIT x 422"

# --- over it -----------------------------------------------------------------
step "request $((LIMIT + 1)) is rejected"
read -r status retry <<<"$(post)"
if [ "$status" = "429" ] && [ "${retry:-0}" -gt 0 ]; then
  pass "429 with Retry-After: $retry"
else
  fail "got status '$status', Retry-After '$retry'; expected 429 with a positive Retry-After"
fi

# --- the counter itself -------------------------------------------------------
step "counter in Valkey"
KEY="$(valkey --scan --pattern "$KEYS" | head -1)"
if [ -n "$KEY" ]; then
  pass "counter key: $KEY = $(valkey get "$KEY")"
  TTL="$(valkey ttl "$KEY")"
  if [ "${TTL:--1}" -gt 0 ]; then pass "counter expires in ${TTL}s"; else fail "counter has TTL $TTL: it would never reset"; fi
else
  fail "no counter key matching $KEYS"
fi

# --- load-test exemption -----------------------------------------------------
step "load-test requests are exempt"
if [ -n "$SECRET" ]; then
  read -r status _ <<<"$(post -H "X-Palladium-Load-Test: $SECRET")"
  [ "$status" = "422" ] && pass "over-limit caller with the load-test header reaches validation" \
    || fail "load-test request returned $status, expected 422"
else
  printf '  skip  LOAD_TEST_SECRET not set in deploy/overlays/local/.env.local\n'
fi

# --- nothing ran -------------------------------------------------------------
step "no turn was started"
STREAMS_AFTER="$(valkey --scan --pattern 'chat:evt:*' | wc -l)"
[ "$STREAMS_AFTER" = "$STREAMS_BEFORE" ] && pass "turn streams unchanged ($STREAMS_AFTER)" \
  || fail "turn streams went $STREAMS_BEFORE -> $STREAMS_AFTER"

echo
if [ "$FAILED" = 0 ]; then echo "ALL CHECKS PASSED"; else echo "SOME CHECKS FAILED" >&2; exit 1; fi
