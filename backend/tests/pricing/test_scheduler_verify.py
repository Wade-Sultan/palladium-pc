"""verify_product: is the product a binding returns still this part?

Google merges and splits catalog ids, so a confirmed binding can start
returning a different product. Each offers fetch checks the title before the
price is trusted; a mismatch marks the binding stale (scheduler.fetch_target).
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest

from app.services.pricing_etl.scheduler import verify_product


def _part(name, manufacturer, part_type="cpu"):
    return SimpleNamespace(
        id=uuid.uuid4(),
        name=name,
        manufacturer=manufacturer,
        part_type=part_type,
        msrp_cents=None,
        street_price_cents=None,
        model_number=None,
    )


CPU = _part("Ryzen 7 7800X3D", "AMD")


def test_the_bound_product_passes():
    assert verify_product(CPU, "AMD Ryzen 7 7800X3D 8-Core Processor") is None


@pytest.mark.parametrize(
    ("title", "reason"),
    [
        ("AMD Ryzen 7 9800X3D 8-Core Processor", "model_mismatch"),
        ("CyberPowerPC Gaming Desktop AMD Ryzen 7 7800X3D RTX 5070", "whole_system"),
        ("AMD Ryzen 7 7800X3D + B650 Motherboard Bundle", "bundle"),
    ],
)
def test_a_different_product_is_caught(title, reason):
    assert verify_product(CPU, title) == reason


def test_a_part_without_a_model_scheme_is_checked_by_coverage():
    case = _part("North", "Fractal Design", "case")
    assert verify_product(case, "Fractal Design North ATX Mid Tower Case") is None
    assert (
        verify_product(case, "Lian Li O11 Dynamic EVO Mid Tower Case") == "low_coverage"
    )


def test_no_title_is_not_a_mismatch():
    assert verify_product(CPU, None) is None
    assert verify_product(CPU, "") is None
