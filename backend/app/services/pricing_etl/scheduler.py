"""The daily product-bound pricing run: re-rank, fetch what is due, write rows.

ONE RUN A DAY, three steps (app/jobs/price_tracking.py):
  1. rerank_if_due: once a week, recompute every bound target's volatility
     from Google's price history and reassign bins (volatility.assign_bins).
  2. fetch what is due: next_due_at passed (or never fetched), confirmed
     binding, high bin first, then most overdue, within DAILY_MAX_FETCHES and
     the month's remaining quota. Each fetch is checked before it is trusted
     (verify_product), publishes its price to street_price_cents with the
     same price-drop alerts as the free-text ETL, and pushes next_due_at out
     by its bin's interval.
  3. write_daily_rows: one daily_price_estimates row per target for today,
     whether or not it was fetched, and replace carried-forward days with
     Google's history whenever a fetch brings it.

FAILURE POLICY. A failed fetch (transport, HTTP, SerpApi error, no stores) is
retried the next day and counted on the binding; FAILURES_BEFORE_STALE in a row
marks the binding stale. A fetch whose product title fails the identity check
marks it stale at once: Google merges and splits catalog ids, and a binding
that now returns a different product must stop being priced immediately. A
stale binding is never fetched again; the part goes back to discovery and the
admin's Product Bindings page.

WHY A DAILY CAP AS WELL AS BINS. On the first run every target is due (never
fetched), roughly a hundred and seventy searches in one go. The cap spreads
that over the first week, and the weekly cadence then keeps each target on the
day it was first fetched, which keeps the load even afterwards.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta

import httpx
from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud import pricing_etl as crud
from app.models.pcparts import PCPart
from app.models.price_tracking import (
    DailyPriceEstimate,
    GoogleProductBinding,
    PriceFetch,
    PriceHistoryPoint,
    PriceTrackingState,
)
from app.services.pricing_etl import (
    alerts,
    binding_discovery,
    fetches,
    offers,
    product_identity,
    title_match,
)
from app.services.pricing_etl import volatility as vol
from app.services.pricing_etl.query_profile import offers_params

logger = logging.getLogger(__name__)

DAILY_MAX_FETCHES = 40
FAILURES_BEFORE_STALE = 3
RERANK_EVERY = timedelta(days=7)
RETRY_AFTER_FAILURE = timedelta(days=1)

# Below this name coverage, a returned product title is not this part.
VERIFY_MIN_COVERAGE = 80.0

_BIN_ORDER = {"high": 0, "medium": 1, "low": 2}

REASON_PRODUCT_MISMATCH = "product_mismatch"

# The price_source written alongside street_price_cents.
PRICE_SOURCE = "google_product"


@dataclass
class FetchResult:
    # "priced", "no_estimate", "failed" or "stale"
    status: str
    alerts_sent: int = 0
    # Alerts that would have gone out with PRICE_ALERTS_ENABLED on.
    alerts_dry_run: int = 0
    # A price written over a different method's: a baseline, not compared.
    method_changed: bool = False


@dataclass
class DueTarget:
    kind: str
    target_id: uuid.UUID
    bin: str
    next_due_at: datetime | None
    part: PCPart
    binding: GoogleProductBinding


def verify_product(part: PCPart, product_title: str | None) -> str | None:
    """Why the product google_product returned is not this part, or None.
    No title is not a mismatch: there is nothing to contradict the binding."""
    if not product_title:
        return None
    ref = binding_discovery.PartRef.of(part)
    reason = title_match.disqualifier(product_title)
    if reason is None:
        reason = product_identity.exclusion_reason(ref.title, product_title)
    if (
        reason is None
        and binding_discovery.coverage(ref.title, product_title) < VERIFY_MIN_COVERAGE
    ):
        reason = binding_discovery.REASON_LOW_COVERAGE
    return reason


# --- 1. weekly re-rank ----------------------------------------------------------------


async def _confirmed_by_part(db: AsyncSession) -> dict[uuid.UUID, GoogleProductBinding]:
    rows = await db.execute(
        select(GoogleProductBinding).where(GoogleProductBinding.status == "confirmed")
    )
    return {b.part_id: b for b in rows.scalars()}


async def _history(
    db: AsyncSession, binding_ids: list[uuid.UUID]
) -> dict[uuid.UUID, list[vol.Point]]:
    out: dict[uuid.UUID, list[vol.Point]] = {b: [] for b in binding_ids}
    if not binding_ids:
        return out
    rows = await db.execute(
        select(
            PriceHistoryPoint.binding_id,
            PriceHistoryPoint.merchant_name,
            PriceHistoryPoint.price_date,
            PriceHistoryPoint.price_cents,
        ).where(PriceHistoryPoint.binding_id.in_(binding_ids))
    )
    for binding_id, merchant, day, cents in rows:
        out[binding_id].append(vol.Point(merchant, day, cents))
    return out


async def rerank_if_due(
    db: AsyncSession, now: datetime, *, force: bool = False
) -> bool:
    last = (
        await db.execute(select(func.max(PriceTrackingState.volatility_computed_at)))
    ).scalar()
    if not force and last is not None and now - last < RERANK_EVERY:
        return False

    states = list((await db.execute(select(PriceTrackingState))).scalars())
    confirmed = await _confirmed_by_part(db)
    bound = [s for s in states if s.tracked_part_id in confirmed]
    history = await _history(db, [confirmed[s.tracked_part_id].id for s in bound])

    measured: dict[tuple[str, uuid.UUID], tuple[float | None, int]] = {}
    inputs = []
    for s in bound:
        v, n = vol.volatility(history[confirmed[s.tracked_part_id].id], now.date())
        measured[(s.target_kind, s.target_id)] = (v, n)
        inputs.append(
            vol.TargetVol(
                key=(s.target_kind, s.target_id),
                volatility=v,
                current_bin=s.bin,
                out_of_top_streak=s.out_of_top_streak,
            )
        )
    assignments = vol.assign_bins(inputs)

    for s in states:
        key = (s.target_kind, s.target_id)
        a = assignments.get(key)
        v, n = measured.get(key, (None, 0))
        new_bin = a.bin if a else "medium"  # unbound: not fetched, nominally medium
        values = {
            "volatility": v,
            "n_observations": n,
            "volatility_rank": a.rank if a else None,
            "out_of_top_streak": a.out_of_top_streak if a else 0,
            "volatility_computed_at": now,
        }
        if new_bin != s.bin:
            values["bin"] = new_bin
            values["bin_changed_at"] = now
            if s.last_fetched_at is not None:
                values["next_due_at"] = s.last_fetched_at + vol.BIN_INTERVALS[new_bin]
        await db.execute(
            update(PriceTrackingState)
            .where(
                PriceTrackingState.target_kind == s.target_kind,
                PriceTrackingState.target_id == s.target_id,
            )
            .values(**values)
        )
    await db.commit()
    counts = {
        b: sum(1 for a in assignments.values() if a.bin == b) for b in vol.BIN_INTERVALS
    }
    logger.info("re-ranked %d bound targets: %s", len(assignments), counts)
    return True


# --- 2. fetching -----------------------------------------------------------------------


async def due_targets(db: AsyncSession, now: datetime, limit: int) -> list[DueTarget]:
    if limit <= 0:
        return []
    rows = await db.execute(
        select(PriceTrackingState, PCPart, GoogleProductBinding)
        .join(PCPart, PCPart.id == PriceTrackingState.tracked_part_id)
        .join(
            GoogleProductBinding,
            (GoogleProductBinding.part_id == PCPart.id)
            & (GoogleProductBinding.status == "confirmed"),
        )
        .where(
            PCPart.is_active.is_(True),
            (PriceTrackingState.next_due_at.is_(None))
            | (PriceTrackingState.next_due_at <= now),
        )
    )
    due = [
        DueTarget(s.target_kind, s.target_id, s.bin, s.next_due_at, p, b)
        for s, p, b in rows
    ]
    far_past = datetime.min.replace(tzinfo=UTC)
    due.sort(
        key=lambda t: (
            _BIN_ORDER.get(t.bin, 9),
            t.next_due_at or far_past,
            str(t.target_id),
        )
    )
    return due[:limit]


async def _set_state(db: AsyncSession, t: DueTarget, **values) -> None:
    await db.execute(
        update(PriceTrackingState)
        .where(
            PriceTrackingState.target_kind == t.kind,
            PriceTrackingState.target_id == t.target_id,
        )
        .values(**values)
    )


async def fetch_target(
    db: AsyncSession,
    store,
    t: DueTarget,
    now: datetime,
    *,
    run_id: uuid.UUID | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> FetchResult:
    """Fetch, verify, parse and schedule one target; publish its price to
    street_price_cents and evaluate price-drop alerts, exactly as the
    free-text ETL does (crud.record_check_outcome, alerts.process_target)."""
    binding = await db.get(GoogleProductBinding, t.binding.id)
    outcome = await fetches.perform_fetch(
        db,
        store,
        purpose="offers",
        params=offers_params(binding.google_product_id),
        run_id=run_id,
        binding_id=binding.id,
        part_id=t.part.id,
        transport=transport,
    )
    binding.last_fetched_at = now
    stores = ((outcome.payload or {}).get("product_results") or {}).get("stores") or []

    if not outcome.ok or not stores:
        binding.consecutive_failures += 1
        result = "failed"
        if binding.consecutive_failures >= FAILURES_BEFORE_STALE:
            binding.status, binding.status_changed_at, result = "stale", now, "stale"
        await _set_state(db, t, next_due_at=now + RETRY_AFTER_FAILURE)
        await db.commit()
        logger.warning(
            "%s %s: fetch failed (%s), %d in a row",
            t.kind,
            t.target_id,
            outcome.response_error or "no stores",
            binding.consecutive_failures,
        )
        return FetchResult(result)

    parsed = offers.parse_product_response(
        outcome.payload, await offers.load_merchant_rules(db)
    )
    mismatch = verify_product(t.part, parsed.product_title)
    if mismatch:
        # Keep the offers as evidence, but this fetch prices nothing.
        parsed.estimate_cents, parsed.estimate_method = None, REASON_PRODUCT_MISMATCH
    await offers.record_parsed(
        db, fetch_id=outcome.fetch_id, binding_id=binding.id, parsed=parsed
    )

    binding = await db.get(GoogleProductBinding, t.binding.id)
    if mismatch:
        binding.status, binding.status_changed_at = "stale", now
        await _set_state(db, t, last_fetched_at=now, next_due_at=None)
        await db.commit()
        logger.warning(
            "%s %s: bound product %s now returns %r (%s); binding marked stale",
            t.kind,
            t.target_id,
            binding.google_product_id,
            parsed.product_title,
            mismatch,
        )
        return FetchResult("stale")

    binding.consecutive_failures = 0
    binding.last_success_at = now
    await _set_state(
        db,
        t,
        last_fetched_at=now,
        next_due_at=now + vol.BIN_INTERVALS.get(t.bin, vol.BIN_INTERVALS["medium"]),
    )
    await db.commit()
    await backfill_from_history(
        db, t.kind, t.target_id, binding.id, now.date(), outcome.fetch_id
    )
    return await _publish(db, t, now, parsed.estimate_cents)


async def _publish(
    db: AsyncSession, t: DueTarget, now: datetime, cents: int | None
) -> FetchResult:
    """Write the estimate to the target's street_price_cents and fire alerts.

    No estimate still stamps last_price_checked_at, like the free-text ETL, so
    "when did we last look" means the same thing whichever job looked."""
    before = await crud.record_check_outcome(
        db,
        target_kind=t.kind,
        target_id=t.target_id,
        checked_at=now,
        price_cents=cents,
        price_source=PRICE_SOURCE,
    )
    if cents is None:
        return FetchResult("no_estimate")
    if not alerts.comparable(
        before.previous_cents, before.previous_source, PRICE_SOURCE
    ):
        logger.info(
            "%s %s: price method changed (%s %s -> %s %s); written as a baseline, "
            "no alerts evaluated",
            t.kind,
            t.target_id,
            before.previous_source,
            before.previous_cents,
            PRICE_SOURCE,
            cents,
        )
        return FetchResult("priced", method_changed=True)
    sent = await alerts.process_target(
        db,
        target_kind=t.kind,
        target_id=t.target_id,
        target_name=before.name,
        previous_cents=before.previous_cents,
        new_cents=cents,
    )
    return FetchResult("priced", alerts_sent=sent.sent, alerts_dry_run=sent.dry_run)


# --- 3. daily rows ---------------------------------------------------------------------


def _midnight(day: date) -> datetime:
    return datetime.combine(day, time.min, tzinfo=UTC)


async def backfill_from_history(
    db: AsyncSession,
    kind: str,
    target_id: uuid.UUID,
    binding_id: uuid.UUID,
    today: date,
    fetch_id: uuid.UUID,
) -> int:
    """Replace this target's carried-forward (or empty) past rows with the
    price Google's history says the stores were charging that day."""
    points = (await _history(db, [binding_id]))[binding_id]
    if not points:
        return 0
    rows = await db.execute(
        select(DailyPriceEstimate.estimate_date).where(
            DailyPriceEstimate.target_kind == kind,
            DailyPriceEstimate.target_id == target_id,
            DailyPriceEstimate.estimate_date < today,
            DailyPriceEstimate.source.in_(("carried", "none")),
        )
    )
    filled = 0
    for (day,) in rows:
        cents = vol.as_of(points, day)
        changed = vol.last_change_on_or_before(points, day)
        if cents is None or changed is None:
            continue
        await db.execute(
            update(DailyPriceEstimate)
            .where(
                DailyPriceEstimate.target_kind == kind,
                DailyPriceEstimate.target_id == target_id,
                DailyPriceEstimate.estimate_date == day,
            )
            .values(
                price_cents=cents,
                source="history",
                last_observed_at=_midnight(changed),
                source_fetch_id=fetch_id,
            )
        )
        filled += 1
    await db.commit()
    return filled


