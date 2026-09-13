"""Explicit profile operations: how a user changes their mind.

merge_profile deliberately accumulates games and carries preferences forward,
because an extractor that misses a field is far more common than a user
retracting one. That leaves no way to represent "I don't play that anymore" —
which is what apply_profile_updates is for. Every operation must be grounded
in a quote from the message that made it, so the extractor cannot retract a
preference the user never touched.
"""

from __future__ import annotations

from app.schemas.chat import BuildProfile, ProfileUpdate
from app.services.graph.state import apply_profile_updates, merge_profile


def _profile(**overrides) -> dict:
    base = {
        "primary_use": "gaming",
        "budget_tier": "mid",
        "price_sensitivity": "firm",
        "gaming_resolution": "1440p",
        "gaming_fps": "144",
        "form_factor": "mini_itx",
        "games": ["Cyberpunk 2077", "Valorant"],
    }
    base.update(overrides)
    return BuildProfile(**base).model_dump()


def test_a_quoted_clear_removes_a_sticky_preference():
    msg = "I no longer care about case size."
    updates = [ProfileUpdate(field="form_factor", operation="clear", evidence=msg)]

    result, applied = apply_profile_updates(_profile(), updates, msg)

    assert result["form_factor"] is None
    assert [op["field"] for op in applied] == ["form_factor"]


def test_a_quoted_remove_drops_one_game_and_keeps_the_rest():
    msg = "Actually I don't play Valorant anymore"
    updates = [
        ProfileUpdate(field="games", operation="remove", value="valorant", evidence=msg)
    ]

    result, _ = apply_profile_updates(_profile(), updates, msg)

    assert result["games"] == ["Cyberpunk 2077"]


def test_an_operation_without_its_quote_in_the_message_is_ignored():
    """The extractor sees the whole history; only the latest message can
    justify a change, and the quote is how that is enforced."""
    updates = [
        ProfileUpdate(
            field="form_factor", operation="clear", evidence="no case preference"
        )
    ]

    result, applied = apply_profile_updates(
        _profile(), updates, "What GPU would you suggest?"
    )

    assert result["form_factor"] == "mini_itx"
    assert applied == []


def test_unknown_fields_and_invalid_values_are_ignored():
    msg = "make it purple and set the flux to 11"
    updates = [
        ProfileUpdate(field="flux", operation="set", value=11, evidence=msg),
        ProfileUpdate(
            field="stated_budget_usd", operation="set", value="lots", evidence=msg
        ),
        ProfileUpdate(field="games", operation="add", value=["x"], evidence=msg),
        ProfileUpdate(field="profile_updates", operation="set", value=[], evidence=msg),
    ]

    result, applied = apply_profile_updates(_profile(), updates, msg)

    assert result == _profile()
    assert applied == []


def test_every_applied_operation_is_returned_not_the_last_per_field():
    """Two removes on `games` in one message must both be recorded, or the
    replay on the next turn would resurrect the first one."""
    msg = "I stopped playing Valorant and Cyberpunk 2077."
    updates = [
        ProfileUpdate(
            field="games", operation="remove", value="Valorant", evidence=msg
        ),
        ProfileUpdate(
            field="games", operation="remove", value="Cyberpunk 2077", evidence=msg
        ),
    ]

    result, applied = apply_profile_updates(_profile(), updates, msg)

    assert result["games"] == []
    assert [op["value"] for op in applied] == ["Valorant", "Cyberpunk 2077"]


def test_a_recorded_retraction_survives_the_next_turns_accumulation():
    """The scenario the whole mechanism exists for: turn N retracts a game,
    turn N+1's full-history extraction sees the old words and re-adds it.
    Replaying the recorded operation over the merge puts it right."""
    msg = "I don't play Valorant anymore"
    retract = ProfileUpdate(
        field="games", operation="remove", value="Valorant", evidence=msg
    )
    after_turn_n, history = apply_profile_updates(_profile(), [retract], msg)
    assert "Valorant" not in after_turn_n["games"]

    # Turn N+1: the extractor read the whole conversation and found Valorant.
    fresh = _profile(games=["Cyberpunk 2077", "Valorant"])
    merged = merge_profile(after_turn_n, fresh)
    assert "Valorant" in merged["games"]  # accumulation, as designed

    for op in history:
        replay = ProfileUpdate(**op)
        merged, _ = apply_profile_updates(merged, [replay], replay.evidence)

    assert merged["games"] == ["Cyberpunk 2077"]


def test_clear_uses_the_fields_own_empty_value():
    msg = "forget the games list and the notes, and budget is no longer a concern"
    updates = [
        ProfileUpdate(field="games", operation="clear", evidence=msg),
        ProfileUpdate(field="notes", operation="clear", evidence=msg),
        ProfileUpdate(field="stated_budget_usd", operation="clear", evidence=msg),
    ]

    result, _ = apply_profile_updates(
        _profile(notes="quiet please", stated_budget_usd=2000), updates, msg
    )

    assert result["games"] == []
    assert result["notes"] == ""
    assert result["stated_budget_usd"] is None


def test_quote_matching_is_case_insensitive_but_must_be_verbatim():
    msg = "I NO LONGER care about case size"
    ok = ProfileUpdate(
        field="form_factor",
        operation="clear",
        evidence="i no longer care about case size",
    )
    paraphrased = ProfileUpdate(
        field="form_factor", operation="clear", evidence="case size doesn't matter"
    )

    assert apply_profile_updates(_profile(), [ok], msg)[0]["form_factor"] is None
    assert (
        apply_profile_updates(_profile(), [paraphrased], msg)[0]["form_factor"]
        == "mini_itx"
    )


def test_only_retractions_are_replayed_from_history():
    """A recorded `set` must not be replayed: merge_profile already carries the
    value forward, and replaying it would let turn 1's budget overwrite a
    newer figure the extractor found but did not report as an operation."""
    from app.services.graph.state import replay_retractions

    history = [
        {
            "field": "stated_budget_usd",
            "operation": "set",
            "value": 2000,
            "evidence": "budget is $2000",
            "message_index": 0,
        },
        {
            "field": "games",
            "operation": "remove",
            "value": "Valorant",
            "evidence": "I don't play Valorant anymore",
            "message_index": 1,
        },
        {
            "field": "form_factor",
            "operation": "clear",
            "value": None,
            "evidence": "I no longer care about case size",
            "message_index": 1,
        },
    ]
    merged = _profile(stated_budget_usd=3000, games=["Cyberpunk 2077", "Valorant"])

    result = replay_retractions(merged, history)

    assert result["stated_budget_usd"] == 3000
    assert result["games"] == ["Cyberpunk 2077"]
    assert result["form_factor"] is None
