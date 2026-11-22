"""
projected_floors.py
===================
Enforces a projected game profile's floors "up to the budget" on the CPU and
GPU candidate sets.

WHAT A PROJECTED PROFILE IS. A `GamePerformanceProfile` whose
`derivation_method` is in `PROJECTED_DERIVATIONS`: an estimate for a title
that is not out on PC yet (console parity, an engine predecessor scaled).
catalog_match.py keeps those floors in `CatalogRequirements.projected_floors`
rather than raising the ordinary floors, and dspy_pipeline attaches them to
the request answers under `requirements.projected.*`.

THE RULE. For each step's candidate set (already capped by that slot's budget
ceiling):

  * if at least one candidate is *verified* to clear every projected floor,
    every other candidate is removed before the DSPy module sees the set;
  * if none is, the set passes through unchanged and the build carries a
    caveat from validation.check_game_performance_profiles instead.

WHY NOT THE ORDINARY TREATMENT. Ordinary benchmark floors are advisory: the
model is told to prefer a verified fit, and a shortfall is a caveat. For a
title someone is buying ahead of, under-building is the failure that matters,
and "prefer" lets the model take a cheaper card that misses the target when
the budget covered one that clears it. Ordinary VRAM floors go the other way,
a hard failure in validation, which is wrong for a guessed number. This module
is the middle: strict when the budget allows it, never a reason a build fails.

WHY UNVERIFIED CANDIDATES ARE DROPPED TOO. When something clears the floor, a
candidate with no benchmark data for the floor's suite is removed with the
ones that miss it. It might clear, but nothing says so, and the point of the
rule is that the model cannot land on a part that was never shown to meet the
target while one that was is affordable.

WHY THIS IS NOT IN scoring.py. Scoring never removes a candidate (its header
explains why), and this does. It runs *before* scoring, while rows still carry
`benchmark_scores`, so perf_score is normalized over the surviving set.

Locked parts are not filtered (queries pass `enforce_projected=False` for the
lock-judging path): an estimate does not override a part the user named. The
lock stands and validation's caveat says it may fall short.
"""

from __future__ import annotations

from collections.abc import Mapping

from app.services.recommender.scoring import _performance_fit

PROJECTED_PREFIX = "requirements.projected."

# CatalogRequirements floor attribute -> the answers key _performance_fit reads
# for the ordinary floor of the same kind. Reusing _performance_fit through a
# remapped answers dict keeps one definition of "clears a floor".
_FIT_KEYS = {
    "min_gpu_raster_score": "requirements.gpu_raster_score",
    "min_gpu_rt_score": "requirements.gpu_rt_score",
    "min_gpu_modern_score": "requirements.gpu_modern_score",
    "min_cpu_single_score": "requirements.cpu_single_score",
    "min_cpu_multi_score": "requirements.cpu_multi_score",
    "min_vram_gb": "requirements.min_vram_gb",
}


def projected_answers(projected_floors: Mapping[str, float]) -> dict[str, str]:
    """Answers entries carrying projected floors, as strings like the rest."""
    return {
        f"{PROJECTED_PREFIX}{attr}": str(value)
        for attr, value in projected_floors.items()
        if value is not None
    }


def _shadow_answers(answers: Mapping) -> dict[str, str]:
    shadow = {}
    for attr, fit_key in _FIT_KEYS.items():
        value = answers.get(f"{PROJECTED_PREFIX}{attr}")
        if value is not None:
            shadow[fit_key] = value
    return shadow


def apply_projected_floors(
    rows: list[dict], part_type: str, answers: Mapping | None
) -> list[dict]:
    """Return the rows the DSPy step may choose from. See the module header.

    Expects rows that still carry `benchmark_scores` (i.e. before
    scoring.score_candidates strips them).
    """
    shadow = _shadow_answers(answers or {})
    if not shadow or not rows:
        return rows

    clearing = []
    any_floor = False
    for row in rows:
        _, fit, _, has_floor = _performance_fit(
            row, row.get("benchmark_scores") or {}, part_type, shadow
        )
        any_floor = any_floor or has_floor
        if fit is True:
            clearing.append(row)

    # No floor applies to this part type (e.g. only GPU floors on the CPU
    # step), or the budget does not reach one: leave the set alone.
    if not any_floor or not clearing:
        return rows
    return clearing
