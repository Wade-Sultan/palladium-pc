"""Parts the user brought to the build: honouring them, and refusing to.

THE CLAIM UNDER TEST, in one line: a pre-selected part replaces its step's LLM
call when we can verify it, and never when we cannot.

Two halves, and the second is the one that matters. Honouring a lock is easy to
get right and cheap to get wrong in only one direction. Refusing one acts
AGAINST what the user asked for, so every refusal path here also has a
companion test proving the same code honours the lock when the evidence for
refusing is missing rather than merely negative — an absent performance floor,
an unpriced part, a check that raised. Silently shipping a different graphics
card than the one somebody asked for, on the strength of a measurement we never
took, is the worst failure this feature can produce.

The DB and LLM layers are mocked throughout, same as test_pipeline_steps.py.
"""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest

from app.schemas.chat import (
    NO_BUDGET_CEILING,
    BuildRequest,
    LockedPart,
    UserPreferences,
)
from app.services.recommender import dspy_pipeline as dp
from app.services.recommender import locked_parts as lp


# --- Helpers ------------------------------------------------------------------


def _request(*locks, budget=2000, use_cases=("gaming",)) -> BuildRequest:
    return BuildRequest(
        use_cases=list(use_cases),
        budget_usd=budget,
        preferences=UserPreferences(),
        locked_parts=list(locks),
    )


def _lock(**overrides) -> dict:
    base = {
        "role": "gpu",
        "stated": "RTX 5090",
        "owned": False,
        "quantity": 1,
        "group_name": "RTX 5090",
        "exact_name": "ASUS TUF RTX 5090",
        "pinned_exact": False,
        "price_usd": 2000,
        "honored": True,
        "override": None,
        "reason": "You asked for it.",
    }
    base.update(overrides)
    return base


def _natural_budget(budget=2000, use_cases=("gaming",)) -> dict:
    return dp._allocate_budget(budget, list(use_cases))


class _FakeSession:
    """Stands in for AsyncSession. Only `get` is ever reached here, because
    every catalog entry point the module uses is monkeypatched per test."""

    def __init__(self, rows=None):
        self._rows = rows or {}

    async def get(self, model, key):
        return self._rows.get(key)


def _patch_find_part(monkeypatch, result):
    """Point discussion.find_part at a canned answer (or an exception)."""
    import app.services.recommender.discussion as discussion

    async def _fake(db, query, category):
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr(discussion, "find_part", _fake)


def _patch_part_lookup(monkeypatch, part, price_cents=200000, group_name=None):
    async def _get_part_by_id(db, part_id):
        return part

    async def _price(db, p):
        return price_cents

    async def _group(session, p):
        return group_name

    monkeypatch.setattr(lp.crud_components, "get_part_by_id", _get_part_by_id)
    monkeypatch.setattr(lp.crud_components, "resolve_part_price_cents", _price)
    monkeypatch.setattr(lp, "_group_name", _group)


def _patch_gpu_candidates(monkeypatch, rows):
    import app.services.recommender.db.queries as queries

    async def _fake(*args, **kwargs):
        return json.dumps(rows)

    monkeypatch.setattr(queries, "get_gpu_chipset_candidates", _fake)


# A candidate set with a wide price spread, all of which clear the floor. This
# is the shape that makes an expensive lock look wasteful.
def _gpu_rows(locked_price=2000, meets=True):
    return [
        {
            "chipset": "RTX 5090",
            "vram_gb": 32,
            "street_price_usd": locked_price,
            "meets_performance_profile": meets,
            "perf_score": 1.0,
        },
        {
            "chipset": "RTX 5060",
            "vram_gb": 12,
            "street_price_usd": 300,
            "meets_performance_profile": True,
            "perf_score": 0.3,
        },
    ]


# --- Budget allocation --------------------------------------------------------


def test_a_part_the_user_owns_frees_its_whole_slot():
    """Owned hardware costs this build nothing, so the money its slot was
    holding has to reach the slots that are still being bought."""
    plain = dp._allocate_budget(2000, ["gaming"])
    locked = dp._allocate_budget(2000, ["gaming"], {"gpu": 0})

    assert locked["gpu"] == 0
    # Nothing left the pot, so every other slot keeps its full share.
    assert locked["cpu"] == plain["cpu"]
    assert locked["ram"] == plain["ram"]


