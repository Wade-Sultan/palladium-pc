#!/usr/bin/env bash
# End-to-end smoke test for the local minikube cluster.
#
# Drives a REAL chat turn through the whole dispatched path — published to
# Pub/Sub, claimed and run by a worker pod, streamed through Valkey, its
# telemetry written to Postgres — and asserts each hop actually happened.
#
# NO LLM IS CALLED. The request carries X-Palladium-Load-Test, which puts both
# the API and the worker into stub-LM mode (app/core/loadtest.py). The stubs are
# in-process and answer DSPy's signatures by parsing their declared output
# fields, so the full eleven-module build pipeline runs and produces a real build
# from the seeded catalog — deterministically, with no LM Studio, no GPU and no
# OpenRouter spend. The build's CONTENT is meaningless; every other behaviour is
# the real thing.
#
# WHAT THIS EXISTS TO CATCH is a false pass. /chat degrades rather than failing:
# if Pub/Sub is unreachable it silently runs the turn in the API process, and a
# test that only checked "did a build come back" would pass while the worker, the
# claim, redelivery and the whole dispatch architecture went untested. So the
# central assertion here is not that the turn worked — it is that a WORKER ran
# it. That is read from the Valkey claim key, whose value is the worker's pod
# name, rather than from a log line that could scroll away.
#
#   ./scripts/mk-smoke.sh
#
# Requires the stack to be up (`tilt up`) with its port-forwards live.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

API="${PALLADIUM_API:-http://localhost:8000}"
PGDB="${PALLADIUM_LOCAL_PG_DB:-palladium_local}"
PROMPT="${PALLADIUM_SMOKE_PROMPT:-I want a gaming PC for 1440p at 144fps, budget around \$1500}"

pass() { printf '  \033[32mPASS\033[0m  %s\n' "$*"; }
warn() { printf '  \033[33mWARN\033[0m  %s\n' "$*"; }
fail() { printf '  \033[31mFAIL\033[0m  %s\n' "$*" >&2; FAILED=1; }
step() { printf '\n== %s\n' "$*"; }
FAILED=0

valkey()  { kubectl exec deploy/valkey -- valkey-cli "$@" 2>/dev/null; }
psql_()   { kubectl exec statefulset/postgres -- psql -U palladium_app -d "$PGDB" -tAc "$1" 2>/dev/null | tail -1; }

# --- preflight ---------------------------------------------------------------
# Refuse to run anywhere but the local cluster. Every assertion below reads and
# writes real state, and the load-test header is a production credential in
# every other environment.
step "preflight"
CTX="$(kubectl config current-context)"
[ "$CTX" = "minikube" ] || { echo "refusing to run against context '$CTX'" >&2; exit 1; }
pass "kubectl context is minikube"

SECRET="$(grep -E '^LOAD_TEST_SECRET=' deploy/overlays/local/.env.local | head -1 | cut -d= -f2-)"
[ -n "$SECRET" ] || { echo "LOAD_TEST_SECRET missing from deploy/overlays/local/.env.local" >&2; exit 1; }

curl -sf -m 10 -o /dev/null "$API/api/v1/healthz" || { echo "builder not reachable at $API" >&2; exit 1; }
pass "builder answering at $API"
[ "$(valkey ping)" = "PONG" ] || { echo "valkey not answering" >&2; exit 1; }
pass "valkey answering"

# --- schema ------------------------------------------------------------------
# Guards a whole class of silent breakage: the seed restore drops and recreates
# every object in the production dump, alembic_version included, so a database
# that is not at head means local is running an older schema than the code and
# any feature touching a newer column fails in a way that looks like a bug in
# the feature.
step "schema is at head"
DB_REV="$(psql_ 'select version_num from alembic_version')"
HEAD_REV="$(kubectl exec deploy/builder -- sh -c 'cd /app && alembic heads' 2>/dev/null | tail -1 | awk '{print $1}')"
if [ -n "$DB_REV" ] && [ "$DB_REV" = "$HEAD_REV" ]; then
  pass "alembic at head ($DB_REV)"
else
  fail "database is at '$DB_REV', code head is '$HEAD_REV' — restore/migrate ordering?"
fi

# --- snapshot ----------------------------------------------------------------
step "driving a turn"
SESSIONS_BEFORE="$(psql_ 'select count(*) from build_sessions')"
CLAIMS_BEFORE="$(valkey --scan --pattern 'chat:claim:*' | sort | tr '\n' ' ')"

BODY=$(cat <<JSON
{"conversation_id":null,"state":{"messages":[],"pipeline":null},
 "commands":[{"type":"add-message","message":{"role":"user",
   "parts":[{"type":"text","text":"$PROMPT"}]}}]}
JSON
)
RESP="$(curl -sS -N -m 300 -X POST "$API/api/v1/chat" \
  -H 'Content-Type: application/json' \
  -H "X-Palladium-Load-Test: $SECRET" \
  -d "$BODY")"

