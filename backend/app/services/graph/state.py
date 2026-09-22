"""State carried through one chat turn, and persisted across turns.

WHAT IS CHECKPOINTED AND WHY IT MATTERS. Before the graph, every turn re-derived
the whole profile from raw conversation text and had no idea what it had already
asked. Two fields here change that:

  profile       accumulated, not replaced. A field the extractor found on turn 2
                and loses on turn 5 (buried under ten intervening messages) stays
                known. See merge_profile below.
  asked_fields  every item the router has already asked about, appended across
                turns. Lets the router notice it has asked twice and been dodged
                twice, and choose differently rather than a third time.

Everything else is per-turn scratch that happens to live in the same dict.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict


class ChatTurnState(TypedDict, total=False):
    # -- inputs, set fresh each turn --------------------------------------
    messages: list[dict[str, str]]
    conversation_id: str | None
    # OpenRouter's session_id, so every call this turn groups into one session
    # in their dashboard. Falls back to a per-turn id for guests.
    session_id: str

    # -- accumulated across turns -----------------------------------------
    profile: dict[str, Any] | None
    asked_fields: Annotated[list[str], operator.add]
    profile_sources: dict[str, Any]
    profile_operations: list[dict[str, Any]]
    phase: str
    proposed_build: dict[str, Any] | None

    # -- per-turn scratch --------------------------------------------------
    missing_fields: list[str]
    # The single item the router chose to ask about, or None when the profile
    # is complete and the turn is going to the builder instead. This is the
    # value the conditional edge branches on.
    next_question: str | None
    price_estimate: int | None
    usage: dict[str, Any]
    build_key: str | None
    build_data: dict[str, Any] | None
    ref_estimate_key: str | None
    ref_estimate_data: dict[str, Any] | None
    # True when the builder stopped at the case step to ask the user which case
    # they want. The turn ends there, there is no build to present yet, and
    # the pick starts a fresh turn that resumes the pipeline. This is the value
    # the edge out of `build` branches on.
    build_paused: bool
    build_rejected: bool
    # The picker shown by a paused turn, persisted onto the assistant message
    # so a reload rebuilds it. Shaped like the case_options event's data.
    case_options: dict[str, Any] | None


def new_usage() -> dict[str, Any]:
    """A zeroed per-turn usage total, shaped for chat_pipeline._merge_usage."""
    return {
        "tokens_in": 0,
        "tokens_out": 0,
        "cost_usd": 0.0,
        "llm_call_count": 0,
        "models": [],
    }


# Fields where the extractor's "I didn't find it" is indistinguishable from
# "the user retracted it". Retraction is rare and correctable by asking again;
# forgetting is common and costs the user a repeated question, so these are
# merged forward rather than overwritten with None.
_STICKY_FIELDS = (
    "gaming_resolution",
    "gaming_fps",
    "gaming_quality",
    "gaming_ray_tracing",
    "gaming_upscaling",
    "gaming_frame_generation",
    "streaming_style",
    "ai_workload",
    "ai_model_scale",
    "server_workload",
    "server_gpu_count",
    "editing_resolution",
    "rendering_software",
    "workload_intensity",
    "price_sensitivity",
    "form_factor",
    "color_theme",
    "rgb_lighting",
    "noise_tolerance",
    "stated_budget_usd",
    "llm_quantization",
    "llm_context_tokens",
)


def merge_profile(
    previous: dict[str, Any] | None, current: dict[str, Any]
) -> dict[str, Any]:
    """Merge a freshly extracted profile over the checkpointed one.

    Only fills gaps: a value the extractor produced this turn always wins, and
    a previous value is reused only where this turn produced nothing. That
    ordering matters. The user really can change their mind about resolution,
    and the extractor really does see the correction, so the fresh answer has
    to be able to overwrite the old one.

    primary_use and budget_tier are handled separately because their "unknown"
    sentinel is a value, not an absence, and would otherwise overwrite a known
    answer with an admission of ignorance.
    """
    if not previous:
        return current

    merged = dict(current)

    changed_use = current.get("primary_use") not in (
        None,
        "unknown",
        previous.get("primary_use"),
    )
    shared = {
        "stated_budget_usd",
        "price_sensitivity",
        "form_factor",
        "color_theme",
        "rgb_lighting",
        "noise_tolerance",
    }
    for field in _STICKY_FIELDS:
        if changed_use and field not in shared:
            continue
        if merged.get(field) is None and previous.get(field) is not None:
            merged[field] = previous[field]

    for field in ("primary_use", "budget_tier"):
        if merged.get(field) in (None, "unknown") and previous.get(field) not in (
            None,
            "unknown",
        ):
            merged[field] = previous[field]

    # List and free-text fields accumulate rather than replace: the user naming
    # a second game does not mean they stopped caring about the first.
    for field in ("games", "workloads"):
        combined = list(previous.get(field) or [])
        for item in merged.get(field) or []:
            if item not in combined:
                combined.append(item)
        merged[field] = combined

    # Pre-selected parts accumulate by SLOT, which is the one thing that makes
    # them different from games. Naming a CPU on turn five does not retract the
    # graphics card named on turn two, so old slots carry forward; but a second
    # graphics card named on turn five is a change of mind, not a request for
    # two, so within a slot the fresh answer wins. Neither rule falls out of
    # list accumulation, which is why this is not folded in with games above.
    #
    # Carried across a change of primary_use as well: a card the user owns is
    # still a card they own once they decide to edit video on it instead.
    locked = {
        entry["role"]: entry
        for entry in (previous.get("locked_parts") or [])
        if isinstance(entry, dict) and entry.get("role")
    }
    locked.update(
        {
            entry["role"]: entry
            for entry in (merged.get("locked_parts") or [])
            if isinstance(entry, dict) and entry.get("role")
        }
    )
    merged["locked_parts"] = list(locked.values())

    if not (merged.get("notes") or "").strip() and previous.get("notes"):
        merged["notes"] = previous["notes"]

    return merged


def apply_profile_updates(
    profile: dict, updates: list, user_text: str
) -> tuple[dict, list[dict]]:
    """Apply only explicit, quoted user changes; leave omissions alone.

    Returns the updated profile and the operations that were actually applied,
    in order. Every applied operation is returned, not the last one per field:
    "I no longer play A or B" is two removes on `games`, and dropping the first
    would let merge_profile's accumulation resurrect A on the next turn.
    """
    from app.schemas.chat import BuildProfile

    result = dict(profile)
    applied: list[dict] = []
    for update in updates:
        field = update.field
        quote = update.evidence.strip()
        if field not in BuildProfile.model_fields or field == "profile_updates":
            continue
        if not quote or quote.casefold() not in user_text.casefold():
            continue
        value = update.value
        if update.operation == "clear":
            value = (
                "unknown"
                if field in ("primary_use", "budget_tier")
                else []
                if field in ("games", "workloads", "locked_parts")
                else ""
                if field == "notes"
                else None
            )
        elif update.operation == "remove" and field == "locked_parts":
            value = _drop_locked_part(result, update.value)
            if value is None:
                continue
        elif update.operation in ("add", "remove"):
            if field not in ("games", "workloads") or not isinstance(value, str):
                continue
            old = list(result.get(field) or [])
            value = (
                [item for item in old if item.casefold() != value.casefold()]
                if update.operation == "remove"
                else old
                + (
                    [value]
                    if value.casefold() not in {item.casefold() for item in old}
                    else []
                )
            )
        try:
            candidate = BuildProfile(**{**result, field: value}).model_dump()
        except ValueError:
            continue
        result = candidate
        applied.append(
            {
                "field": field,
                "operation": update.operation,
                "value": update.value,
                "evidence": quote,
            }
        )
    return result, applied


def _drop_locked_part(profile: dict, target) -> list | None:
    """The locked-parts list with one entry removed, or None if nothing matched.

    A user retracting a pre-selected part names either the slot ("forget the
    graphics card") or the part ("not the 5090 after all"), and the extractor
    reports whichever they said. Both have to resolve or half the retractions
    silently do nothing. Slot is tried first: a slot holds at most one lock, so
    naming it is unambiguous, while a part name has to be matched loosely and
    could in principle hit the wrong row.

    Returning None rather than the unchanged list matters. The caller skips an
    operation that produced nothing, which keeps it out of profile_operations,
    and a no-op recorded there would be replayed against every future turn for
    the life of the conversation.
    """
    entries = [e for e in (profile.get("locked_parts") or []) if isinstance(e, dict)]
    if not entries or not isinstance(target, str) or not target.strip():
        return None
    wanted = target.strip().casefold()
    kept = [e for e in entries if (e.get("role") or "").casefold() != wanted]
    if len(kept) == len(entries):
        kept = [e for e in entries if wanted not in (e.get("name") or "").casefold()]
    return kept if len(kept) != len(entries) else None


def replay_retractions(profile: dict, history: list[dict]) -> dict:
    """Re-apply every recorded clear/remove, in order, over a merged profile.

    Only retractions are replayed. merge_profile already carries values
    forward, so a recorded set/add has nothing to add, and replaying one
    would let a stale "set budget 2000" from turn 1 overwrite a fresh 3000
    the extractor found this turn but did not report as an operation. A
    retraction is the one thing accumulation cannot represent, so it is the
    one thing that has to be said again each turn.
    """
    from app.schemas.chat import ProfileUpdate

    for old in history:
        if old.get("operation") not in ("clear", "remove"):
            continue
        operation = ProfileUpdate(
            **{k: v for k, v in old.items() if k != "message_index"}
        )
        profile, _ = apply_profile_updates(profile, [operation], operation.evidence)
    return profile
