"""The post-build part lookup's deterministic first step.

The planner writes what a person would say and the catalog stores what the
manufacturer prints, so before any vector search the lookup pulls the one
substring that identifies the part and matches on it. Candidates still pass
through exclusion_reason, so a loose token cannot hand back the wrong SKU.
"""

from __future__ import annotations

from app.services.recommender.discussion import _identity_token


def test_a_gpu_query_yields_its_model_number():
    assert _identity_token("NVIDIA RTX 5070") == "5070"
    assert _identity_token("rtx 5070 ti super") == "5070"
    assert _identity_token("Radeon RX 9070 XT") == "9070"


def test_a_cpu_query_yields_its_model_number():
    assert _identity_token("AMD Ryzen 7 9800X3D") == "9800"
    assert _identity_token("Intel Core i7-14700K") == "14700"


def test_a_query_without_any_identifier_yields_nothing():
    assert _identity_token("a quiet case") is None
    assert _identity_token("Samsung 990 Pro") == "990"
    assert _identity_token("") is None
