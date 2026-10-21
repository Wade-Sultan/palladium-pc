"""The frozen query conditions.

The pinned hashes are the point of this file. A change to any fixed parameter
changes the hash, and the fix for this test failing is to bump
QUERY_PROFILE_VERSION and re-pin, never to re-pin alone: every stored fetch
carries the hash, and a silent change of conditions inside one version is
exactly the series break the profile exists to prevent.
"""

from __future__ import annotations

import pytest

from app.services.pricing_etl import query_profile as q

_PINNED = {
    1: {
        q.ENGINE_OFFERS: "4759330878b26ad60d369f7d8b5cc9c9749ba333f3e0cf57aaa821cb857d1c7e",
        q.ENGINE_DISCOVERY: "bcdbb24126aa20b74342049cdd0d6d344267a5ab43a9a48d9c5eff5d3fdfe459",
    },
}


@pytest.mark.parametrize("engine", [q.ENGINE_OFFERS, q.ENGINE_DISCOVERY])
def test_conditions_hash_is_pinned_for_this_version(engine):
    assert (
        q.QUERY_PROFILE_VERSION in _PINNED
    ), "new profile version: pin its hashes here"
    assert q.conditions_hash(engine) == _PINNED[q.QUERY_PROFILE_VERSION][engine]


def test_the_lookup_value_is_not_part_of_the_conditions_hash():
    """One hash per engine across every product is what proves the conditions
    never moved; a per-product hash would prove nothing."""
    a = q.offers_params("111")
    b = q.offers_params("222")
    assert a != b
    assert {k: v for k, v in a.items() if k != "product_id"} == {
        k: v for k, v in b.items() if k != "product_id"
    }


def test_offers_params_carry_only_the_frozen_conditions_and_the_id():
    params = q.offers_params(" 19637827 ")
    assert params == {
        "engine": "google_product",
        "gl": "us",
        "hl": "en",
        "no_cache": "true",
        "product_id": "19637827",
    }


def test_discovery_params_are_a_different_engine():
    params = q.discovery_params("AMD Ryzen 7 9800X3D")
    assert params["engine"] == "google_shopping"
    assert params["q"] == "AMD Ryzen 7 9800X3D"
    assert "product_id" not in params


def test_callers_cannot_mutate_the_profile():
    q.frozen(q.ENGINE_OFFERS)["gl"] = "uk"
    assert q.offers_params("1")["gl"] == "us"


@pytest.mark.parametrize("bad", ["", "   "])
def test_empty_lookup_values_are_refused(bad):
    with pytest.raises(ValueError):
        q.offers_params(bad)
    with pytest.raises(ValueError):
        q.discovery_params(bad)
