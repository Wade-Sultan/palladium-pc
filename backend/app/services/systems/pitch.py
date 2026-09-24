"""The few sentences that introduce a system offer.

The model phrases; it does not decide. Everything it may claim is in the
Assessment it is handed, and the prompt says so, because the failure worth
guarding against here is a confident pitch for a spec the box does not have
("runs CUDA" about a Mac, "fast" about a 273 GB/s part).

If the call fails, a fixed sentence goes out instead. The offer card carries the
substance either way; losing the prose must not lose the offer.
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from typing import Any

from langchain_core.messages import HumanMessage

from app.schemas.chat import BuildProfile, ChatMessage
from app.services.chat_models import ChatModelConfig
from app.services.llm import get_chat_model

logger = logging.getLogger(__name__)

_PITCH_SYSTEM = """\
You are Palladium's PC advisor. The user has finished describing what they need,
and a rules check found that a complete, ready-made system may suit them better
than a custom PC. Below the conversation you are given that check's result as
JSON. A card showing the system, its price, a side-by-side against a custom
build estimate, and two buttons ("go with this" / "build a custom PC instead")
appears directly under your message.

Write 3 to 5 sentences, plain prose, no lists, no headings:
- Open in the spirit of: "Based on what you've told me, I think a <system> could
  be just the right fit for you." Name it as primary.family_name does, dropping
  any parenthetical.
- Tie the reason to what THEY said: the model they want to run and how much
  memory it needs, or the editing / music work they described.
- Name one honest tradeoff, taken from primary.limitations. Do not add any
  tradeoff that is not listed there.
- End by saying the choice is theirs: take the system, or you'll build a custom
  PC instead.

Only state facts present in the JSON. Never invent specs, benchmarks, prices or
availability. Prices are approximate. Do not describe the card's contents
item by item. Never use em-dashes.
"""


def fallback_pitch(offer: dict[str, Any]) -> str:
    name = (offer.get("primary") or {}).get("family_name") or "ready-made system"
    return (
        f"Based on what you've told me, I think a {name} "
        "could be just the right fit for you. I've put it side by side with a "
        "custom build below. Take it, or I'll build you a custom PC instead."
    )


def template_pitch(profile: BuildProfile, offer: dict[str, Any]) -> str:
    """Introduce an assessed offer using only the saved facts on its card."""
    primary = offer.get("primary") or {}
    name = (primary.get("family_name") or "ready-made system").split(" (")[0]
    opening = f"Based on what you've told me, a {name} could fit your needs."
    need = offer.get("memory_need_gb")
    memory = primary.get("gpu_memory_gb")
    if offer.get("reason") == "memory" and need and memory:
        reason = (
            f"Your estimated model requirement is {need} GB, and this system "
            f"has {memory} GB of GPU-addressable memory."
        )
    elif profile.primary_use == "video_editing":
        reason = "It is curated for the video editing work you described."
    elif profile.primary_use == "music_production":
        reason = "It is curated for the music production work you described."
    else:
        reason = "The system has been checked against your requirements."
    limitations = primary.get("limitations") or []
    if profile.primary_use in ("video_editing", "music_production"):
        # The first Mac limitation is about CUDA training. For creative work,
        # lead with a limitation that affects buying or using the workstation.
        relevant = next(
            (item for item in limitations if "cuda" not in item.lower()), None
        )
    else:
        relevant = limitations[0] if limitations else None
    tradeoff = f"One tradeoff: {relevant.rstrip('.')}." if relevant else ""
    choice = "You can take this system, or I'll build you a custom PC instead."
    return " ".join(part for part in (opening, reason, tradeoff, choice) if part)


def _context(profile: BuildProfile, offer: dict[str, Any]) -> str:
    payload = {k: v for k, v in offer.items() if k not in ("token", "chosen")}
    payload["user_profile"] = {
        k: v
        for k, v in profile.model_dump().items()
        if v not in (None, "", [], "unknown")
    }
    return "SYSTEM CHECK RESULT:\n" + json.dumps(payload, default=str)


async def stream_pitch(
    messages: list[ChatMessage],
    profile: BuildProfile,
    offer: dict[str, Any],
    usage_sink: dict | None = None,
    session_id: str | None = None,
) -> AsyncIterator[str]:
    if ChatModelConfig.SYSTEM_PITCH_TEMPLATE:
        yield template_pitch(profile, offer)
        return

    from app.services import chat_pipeline as cp

    model = get_chat_model(
        ChatModelConfig.get_recommend_model(),
        session_id=session_id,
        temperature=0.5,
        max_tokens=ChatModelConfig.RECOMMEND_MAX_TOKENS,
        streaming=True,
    )
    api_messages = cp._to_langchain_messages(messages, _PITCH_SYSTEM)
    api_messages.append(HumanMessage(content=_context(profile, offer)))

    emitted = False
    try:
        async for text in cp._stream_text(model, api_messages, usage_sink):
            emitted = True
            yield text
    except Exception:
        logger.warning("system pitch failed; using the fixed line", exc_info=True)
        if not emitted:
            yield fallback_pitch(offer)
        return
    if not emitted:
        yield fallback_pitch(offer)