def test_a_part_the_user_is_buying_shrinks_every_other_slot():
    """The defining bug this prevents: sizing the CPU against money that a
    locked graphics card has already spent."""
    plain = dp._allocate_budget(2000, ["gaming"])
    locked = dp._allocate_budget(2000, ["gaming"], {"gpu": 1500})

    assert locked["gpu"] == 1500
    # $500 of $2000 survives, so the remaining ceilings are a quarter of what
    # they were.
    assert locked["cpu"] == pytest.approx(plain["cpu"] * 0.25, abs=2)
    assert locked["storage"] == pytest.approx(plain["storage"] * 0.25, abs=2)


def test_locked_slots_keep_their_relative_shares():
    """Scaled, not renormalized. The ceilings deliberately do not sum to 1.0,
    and dividing the survivors by their own total would inflate them."""
    locked = dp._allocate_budget(2000, ["gaming"], {"gpu": 1000})
    plain = dp._allocate_budget(2000, ["gaming"])

    assert locked["cpu"] / locked["ram"] == pytest.approx(
        plain["cpu"] / plain["ram"], rel=0.02
    )


def test_an_unlimited_budget_ignores_locked_costs_entirely():
    """There is no total to take a share of, so there is nothing to subtract."""
    allocation = dp._allocate_budget(NO_BUDGET_CEILING, ["gaming"], {"gpu": 2000})
    assert set(allocation.values()) == {NO_BUDGET_CEILING}


def test_locks_that_were_overridden_take_nothing_out_of_the_budget():
    costs = lp.slot_costs(
        {
            "gpu": _lock(honored=False, override="overspec"),
            "cpu": _lock(role="cpu", price_usd=400),
        }
    )
    assert costs == {"cpu": 400}


def test_owned_parts_cost_nothing_but_still_claim_their_slot():
    costs = lp.slot_costs({"gpu": _lock(owned=True, price_usd=2000)})
    assert costs == {"gpu": 0}


def test_quantity_multiplies_a_locked_cost():
    costs = lp.slot_costs({"gpu": _lock(price_usd=1000, quantity=2)})
    assert costs == {"gpu": 2000}


# --- Resolution ---------------------------------------------------------------


def test_a_part_the_catalog_does_not_carry_is_not_honoured(monkeypatch):
    _patch_find_part(monkeypatch, None)
    locked = asyncio.run(
        lp.resolve(
            _FakeSession(),
            _request(LockedPart(role="gpu", name="RTX 9090 Ti Super")),
            _natural_budget(),
        )
    )
    assert locked["gpu"]["honored"] is False
    assert locked["gpu"]["override"] == "unresolved"


def test_a_lookup_that_raises_does_not_take_the_build_down(monkeypatch):
    _patch_find_part(monkeypatch, RuntimeError("catalog is on fire"))
    locked = asyncio.run(
        lp.resolve(
            _FakeSession(),
            _request(LockedPart(role="gpu", name="RTX 5090")),
            _natural_budget(),
        )
    )
    assert locked["gpu"]["override"] == "unresolved"


def test_naming_a_chipset_leaves_the_board_open(monkeypatch):
    """ "RTX 5090" is a chipset, so the later fit resolver still gets to choose
    which board. "ASUS TUF RTX 5090" is not, and pins it."""
    _patch_find_part(monkeypatch, {"part_id": "0" * 32})
    _patch_part_lookup(
        monkeypatch,
        SimpleNamespace(name="ASUS TUF RTX 5090", part_type="gpu"),
        group_name="RTX 5090",
    )
    monkeypatch.setattr(lp, "_JUDGES", {})

    locked = asyncio.run(
        lp.resolve(
            _FakeSession(),
            _request(LockedPart(role="gpu", name="RTX 5090")),
            _natural_budget(),
        )
    )
    assert locked["gpu"]["pinned_exact"] is False
    assert locked["gpu"]["group_name"] == "RTX 5090"


def test_naming_a_specific_board_pins_it(monkeypatch):
    _patch_find_part(monkeypatch, {"part_id": "0" * 32})
    _patch_part_lookup(
        monkeypatch,
        SimpleNamespace(name="ASUS TUF RTX 5090", part_type="gpu"),
        group_name="RTX 5090",
    )
    monkeypatch.setattr(lp, "_JUDGES", {})

    locked = asyncio.run(
        lp.resolve(
            _FakeSession(),
            _request(LockedPart(role="gpu", name="ASUS TUF RTX 5090")),
            _natural_budget(),
        )
    )
    assert locked["gpu"]["pinned_exact"] is True


