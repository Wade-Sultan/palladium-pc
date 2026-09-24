"""Guards the complete-system fork through the real graph.

What the fit rules decide is tested in test_system_fit.py. This is about what
the turn does with that decision, and the risks are all in the plumbing:

  - an offer turn must end on the card, with no build and no progress event
    (the frontend reads progress as "a build is coming");
  - "build me a PC instead" must build from the SAVED profile and carry the
    declined system onto the build for the side-by-side;
  - a pick is redeemable once: a double-click on "custom" must not run the
    pipeline twice;
  - a case-picker token must never redeem an offer, or the reverse;
  - a question typed while the card is open goes to discussion, not back
    through intake, which would show the same offer a second time.

No network and no Postgres: the offer store runs on a fake Valkey, and the
assessment, pitch and builder are stubbed.
"""

from __future__ import annotations

import asyncio
import json

import pytest

from app.schemas.chat import BuildProfile, ChatMessage
from app.services import chat_pipeline as cp
from app.services import paused_build
from app.services.graph import graph as graph_mod
from app.services.graph import nodes
from app.services.systems import catalog, pitch
from app.services.systems import offer as offers
from app.services.systems.fit import Assessment, CustomEstimate, SystemOption

_SPARK = SystemOption(
    part_id="spark-1",
    name="ASUS Ascent GX10 128GB 1TB",
    manufacturer="ASUS",
    family_id="fam-gb10",
    family_name="DGX Spark (GB10)",
    platform="nvidia_gb10",
    gpu_backend="cuda",
    os="DGX OS (Ubuntu)",
    chip="GB10",
    unified_memory_gb=128,
    gpu_memory_gb=120,
    bandwidth_gbps=273,
    storage_gb=1000,
    price_cents=399_999,
    suited_for=("llm_inference", "llm_training"),
)
_ASSESSMENT = Assessment(
    reason="memory",
    primary=_SPARK,
    memory_need_gb=42,
    estimate=CustomEstimate("RTX 3090", 2, 48, 300_000, 150_000),
    budget_usd=5000,
)


def _profile() -> dict:
    return {
        "primary_use": "ai",
        "budget_tier": "high",
        "ai_workload": "inference",
        "ai_model_scale": "large",
        "llm_quantization": "yes",
        "llm_context_tokens": "8k",
        "stated_budget_usd": 5000,
        "price_sensitivity": "flexible",
    }


def _no_models(*args, **kwargs):
    raise AssertionError("a real chat model was requested; stub the call instead")


class _FakeValkey:
    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    async def set(self, key, value, ex=None):
        self.store[key] = value

    async def get(self, key):
        return self.store.get(key)

    async def getdel(self, key):
        return self.store.pop(key, None)


class _NoPostgres:
    """Stands in for AsyncSessionLocal: every use fails, as if unreachable."""

    def __call__(self):
        raise RuntimeError("no database in this test")


@pytest.fixture
def world(monkeypatch):
    """In-memory graph, fake offer store, and every model call stubbed."""

    async def _no_client():
        return None

    fake = _FakeValkey()

    async def _fake_client():
        return fake

    async def _noop(*args, **kwargs):
        return None

    # Tripwire: every model call in this file is stubbed below, so any request
    # for a real one means the turn took a branch the test did not intend.
    monkeypatch.setattr(nodes, "get_chat_model", _no_models)
    monkeypatch.setattr(cp, "get_chat_model", _no_models)
    monkeypatch.setattr(pitch, "get_chat_model", _no_models)
    monkeypatch.setattr(graph_mod, "get_client", _no_client)
    monkeypatch.setattr(paused_build, "get_client", _fake_client)
    monkeypatch.setattr(paused_build, "AsyncSessionLocal", _NoPostgres())
    monkeypatch.setattr(paused_build, "_mark_resumed", _noop)
    monkeypatch.setattr(paused_build, "_claim_in_postgres", _noop)

    async def _extract(messages, usage_sink=None, session_id=None):
        return BuildProfile(**_profile())

    async def _assess(profile, reference):
        return _ASSESSMENT

    async def _pitch(messages, profile, offer, usage_sink=None, session_id=None):
        yield "Based on what you've told me, a DGX Spark could fit."

    built: list[dict] = []

    async def _build(state):
        built.append(dict(state))
        writer = nodes.get_stream_writer()
        payload = {"parts": [], "system_comparison": state.get("system_comparison")}
        writer({"type": "progress", "step": "resolving", "message": "Building…"})
        writer({"type": "build", "key": "custom_dspy", "data": payload})
        return {"build_key": "custom_dspy", "build_data": payload}

    async def _recommend(messages, *a, **kw):
        yield "Here is your custom build."

    monkeypatch.setattr(cp, "extract_profile", _extract)
    monkeypatch.setattr(catalog, "assess_profile", _assess)
    monkeypatch.setattr(pitch, "stream_pitch", _pitch)
    monkeypatch.setattr(nodes, "build", _build)
    monkeypatch.setattr(cp, "stream_recommendation", _recommend)
    graph_mod.reset_for_tests()
    yield {"built": built, "store": fake}
    graph_mod.reset_for_tests()


def _turn(messages=None, system_pick=None):
    messages = messages or [ChatMessage(role="user", content="70B locally, $5000")]

    async def scenario():
        return [e async for e in cp.run_chat_turn(messages, system_pick=system_pick)]

    return asyncio.run(scenario())


