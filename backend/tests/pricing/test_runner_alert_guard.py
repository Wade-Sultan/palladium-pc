"""The free-text ETL's side of the same-method alert rule.

Product-bound pricing (scheduler.py) now writes street_price_cents too. The
free-text runner must not read that as market movement either: when the
stored price came from another method, it writes its own as the baseline and
evaluates no alerts. Everything around _check_target is faked; this pins only
the decision of whether alerts run.
"""

from __future__ import annotations

import asyncio
import uuid

import pytest

from app.crud.pricing_etl import CheckOutcome
from app.services.pricing_etl import alerts, quota, runner
from app.services.pricing_etl.serpapi_client import ShoppingResult


@pytest.fixture
def harness(monkeypatch):
    calls = {"alerts": [], "written": []}

    async def search(_query):
        return [
            ShoppingResult(f"AMD Ryzen 7 7800X3D Processor {i}", p, "Store", None)
            # Tight enough to survive stats.py's MAD band; median $415.99.
            for i, p in enumerate((414.0, 415.99, 417.0))
        ]

    async def noop(*_a, **_k):
        return None

    def outcome_for(previous_cents, previous_source):
        async def record(_db, **kwargs):
            calls["written"].append((kwargs["price_cents"], kwargs["price_source"]))
            return CheckOutcome("Ryzen 7 7800X3D", previous_cents, previous_source)

        monkeypatch.setattr(runner.crud, "record_check_outcome", record)

    async def process(_db, **kwargs):
        calls["alerts"].append(kwargs)
        return alerts.Outcome(considered=1, fired=1, sent=1)

    monkeypatch.setattr(runner, "search_shopping", search)
    monkeypatch.setattr(quota, "record_search", noop)
    monkeypatch.setattr(runner.crud, "record_price_check", noop)
    monkeypatch.setattr(alerts, "process_target", process)
    calls["set_previous"] = outcome_for
    return calls


def _check():
    target = runner._Target(
        kind="pc_part", id=uuid.uuid4(), queries=["AMD Ryzen 7 7800X3D"]
    )
    return asyncio.run(runner._check_target(None, uuid.uuid4(), target, 3))


def test_a_price_from_the_same_method_is_alerted_on(harness):
    harness["set_previous"](45000, "serpapi")
    searches, matched, sent = _check()

    assert matched and sent == 1
    assert harness["written"] == [(41599, "serpapi")]
    assert harness["alerts"][0]["previous_cents"] == 45000


def test_a_price_from_product_bound_pricing_is_a_baseline_not_a_drop(harness):
    harness["set_previous"](45000, "google_product")
    _searches, matched, sent = _check()

    assert matched
    assert sent == 0
    assert harness["alerts"] == []
    assert harness["written"] == [(41599, "serpapi")], "the price is still written"


def test_a_first_ever_price_still_reaches_the_alerts(harness):
    harness["set_previous"](None, None)
    _searches, _matched, sent = _check()
    assert sent == 1