# --- Refusal: unaffordable ----------------------------------------------------


def test_a_part_that_eats_the_whole_budget_is_refused(monkeypatch):
    _patch_find_part(monkeypatch, {"part_id": "0" * 32})
    _patch_part_lookup(
        monkeypatch,
        SimpleNamespace(name="RTX 5090", part_type="gpu"),
        price_cents=190000,
        group_name="RTX 5090",
    )
    monkeypatch.setattr(lp, "_JUDGES", {})

    locked = asyncio.run(
        lp.resolve(
            _FakeSession(),
            _request(LockedPart(role="gpu", name="RTX 5090"), budget=2000),
            _natural_budget(),
        )
    )
    assert locked["gpu"]["override"] == "unaffordable"


def test_a_part_the_user_already_owns_is_never_unaffordable(monkeypatch):
    """The whole point of the owned flag: hardware on the desk cannot price
    the user out of the machine they are building around it."""
    _patch_find_part(monkeypatch, {"part_id": "0" * 32})
    _patch_part_lookup(
        monkeypatch,
        SimpleNamespace(name="RTX 5090", part_type="gpu"),
        price_cents=190000,
        group_name="RTX 5090",
    )
    monkeypatch.setattr(lp, "_JUDGES", {})

    locked = asyncio.run(
        lp.resolve(
            _FakeSession(),
            _request(LockedPart(role="gpu", name="RTX 5090", owned=True), budget=2000),
            _natural_budget(),
        )
    )
    assert locked["gpu"]["honored"] is True


def test_an_unlimited_budget_makes_nothing_unaffordable(monkeypatch):
    _patch_find_part(monkeypatch, {"part_id": "0" * 32})
    _patch_part_lookup(
        monkeypatch,
        SimpleNamespace(name="RTX 5090", part_type="gpu"),
        price_cents=1500000,
        group_name="RTX 5090",
    )
    monkeypatch.setattr(lp, "_JUDGES", {})

    locked = asyncio.run(
        lp.resolve(
            _FakeSession(),
            _request(LockedPart(role="gpu", name="RTX 5090"), budget=NO_BUDGET_CEILING),
            _natural_budget(NO_BUDGET_CEILING),
        )
    )
    assert locked["gpu"]["honored"] is True


# --- Refusal: insufficient and overspec ---------------------------------------


def test_a_card_that_misses_the_measured_floor_is_refused(monkeypatch):
    _patch_gpu_candidates(monkeypatch, _gpu_rows(locked_price=400, meets=False))
    lock = lp.Lock(role="gpu", stated="RTX 5090", group_name="RTX 5090")
    asyncio.run(lp._judge_gpu(_FakeSession(), lock, _request(), {"gpu": 1000}, None))
    assert lock.override == "insufficient"


def test_a_wildly_overspecced_card_is_refused_when_floors_are_known(monkeypatch):
    """Rainbow Six at 1080p on a 5090: it clears the floor, and the money above
    the cheapest card that also clears it exceeds the whole GPU slot."""
    _patch_gpu_candidates(monkeypatch, _gpu_rows(locked_price=2000))
    requirements = SimpleNamespace(min_vram_gb=8, matched_names=["Rainbow Six Siege"])
    lock = lp.Lock(role="gpu", stated="RTX 5090", group_name="RTX 5090")

    asyncio.run(
        lp._judge_gpu(_FakeSession(), lock, _request(), {"gpu": 1000}, requirements)
    )
    assert lock.override == "overspec"
    assert "RTX 5060" in lock.reason


def test_the_same_card_is_honoured_when_no_floor_was_resolved(monkeypatch):
    """THE MOST IMPORTANT TEST HERE. With no floors, "cheapest sufficient" is
    just "cheapest", and every good part scores as waste. Acting on that would
    override a user on the strength of a measurement we never took."""
    _patch_gpu_candidates(monkeypatch, _gpu_rows(locked_price=2000))
    lock = lp.Lock(role="gpu", stated="RTX 5090", group_name="RTX 5090")

    asyncio.run(lp._judge_gpu(_FakeSession(), lock, _request(), {"gpu": 1000}, None))
    assert lock.override is None


