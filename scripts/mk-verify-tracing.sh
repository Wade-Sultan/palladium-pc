#!/usr/bin/env bash
# Verifies OpenTelemetry tracing on the local minikube cluster, against the
# Jaeger stand-in for Managed OTel (deploy/overlays/local/jaeger.yaml).
#
# Three things, each of which has failed silently before or would:
#
#   1. The OTLP endpoint actually reached the builder and worker Pods. A
#      ConfigMap edit rolls nothing on its own, and a pod holding the old
#      environment simply exports nowhere.
#   2. FastAPI emits request spans. The contrib instrumentor this replaced never
#      produced one in production, and nothing complained.
#   3. One chat turn is ONE trace across the Pub/Sub hop, API request span and
#      worker spans together. That is the reason the Google pipe exists, and it
#      depends on the request span existing to be propagated at all.
#   4. Load-test traffic is NOT traced. Otherwise a Locust run ships a trace per
#      stubbed turn to Cloud Trace and LangSmith.
#
# The method: every request here carries a W3C traceparent with a trace id this
# script generated. FastAPI continues an incoming trace, so each assertion is an
# exact lookup of that id in Jaeger rather than a search for "something recent".
#
# NO LLM IS CALLED. The traced turn is a case pick nothing can claim, answered
# with fixed text; the untraced one carries the load-test header.
#
#   ./scripts/mk-verify-tracing.sh
#
# Requires the stack to be up (`tilt up`) with its port-forwards live.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

API="${PALLADIUM_API:-http://localhost:8000}"
JAEGER="${PALLADIUM_JAEGER:-http://localhost:16686}"

pass() { printf '  \033[32mPASS\033[0m  %s\n' "$*"; }
fail() { printf '  \033[31mFAIL\033[0m  %s\n' "$*" >&2; FAILED=1; }
step() { printf '\n== %s\n' "$*"; }
FAILED=0

hex() { python3 -c "import secrets; print(secrets.token_hex($1))"; }
traceparent() { printf '00-%s-%s-01' "$1" "$(hex 8)"; }

# Prints "<service>\t<span name>\t<kind>" per span of trace $1, or nothing if
# Jaeger does not have it (yet). The v3 API, because Jaeger v2 no longer serves
# the old /api/traces; it returns OTLP JSON, whose span kind may come back as
# the enum's number or its name depending on the serializer.
trace_spans() {
  curl -s -m 10 "$JAEGER/api/v3/traces/$1" | python3 -c '
import json, sys
KINDS = {1: "internal", 2: "server", 3: "client", 4: "producer", 5: "consumer"}
try:
    result = json.load(sys.stdin).get("result") or {}
except ValueError:
    sys.exit(0)
for rs in result.get("resourceSpans", []):
    attrs = {a["key"]: a["value"].get("stringValue") for a in rs["resource"].get("attributes", [])}
    for ss in rs.get("scopeSpans", []):
        for s in ss.get("spans", []):
            kind = s.get("kind", 0)
            kind = KINDS.get(kind, "") if isinstance(kind, int) else kind.removeprefix("SPAN_KIND_").lower()
            print(attrs.get("service.name", ""), s["name"], kind, sep="\t")
'
}

# grep without -q throughout, its output discarded instead. Under pipefail, -q
# exits on the first match, the writer upstream takes SIGPIPE, and the pipeline
# reports failure for a match it found. `kubectl logs` on a DEBUG-level pod is
# big enough to hit that every time.
has() { grep -P "$1" >/dev/null; }

# Polls until trace $1 has a span matching the grep pattern $2, up to $3 seconds.
# Spans are batched (BatchSpanProcessor's default delay is 5s), so the first
# look nearly always misses.
await_span() {
  local deadline=$((SECONDS + $3))
  while [ "$SECONDS" -lt "$deadline" ]; do
    if trace_spans "$1" | has "$2"; then return 0; fi
    sleep 2
  done
  return 1
}

# --- preflight ---------------------------------------------------------------
step "preflight"
CTX="$(kubectl config current-context)"
[ "$CTX" = "minikube" ] || { echo "refusing to run against context '$CTX'" >&2; exit 1; }
pass "kubectl context is minikube"

SECRET="$(grep -E '^LOAD_TEST_SECRET=' deploy/overlays/local/.env.local | head -1 | cut -d= -f2-)"
[ -n "$SECRET" ] || { echo "LOAD_TEST_SECRET missing from deploy/overlays/local/.env.local" >&2; exit 1; }

curl -sf -m 10 -o /dev/null "$API/api/v1/healthz" || { echo "builder not reachable at $API" >&2; exit 1; }
pass "builder answering at $API"
curl -sf -m 10 -o /dev/null "$JAEGER/api/v3/services" || { echo "jaeger not reachable at $JAEGER (Tilt port-forward?)" >&2; exit 1; }
pass "jaeger answering at $JAEGER"

# --- 1. the endpoint reached the pods ----------------------------------------
# Read from the running process's environment, never the ConfigMap: the
# ConfigMap is correct in exactly the stale-pod case this is checking for.
step "OTLP endpoint is in the running pods"
for d in builder worker; do
  EP="$(kubectl exec "deploy/$d" -- printenv OTEL_EXPORTER_OTLP_ENDPOINT 2>/dev/null || true)"
  if [ -n "$EP" ]; then
    pass "$d: OTEL_EXPORTER_OTLP_ENDPOINT=$EP"
  else
    fail "$d has no OTEL_EXPORTER_OTLP_ENDPOINT: restart it (Tilt 'config-roll')"
  fi
  # Polled: the worker logs this some seconds after it reports Ready, so a run
  # straight after a restart would otherwise fail on timing alone.
  found=""
  for _ in $(seq 15); do
    if kubectl logs "deploy/$d" 2>/dev/null | has 'tracing: exporting to OTLP endpoint'; then found=1; break; fi
    sleep 2
  done
  if [ -n "$found" ]; then
    pass "$d: tracing.py attached the OTLP exporter"
  else
    fail "$d never logged 'tracing: exporting to OTLP endpoint'"
  fi
