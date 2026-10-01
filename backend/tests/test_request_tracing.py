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
