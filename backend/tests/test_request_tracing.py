"""Request spans from FastAPI's native telemetry, against the real app object.

Both failures this guards against were silent in production: the contrib
instrumentor produced no request span at all for as long as it was installed,
and FastAPI's auto-configure would claim the global tracer provider before
configure_tracing() could, which drops the LangSmith exporter with nothing worse
than one warning line. See the telemetry= comment in app/main.py.
"""

from contextlib import asynccontextmanager

import pytest
from fastapi.testclient import TestClient
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)
from opentelemetry.trace import ProxyTracerProvider, SpanKind
from opentelemetry.util._once import Once

from app.main import app


@pytest.fixture
def otel_globals():
    """Give the test a fresh, unset global tracer provider, then put it back.

    The global is set-once per process by design, so this resets the same two
    module attributes opentelemetry-test-utils does.
    """
    saved = (trace._TRACER_PROVIDER, trace._TRACER_PROVIDER_SET_ONCE)
    trace._TRACER_PROVIDER = None
    trace._TRACER_PROVIDER_SET_ONCE = Once()
    yield
    trace._TRACER_PROVIDER, trace._TRACER_PROVIDER_SET_ONCE = saved


@pytest.fixture
def exporter(otel_globals):  # noqa: ARG001
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    return exporter


def test_request_emits_server_span_with_route(exporter: InMemorySpanExporter):
    # No `with`: the lifespan (DSPy warm-up, metrics port) is not under test.
    TestClient(app).get("/api/v1/health")

    spans = exporter.get_finished_spans()
    server = [s for s in spans if s.kind == SpanKind.SERVER]
    assert len(server) == 1
    assert server[0].name == "GET /api/v1/health"
    assert server[0].attributes["http.route"] == "/api/v1/health"
    assert server[0].attributes["http.response.status_code"] == 200

    endpoint = [s for s in spans if s.name == "fastapi.endpoint"]
    assert endpoint, [s.name for s in spans]
    assert endpoint[0].context.trace_id == server[0].context.trace_id


@pytest.mark.parametrize("path", ["/api/v1/healthz", "/api/v1/readyz"])
def test_probe_paths_are_not_traced(exporter: InMemorySpanExporter, path: str):
    TestClient(app).get(path)
    assert exporter.get_finished_spans() == ()


def test_startup_leaves_global_provider_to_configure_tracing(
    otel_globals,  # noqa: ARG001
    monkeypatch: pytest.MonkeyPatch,
):
    # What Managed OTel injects into every selected pod.
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://127.0.0.1:4318")

    # Swap out only the app's own lifespan body. FastAPI's telemetry hook wraps
    # the lifespan protocol outside it and still sees the startup message.
    @asynccontextmanager
    async def noop_lifespan(_app):
        yield

    monkeypatch.setattr(app.router, "lifespan_context", noop_lifespan)

    with TestClient(app):
        pass

    assert isinstance(trace.get_tracer_provider(), ProxyTracerProvider)


def test_load_test_request_gets_no_request_span(
    exporter: InMemorySpanExporter, monkeypatch: pytest.MonkeyPatch
):
    from app.core.config import settings

    monkeypatch.setattr(settings, "LOAD_TEST_SECRET", "s3cret", raising=False)
    client = TestClient(app)

    client.get("/api/v1/health", headers={"X-Palladium-Load-Test": "s3cret"})
    assert exporter.get_finished_spans() == ()

    # A wrong secret is an ordinary request, and an ordinary request is traced.
    client.get("/api/v1/health", headers={"X-Palladium-Load-Test": "guess"})
    assert [
        s.name for s in exporter.get_finished_spans() if s.kind == SpanKind.SERVER
    ] == ["GET /api/v1/health"]


def test_sampler_drops_load_test_spans_and_their_descendants(
    monkeypatch: pytest.MonkeyPatch,
):
    """Includes the Pub/Sub shape: a span started later, with no load-test flag
    in sight, whose parent is a span the sampler dropped."""
    from opentelemetry.sdk.trace.sampling import ALWAYS_ON, ParentBased

    from app.core.config import settings
    from app.core.loadtest import load_test_scope
    from app.core.tracing import _build_load_test_sampler

    monkeypatch.setattr(settings, "LOAD_TEST_SECRET", "s3cret", raising=False)
    exporter = InMemorySpanExporter()
    provider = TracerProvider(sampler=_build_load_test_sampler(ParentBased(ALWAYS_ON)))
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracer = provider.get_tracer(__name__)

    with load_test_scope(True), tracer.start_as_current_span("publish") as publish:
        carried = trace.set_span_in_context(publish)
    with tracer.start_as_current_span("subscribe", context=carried):
        pass
    with tracer.start_as_current_span("real request"):
        pass

    assert [s.name for s in exporter.get_finished_spans()] == ["real request"]


def test_pubsub_batch_span_with_no_sampled_messages_is_dropped():
    """Pub/Sub links a batch RPC span only to sampled message spans, so an
    unlinked one belongs to unsampled (load-test) messages. A linked one, or any
    per-message span, is left to the inner sampler."""
    from opentelemetry.sdk.trace.sampling import ALWAYS_ON, ParentBased
    from opentelemetry.trace import Link

    from app.core.tracing import _build_load_test_sampler

    exporter = InMemorySpanExporter()
    provider = TracerProvider(sampler=_build_load_test_sampler(ParentBased(ALWAYS_ON)))
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracer = provider.get_tracer(__name__)
    batch = {"messaging.system": "gcp_pubsub", "messaging.batch.message_count": 1}

    with tracer.start_as_current_span("real create") as create:
        pass
    tracer.start_span("load-test publish", attributes=batch).end()
    tracer.start_span(
        "real publish", attributes=batch, links=[Link(create.get_span_context())]
    ).end()
    tracer.start_span("subscribe", attributes={"messaging.system": "gcp_pubsub"}).end()

    assert [s.name for s in exporter.get_finished_spans()] == [
        "real create",
        "real publish",
        "subscribe",
    ]
