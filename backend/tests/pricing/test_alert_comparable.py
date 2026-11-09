"""alerts.comparable: alert only against a price the same method produced.

The real case behind it: on the local seed the free-text ETL ("serpapi") had
the Ryzen 7 7800X3D at $1,331.66, contaminated by a prebuilt. Product-bound
pricing measured $415.99. Comparing the two would have mailed every subscriber
a $915 "price drop" that never happened in any store.
"""

from __future__ import annotations

from app.services.pricing_etl.alerts import comparable


def test_same_method_is_comparable():
    assert comparable(41599, "google_product", "google_product")
    assert comparable(45000, "serpapi", "serpapi")


def test_a_method_change_is_not():
    assert not comparable(133166, "serpapi", "google_product")
    assert not comparable(41599, "google_product", "serpapi")
    assert not comparable(399900, "msrp", "google_product")


def test_a_legacy_price_with_no_recorded_method_is_not():
    """Unknown provenance cannot be assumed to be the same measurement."""
    assert not comparable(45000, None, "google_product")


def test_no_previous_price_is_comparable():
    """Nothing to misread: alerts.decide falls back to the subscribe-time
    baseline, as it always has for a first price."""
    assert comparable(None, None, "google_product")
    assert comparable(None, "serpapi", "google_product")
