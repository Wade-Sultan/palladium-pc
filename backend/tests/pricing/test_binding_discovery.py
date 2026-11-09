"""Choosing a Google product id for a catalog SKU.

The search sample is shaped on the first real discovery capture; see
serpapi_samples.shopping_9800x3d for which traps are the real ones.
"""

from __future__ import annotations

import copy
import uuid

import pytest

from app.services.pricing_etl import binding_discovery as bd
from tests.pricing.serpapi_samples import SHOPPING_9800X3D_TRUE_MATCH, shopping_9800x3d

_CPU = bd.PartRef(
    id=uuid.uuid4(),
    name="Ryzen 7 9800X3D",
    manufacturer="AMD",
    part_type="cpu",
    msrp_cents=47900,
    model_number="100-100001084WOF",
)


def _match(**changes):
    hit = copy.deepcopy(SHOPPING_9800X3D_TRUE_MATCH)
    hit.update(changes)
    return hit


def _rejected(result):
    return {c.title: c.rejected for c in result.rejected}


# --- the search as Google actually answered it ----------------------------------


def test_the_real_shape_finds_nothing_rather_than_something_wrong():
    result = bd.score_results(_CPU, shopping_9800x3d())
    assert result.decision == bd.DECISION_NONE
    assert result.survivors == []


def test_a_prebuilt_with_the_exact_model_name_is_caught_as_a_system():
    """The identity rules pass it: it really does contain a 9800X3D."""
    reasons = _rejected(bd.score_results(_CPU, shopping_9800x3d()))
    assert (
        reasons["ASUS ROG GM700 Gaming Desktop AMD Ryzen 7 9800X3D"] == "whole_system"
    )


def test_sibling_skus_fail_the_model_check():
    reasons = _rejected(bd.score_results(_CPU, shopping_9800x3d()))
    assert reasons["AMD Ryzen 7 7800X3D 8-Core Processor"] == "model_mismatch"
    assert reasons["AMD Ryzen 7 9850X3D 8-Core Processor"] == "model_mismatch"


def test_a_system_that_abbreviates_the_chip_fails_the_model_check():
    reasons = _rejected(bd.score_results(_CPU, shopping_9800x3d()))
    assert reasons["iBUYPOWER Trace Liquid Gaming R7 9800X3D 32GB"] == "model_missing"


# --- what a good match does ------------------------------------------------------


def test_the_catalog_product_is_confirmed_automatically():
    result = bd.score_results(_CPU, shopping_9800x3d(_match()))

    assert result.decision == bd.DECISION_AUTO
    assert result.chosen.product_id == "4300000000000000001"
    assert result.chosen.coverage == 100.0
    assert result.why_not_auto == []


def test_long_catalog_titles_keep_full_coverage():
    """Token-sort similarity drops this title to ~51; coverage does not."""
    result = bd.score_results(_CPU, shopping_9800x3d(_match()))
    assert result.chosen.similarity < 60
    assert result.chosen.coverage == 100.0


@pytest.mark.parametrize(
    ("changes", "why"),
    [
        ({"multiple_sources": False}, "single-seller"),
        ({"extracted_price": 899.0}, "price ratio"),  # plausible gate, not auto
    ],
)
def test_anything_less_than_clear_goes_to_review(changes, why):
    result = bd.score_results(_CPU, shopping_9800x3d(_match(**changes)))
    assert result.decision == bd.DECISION_REVIEW
    assert any(why in reason for reason in result.why_not_auto)


def test_two_plausible_products_go_to_review():
    second = _match(
        product_id="4300000000000000002",
        title="AMD Ryzen 7 9800X3D Desktop Processor (Tray)",
        position=7,
    )
    result = bd.score_results(_CPU, shopping_9800x3d(_match(), second))
    assert result.decision == bd.DECISION_REVIEW
    assert {c.product_id for c in result.survivors} == {
        "4300000000000000001",
        "4300000000000000002",
    }
    assert "2 distinct products survived" in result.why_not_auto


def test_a_wildly_wrong_price_is_rejected_outright():
    result = bd.score_results(_CPU, shopping_9800x3d(_match(extracted_price=1999.0)))
    assert result.decision == bd.DECISION_NONE
    assert (
        _rejected(result)[SHOPPING_9800X3D_TRUE_MATCH["title"]] == "implausible_price"
    )


def test_no_anchor_price_means_review():
    no_msrp = bd.PartRef(**{**_CPU.__dict__, "msrp_cents": None})
    result = bd.score_results(no_msrp, shopping_9800x3d(_match()))
    assert result.decision == bd.DECISION_REVIEW
    assert any("no MSRP" in r for r in result.why_not_auto)


def test_the_same_product_at_two_positions_is_one_candidate():
    again = _match(position=9, source="Walmart")
    result = bd.score_results(_CPU, shopping_9800x3d(_match(), again))
    assert result.decision == bd.DECISION_AUTO
    assert len(result.survivors) == 1


# --- parts the identity rules cannot read ---------------------------------------

_CASE = bd.PartRef(
    id=uuid.uuid4(),
    name="North",
    manufacturer="Fractal Design",
    part_type="case",
    msrp_cents=13999,
    model_number="FD-C-NOR1C-02",
)


def _case_search(title):
    return {
        "shopping_results": [
            {
                "position": 1,
                "title": title,
                "product_id": "555",
                "source": "Newegg.com",
                "extracted_price": 139.99,
                "multiple_sources": True,
            }
        ]
    }


def test_a_bigger_product_containing_the_name_is_never_auto_confirmed():
    """'North' is fully contained in 'North XL'. Coverage cannot tell them
    apart, and there is no model scheme to check, so a human decides."""
    result = bd.score_results(
        _CASE, _case_search("Fractal Design North XL ATX Full Tower Case")
    )
    assert result.decision == bd.DECISION_REVIEW
    assert any("model number is not in the title" in r for r in result.why_not_auto)


def test_a_model_number_in_the_title_is_enough_identity_for_auto():
    result = bd.score_results(
        _CASE, _case_search("Fractal Design North ATX Mid Tower Case FD-C-NOR1C-02")
    )
    assert result.decision == bd.DECISION_AUTO
    assert result.chosen.model_number_in_title


def test_a_made_up_short_model_number_proves_nothing():
    short = bd.PartRef(**{**_CASE.__dict__, "model_number": "NORTH"})
    assert not bd.model_number_in(short, "Fractal Design North ATX Mid Tower Case")


# --- query and title ------------------------------------------------------------


def test_the_query_is_brand_name_and_a_type_noun():
    assert bd.discovery_query(_CPU) == "AMD Ryzen 7 9800X3D processor"


def test_a_brand_already_in_the_name_is_not_repeated():
    gpu = bd.PartRef(
        id=uuid.uuid4(), name="ASUS TUF RTX 5080", manufacturer="ASUS", part_type="gpu"
    )
    assert gpu.title == "ASUS TUF RTX 5080"
    assert bd.discovery_query(gpu) == "ASUS TUF RTX 5080 graphics card"


def test_a_system_gets_no_noun():
    system = bd.PartRef(
        id=uuid.uuid4(), name="DGX Spark", manufacturer="NVIDIA", part_type="system"
    )
    assert bd.discovery_query(system) == "NVIDIA DGX Spark"
