#!/usr/bin/env bash
# Verifies pre-selected ("locked") parts against the REAL local catalog.
#
# WHY THIS IS NOT mk-smoke.sh. That script drives a chat turn end to end with
# stub LMs, which is the right harness for the dispatch path but the wrong one
# here: the stub answers a DSPy signature by parsing its declared output fields,
# so the profile extractor under a stub never produces the locked_parts entry
# this feature keys on. There is nothing to smoke-test through the front door
# without spending real LLM money on extraction.
#
# What is testable locally, and is what actually carries the risk, is
# everything downstream of extraction: does a named part resolve against a real
# catalog, does it get priced, is it refused when it would eat the budget, does
# the budget allocator take it out of the pot, and does the step really skip its
# model call. None of that needs an LLM, because a locked step skips the LLM by
# definition. So this runs the machinery in-cluster against the seeded Postgres.
#
#   ./scripts/mk-verify-locked-parts.sh
#
# Requires the stack to be up (`tilt up`).
#
# KNOWN LOCAL GAP, reported rather than skipped silently: the overspec refusal
# reads absolute performance floors published by game_performance_profiles, and
# the local seed has none (nor any embeddings to match titles with). That path
# is unit-tested in backend/tests/recommender/test_locked_parts.py and is
# reported UNVERIFIED here, because a local pass would prove only that the
# catalog is empty.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

POD="${PALLADIUM_BUILDER_POD:-deploy/builder}"

printf '\n== Verifying locked parts against the in-cluster catalog\n'
kubectl exec -i "$POD" -- python - <<'PYEOF'
import asyncio
import sys

from app.core.db import AsyncSessionLocal
from app.schemas.chat import BuildRequest, LockedPart, UserPreferences
from app.services.recommender import dspy_pipeline as dp
from app.services.recommender import locked_parts as lp

FAILED = 0


def check(ok, label, detail=""):
    global FAILED
    if ok:
        print(f"  \033[32mPASS\033[0m  {label}")
    else:
        FAILED = 1
        print(f"  \033[31mFAIL\033[0m  {label} {detail}", file=sys.stderr)


def warn(label):
    print(f"  \033[33mWARN\033[0m  {label}")


def request(*locks, budget):
    return BuildRequest(
        use_cases=["gaming"],
        budget_usd=budget,
        preferences=UserPreferences(),
        locked_parts=list(locks),
    )


async def main():
    async with AsyncSessionLocal() as db:
        # -- 1. A real chipset name resolves and prices from the catalog ------
        big = request(LockedPart(role="gpu", name="RTX 5090"), budget=8000)
        locked = await lp.resolve(db, big, dp._allocate_budget(8000, ["gaming"]))
        gpu = locked.get("gpu", {})
        check(gpu.get("group_name") == "RTX 5090", "a named chipset resolves",
              f"got {gpu.get('group_name')!r}")
        check(bool(gpu.get("price_usd")), "the locked part is priced",
              f"got {gpu.get('price_usd')!r}")
        check(gpu.get("honored") is True,
              "an affordable card is honoured", f"override={gpu.get('override')!r}")
        check(gpu.get("pinned_exact") is False,
              "naming a chipset leaves the board open")
        print(f"         resolved to {gpu.get('exact_name')} at ${gpu.get('price_usd')}")

        # -- 2. The same card on a budget it would swallow --------------------
        small = request(LockedPart(role="gpu", name="RTX 5090"), budget=1500)
        locked = await lp.resolve(db, small, dp._allocate_budget(1500, ["gaming"]))
        check(locked["gpu"].get("override") == "unaffordable",
              "a card that eats the budget is refused",
              f"override={locked['gpu'].get('override')!r}")

        # -- 3. ...unless the user already owns it ----------------------------
        owned = request(
            LockedPart(role="gpu", name="RTX 5090", owned=True), budget=1500
        )
        locked = await lp.resolve(db, owned, dp._allocate_budget(1500, ["gaming"]))
        check(locked["gpu"].get("honored") is True,
              "a card the user already owns is never unaffordable",
              f"override={locked['gpu'].get('override')!r}")
        check(lp.slot_costs(locked) == {"gpu": 0},
              "owned hardware costs the build nothing")

        # -- 4. The budget the rest of the build is sized against -------------
        plain = dp._allocate_budget(8000, ["gaming"])
        with_lock = dp._allocate_budget(8000, ["gaming"], {"gpu": 4499})
        check(with_lock["cpu"] < plain["cpu"],
              "a bought card shrinks the other slots",
              f"{with_lock['cpu']} vs {plain['cpu']}")
        with_owned = dp._allocate_budget(8000, ["gaming"], {"gpu": 0})
        check(with_owned["cpu"] == plain["cpu"],
              "an owned card leaves the other slots whole")

        # -- 5. The step gate itself ------------------------------------------
        state = dp.DSPyBuildState(request=big, locked=locked, mobo_pcie_x16_slots=1)
        result = dp._locked_result(
            state, None, dp.load_gpu(), role="gpu", output_field="gpu_chipset",
            extra_outputs={"gpu_count": 1, "gpu_required": True},
        )
        check(result is not None and result.gpu_chipset == "RTX 5090",
              "the GPU step resolves from the lock with no model call")

        # -- 6. A part the catalog does not carry -----------------------------
        unknown = request(
            LockedPart(role="gpu", name="GeForce Vortex 9990 XTX"), budget=8000
        )
        locked = await lp.resolve(db, unknown, dp._allocate_budget(8000, ["gaming"]))
        check(locked["gpu"].get("override") == "unresolved",
              "an unknown part falls back to choosing the slot normally",
              f"override={locked['gpu'].get('override')!r}")

    # -- 7. The headline scenario: a light game on a heavy card ---------------
    #
    # The local seed carries no games and no embeddings, so the absolute floors
    # this refusal reads do not exist here. Rather than skip the one case the
    # feature was asked for, the profile is seeded INSIDE A TRANSACTION THAT IS
    # ROLLED BACK. The check runs against real catalog GPUs and real pricing,
    # and the cluster is left exactly as it was found.
    await _overspec_scenario()

    return FAILED