if grep -q '"build"' <<<"$RESP" && grep -q '"total_approx"' <<<"$RESP"; then
  pass "turn returned a build ($(grep -o '"label": "[^"]*"' <<<"$RESP" | head -1))"
else
  fail "turn did not produce a build"
  printf '%s\n' "$RESP" | tail -c 500 >&2
fi

# --- the assertion that matters ----------------------------------------------
# A claim is written by app/worker.py before it runs the turn, and its VALUE is
# the worker's pod name. The in-process fallback in api/routes/chat.py calls
# run_turn directly and never claims — so a new claim owned by a worker-* pod is
# positive proof the dispatched path ran, and its absence means the turn quietly
# fell back even though it succeeded.
step "the turn reached a worker (not the inline fallback)"
NEW_CLAIM=""
for key in $(valkey --scan --pattern 'chat:claim:*'); do
  case " $CLAIMS_BEFORE " in *" $key "*) continue;; esac
  NEW_CLAIM="$key"; break
done
if [ -z "$NEW_CLAIM" ]; then
  fail "no new turn claim — the turn ran INLINE. Check that the emulator has its
        topics (kubectl logs job/pubsub-setup) and re-trigger 'pubsub-setup'."
else
  OWNER="$(valkey get "$NEW_CLAIM")"
  case "$OWNER" in
    worker-*) pass "claimed by $OWNER" ;;
    *)        fail "claim held by '$OWNER', which is not a worker pod" ;;
  esac
fi

# --- valkey ------------------------------------------------------------------
step "valkey state"
TURN_ID="${NEW_CLAIM#chat:claim:\{}"; TURN_ID="${TURN_ID%\}}"
if [ -n "$TURN_ID" ]; then
  LAST="$(valkey xrevrange "chat:evt:{$TURN_ID}" + - COUNT 1 | tail -1)"
  if grep -q '"end"' <<<"$LAST"; then
    pass "event stream terminated (turn is durable before readers disconnect)"
  else
    fail "event stream has no terminal entry; last was: $LAST"
  fi
fi

WAKE="$(valkey llen chat:wake)"
[ "$WAKE" = "0" ] && pass "wake queue drained (cleared at pickup)" \
                 || fail "wake queue still holds $WAKE entr(y/ies) — clear_wake leaking keeps a pod alive forever"

PENDING="$(valkey llen build:telemetry:pending)"
[ "$PENDING" = "0" ] && pass "telemetry buffer drained" \
                     || fail "$PENDING telemetry payload(s) stuck in Valkey — the Postgres write failed; see the builder/worker log"

# --- postgres ----------------------------------------------------------------
# The Valkey-to-storage hop, and the one the CronJob is only a backstop for:
# turn_runner drains the buffer synchronously at the end of every turn, so this
# should already be true with no waiting at all.
step "telemetry reached postgres"
SESSIONS_AFTER="$(psql_ 'select count(*) from build_sessions')"
if [ "${SESSIONS_AFTER:-0}" -gt "${SESSIONS_BEFORE:-0}" ]; then
  pass "build_sessions $SESSIONS_BEFORE -> $SESSIONS_AFTER"
else
  fail "build_sessions did not grow ($SESSIONS_BEFORE -> $SESSIONS_AFTER)"
fi

# --- did the REAL pipeline run, or was a canned build served? ----------------
# A build coming back is not evidence the recommender ran. When any Decide* step
# raises — no candidate fits the budget, the model returns something the
# signature cannot parse, the run exceeds DSPY_CHAT_TIMEOUT_S — the result is
# discarded and a pre-built reference build is served instead, with
# status=error. The response looks completely normal, so without this check the
# assertions above all pass while the thing under test never executed.
#
# A WARNING, NOT A FAILURE, and deliberately so. The fallback is correct
# behaviour: it is what keeps a user from seeing an error page. Whether it
# SHOULD have triggered is a question about catalog prices and model quality,
# not about whether this cluster works — and with the pricing ETL currently
# leaving parts priced above what a mid-range budget allocates, a hard failure
# here would make this script permanently red for a reason it does not own.
step "did the custom build pipeline actually run?"
STATUS="$(psql_ 'select status from build_sessions order by created_at desc limit 1')"
STEPS="$(psql_ "select count(*) from module_decisions where session_id=(select id from build_sessions order by created_at desc limit 1)")"
if [ "$STATUS" = "completed" ]; then
  pass "full ladder ran ($STEPS module decisions recorded)"
else
  warn "FELL BACK to a reference build (status=$STATUS, only $STEPS ladder step(s) ran).
        The turn and every hop above still worked — but the recommender itself did
        not. Cause is in the worker log:
          kubectl logs deploy/worker | grep 'using reference build'
        Known triggers: no candidate under a slot's budget ceiling (pricing ETL),
        a model reply the Decide* signature cannot parse, or DSPY_CHAT_TIMEOUT_S."
fi

step "result"
if [ "$FAILED" = "0" ]; then
  printf '  \033[32mall checks passed\033[0m\n'
else
  printf '  \033[31mone or more checks failed\033[0m\n' >&2
fi
exit "$FAILED"
