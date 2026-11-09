"""Binding discovery over real google_shopping captures, when present locally.

Skips without <repo>/.local-seed/serpapi/ (raw responses are never committed).
The 9800X3D capture is pinned by name because its lesson is specific: Google
returned 40 results and not one was the CPU, so the right answer is no binding.
Any other google_shopping capture gets the generic invariants.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest

from app.services.pricing_etl import binding_discovery as bd

_CAPTURES = Path(__file__).resolve().parents[3] / ".local-seed" / "serpapi"
_SHOPPING = sorted(_CAPTURES.glob("google_shopping_*.json"))
_9800X3D = _CAPTURES / "google_shopping_ryzen7_9800x3d_2026-10-21.json"

pytestmark = pytest.mark.skipif(
    not _SHOPPING, reason=f"no real captures in {_CAPTURES}"
)

_CPU_9800X3D = bd.PartRef(
    id=uuid.uuid4(),
    name="Ryzen 7 9800X3D",
    manufacturer="AMD",
    part_type="cpu",
    msrp_cents=47900,
    model_number="100-100001084WOF",
)


@pytest.mark.skipif(not _9800X3D.exists(), reason="9800X3D capture not present")
def test_the_real_9800x3d_search_yields_no_binding():
    result = bd.score_results(_CPU_9800X3D, json.loads(_9800X3D.read_bytes()))
    reasons = {c.title: c.rejected for c in result.rejected}

    assert result.decision == bd.DECISION_NONE
    assert len(result.rejected) == 40
    assert (
        reasons["ASUS ROG GM700 Gaming Desktop AMD Ryzen 7 9800X3D"] == "whole_system"
    )
    assert reasons["AMD Ryzen 7 7800X3D 8-Core Processor"] == "model_mismatch"


@pytest.mark.parametrize("path", _SHOPPING, ids=lambda p: p.name)
def test_every_result_is_either_rejected_with_a_reason_or_a_survivor(path):
    payload = json.loads(path.read_bytes())
    result = bd.score_results(_CPU_9800X3D, payload)
    n_results = len(payload.get("shopping_results") or [])
    survivor_appearances = n_results - len(result.rejected)

    assert all(c.rejected for c in result.rejected)
    assert survivor_appearances >= len(result.survivors)
