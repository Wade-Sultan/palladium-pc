"""OpenTelemetry tracing: one SDK, two destinations.

    spans ──┬─► OTLP to $OTEL_EXPORTER_OTLP_ENDPOINT ──► Google Cloud Observability
            │   (Managed OpenTelemetry for GKE injects that variable)
            └─► OTLP to LangSmith, scope-filtered ─────► LangSmith

WHY TWO PIPES RATHER THAN A COLLECTOR FAN-OUT. Managed OpenTelemetry for GKE
cannot export to third-party backends, it writes to Google Cloud Observability
and nowhere else, and it owns OTEL_EXPORTER_OTLP_ENDPOINT in the pod, so it
cannot be pointed at LangSmith either. Reaching both means either self-hosting a
collector that fans out, or attaching a second span processor here. This is the
second, which costs no infrastructure to run.

WHY THE LANGSMITH PIPE IS FILTERED. Everything the process traces goes to Google:
FastAPI request spans, Cloud SQL spans, Pub/Sub spans. LangSmith is an LLM
observability tool billed by what you send it, and a chat turn's HTTP span tells
it nothing it can use. So only spans from the LLM and graph instrumentation
scopes take that exit. Cloud Trace still sees all of them.

EVERY PIECE IS INDEPENDENTLY OPTIONAL. No OTLP endpoint, no Google pipe. No
LangSmith key, no LangSmith pipe. Neither configured, and configure_tracing() is
a no-op that leaves the global provider alone. Local development and the test
suite hit that last case, and must keep working exactly as they did.
"""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

# Instrumentation scopes whose spans are worth sending to LangSmith. Matched as
# prefixes, because these libraries version their scope names ("langsmith",
# "langsmith.client", "opentelemetry.instrumentation.openai_v2" and so on) and
# pinning exact strings would silently stop matching on an upgrade: a failure
# that looks like "tracing just stopped working" with nothing in the logs.
_LLM_SCOPE_PREFIXES = (
    "langsmith",
    "langchain",
    "langgraph",
    "opentelemetry.instrumentation.openai",
    "dspy",
)

_provider = None


def _is_llm_scope(name: str | None) -> bool:
    return bool(name) and name.startswith(_LLM_SCOPE_PREFIXES)  # type: ignore[union-attr]


def _build_scope_filter_processor(inner):
    """Wrap a span processor so only LLM/graph spans reach it.

    Defined inside a function so the opentelemetry.sdk import stays off the
    module's import path. This module is imported by main.py at startup, and
    the SDK is not needed at all when tracing is unconfigured.
    """
    from opentelemetry.sdk.trace import ReadableSpan, SpanProcessor

    class ScopeFilterSpanProcessor(SpanProcessor):
        """Forwards only spans emitted by an LLM/graph instrumentation scope.

        Filtering on end rather than on start: a span's scope is known at both
        points, but dropping at on_start would also drop the matching on_end and
        leave the wrapped BatchSpanProcessor with an unbalanced view. on_start
        is forwarded unconditionally and is cheap. The batch processor does
        nothing with it.
        """

        def __init__(self, wrapped: SpanProcessor) -> None:
            self._wrapped = wrapped

        def on_start(self, span, parent_context=None) -> None:
            self._wrapped.on_start(span, parent_context)

        def on_end(self, span: ReadableSpan) -> None:
            scope = getattr(span, "instrumentation_scope", None)
            if _is_llm_scope(getattr(scope, "name", None)):
                self._wrapped.on_end(span)

        def shutdown(self) -> None:
            self._wrapped.shutdown()

        def force_flush(self, timeout_millis: int = 30_000) -> bool:
            return self._wrapped.force_flush(timeout_millis)

    return ScopeFilterSpanProcessor(inner)