done

# --- 2. request spans --------------------------------------------------------
step "FastAPI request spans"
T_HEALTH="$(hex 16)"
T_PROBE="$(hex 16)"
curl -sf -m 10 -o /dev/null -H "traceparent: $(traceparent "$T_HEALTH")" "$API/api/v1/health"
curl -sf -m 10 -o /dev/null -H "traceparent: $(traceparent "$T_PROBE")" "$API/api/v1/healthz"

if await_span "$T_HEALTH" '^palladium-api\tGET /api/v1/health\tserver$' 30; then
  pass "server span 'GET /api/v1/health' continued the caller's trace"
  if trace_spans "$T_HEALTH" | has '^palladium-api\tfastapi\.endpoint\t'; then
    pass "operation span 'fastapi.endpoint' under it"
  else
    fail "no 'fastapi.endpoint' span: operation_spans off?"
  fi
else
  fail "no request span in Jaeger for trace $T_HEALTH after 30s"
fi

# Checked after the span above arrived, so the batch the probe would have been
# in has already been flushed.
if [ -z "$(trace_spans "$T_PROBE")" ]; then
  pass "probe path /api/v1/healthz produced no trace"
else
  fail "probe path was traced: the telemetry exclude in app/main.py is not matching"
fi

# --- 3. one trace across the Pub/Sub hop -------------------------------------
# NOT a load-test turn: those are deliberately untraced now (see 4 below). And
# not an ordinary message either, which would call the real model. A case pick
# with a token nothing issued is the one turn that is both real and free: it is
# dispatched over Pub/Sub, run by a worker, looked up in Valkey and Postgres,
# and answered with a fixed apology (resume_build in chat_pipeline.py).
step "a chat turn is one trace, API and worker"
T_TURN="$(hex 16)"
BODY="{\"conversation_id\":null,\"state\":{\"messages\":[],\"pipeline\":null},
 \"commands\":[{\"type\":\"select-case\",\"token\":\"$(hex 16)\",\"caseName\":\"none\"}]}"
curl -sS -N -m 300 -o /dev/null -X POST "$API/api/v1/chat" \
  -H 'Content-Type: application/json' \
  -H "traceparent: $(traceparent "$T_TURN")" \
  -d "$BODY"

if await_span "$T_TURN" '^palladium-api\tPOST /api/v1/chat\tserver$' 30; then
  pass "API: server span 'POST /api/v1/chat'"
else
  fail "API: no 'POST /api/v1/chat' span in trace $T_TURN"
fi
if await_span "$T_TURN" '^palladium-worker\tchat-turns-workers subscribe\t' 60; then
  pass "worker: Pub/Sub's subscribe span joined the trace"
else
  fail "worker: no subscribe span in trace $T_TURN. Either the turn ran inline
        (see mk-smoke.sh) or trace context did not cross Pub/Sub"
fi
# The turn's own work, not just the library's bookkeeping. Pub/Sub's spans join
# the trace on their own; the turn's do so only because app/worker.py parents
# them on the subscribe span, and without that this trace ends at the
# subscriber while the turn scatters into one-span traces of its own.
if await_span "$T_TURN" '^palladium-worker\t(?!chat-turns-workers |subscriber )' 30; then
  pass "worker: the turn's own spans (Valkey, SQL) are in the trace"
else
  fail "worker: only Pub/Sub's spans in trace $T_TURN, the turn itself is
        detached (see _trace_parent in app/worker.py)"
fi
printf '        spans by service: %s\n' \
  "$(trace_spans "$T_TURN" | cut -f1 | sort | uniq -c | awk '{printf "%s=%s ", $2, $1}' || true)"
printf '        view: %s/trace/%s\n' "$JAEGER" "$T_TURN"

# --- 4. load-test traffic is not traced --------------------------------------
# The caller's traceparent goes unused (FastAPI's span is excluded for these
# requests, and the sampler drops everything under them), so the id it carried
# must never appear. Checked after 3 has seen its spans arrive, so the export
# path is known to be working and an empty answer means something.
step "a load-test turn leaves no trace"
T_LOAD="$(hex 16)"
LOAD_BODY='{"conversation_id":null,"state":{"messages":[],"pipeline":null},
 "commands":[{"type":"add-message","message":{"role":"user",
   "parts":[{"type":"text","text":"gaming pc"}]}}]}'
curl -sS -N -m 300 -o /dev/null -X POST "$API/api/v1/chat" \
  -H 'Content-Type: application/json' \
  -H "X-Palladium-Load-Test: $SECRET" \
  -H "traceparent: $(traceparent "$T_LOAD")" \
  -d "$LOAD_BODY"
sleep 15  # two batch intervals, so anything recorded has been exported
if [ -z "$(trace_spans "$T_LOAD")" ]; then
  pass "no spans under the load-test request's trace id"
else
  fail "load-test turn was traced: $(trace_spans "$T_LOAD" | cut -f1,2 | head -3 | tr '\n' ';')"
fi

step "result"
if [ "$FAILED" = "0" ]; then
  printf '  \033[32mall checks passed\033[0m\n'
else
  printf '  \033[31mone or more checks failed\033[0m\n' >&2
fi
exit "$FAILED"
