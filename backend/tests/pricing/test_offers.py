"""The offer parser, against the shape of a real google_product response.

The sample (serpapi_samples.py) is hand-written from the first live capture
(2026-10-21, AMD Ryzen 7 7800X3D, 3 stores); raw responses are not committed.
Tests that need a coupon, a membership price, a rebate or a used listing derive
them by editing one store, because no real example of those has been captured
yet. When one is, check these derived cases against it. The parser is run over
the real captures too, in test_offers_real_captures.py, when they are present.
"""

from __future__ import annotations

import copy
from datetime import date

import pytest

from app.services.pricing_etl import offers as o
from tests.pricing.serpapi_samples import product_7800x3d

_RULES = [
    ("costco", "membership"),
    ("sam's club", "membership"),
    ("bj's", "membership"),
]


@pytest.fixture
def real():
    return product_7800x3d()


def _variant(real, store_index, **changes):
    payload = copy.deepcopy(real)
    payload["product_results"]["stores"][store_index].update(changes)
    return payload


def _by_merchant(parsed):
    return {offer.merchant_name: offer for offer in parsed.offers}


# --- the real response ------------------------------------------------------------


def test_real_response_yields_three_new_offers_at_pre_tax_item_prices(real):
    parsed = o.parse_product_response(real, _RULES)
    stores = _by_merchant(parsed)

    assert parsed.product_title == "AMD Ryzen 7 7800X3D 8-Core Processor"
    assert set(stores) == {"Newegg.com", "Best Buy", "Walmart"}
    assert {m: s.price_cents for m, s in stores.items()} == {
        "Newegg.com": 38900,
        "Best Buy": 42000,
        "Walmart": 41599,
    }
    assert all(s.included and s.condition == "new" for s in stores.values())
    assert all(s.shipping_cents == 0 for s in stores.values())
    # +tax is what makes extracted_price pre-tax; keep the evidence on the row.
    assert all(s.details["additional_costs"] == "+tax" for s in stores.values())


def test_real_response_estimate_is_the_median_of_the_three(real):
    parsed = o.parse_product_response(real, _RULES)
    assert parsed.estimate_cents == 41599
    assert parsed.estimate_method == "median_of_3"
    assert parsed.n_used == 3


def test_a_sale_is_a_real_price_and_a_free_gift_is_only_a_flag(real):
    stores = _by_merchant(o.parse_product_response(real, _RULES))
    newegg = stores["Newegg.com"]

    assert newegg.included
    assert o.FLAG_SALE in newegg.flags  # $389 against a $449 original
    assert o.FLAG_GIFT in newegg.flags  # "Free ASRock Pro 850B Power Supply"
    assert o.FLAG_GIFT not in stores["Walmart"].flags  # only free delivery/returns


def test_real_band_is_parsed(real):
    assert o.parse_product_response(real, _RULES).band == (34900, 41600)


def test_real_history_has_every_store_change(real):
    history = o.parse_product_response(real, _RULES).history
    per_store = {}
    for point in history:
        per_store.setdefault(point.merchant_name, []).append(point)

    assert {m: len(p) for m, p in per_store.items()} == {
        "Newegg.com": 5,
        "Best Buy": 4,
        "Walmart": 4,
    }
    assert min(p.price_date for p in history) == date(2025, 10, 20)
    newegg_oct12 = [
        p for p in per_store["Newegg.com"] if p.price_date == date(2026, 10, 12)
    ]
    assert newegg_oct12[0].price_cents == 34800


# --- exclusions, derived from the real response ------------------------------------


def test_a_membership_merchant_is_excluded_and_the_rest_still_price(real):
    parsed = o.parse_product_response(_variant(real, 2, name="Costco"), _RULES)
    costco = _by_merchant(parsed)["Costco"]

    assert not costco.included
    assert costco.exclusion_reason == o.REASON_MEMBERSHIP_MERCHANT
    assert parsed.estimate_cents == 40450  # median of 389.00 and 420.00
    assert parsed.estimate_method == "median_of_2"


@pytest.mark.parametrize(
    ("changes", "condition"),
    [
        ({"title": "AMD Ryzen 7 7800X3D (Renewed)"}, "refurbished"),
        ({"title": "AMD Ryzen 7 7800X3D Refurbished"}, "refurbished"),
        ({"details_and_offers": ["Open box", "Free delivery"]}, "open_box"),
        ({"details_and_offers": ["Used - Like New"]}, "used"),
        ({"details_and_offers": ["Pre-owned"]}, "used"),
    ],
)
def test_anything_not_new_is_excluded(real, changes, condition):
    offer = o.parse_product_response(_variant(real, 1, **changes), _RULES).offers[1]
    assert not offer.included
    assert offer.condition == condition
    assert offer.exclusion_reason == o.REASON_NOT_NEW