async def _overspec_scenario():
    import uuid

    from app.models.games_catalog import Game, GamePerformanceProfile
    from app.services.recommender.dspy_pipeline import (
        _attach_catalog_floors,
        _resolve_catalog_requirements,
    )

    # $6,000 is chosen, not arbitrary. Below roughly $6,000 a $4,500 card is
    # refused as unaffordable before appropriateness is ever consulted, and
    # above roughly $6,700 its excess no longer exceeds the GPU slot. This is
    # the band where overspec is the binding refusal, which is the one under
    # test.
    budget = 6000
    title = f"Locked Part Probe {uuid.uuid4().hex[:8]}"

    async with AsyncSessionLocal() as db:
        try:
            game = Game(title=title, slug=title.lower().replace(" ", "-"))
            db.add(game)
            await db.flush()
            db.add(
                GamePerformanceProfile(
                    game_id=game.id,
                    resolution="1080p",
                    target_fps=144,
                    quality_preset="high",
                    ray_tracing_mode="off",
                    upscaling_mode="native",
                    # A floor low enough that every modern card clears it. The
                    # refusal under test is about money, not capability. An
                    # insufficient card would be refused by a different branch.
                    min_vram_gb=8,
                    derivation_method="synthetic_probe",
                    confidence=0.9,
                )
            )
            await db.flush()
        except Exception as exc:
            await db.rollback()
            warn(
                "overspec refusal UNVERIFIED: could not seed a performance "
                f"profile in this cluster ({type(exc).__name__}). Covered by "
                "backend/tests/recommender/test_locked_parts.py"
            )
            return

        try:
            req = BuildRequest(
                use_cases=["gaming"],
                budget_usd=budget,
                preferences=UserPreferences(),
                answers={"gaming.resolution": "1080p", "gaming.games": [title]},
                locked_parts=[LockedPart(role="gpu", name="RTX 5090")],
            )
            requirements = await _resolve_catalog_requirements(db, req)
            if requirements is None or not requirements.matched_names:
                warn(
                    "overspec refusal UNVERIFIED: the seeded title did not match, "
                    "so no floors reached the check"
                )
                return
            _attach_catalog_floors(req, requirements)

            locked = await lp.resolve(
                db, req, dp._allocate_budget(budget, ["gaming"]), requirements
            )
            gpu = locked.get("gpu", {})
            check(
                gpu.get("override") == "overspec",
                "a light 1080p workload refuses a flagship card as overspec",
                f"override={gpu.get('override')!r} reason={gpu.get('reason')!r}",
            )
            check(
                gpu.get("honored") is False,
                "the refused lock leaves the GPU step to run",
            )
            print(f"         {gpu.get('reason')}")
        finally:
            # Always. The catalog is left exactly as it was found.
            await db.rollback()


sys.exit(asyncio.run(main()))
PYEOF

printf '\n\033[32mLocked-part verification passed.\033[0m\n'