def _offer_of(events) -> dict:
    return next(e["data"] for e in events if e["type"] == "system_offer")


def _text(events) -> str:
    return "".join(e["text"] for e in events if e["type"] == "token")


# ------------------------------------------------------------------ the offer --


def test_a_fitting_profile_ends_on_the_offer_card(world):
    events = _turn()
    types = [e["type"] for e in events]

    assert "build" not in types
    assert "progress" not in types
    assert types[0] == "system_offer"
    assert types[-2:] == ["usage", "done"]
    offer = _offer_of(events)
    assert offer["chosen"] is None
    assert offer["primary"]["part_id"] == "spark-1"
    assert offer["estimate"]["total_cents"] == 450_000
    assert "DGX Spark" in _text(events)
    assert world["built"] == []


def test_an_offer_that_cannot_be_saved_is_not_shown(world, monkeypatch):
    """A card whose buttons cannot be redeemed is worse than no card."""

    async def _unsaved(*args, **kwargs):
        return False

    monkeypatch.setattr(paused_build, "save", _unsaved)
    types = [e["type"] for e in _turn()]

    assert "system_offer" not in types
    assert "build" in types


# ------------------------------------------------------------------ the picks --


def test_choosing_custom_builds_with_the_declined_system_attached(world):
    token = _offer_of(_turn())["token"]

    events = _turn(system_pick=(token, "custom"))
    types = [e["type"] for e in events]

    resolved = _offer_of(events)
    assert resolved["token"] == token
    assert resolved["chosen"] == "custom"
    assert "build" in types and "token" in types
    build = next(e["data"] for e in events if e["type"] == "build")
    assert build["system_comparison"]["system"]["part_id"] == "spark-1"

    # Built from the profile the offer was assessed on, and the decline sticks.
    state = world["built"][0]
    assert state["profile"]["ai_model_scale"] == "large"
    assert state["system_offer_declined"] is True


def test_taking_the_system_records_it_and_builds_nothing(world):
    token = _offer_of(_turn())["token"]

    events = _turn(system_pick=(token, "spark-1"))

    assert _offer_of(events)["chosen"] == "spark-1"
    assert "build" not in [e["type"] for e in events]
    assert "ASUS Ascent GX10" in _text(events)
    assert world["built"] == []


def test_a_double_click_redeems_the_offer_once(world):
    token = _offer_of(_turn())["token"]

    first = _turn(system_pick=(token, "custom"))
    second = _turn(system_pick=(token, "custom"))

    assert "build" in [e["type"] for e in first]
    assert "build" not in [e["type"] for e in second]
    assert "expired" in _text(second)
    assert len(world["built"]) == 1


def test_a_choice_that_was_never_offered_builds_nothing(world):
    token = _offer_of(_turn())["token"]

    events = _turn(system_pick=(token, "some-other-part"))

    assert "build" not in [e["type"] for e in events]
    assert "system_offer" not in [e["type"] for e in events]
    assert "expired" in _text(events)


def test_a_case_token_cannot_redeem_an_offer_or_the_reverse(world):
    """Both pauses share one store; the kind is checked before claiming, so a
    token of one kind neither works for nor burns a pause of the other."""
    token = _offer_of(_turn())["token"]

    assert asyncio.run(paused_build.load_and_claim(token, None)) is None
    # Still redeemable as what it is.
    assert asyncio.run(offers.claim(token, None)) is not None

    world["store"].store[paused_build._key("case-tok")] = json.dumps(
        {"state": {}, "conversation_id": None}
    )
    assert asyncio.run(offers.claim("case-tok", None)) is None
    assert asyncio.run(paused_build.load_and_claim("case-tok", None)) is not None


# ------------------------------------------------ typing while the card is open --


def test_a_question_asked_while_the_card_is_open_is_discussed(world, monkeypatch):
    offer = _offer_of(_turn())
    seen: list[dict] = []

    async def _discuss(messages, proposed_build, session_id):
        seen.append(proposed_build)
        yield {"type": "token", "text": "It holds the model comfortably."}

    from app.services.recommender import discussion

    monkeypatch.setattr(discussion, "discuss", _discuss)
    messages = [
        ChatMessage(role="user", content="70B locally, $5000"),
        ChatMessage(role="assistant", content="A DGX Spark...", system_offer=offer),
        ChatMessage(role="user", content="How fast is it?"),
    ]
    events = _turn(messages)

    assert seen and seen[0]["kind"] == "system_offer"
    assert "token" not in seen[0]["offer"]
    assert "system_offer" not in [e["type"] for e in events]


def test_a_taken_system_is_what_later_turns_discuss():
    offer = {**offers.offer_data("t", _ASSESSMENT), "chosen": "spark-1"}
    proposal = offers.proposal_from_offer(offer)
    assert proposal["kind"] == "system"
    assert proposal["system"]["part_id"] == "spark-1"


def test_a_declined_offer_proposes_nothing():
    offer = {**offers.offer_data("t", _ASSESSMENT), "chosen": "custom"}
    assert offers.proposal_from_offer(offer) is None


def test_a_declined_conversation_is_not_offered_again():
    state = {"system_offer_declined": True, "profile": _profile()}
    assert asyncio.run(nodes.assess(state)) == {"system_offer": None}