def test_an_overspecced_card_is_honoured_when_the_user_set_no_budget(monkeypatch):
    """Someone who said cost is not a constraint cannot be told they overspent."""
    _patch_gpu_candidates(monkeypatch, _gpu_rows(locked_price=2000))
    requirements = SimpleNamespace(min_vram_gb=8, matched_names=["Rainbow Six Siege"])
    lock = lp.Lock(role="gpu", stated="RTX 5090", group_name="RTX 5090")

    asyncio.run(
        lp._judge_gpu(
            _FakeSession(),
            lock,
            _request(budget=NO_BUDGET_CEILING),
            {"gpu": NO_BUDGET_CEILING},
            requirements,
        )
    )
    assert lock.override is None


def test_a_card_missing_from_the_candidate_set_is_left_alone(monkeypatch):
    _patch_gpu_candidates(monkeypatch, _gpu_rows())
    lock = lp.Lock(role="gpu", stated="Arc B990", group_name="Arc B990")
    asyncio.run(lp._judge_gpu(_FakeSession(), lock, _request(), {"gpu": 1000}, None))
    assert lock.override is None


def test_a_check_that_crashes_honours_the_lock(monkeypatch):
    """A refusal needs positive evidence. A crashed check produced none."""
    _patch_find_part(monkeypatch, {"part_id": "0" * 32})
    _patch_part_lookup(
        monkeypatch,
        SimpleNamespace(name="RTX 5090", part_type="gpu"),
        price_cents=50000,
        group_name="RTX 5090",
    )

    async def _boom(*args, **kwargs):
        raise RuntimeError("scoring exploded")

    monkeypatch.setattr(lp, "_JUDGES", {"gpu": _boom})

    locked = asyncio.run(
        lp.resolve(
            _FakeSession(),
            _request(LockedPart(role="gpu", name="RTX 5090")),
            _natural_budget(),
        )
    )
    assert locked["gpu"]["honored"] is True


# --- The step gate ------------------------------------------------------------


def _program(category="gpu"):
    return SimpleNamespace(
        category=category, signature_name="DecideGPU", signature_version=3
    )


def test_an_honoured_lock_produces_the_step_result_with_no_llm_call():
    state = dp.DSPyBuildState(request=_request(), locked={"gpu": _lock()})
    result = dp._locked_result(
        state,
        None,
        _program(),
        role="gpu",
        output_field="gpu_chipset",
        extra_outputs={"gpu_count": 1, "gpu_required": True},
    )
    assert result is not None
    assert result.gpu_chipset == "RTX 5090"
    assert result.gpu_required is True


def test_an_overridden_lock_leaves_the_step_to_run():
    state = dp.DSPyBuildState(
        request=_request(), locked={"gpu": _lock(honored=False, override="overspec")}
    )
    assert (
        dp._locked_result(
            state, None, _program(), role="gpu", output_field="gpu_chipset"
        )
        is None
    )


def test_multi_part_slots_are_never_gated():
    """Naming one drive means "include this", not "this is the whole answer",
    so storage still runs and decides whether a second drive is wanted."""
    state = dp.DSPyBuildState(
        request=_request(), locked={"storage": _lock(role="storage")}
    )
    assert (
        dp._locked_result(
            state,
            None,
            _program("storage"),
            role="storage",
            output_field="storage_groups",
        )
        is None
    )


def test_a_locked_step_is_still_recorded():
    """A missing decision row reads as a pipeline failure, so a skipped step
    has to leave the same trail a run one would."""
    recorded = []

    recorder = SimpleNamespace(
        record_deterministic_decision=lambda **kw: recorded.append(kw)
    )
    state = dp.DSPyBuildState(request=_request(), locked={"gpu": _lock()})
    dp._locked_result(
        state, recorder, _program(), role="gpu", output_field="gpu_chipset"
    )

    assert len(recorded) == 1
    assert recorded[0]["chosen_name"] == "RTX 5090"
    # None, not "[]": nothing was chosen from anything, and an empty list would
    # record as "we looked and found nothing available".
    assert recorded[0]["candidates_json"] is None


# --- Carrying locks across turns ----------------------------------------------


def test_locked_parts_accumulate_by_slot():
    from app.services.graph.state import merge_profile

    previous = {"locked_parts": [{"role": "gpu", "name": "RTX 5090"}]}
    current = {"locked_parts": [{"role": "cpu", "name": "9800X3D"}]}
    merged = merge_profile(previous, current)

    assert {e["role"] for e in merged["locked_parts"]} == {"gpu", "cpu"}