def _unsampled_pubsub_batch(attributes, links) -> bool:
    """A Pub/Sub batch RPC span none of whose messages were sampled.

    See _build_load_test_sampler. The batch-count attribute is what tells the
    batch RPCs apart from Pub/Sub's per-message spans (create, subscribe,
    process), which have a parent to decide by and must be left to it.
    """
    return bool(
        attributes
        and attributes.get("messaging.system") == "gcp_pubsub"
        and "messaging.batch.message_count" in attributes
        and not links
    )


def _build_load_test_sampler(inner):
    """Wrap a sampler so nothing started during a load-tested request or turn is
    recorded.

    A load test runs thousands of stubbed turns, and tracing them ships
    thousands of traces describing LLM calls that never happened: into Cloud
    Trace, and into LangSmith, which bills per trace and whose threads are what
    the spend and abandonment questions are asked of. This used to be a check at
    the top of configure_tracing(), which could never fire: the load-test flag
    is per request, and that runs once at startup, when no request exists.

    Per span instead, at creation, when the flag is set: LoadTestMiddleware sets
    it for the API request and load_test_scope() for the worker's turn. The two
    gaps it cannot see on its own are covered elsewhere. FastAPI's request span
    starts outside the middleware, so app/main.py excludes load-test requests
    from it. And Pub/Sub's subscriber spans start before the worker reads the
    message, but their parent is the publish span this sampler dropped, so a
    parent-based inner sampler (the default, and Managed OTel's) drops them too.

    Pub/Sub's batch RPC spans (publish, modack, ack, nack) are the one thing
    left. They start on the library's own threads with no parent and no flag,
    one of each per turn, so a load test still shipped three orphan traces a
    turn. What they do carry is links to the message spans in the batch, and
    the library adds a link only for a message span that was sampled. A batch
    span with no links therefore covers no sampled message, and recording it
    would describe work nothing else in the trace backend contains. Found on
    minikube, with Jaeger counting what a Locust run left behind.
    """
    from opentelemetry.sdk.trace.sampling import Decision, Sampler, SamplingResult

    from app.core.loadtest import is_load_test

    class LoadTestSampler(Sampler):
        def should_sample(
            self,
            parent_context,
            trace_id,
            name,
            kind=None,
            attributes=None,
            links=None,
            trace_state=None,
        ) -> SamplingResult:
            if is_load_test() or _unsampled_pubsub_batch(attributes, links):
                return SamplingResult(Decision.DROP)
            return inner.should_sample(
                parent_context, trace_id, name, kind, attributes, links, trace_state
            )

        def get_description(self) -> str:
            return f"LoadTestSampler{{{inner.get_description()}}}"

    return LoadTestSampler()


def _instrument_infra() -> None:
    """Attach span emission to the non-LLM half of a turn.

    These are the spans the scope filter deliberately keeps out of LangSmith:
    the SQL a turn runs, the Valkey checkpoint reads, the outbound HTTP. They
    exist for Cloud Trace, and they are the reason the Google pipe is worth
    turning on at all, without them it carries the same LLM spans LangSmith
    already has and nothing else.

    The inbound request span is not attached here. FastAPI emits it natively
    (see the telemetry= argument in app/main.py) through whatever global
    provider is installed when a request arrives. The contrib
    FastAPIInstrumentor used to live here and never produced a span in
    production: called from the lifespan hook, it patched
    build_middleware_stack after Starlette had already built the stack for the
    lifespan event itself, so the patch never ran. It is gone rather than moved
    to module level because FastAPI disables its native telemetry whenever that
    middleware is present.

    Managed OpenTelemetry for GKE does not supply any of this. It runs a
    collector and injects OTEL_EXPORTER_OTLP_ENDPOINT; instrumenting the
    process is still the process's job.

    Each instrumentor is caught separately. A missing optional dependency or
    a version skew in one should not cost the others.
    """
    try:
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

        SQLAlchemyInstrumentor().instrument()
    except Exception:
        logger.warning("SQLAlchemy OTel instrumentation failed", exc_info=True)

    try:
        from opentelemetry.instrumentation.redis import RedisInstrumentor

        RedisInstrumentor().instrument()
    except Exception:
        logger.warning("Redis/Valkey OTel instrumentation failed", exc_info=True)

    try:
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

        # Catches ChatOpenRouter too, which reaches OpenRouter over a bare httpx
        # client rather than the openai SDK. Those spans carry no prompt or
        # token counts. They are transport timing, which is what Cloud Trace
        # wants and what the LangSmith scope filter is right to drop.
        HTTPXClientInstrumentor().instrument()
    except Exception:
        logger.warning("httpx OTel instrumentation failed", exc_info=True)


