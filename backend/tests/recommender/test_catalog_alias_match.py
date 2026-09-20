"""
Unit tests for the exact name/alias tier of app.services.recommender.catalog_match.

The normalization is the part worth pinning down. Aliases are typed by hand in
the admin panel and by users in chat, and neither side will agree on case,
spacing or punctuation — "Rainbow 6", "rainbow6" and "RAINBOW-6" have to be one
key, or curating aliases becomes an exercise in guessing how a user will type.

The vector-search tier is not exercised here: it needs a live embedding API and
a populated pgvector table, and scripts/probe_catalog_match.py is the tool for
measuring it against real data.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace

from app.services.recommender.catalog_match import (
    CatalogRequirements,
    _apply_performance_profile,
    _normalize_term,
    _select_performance_profile,
)


def test_normalization_folds_case():
    assert _normalize_term("RAINBOW SIX") == _normalize_term("rainbow six")


def test_normalization_folds_spacing_and_punctuation():
    """The four ways a person writes the same name must be one key."""
    variants = ["Rainbow 6", "rainbow6", "RAINBOW-6", "rainbow_6"]
    normalized = {_normalize_term(v) for v in variants}
    assert len(normalized) == 1


def test_normalization_folds_surrounding_whitespace():
    assert _normalize_term("  R6  ") == _normalize_term("R6")


def test_normalization_folds_colons():
    """Sequel and subtitle punctuation is exactly where users diverge."""
    assert _normalize_term("Rainbow Six: Siege") == _normalize_term("Rainbow Six Siege")


def test_normalization_keeps_distinct_names_distinct():
    """Folding must not go so far that different titles collide."""
    assert _normalize_term("Valorant") != _normalize_term("Valheim")
    assert _normalize_term("R6") != _normalize_term("R7")


def test_empty_and_whitespace_terms_normalize_to_empty():
    """_match_by_alias short-circuits on these rather than matching a row whose
    alias list happens to contain an empty string."""
    assert _normalize_term("") == ""
    assert _normalize_term("   ") == ""


# --- What the summary tells the build steps -----------------------------------


def test_an_unmatched_model_is_reported_rather_than_dropped():
    """THE REGRESSION. A model absent from the catalog used to vanish entirely:
    is_empty was true, summary() returned "", and the GPU step was never told the
    user had named anything. It then sized a $15000 96GB card for a 31B model
    that fits a 24GB card at q4."""
    req = CatalogRequirements(unmatched_terms=["Gemma 4 31B"])

    assert not req.is_empty
    summary = req.summary()
    assert "Gemma 4 31B" in summary
    assert "NOT in our catalog" in summary


def test_an_unmatched_model_carries_the_quantization_arithmetic():
    """Naming the gap is not enough — the step needs the math to close it."""
    summary = CatalogRequirements(unmatched_terms=["Gemma 4 31B"]).summary()

    assert "bytes_per_weight" in summary
    assert "q4 = 0.5" in summary


def test_a_fully_empty_result_still_says_nothing():
    """No terms at all must stay silent; the primer is for named-but-unknown
    models, not for every build that mentioned no software."""
    assert CatalogRequirements().summary() == ""
    assert CatalogRequirements().is_empty


def test_matched_and_unmatched_terms_coexist_in_one_summary():
    req = CatalogRequirements(
        matched_names=["Llama 3.1 70B"],
        unmatched_terms=["Gemma 4 31B"],
        notes=["Llama 3.1 70B (inference at q4): needs 42GB VRAM"],
        min_vram_gb=42,
    )
    summary = req.summary()

    assert "Llama 3.1 70B" in summary
    assert "Gemma 4 31B" in summary
    assert "at least 42GB of VRAM" in summary


def _performance_profile(**overrides):
    values = {
        "id": uuid.uuid4(),
        "is_active": True,
        "game_version": "2.3",
        "resolution": "1440p",
        "target_fps": 60,
        "quality_preset": "high",
        "ray_tracing_mode": "off",
        "upscaling_mode": "native",
        "frame_generation": False,
        "min_gpu_raster_score": 16000.0,
        "min_gpu_rt_score": None,
        "min_gpu_modern_score": 3500.0,
        "min_cpu_single_score": 2400.0,
        "min_cpu_multi_score": None,
        "min_vram_gb": 8,
        "min_ram_gb": 16,
        "required_features": [],
        "confidence": 0.8,
        "sample_count": 4,
        "derivation_method": "review_aggregate",
        "source_urls": ["https://example.test/benchmark"],
        "notes": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_performance_profile_selection_prefers_requested_rt_scenario():
    raster = _performance_profile()
    ray = _performance_profile(
        ray_tracing_mode="high", min_gpu_rt_score=12000.0, upscaling_mode="quality"
    )

    selected, note = _select_performance_profile(
        [raster, ray],
        resolution="1440p",
        target_fps="60",
        quality_preset="high",
        ray_tracing="on",
        upscaling="quality",
        frame_generation="no",
    )

    assert selected is ray
    assert note is None


def test_performance_profile_selection_reports_approximation():
    selected, note = _select_performance_profile(
        [_performance_profile()],
        resolution="4k",
        target_fps="120",
        quality_preset="ultra",
        ray_tracing="off",
        upscaling="allowed",
        frame_generation="allowed",
    )

    assert selected is not None
    assert "requested 4k" in note
    assert "requested 120 FPS" in note


def test_performance_profile_becomes_numeric_catalog_floors():
    game = SimpleNamespace(title="Example Quest")
    profile = _performance_profile(ray_tracing_mode="high", min_gpu_rt_score=12000.0)
    requirements = CatalogRequirements(matched_names=[game.title])

    _apply_performance_profile(
        game, profile, None, requirements, requested_ray_tracing="on"
    )

    assert requirements.min_gpu_raster_score == 16000
    assert requirements.min_gpu_rt_score == 12000
    assert requirements.min_vram_gb == 8
    assert "ray_tracing" in requirements.required_features
    assert requirements.to_dict()["game_performance_profiles"][0]["game"] == game.title


def test_rt_profile_does_not_force_rt_when_the_user_requested_raster():
    game = SimpleNamespace(title="Example Quest")
    profile = _performance_profile(
        ray_tracing_mode="high",
        min_gpu_rt_score=12000.0,
        required_features=["ray_tracing"],
    )
    requirements = CatalogRequirements(matched_names=[game.title])

    _apply_performance_profile(
        game, profile, "only an RT profile is available", requirements
    )

    assert requirements.min_gpu_rt_score is None
    assert "ray_tracing" not in requirements.required_features
    assert requirements.min_gpu_raster_score == 16000


def test_profile_approximation_reports_upscaling_and_frame_generation():
    selected, note = _select_performance_profile(
        [_performance_profile(upscaling_mode="quality", frame_generation=True)],
        resolution="1440p",
        target_fps="60",
        quality_preset="high",
        ray_tracing="off",
        upscaling="native",
        frame_generation="no",
    )

    assert selected is not None
    assert "requested native upscaling" in note
    assert "requested frame generation no" in note
