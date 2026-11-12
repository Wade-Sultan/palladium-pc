"""DSPy's native engine (3.5+), exercised over a real socket.

litellm is no longer installed, and every DSPy call goes through DSPy's own
engine instead. Several things about that engine fail quietly rather than
loudly, and each test here pins one of them against an in-process fake
OpenAI-compatible server, so the assertion is about what reached the wire:

- An option the engine cannot carry (extra_body, `usage`, `session_id`) is
  refused, or under engine="auto" handed to litellm, which surfaces only at
  call time as an ImportError from inside a build step.
- `dspy.LM(provider=...)` swallows an OpenRouter provider pin without error.
- model_type="auto" sends an `openai/` model to /v1/responses.
- DSPy's own history["cost"] is None for models without a bundled price, so
  OpenRouter's billed cost has to be read off the raw response.
- 3.5 changed ChainOfThought's reasoning field type, which would change
  artifacts.schema_hash and reject every pinned prompt release.

No LLM is called and nothing leaves the machine.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

import pytest

_COMPLETION = (
    "[[ ## reasoning ## ]]\nbecause\n\n[[ ## answer ## ]]\nok\n\n[[ ## completed ## ]]"
)


class _FakeServer:
    """Answers every POST with one Chat Completions response, recording each request."""

    def __init__(self) -> None:
        self.requests: list[dict[str, Any]] = []
        server = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:  # noqa: N802 - http.server's name
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                server.requests.append({"path": self.path, "body": body})
                out = json.dumps(
                    {
                        "id": "gen-123",
                        "object": "chat.completion",
                        "created": 1,
                        "model": body.get("model"),
                        "choices": [
                            {
                                "index": 0,
                                "finish_reason": "stop",
                                "message": {
                                    "role": "assistant",
                                    "content": _COMPLETION,
                                },
                            }
                        ],
                        # `cost` is OpenRouter's extension to usage.
                        "usage": {
                            "prompt_tokens": 11,
                            "completion_tokens": 7,
                            "total_tokens": 18,
                            "cost": 0.00042,
                        },
                    }
                ).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(out)))
                self.end_headers()
                self.wfile.write(out)

            def log_message(self, *args: Any) -> None:
                pass

        self.httpd = HTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.httpd.server_address[1]}"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()


@pytest.fixture
def fake_server(monkeypatch: pytest.MonkeyPatch) -> Iterator[_FakeServer]:
    server = _FakeServer()
    # Never through a proxy, which a sandbox or CI runner may set.
    monkeypatch.setenv("NO_PROXY", "127.0.0.1,localhost")
    monkeypatch.setenv("no_proxy", "127.0.0.1,localhost")
    yield server
    server.httpd.shutdown()


@pytest.fixture
def openrouter(
    monkeypatch: pytest.MonkeyPatch, fake_server: _FakeServer
) -> _FakeServer:
    """The production configuration, with OpenRouter's address pointed at the fake."""
    from app.core.config import settings

    monkeypatch.setattr(settings, "LLM_BASE_URL", "")
    monkeypatch.setattr(settings, "OPENROUTER_PROVIDER", {"order": ["deepinfra"]})
    # DSPy reads <PREFIX>_API_BASE for an `openrouter/` model.
    monkeypatch.setenv("OPENROUTER_API_BASE", f"{fake_server.url}/api/v1")
    return fake_server


def _run_step(lm: Any) -> Any:
    """One ChainOfThought call, configured as configure_dspy configures it.

    Callers build LMs with cache=False: DSPy's response cache lives on disk and
    survives between runs, and a cache hit never reaches the fake server.
    """
    import dspy

    from app.services.recommender.artifacts import chain_of_thought

    with dspy.context(lm=lm, adapter=dspy.ChatAdapter(), track_usage=True):
        return chain_of_thought("question -> answer")(question="q")


def test_openrouter_call_carries_the_pin_and_nothing_the_engine_refuses(openrouter):
    from app.services.recommender.dspy_pipeline import make_lm

    prediction = _run_step(
        make_lm("google/gemma-4-31b-it", temperature=0.3, cache=False)
    )

    assert prediction.answer == "ok"
    assert prediction.reasoning == "because"
    [request] = openrouter.requests
    assert request["path"] == "/api/v1/chat/completions"
    body = request["body"]
    assert body["model"] == "google/gemma-4-31b-it"
    assert body["provider"] == {"order": ["deepinfra"]}
    for refused in ("usage", "session_id", "extra_body"):
        assert refused not in body


