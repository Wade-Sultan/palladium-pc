"""Projected game floors are enforced up to the budget.

See app/services/recommender/projected_floors.py for the rule and why it
differs from the ordinary (advisory) benchmark floors.
"""

from app.services.recommender.projected_floors import (
    apply_projected_floors,
    projected_answers,
)


def _gpu(name, *, timespy=None, vram=16, rt=True):
    scores = {} if timespy is None else {"timespy": timespy}
    return {
        "chipset": name,
        "vram_gb": vram,
        "has_ray_tracing": rt,
        "street_price_usd": 500,
        "benchmark_scores": scores,
    }


def _answers(**floors):
    return projected_answers(floors)


def test_answers_carry_projected_floors_under_their_own_prefix():
    answers = projected_answers({"min_gpu_raster_score": 20000.0, "min_vram_gb": 12})
    assert answers == {
        "requirements.projected.min_gpu_raster_score": "20000.0",
        "requirements.projected.min_vram_gb": "12",
    }


def test_candidates_that_miss_are_removed_when_one_clears():
    rows = [_gpu("slow", timespy=15000), _gpu("fast", timespy=22000)]
    kept = apply_projected_floors(
        rows, "gpu", _answers(min_gpu_raster_score=20000.0)
    )
    assert [r["chipset"] for r in kept] == ["fast"]


def test_unverified_candidates_are_removed_when_one_clears():
    rows = [_gpu("unmeasured"), _gpu("fast", timespy=22000)]
    kept = apply_projected_floors(
        rows, "gpu", _answers(min_gpu_raster_score=20000.0)
    )
    assert [r["chipset"] for r in kept] == ["fast"]


def test_the_set_passes_through_when_the_budget_reaches_nothing_that_clears():
    rows = [_gpu("slow", timespy=15000), _gpu("unmeasured")]
    kept = apply_projected_floors(
        rows, "gpu", _answers(min_gpu_raster_score=20000.0)
    )
    assert kept == rows


def test_a_projected_vram_floor_filters_like_a_benchmark_floor():
    rows = [_gpu("small", timespy=25000, vram=8), _gpu("big", timespy=25000)]
    kept = apply_projected_floors(rows, "gpu", _answers(min_vram_gb=12))
    assert [r["chipset"] for r in kept] == ["big"]


def test_ordinary_floors_are_not_enforced_here():
    rows = [_gpu("slow", timespy=15000), _gpu("fast", timespy=22000)]
    answers = {"requirements.gpu_raster_score": "20000"}
    assert apply_projected_floors(rows, "gpu", answers) == rows


def test_gpu_only_floors_leave_the_cpu_set_alone():
    rows = [
        {"name": "a", "benchmark_scores": {"geekbench_6_single": 2000}},
        {"name": "b", "benchmark_scores": {}},
    ]
    kept = apply_projected_floors(
        rows, "cpu", _answers(min_gpu_raster_score=20000.0)
    )
    assert kept == rows


def test_cpu_floors_filter_the_cpu_set():
    rows = [
        {"name": "a", "benchmark_scores": {"geekbench_6_single": 2000}},
        {"name": "b", "benchmark_scores": {"geekbench_6_single": 3200}},
    ]
    kept = apply_projected_floors(
        rows, "cpu", _answers(min_cpu_single_score=3000.0)
    )
    assert [r["name"] for r in kept] == ["b"]