def _instrument_llm_clients() -> None:
    """Attach span emission to the openai SDK calls LangChain does not cover.

    The chat pipeline's own calls go through ChatOpenRouter and are traced by
    LangChain itself. The DSPy build steps are traced by dspy_lm_callbacks,
    which every DSPy LM carries from construction, so there is nothing to
    install for them here.
    """
    try:
        from opentelemetry.instrumentation.openai_v2 import OpenAIInstrumentor

        OpenAIInstrumentor().instrument()
    except Exception:
        logger.warning("openai OTel instrumentation failed", exc_info=True)


# --- DSPy LM spans -----------------------------------------------------------
#
# The recommender's DSPy calls are most of a completed build's spend, so leaving
# them untraced would make the per-conversation total in LangSmith an
# understatement rather than a number.
#
# WHY A CALLBACK OF OUR OWN. These calls used to reach OpenRouter through
# litellm, whose "otel" and "langsmith" callbacks produced the spans. DSPy 3.5
# speaks to providers natively and litellm is no longer installed. Its native
# engine has its own HTTP client (not httpx, not requests), so no
# auto-instrumentation sees these calls either. One span per LM call, from
# DSPy's own callback hook, is what replaces them.
#
# The span carries the gen_ai.* attributes LangSmith's OTel ingestion maps
# (model, token counts) and `langsmith.span.kind=llm` so it is shown as an LLM
# run. No cost attribute: LangSmith's mapping has none (see the header of
# app/services/llm/openrouter.py), and our own cost lives in module_decisions.
# No prompt or completion text either, which litellm's callbacks did attach:
# the span also goes to Cloud Trace, and the prompts carry what users typed.
#
# Scope name "dspy.lm" matches the "dspy" prefix in _LLM_SCOPE_PREFIXES, so the
# spans reach LangSmith as well as the OTLP endpoint.
_DSPY_TRACER_SCOPE = "dspy.lm"


def dspy_lm_callbacks(tracer_provider: Any = None) -> list:
    """Callbacks to construct every DSPy LM with: one span per LM call.

    Attached per LM (dspy.LM(callbacks=...)) rather than through
    dspy.configure, which is restricted to the thread that first called it and
    runs at a different point of startup than configure_tracing. lm.copy keeps
    them. Without a tracer provider the spans are non-recording and cost next
    to nothing, so attaching them unconditionally is safe. A failure inside
    the callback is logged and never fails the LM call.

    tracer_provider is for tests; production uses the global one installed by
    configure_tracing, looked up per call so an LM built before tracing was
    configured still traces.
    """
    import threading

    from dspy.utils.callback import BaseCallback
    from opentelemetry import trace
    from opentelemetry.trace import SpanKind, Status, StatusCode

    class DspyLMSpans(BaseCallback):
        def __init__(self) -> None:
            self._spans: dict[str, Any] = {}
            self._lock = threading.Lock()

        def on_lm_start(self, call_id: str, instance: Any, inputs: dict) -> None:
            try:
                model = str(getattr(instance, "model", "") or "")
                system, _, name = model.partition("/")
                kwargs = getattr(instance, "kwargs", None) or {}
                attributes: dict[str, Any] = {
                    "gen_ai.operation.name": "chat",
                    "gen_ai.system": system if name else "unknown",
                    "gen_ai.request.model": name or model,
                    "langsmith.span.kind": "llm",
                }
                for key in ("temperature", "max_tokens"):
                    if kwargs.get(key) is not None:
                        attributes[f"gen_ai.request.{key}"] = kwargs[key]
                tracer = trace.get_tracer(
                    _DSPY_TRACER_SCOPE, tracer_provider=tracer_provider
                )
                span = tracer.start_span(
                    f"chat {name or model}", kind=SpanKind.CLIENT, attributes=attributes
                )
                with self._lock:
                    self._spans[call_id] = span
            except Exception:
                logger.debug("dspy span start failed", exc_info=True)

        def on_lm_end(
            self,
            call_id: str,
            outputs: Any,
            exception: BaseException | None = None,
        ) -> None:
            with self._lock:
                span = self._spans.pop(call_id, None)
            if span is None:
                return
            try:
                if exception is not None:
                    span.record_exception(exception)
                    span.set_status(Status(StatusCode.ERROR, type(exception).__name__))
                else:
                    # outputs is DSPy's native Response (lm15) for this call.
                    _set_response_attributes(span, outputs)
            except Exception:
                logger.debug("dspy span end failed", exc_info=True)
            finally:
                span.end()

    return [DspyLMSpans()]


