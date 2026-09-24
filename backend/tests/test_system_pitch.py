"""The local offer introduction uses only assessed facts and skips the model."""

import asyncio

from app.schemas.chat import BuildProfile
from app.services.chat_models import ChatModelConfig
from app.services.graph import nodes
from app.services.systems import pitch


def test_local_pitch_is_immediate_and_includes_fit_and_tradeoff(monkeypatch):
    profile = BuildProfile(primary_use="ai", budget_tier="high")
    offer = {
        "reason": "memory",
        "memory_need_gb": 42,
        "primary": {
            "family_name": "DGX Spark (GB10)",
            "gpu_memory_gb": 120,
            "limitations": ["273 GB/s bandwidth limits token generation"],
        },
    }
    monkeypatch.setattr(ChatModelConfig, "SYSTEM_PITCH_TEMPLATE", True)

    def _unexpected_model(*_args, **_kwargs):
        raise AssertionError("the local pitch requested a chat model")

    monkeypatch.setattr(pitch, "get_chat_model", _unexpected_model)

    async def _run():
        return [chunk async for chunk in pitch.stream_pitch([], profile, offer)]

    chunks = asyncio.run(_run())
    assert len(chunks) == 1
    assert "DGX Spark" in chunks[0]
    assert "42 GB" in chunks[0] and "120 GB" in chunks[0]
    assert offer["primary"]["limitations"][0] in chunks[0]
    assert "custom PC" in chunks[0]


def test_template_offer_does_not_count_an_llm_call(monkeypatch):
    profile = BuildProfile(primary_use="ai", budget_tier="high")
    offer = {"primary": {"family_name": "DGX Spark"}, "reason": "memory"}
    events = []
    monkeypatch.setattr(ChatModelConfig, "SYSTEM_PITCH_TEMPLATE", True)
    monkeypatch.setattr(nodes, "get_stream_writer", lambda: events.append)

    result = asyncio.run(
        nodes.offer(
            {
                "system_offer": offer,
                "profile": profile.model_dump(),
                "messages": [],
            }
        )
    )

    assert [event["type"] for event in events] == ["system_offer", "token"]
    assert result["usage"]["llm_call_count"] == 0


def test_creative_pitch_uses_a_relevant_catalog_tradeoff():
    profile = BuildProfile(primary_use="video_editing", budget_tier="high")
    offer = {
        "reason": "creative",
        "primary": {
            "family_name": "Mac Studio (M5 Max)",
            "limitations": [
                "No CUDA: many training tools assume NVIDIA",
                "Memory and storage are fixed at purchase",
            ],
        },
    }

    result = pitch.template_pitch(profile, offer)

    assert "Memory and storage are fixed at purchase" in result
    assert "No CUDA" not in result
