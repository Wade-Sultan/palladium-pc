"""scheduler.fetch_target: the schedule and the published price commit together.

If they commit separately, a run that stops between the two commits leaves
the old street_price_cents in place while next_due_at says the target was
priced. The target is then not fetched again for up to two weeks.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from app.crud.pricing_etl import CheckOutcome
from app.services.pricing_etl import scheduler
from tests.pricing.serpapi_samples import product_7800x3d

NOW = datetime(2026, 11, 9, 6, 0, tzinfo=UTC)


class FakeDB:
    """Records writes in order. commit() moves pending writes to committed."""

    def __init__(self, binding):
        self.binding = binding
        self.pending: list[str] = []
        self.committed: list[str] = []
        self.commits = 0
        self.rollbacks = 0
        # Steps after the price commit, in the order they ran.
        self.after_commit: list[str] = []

    async def get(self, _model, _id):
        return self.binding

    async def commit(self):
        self.committed.extend(self.pending)
        self.pending.clear()
        self.commits += 1

    async def rollback(self):
        self.pending.clear()
        self.rollbacks += 1


def _target():
    part = SimpleNamespace(
        id=uuid.uuid4(),
        name="Ryzen 7 7800X3D",
        manufacturer="AMD",
        part_type="cpu",
        msrp_cents=None,
        street_price_cents=None,
        model_number=None,
    )
    binding = SimpleNamespace(
        id=uuid.uuid4(),
        google_product_id="14072215030660324520",
        consecutive_failures=0,
        status="confirmed",
        status_changed_at=None,
        last_fetched_at=None,
        last_success_at=None,
    )
    t = scheduler.DueTarget(
        kind="part",
        target_id=part.id,
        bin="medium",
        next_due_at=None,
        part=part,
        binding=binding,
    )
    return t, binding


@pytest.fixture
def run(monkeypatch):
    """Run fetch_target with every database write replaced by a recorder.

    `fail_at` names the step that raises, to simulate the run stopping there."""

    def _run(fail_at: str | None = None):
        t, binding = _target()
        db = FakeDB(binding)

        def step(name):
            if name == fail_at:
                raise RuntimeError(f"run stopped at {name}")
            db.pending.append(name)

        async def perform_fetch(*_a, **_k):
            return SimpleNamespace(
                ok=True,
                payload=product_7800x3d(),
                fetch_id=uuid.uuid4(),
                response_error=None,
            )

        async def load_merchant_rules(_db):
            return []

        async def record_parsed(_db, *, commit=True, **_k):
            assert commit is False, "the parse must not commit on its own"
            step("parse")

        async def set_state(_db, _t, **values):
            step("schedule" if values.get("next_due_at") else "state")

        async def record_check_outcome(_db, *, commit=True, price_cents, **_k):
            assert commit is False, "the price must not commit on its own"
            assert price_cents is not None
            step("price")
            return CheckOutcome("Ryzen 7 7800X3D", None, None)

        async def backfill(*_a, **_k):
            db.after_commit.append("backfill")
            if fail_at == "backfill":
                raise RuntimeError("backfill failed")
            return 0

        async def process_target(*_a, **_k):
            db.after_commit.append("alerts")
            return SimpleNamespace(sent=1, dry_run=0)

        monkeypatch.setattr(scheduler.fetches, "perform_fetch", perform_fetch)
        monkeypatch.setattr(scheduler.offers, "load_merchant_rules", load_merchant_rules)
        monkeypatch.setattr(scheduler.offers, "record_parsed", record_parsed)
        monkeypatch.setattr(scheduler, "_set_state", set_state)
        monkeypatch.setattr(scheduler.crud, "record_check_outcome", record_check_outcome)
        monkeypatch.setattr(scheduler, "backfill_from_history", backfill)
        monkeypatch.setattr(scheduler.alerts, "process_target", process_target)

        try:
            result = asyncio.run(scheduler.fetch_target(db, None, t, NOW))
        except RuntimeError:
            result = None
        return db, result

    return _run


def test_schedule_and_price_commit_in_one_transaction(run):
    db, result = run()
    assert result is not None and result.status == "priced"
    assert db.commits == 1
    assert db.committed == ["parse", "schedule", "price"]


def test_alerts_run_before_the_backfill(run):
    db, _ = run()
    assert db.after_commit == ["alerts", "backfill"]


def test_a_run_that_stops_before_the_price_advances_nothing(run):
    db, result = run(fail_at="price")
    assert result is None
    # Nothing committed, so next_due_at is unchanged and the target stays due.
    assert db.commits == 0
    assert db.committed == []


def test_a_failed_backfill_keeps_the_price_and_the_alerts(run):
    # The new price is committed before the backfill. If a backfill failure
    # stopped the alerts, the next fetch would compare against the new price
    # and the drop would never be sent.
    db, result = run(fail_at="backfill")
    assert result is not None and result.status == "priced"
    assert result.alerts_sent == 1
    assert db.after_commit == ["alerts", "backfill"]
    assert db.committed == ["parse", "schedule", "price"]
    assert db.rollbacks == 1