def _set_response_attributes(span: Any, response: Any) -> None:
    if response is None:
        return
    for attr, key in (("model", "gen_ai.response.model"), ("id", "gen_ai.response.id")):
        value = getattr(response, attr, None)
        if value:
            span.set_attribute(key, str(value))
    finish = getattr(response, "finish_reason", None)
    if finish:
        span.set_attribute("gen_ai.response.finish_reasons", [str(finish)])
    usage = getattr(response, "usage", None)
    for attr, key in (
        ("input_tokens", "gen_ai.usage.input_tokens"),
        ("output_tokens", "gen_ai.usage.output_tokens"),
        ("total_tokens", "gen_ai.usage.total_tokens"),
    ):
        value = getattr(usage, attr, None)
        if value is not None:
            span.set_attribute(key, int(value))


def configure_tracing(service_name: str) -> None:
    """Install the tracer provider for this process. Idempotent.

    service_name distinguishes the API pod from the worker pod in both
    backends: they run the same image and the same pipeline, so without it a
    trace gives no clue which one produced it.
    """
    global _provider

    if _provider is not None:
        return

    from app.core.config import settings

    otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    langsmith_key = settings.LANGSMITH_API_KEY

    if not otlp_endpoint and not langsmith_key:
        logger.info(
            "tracing not configured (no OTEL_EXPORTER_OTLP_ENDPOINT, no "
            "LANGSMITH_API_KEY); spans are not being exported"
        )
        return

    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    from app.services.recommender.dspy_pipeline import PIPELINE_VERSION

    provider = TracerProvider(
        resource=Resource.create(
            {
                "service.name": service_name,
                "service.version": PIPELINE_VERSION,
                "deployment.environment": settings.ENVIRONMENT,
            }
        )
    )
    # Wrapped, not replaced: provider.sampler is what TracerProvider resolved
    # from OTEL_TRACES_SAMPLER, which Managed OTel injects, and that ratio must
    # keep governing real traffic. Set before any tracer exists, since each
    # tracer copies the sampler when it is created.
    provider.sampler = _build_load_test_sampler(provider.sampler)

    if otlp_endpoint:
        # No endpoint argument: the exporter reads OTEL_EXPORTER_OTLP_ENDPOINT
        # itself, along with the rest of the standard OTEL_* knobs. Managed OTel
        # for GKE sets those through its Instrumentation CR, and hardcoding an
        # endpoint here would override an injection that is meant to win.
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
        logger.info("tracing: exporting to OTLP endpoint %s", otlp_endpoint)

    if langsmith_key:
        langsmith_exporter = OTLPSpanExporter(
            endpoint=f"{settings.LANGSMITH_OTEL_ENDPOINT.rstrip('/')}/v1/traces",
            headers={
                "x-api-key": langsmith_key,
                "Langsmith-Project": settings.LANGSMITH_PROJECT,
            },
        )
        provider.add_span_processor(
            _build_scope_filter_processor(BatchSpanProcessor(langsmith_exporter))
        )
        # Attaches LangChain's tracer to every chain, graph node and model call.
        # Without it LangChain never instruments anything and the LangSmith pipe
        # below carries only the DSPy spans. ChatOpenRouter subclasses
        # BaseChatModel over raw httpx, so the openai instrumentor does not see
        # the chat pipeline either, and the graph goes entirely untraced.
        os.environ["LANGSMITH_TRACING"] = "true"
        # Makes LangGraph/LangChain emit OTel spans instead of posting to
        # LangSmith's own REST API. Set here rather than in the environment so
        # it cannot be true while this provider is absent, which would send the
        # graph's spans nowhere at all.
        #
        # LANGSMITH_TRACING_MODE, not the older LANGSMITH_OTEL_ENABLED: that one
        # is now a legacy alias resolving to "hybrid", which keeps the REST
        # posts *as well as* the spans and bills LangSmith for each run twice.
        os.environ["LANGSMITH_TRACING_MODE"] = "otel"
        logger.info(
            "tracing: exporting LLM spans to LangSmith project %r",
            settings.LANGSMITH_PROJECT,
        )

    trace.set_tracer_provider(provider)
    _provider = provider

    _instrument_llm_clients()
    _instrument_infra()


