"""The offer parser over real SerpApi captures, when they exist locally.

Real responses are never committed (see .gitignore). Anyone holding captures
in <repo>/.local-seed/serpapi/ gets these run against them; CI and a fresh
clone skip. The assertions are invariants every google_product response must
satisfy, not figures from one file, so new captures can be dropped in as they
are taken (especially the first real coupon, membership or used offer, which
is what the parser's untested rules are waiting on).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services.pricing_etl import offers as o

_CAPTURES = Path(__file__).resolve().parents[3] / ".local-seed" / "serpapi"
_PRODUCT_FILES = sorted(_CAPTURES.glob("google_product_*.json"))

pytestmark = pytest.mark.skipif(
    not _PRODUCT_FILES, reason=f"no real captures in {_CAPTURES}"
)
_RULES = [
    ("costco", "membership"),
    ("sam's club", "membership"),
    ("bj's", "membership"),
]


@pytest.fixture(params=_PRODUCT_FILES, ids=lambda p: p.name)
def capture(request):
    return json.loads(request.param.read_bytes())


def test_every_store_becomes_an_offer(capture):
    stores = capture["product_results"].get("stores") or []
    parsed = o.parse_product_response(capture, _RULES)
    assert len(parsed.offers) == len(stores)


def test_every_offer_has_a_positive_pre_tax_price(capture):
    for offer in o.parse_product_response(capture, _RULES).offers:
        assert offer.price_cents and offer.price_cents > 0
        if offer.details.get("additional_costs") is not None:
            assert "+tax" in offer.details["additional_costs"]


def test_the_estimate_is_explained(capture):
    parsed = o.parse_product_response(capture, _RULES)
    assert parsed.estimate_method
    if parsed.estimate_cents is not None:
        used = sorted(x.price_cents for x in parsed.offers if x.included)
        assert used[0] <= parsed.estimate_cents <= used[-1] or (
            parsed.estimate_method == "single_in_band"
        )


def test_no_history_row_is_silently_dropped(capture):
    insights = capture["product_results"].get("price_insights") or {}
    raw_keys = {
        (s["name"], p["date"])
        for s in insights.get("stores") or []
        for p in s.get("prices") or []
    }
    assert len(o.parse_product_response(capture, _RULES).history) == len(raw_keys)


def test_a_band_when_google_gives_one(capture):
    if capture["product_results"].get("price_range"):
        assert o.parse_product_response(capture, _RULES).band is not None