@pytest.mark.parametrize(
    ("details", "reason"),
    [
        (["$379.99 with coupon"], o.REASON_COUPON_PRICE),
        (["Save $20 with code GAMER20"], o.REASON_COUPON_PRICE),
        (["Price after mail-in rebate"], o.REASON_REBATE_PRICE),
        (["Member price"], o.REASON_MEMBERSHIP_PRICE),
        (["With paid membership"], o.REASON_MEMBERSHIP_PRICE),
    ],
)
def test_a_price_that_depends_on_a_coupon_rebate_or_membership_is_excluded(
    real, details, reason
):
    offer = o.parse_product_response(
        _variant(real, 1, details_and_offers=details), _RULES
    ).offers[1]
    assert not offer.included
    assert offer.exclusion_reason == reason


@pytest.mark.parametrize(
    ("details", "flag"),
    [
        (["Coupon available"], o.FLAG_COUPON_AVAILABLE),
        (["Mail-in rebate available"], o.FLAG_REBATE_AVAILABLE),
    ],
)
def test_an_available_coupon_or_rebate_keeps_the_listed_price(real, details, flag):
    """The listed price is then the pre-coupon price, which is the one wanted."""
    offer = o.parse_product_response(
        _variant(real, 1, details_and_offers=details), _RULES
    ).offers[1]
    assert offer.included
    assert flag in offer.flags


def test_member_shipping_perks_do_not_exclude_the_price(real):
    offer = o.parse_product_response(
        _variant(real, 1, details_and_offers=["Free shipping for Prime members"]),
        _RULES,
    ).offers[1]
    assert offer.included


def test_a_mislisted_bundle_far_above_the_band_is_excluded(real):
    parsed = o.parse_product_response(
        _variant(real, 0, extracted_price=2749.99, price="$2,749.99"), _RULES
    )
    newegg = _by_merchant(parsed)["Newegg.com"]
    assert newegg.exclusion_reason == o.REASON_ABOVE_BAND
    assert parsed.estimate_method == "median_of_2"


def test_shipping_is_stored_and_never_priced(real):
    parsed = o.parse_product_response(
        _variant(real, 2, shipping="$9.99", extracted_total=425.98), _RULES
    )
    walmart = _by_merchant(parsed)["Walmart"]
    assert walmart.shipping_cents == 999
    assert walmart.total_cents == 42598
    assert walmart.price_cents == 41599
    assert parsed.estimate_cents == 41599


def test_no_stores_means_no_estimate():
    parsed = o.parse_product_response({"product_results": {"stores": []}})
    assert parsed.estimate_cents is None
    assert parsed.estimate_method == "no_usable_offers"


# --- the estimate rule --------------------------------------------------------------

_BAND = (34900, 41600)


@pytest.mark.parametrize(
    ("prices", "band", "expected"),
    [
        ([38900, 42000, 41599], _BAND, (41599, "median_of_3")),
        ([38900, 42000], _BAND, (40450, "median_of_2")),
        ([1, 2], None, (2, "median_of_2")),  # half-up, not banker's rounding
        ([42000], _BAND, (42000, "single_in_band")),  # 1% over the top: tolerated
        ([34000], _BAND, (34000, "single_in_band")),
        ([45000], _BAND, (None, "single_outside_band")),
        ([30000], _BAND, (None, "single_outside_band")),
        ([42000], None, (None, "single_no_band")),
        ([], _BAND, (None, "no_usable_offers")),
    ],
)
def test_estimate(prices, band, expected):
    assert o.estimate(prices, band) == expected


@pytest.mark.parametrize(
    ("text", "band"),
    [
        ("$349-$416", (34900, 41600)),
        ("$1,099–$1,299", (109900, 129900)),
        ("$416 - $349", (34900, 41600)),
        ("$349", (34900, 34900)),
        ("", None),
        ("call for price", None),
        (None, None),
    ],
)
def test_parse_band(text, band):
    assert o.parse_band(text) == band


def test_history_keeps_the_last_price_for_a_repeated_date_and_skips_garbage():
    points = o.parse_history(
        {
            "stores": [
                {
                    "name": "Newegg.com",
                    "prices": [
                        {"date": "Oct 12, 2026", "price": 348.0},
                        {"date": "Oct 12, 2026", "price": 352.0},
                        {"date": "someday", "price": 300.0},
                        {"date": "Sept 3, 2026", "price": 401.0},
                    ],
                }
            ]
        }
    )
    assert [(p.price_date, p.price_cents) for p in points] == [
        (date(2026, 9, 3), 40100),
        (date(2026, 10, 12), 35200),
    ]