def shutdown_tracing() -> None:
    """Flush and stop the exporters. Idempotent.

    Matters most in the worker: turns are short, spans are batched, and SIGTERM
    arrives without warning, so without this the last turn before a rollout
    routinely disappears from both backends.
    """
    global _provider
    if _provider is None:
        return
    provider, _provider = _provider, None
    try:
        provider.shutdown()
    except Exception:
        logger.debug("tracing shutdown failed (exiting anyway)", exc_info=True)


# --- Run metadata: the join key between LangSmith and our own telemetry ------
#
# LangSmith's OTel ingestion promotes span attributes named
# `langsmith.metadata.<key>` into a run's metadata, and groups runs into Threads
# on the metadata keys `thread_id` / `session_id` / `conversation_id`. Without
# one of those set, every chat turn arrives as an isolated trace and no
# multi-turn question ("how many turns to a build?", "did they abandon?") can be
# asked at all, which is the whole reason this exists.
#
# Several aliases are written rather than one, because which key LangSmith
# groups on has changed across versions and writing three costs nothing.
#
# THE JOIN. `build_session_id` is not a LangSmith concept; it is the primary key
# of our own `build_sessions` row. Putting it in run metadata is what lets a bad
# trace in LangSmith be traced back to the exact candidate sets and chosen parts
# in `module_decisions`, and, with conversation_id on both sides, back again.
_THREAD_METADATA_ALIASES = ("thread_id", "session_id", "conversation_id")


def attach_run_metadata(**values: object) -> None:
    """Attach metadata to the current span, for LangSmith to promote onto the run.

    A no-op when tracing is unconfigured or no span is recording, so call sites
    need no guard of their own. Never raises: losing a metadata tag must not
    fail a chat turn.
    """
    try:
        from opentelemetry import trace as _trace

        span = _trace.get_current_span()
        if span is None or not span.is_recording():
            return
        for key, value in values.items():
            if value is None:
                continue
            span.set_attribute(f"langsmith.metadata.{key}", str(value))
    except Exception:  # pragma: no cover - defensive
        logger.debug("attach_run_metadata failed", exc_info=True)


def attach_thread(conversation_id: object) -> None:
    """Mark the current span as belonging to a conversation Thread.

    Writes every alias LangSmith has used for thread grouping. See
    _THREAD_METADATA_ALIASES.
    """
    if conversation_id is None:
        return
    attach_run_metadata(**{k: conversation_id for k in _THREAD_METADATA_ALIASES})
