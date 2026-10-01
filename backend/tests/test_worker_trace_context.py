"""The worker's turn runs inside the trace Pub/Sub delivered it with.

google-cloud-pubsub leaves no span current while the subscriber callback runs
(see app.worker._trace_parent), so before that function a turn's spans each
started a trace of their own. Found on minikube with Jaeger, where the trace
crossing Pub/Sub ended at the subscriber.

The callback thread here deliberately has NO current span, which is what the
library actually provides. A test that made a span current itself would pass
with or without the fix.
"""

import threading
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider

from app import worker as worker_mod


@pytest.fixture
def worker():
    w = worker_mod.Worker()
    thread = threading.Thread(target=w._run_loop, daemon=True)
    thread.start()
    yield w
    w._loop.call_soon_threadsafe(w._loop.stop)
    thread.join(timeout=5)


@pytest.fixture
def seen(monkeypatch) -> list[trace.SpanContext]:
    seen: list[trace.SpanContext] = []

    async def fake_handle(*_args):
        seen.append(trace.get_current_span().get_span_context())

    monkeypatch.setattr(worker_mod, "_handle", fake_handle)
    monkeypatch.setattr(
        worker_mod,
        "_decode",
        lambda _m: ("turn-1", [], None, None, False, False, None, None),
    )
    return seen


def _deliver(worker, message) -> None:
    # On a thread of its own, as Pub/Sub's callback pool does.
    t = threading.Thread(target=worker._callback, args=(message,))
    t.start()
    t.join(timeout=10)


def test_turn_is_a_child_of_the_subscribe_span(worker, seen):
    # A local provider, not the global one: only the span's context matters here.
    subscribe = TracerProvider().get_tracer(__name__).start_span("subscribe")
    message = MagicMock()
    message.opentelemetry_data = SimpleNamespace(subscribe_span=subscribe)

    _deliver(worker, message)

    message.ack.assert_called_once()
    assert seen[0].trace_id == subscribe.get_span_context().trace_id
    assert seen[0].span_id == subscribe.get_span_context().span_id


def test_tracing_off_still_runs_the_turn(worker, seen):
    message = MagicMock()
    message.opentelemetry_data = None

    _deliver(worker, message)

    message.ack.assert_called_once()
    assert not seen[0].is_valid
