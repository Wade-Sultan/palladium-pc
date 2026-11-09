"""offers.reparse_fetch applies the same identity check as a scheduled fetch.

Without the check, a re-parse gives a usable estimate to a stored response
that was rejected because Google returned a different product.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from types import SimpleNamespace

import pytest

from app.models.pcparts import PCPart
from app.models.price_tracking import PriceFetch
from app.services.pricing_etl import offers
from app.services.pricing_etl.identity_check import REASON_PRODUCT_MISMATCH
from tests.pricing.serpapi_samples import product_7800x3d


def _part(name):
    return SimpleNamespace(
        id=uuid.uuid4(),
        name=name,
        manufacturer="AMD",
        part_type="cpu",
        msrp_cents=None,
        street_price_cents=None,
        model_number=None,
    )


class FakeDB:
    def __init__(self, fetch, part):
        self.rows = {PriceFetch: fetch, PCPart: part}

    async def get(self, model, _id):
        return self.rows.get(model)


class FakeStore:
    async def get(self, _uri):
        return json.dumps(product_7800x3d()).encode()


@pytest.fixture
def reparse(monkeypatch):
    """Re-parse the stored 7800X3D response for `part`; return what was recorded."""

    def _reparse(part, *, part_id=True):
        fetch = SimpleNamespace(
            raw_uri="gs://bucket/raw.json",
            binding_id=uuid.uuid4(),
            part_id=(part.id if part is not None else uuid.uuid4()) if part_id else None,
        )
        recorded = {}

        async def load_merchant_rules(_db):
            return []

        async def record_parsed(_db, *, parsed, **_k):
            recorded["parsed"] = parsed

        monkeypatch.setattr(offers, "load_merchant_rules", load_merchant_rules)
        monkeypatch.setattr(offers, "record_parsed", record_parsed)
        asyncio.run(offers.reparse_fetch(FakeDB(fetch, part), FakeStore(), uuid.uuid4()))
        return recorded["parsed"]

    return _reparse


def test_the_matching_part_keeps_its_estimate(reparse):
    parsed = reparse(_part("Ryzen 7 7800X3D"))
    assert parsed.estimate_cents is not None


def test_a_mismatched_product_gets_no_estimate(reparse):
    # The stored response is a 7800X3D. For a 9800X3D part, the scheduled
    # fetch rejects it, and the re-parse must reject it too.
    parsed = reparse(_part("Ryzen 7 9800X3D"))
    assert parsed.estimate_cents is None
    assert parsed.estimate_method == REASON_PRODUCT_MISMATCH
    # The offers stay as evidence.
    assert parsed.offers


@pytest.mark.parametrize("part_id", [False, True])
def test_a_fetch_without_its_part_is_refused(reparse, part_id):
    # part_id=False: the fetch has no part_id. True: the part row is gone.
    with pytest.raises(LookupError):
        reparse(None, part_id=part_id)