def test_naming_a_second_part_for_one_slot_replaces_the_first():
    """A change of mind, not a request for two."""
    from app.services.graph.state import merge_profile

    previous = {"locked_parts": [{"role": "gpu", "name": "RTX 5090"}]}
    current = {"locked_parts": [{"role": "gpu", "name": "RX 9070 XT"}]}
    merged = merge_profile(previous, current)

    assert merged["locked_parts"] == [{"role": "gpu", "name": "RX 9070 XT"}]


@pytest.mark.parametrize("target", ["gpu", "RTX 5090", "rtx 5090"])
def test_a_lock_can_be_retracted_by_slot_or_by_name(target):
    from app.services.graph.state import _drop_locked_part

    profile = {"locked_parts": [{"role": "gpu", "name": "RTX 5090"}]}
    assert _drop_locked_part(profile, target) == []


def test_retracting_something_that_was_never_locked_is_a_no_op():
    """Returning None keeps the operation out of profile_operations, where it
    would otherwise be replayed on every future turn forever."""
    from app.services.graph.state import _drop_locked_part

    profile = {"locked_parts": [{"role": "gpu", "name": "RTX 5090"}]}
    assert _drop_locked_part(profile, "case") is None


# --- What the remaining steps are told ----------------------------------------


def test_honoured_locks_are_stated_to_the_other_steps_as_fixed():
    text = lp.summary({"gpu": _lock()})
    assert "FIXED" in text
    assert "RTX 5090" in text or "ASUS TUF RTX 5090" in text


def test_a_refused_lock_is_named_so_no_step_re_proposes_it():
    text = lp.summary(
        {"gpu": _lock(honored=False, override="overspec", reason="Too much card.")}
    )
    assert "could not use" in text
    assert "Too much card." in text


def test_no_locks_means_no_added_prose():
    assert lp.summary({}) == ""


# --- The steps themselves -----------------------------------------------------
#
# The tests above prove the gate returns the right thing. These prove the steps
# are actually wired to it: that no LLM call happens, that no candidate query
# happens either, and that the state a locked step leaves behind is the same
# shape the LLM path would have left.


def _explode_if_called(monkeypatch, *names):
    """Make the LLM path and the candidate queries hard failures."""

    async def _boom(*args, **kwargs):
        raise AssertionError("a locked step reached the catalog or the model")

    for name in names:
        monkeypatch.setattr(dp, name, _boom)


def test_a_locked_gpu_skips_both_the_model_and_the_candidate_query(monkeypatch):
    """The candidate query matters as much as the LLM call. A locked slot's
    budget entry holds what the part cost, which for a part the user already
    owns is zero — querying candidates under a $0 ceiling returns nothing and
    _ensure_candidates would fail a perfectly buildable machine."""
    _explode_if_called(monkeypatch, "_run_step", "get_gpu_chipset_candidates")

    async def _variants(session, chipset):
        return [
            SimpleNamespace(
                chipset=SimpleNamespace(tdp_watts=575, recommended_psu_watts=1000)
            )
        ]

    monkeypatch.setattr(dp.crud_components, "get_gpus_for_chipset", _variants)

    state = dp.DSPyBuildState(
        request=_request(), locked={"gpu": _lock(owned=True)}, mobo_pcie_x16_slots=1
    )
    asyncio.run(dp._step_gpu(state, _FakeSession(), {"gpu": 0}, _program(), None))

    assert state.gpu_chipset == "RTX 5090"
    assert state.gpu_required is True
    assert state.gpu_count == 1
    # Sized for the PSU step exactly as the LLM path would have sized it.
    assert state.gpu_tdp_w == 575
    assert state.gpu_recommended_psu_w == 1000


def test_a_locked_gpu_count_is_still_clamped_to_the_board(monkeypatch):
    """The user asking for four cards does not conjure slots to put them in."""
    _explode_if_called(monkeypatch, "_run_step", "get_gpu_chipset_candidates")

    async def _variants(session, chipset):
        return []

    monkeypatch.setattr(dp.crud_components, "get_gpus_for_chipset", _variants)

    state = dp.DSPyBuildState(
        request=_request(),
        locked={"gpu": _lock(quantity=4)},
        mobo_pcie_x16_slots=2,
    )
    asyncio.run(dp._step_gpu(state, _FakeSession(), {"gpu": 0}, _program(), None))

    assert state.gpu_count == 2