async def write_daily_rows(db: AsyncSession, today: date) -> int:
    """Today's row for every target: the latest estimate, marked "fetch" if
    it was measured today, "carried" if older, "none" if there is none yet."""
    states = list((await db.execute(select(PriceTrackingState))).scalars())
    part_ids = [s.tracked_part_id for s in states if s.tracked_part_id]
    latest: dict[uuid.UUID, PriceFetch] = {}
    if part_ids:
        rows = await db.execute(
            select(PriceFetch)
            .where(
                PriceFetch.purpose == "offers",
                PriceFetch.estimate_cents.is_not(None),
                PriceFetch.part_id.in_(part_ids),
            )
            .distinct(PriceFetch.part_id)
            .order_by(PriceFetch.part_id, PriceFetch.fetched_at.desc())
        )
        latest = {f.part_id: f for f in rows.scalars()}

    values = []
    for s in states:
        f = latest.get(s.tracked_part_id)
        if f is None:
            source, cents, seen, fid = "none", None, None, None
        else:
            source = (
                "fetch" if f.fetched_at.astimezone(UTC).date() == today else "carried"
            )
            cents, seen, fid = f.estimate_cents, f.fetched_at, f.id
        values.append(
            {
                "target_kind": s.target_kind,
                "target_id": s.target_id,
                "estimate_date": today,
                "price_cents": cents,
                "last_observed_at": seen,
                "source_fetch_id": fid,
                "bin": s.bin,
                "source": source,
            }
        )
    if values:
        stmt = insert(DailyPriceEstimate).values(values)
        await db.execute(
            stmt.on_conflict_do_update(
                index_elements=["target_kind", "target_id", "estimate_date"],
                set_={
                    c: stmt.excluded[c]
                    for c in (
                        "price_cents",
                        "last_observed_at",
                        "source_fetch_id",
                        "bin",
                        "source",
                    )
                },
            )
        )
    await db.commit()
    return len(values)