def test_session_lm_copy_still_reaches_the_wire(openrouter):
    import dspy

    from app.services.recommender.dspy_pipeline import make_lm, session_lm

    with dspy.context(lm=make_lm("google/gemma-4-31b-it", cache=False)):
        extraction = session_lm("turn-1", model="google/gemma-3-4b-it")
    _run_step(extraction)

    body = openrouter.requests[-1]["body"]
    assert body["model"] == "google/gemma-3-4b-it"
    assert body["provider"] == {"order": ["deepinfra"]}


@pytest.mark.usefixtures("openrouter")
def test_cost_and_tokens_are_recorded_from_the_billed_response():
    from app.services.recommender.dspy_pipeline import make_lm
    from app.services.recommender.recording import extract_usage

    lm = make_lm("google/gemma-4-31b-it", cache=False)
    prediction = _run_step(lm)
    entry = dict(lm.history[-1])

    tokens_in, tokens_out, cost, model, prompt_hash = extract_usage(prediction, entry)

    assert (tokens_in, tokens_out) == (11, 7)
    # DSPy's own estimate is None for a model its price table lacks; the
    # recorded figure must be OpenRouter's.
    assert cost == pytest.approx(0.00042)
    assert model == "openrouter/google/gemma-4-31b-it"
    assert prompt_hash


def test_local_server_gets_chat_completions_and_no_think(monkeypatch, fake_server):
    from app.core.config import settings
    from app.services.recommender import dspy_pipeline as dp

    monkeypatch.setattr(settings, "LLM_BASE_URL", f"{fake_server.url}/v1")
    monkeypatch.setattr(settings, "OPENROUTER_PROVIDER", {"order": ["X"]})
    monkeypatch.setattr(dp, "RECOMMEND_THINK_STEPS", frozenset())

    _run_step(dp.step_lm(dp.make_lm("qwen3.8-27b", cache=False), "ddr"))

    [request] = fake_server.requests
    # Not /v1/responses, which model_type="auto" picks for an `openai/` model.
    assert request["path"] == "/v1/chat/completions"
    assert request["body"]["model"] == "qwen3.8-27b"
    assert request["body"]["reasoning_effort"] == "none"
    assert "provider" not in request["body"]


@pytest.mark.usefixtures("openrouter")
def test_each_call_emits_one_llm_span():
    import dspy
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
        InMemorySpanExporter,
    )

    from app.core.tracing import _is_llm_scope, dspy_lm_callbacks
    from app.services.recommender.dspy_pipeline import make_lm

    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    lm = make_lm("google/gemma-4-31b-it", temperature=0.3, cache=False)
    lm.callbacks = dspy_lm_callbacks(tracer_provider=provider)

    _run_step(lm)

    [span] = exporter.get_finished_spans()
    assert _is_llm_scope(span.instrumentation_scope.name)
    attrs = dict(span.attributes or {})
    assert attrs["langsmith.span.kind"] == "llm"
    assert attrs["gen_ai.system"] == "openrouter"
    assert attrs["gen_ai.request.model"] == "google/gemma-4-31b-it"
    assert attrs["gen_ai.request.temperature"] == 0.3
    assert attrs["gen_ai.response.id"] == "gen-123"
    assert attrs["gen_ai.usage.input_tokens"] == 11
    assert attrs["gen_ai.usage.output_tokens"] == 7
    assert not dspy.settings.callbacks  # attached per LM, not globally


def test_every_program_keeps_a_plain_reasoning_field():
    """The pinned prompt releases verify against artifacts.schema_hash, which
    includes each field's annotation. DSPy 3.5's default ChainOfThought types
    `reasoning` as dspy.Reasoning; any module built with that default would
    fail verification in production, where there is no fallback."""
    import dspy

    from app.services.recommender.artifacts import MODULES, new_program

    for name in MODULES:
        program = new_program(name)
        for pred_name, predictor in program.named_predictors():
            for field_name, field in predictor.signature.fields.items():
                assert field.annotation is not dspy.Reasoning, (
                    f"{name}.{pred_name}.{field_name}: build it with "
                    "artifacts.chain_of_thought, not dspy.ChainOfThought"
                )