def test_a_locked_cpu_still_loads_its_platform_facts(monkeypatch):
    """Skipping the model must not skip the catalog lookup that gives the
    following four steps a socket, a TDP and a memory generation."""
    _explode_if_called(monkeypatch, "_run_step", "get_cpu_candidates")

    async def _cpu(session, name):
        return SimpleNamespace(
            socket="AM5",
            tdp_watts=120,
            pcie_lanes=24,
            ddr_generation=["ddr5"],
        )

    monkeypatch.setattr(dp.crud_components, "get_cpu_by_name", _cpu)

    state = dp.DSPyBuildState(
        request=_request(),
        locked={"cpu": _lock(role="cpu", group_name="Ryzen 7 9800X3D")},
    )
    asyncio.run(dp._step_cpu(state, _FakeSession(), {"cpu": 0}, _program("cpu"), None))

    assert state.cpu_name == "Ryzen 7 9800X3D"
    assert state.cpu_socket == "AM5"
    assert state.cpu_tdp_w == 120
    assert state.cpu_ddr_gens == ["ddr5"]


def test_a_locked_case_becomes_the_only_option_and_still_pauses(monkeypatch):
    """The picker stays, so the whole resume path keeps working, but it is a
    one-click confirmation rather than a choice between three."""
    _explode_if_called(monkeypatch, "_run_step", "get_case_candidates")

    state = dp.DSPyBuildState(
        request=_request(),
        locked={"case": _lock(role="case", group_name="Fractal North")},
    )
    asyncio.run(
        dp._step_case(state, _FakeSession(), {"case": 0}, _program("case"), None)
    )

    assert [o["name"] for o in state.case_options] == ["Fractal North"]


def test_a_user_named_board_survives_the_fit_resolver(monkeypatch):
    """Overruling a board somebody named on clearance grounds would ship a
    different card than the one they asked for. The case and the supply were
    sized around this card, not the other way round."""
    wanted = SimpleNamespace(
        name="ASUS TUF RTX 5090",
        length_mm=9999,
        width_slots=4,
        chipset=SimpleNamespace(tdp_watts=575, recommended_psu_watts=1000),
    )
    other = SimpleNamespace(
        name="Gigabyte Windforce RTX 5090",
        length_mm=300,
        width_slots=2,
        chipset=SimpleNamespace(tdp_watts=575, recommended_psu_watts=1000),
    )

    async def _variants(session, chipset):
        return [other, wanted]

    monkeypatch.setattr(dp.crud_components, "get_gpus_for_chipset", _variants)

    state = dp.DSPyBuildState(
        request=_request(),
        locked={"gpu": _lock(pinned_exact=True)},
        gpu_chipset="RTX 5090",
        gpu_required=True,
        case_max_gpu_length_mm=300,
    )
    asyncio.run(dp._resolve_gpu_variant(state, _FakeSession()))

    assert state.gpu_name == "ASUS TUF RTX 5090"


def test_a_chipset_only_lock_lets_the_fit_resolver_choose(monkeypatch):
    """Naming "RTX 5090" expresses no view on which board, so clearance still
    decides — which is the whole reason pinned_exact exists."""
    too_long = SimpleNamespace(
        name="ASUS TUF RTX 5090",
        length_mm=9999,
        width_slots=2,
        chipset=SimpleNamespace(tdp_watts=575, recommended_psu_watts=1000),
    )
    fits = SimpleNamespace(
        name="Gigabyte Windforce RTX 5090",
        length_mm=300,
        width_slots=2,
        chipset=SimpleNamespace(tdp_watts=575, recommended_psu_watts=1000),
    )

    async def _variants(session, chipset):
        return [too_long, fits]

    async def _psu(session, name):
        return None

    monkeypatch.setattr(dp.crud_components, "get_gpus_for_chipset", _variants)
    monkeypatch.setattr(dp.crud_components, "get_psu_by_name", _psu)

    state = dp.DSPyBuildState(
        request=_request(),
        locked={"gpu": _lock(pinned_exact=False)},
        gpu_chipset="RTX 5090",
        gpu_required=True,
        case_max_gpu_length_mm=300,
    )
    asyncio.run(dp._resolve_gpu_variant(state, _FakeSession()))

    assert state.gpu_name == "Gigabyte Windforce RTX 5090"
