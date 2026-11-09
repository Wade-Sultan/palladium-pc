"""Daily job entrypoint: `python -m app.jobs.price_tracking`.

Product-bound pricing's daily run (app/services/pricing_etl/scheduler.py):
re-rank bins weekly, fetch the targets that are due, publish each new price
to street_price_cents with the same price-drop alerts as the free-text ETL,
write today's row for every target.

SHIPPED SUSPENDED. It spends from the same 1000/month SerpApi account as the
free-text pricing ETL (app.jobs.pricing_etl), and the two together would
overrun it: about 725/month for this one at steady state (5 daily, 100 weekly,
the rest every two weeks) against about 600 for the old one. Switching over is
one change: unsuspend this CronJob and suspend pricing-etl in the same deploy.

  PRICE_TRACKING_DRY_RUN  "1" re-ranks if due and lists what would be fetched;
                          spends nothing and writes no daily rows
"""

import asyncio
import logging
import os
from datetime import UTC, datetime

import httpx

from app.core.db import AsyncSessionLocal
from app.core.logging import configure_logging
from app.crud import pricing_etl as crud
from app.services.pricing_etl import quota, scheduler, tracking
from app.services.pricing_etl.raw_store import get_store

configure_logging()
logger = logging.getLogger(__name__)

# Searches this job leaves untouched at month end, so an admin can still run
# discovery for a new part without waiting for the 1st.
QUOTA_RESERVE = 30

_DRY_RUN = (os.getenv("PRICE_TRACKING_DRY_RUN") or "").strip() == "1"


async def run(
    *,
    dry_run: bool = _DRY_RUN,
    now: datetime | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> dict[str, int]:
    now = now or datetime.now(UTC)
    async with AsyncSessionLocal() as db:
        await tracking.ensure_tracking_state(db)
        reranked = await scheduler.rerank_if_due(db, now)
        remaining = await quota.get_remaining(db)
        budget = min(scheduler.DAILY_MAX_FETCHES, max(0, remaining - QUOTA_RESERVE))
        due = await scheduler.due_targets(db, now, budget)

    logger.info(
        "re-ranked: %s; %d targets due within today's budget of %d (%d searches left this month)",
        reranked,
        len(due),
        budget,
        remaining,
    )
    if dry_run:
        for t in due:
            logger.info(
                "DRY RUN would fetch: %s bin, %s %s via %r (product %s)",
                t.bin,
                t.kind,
                t.target_id,
                t.part.name,
                t.binding.google_product_id,
            )
        return {"would_fetch": len(due)}

    counts = {
        "priced": 0,
        "no_estimate": 0,
        "failed": 0,
        "stale": 0,
        "alerts_sent": 0,
        "alerts_dry_run": 0,
        "method_changed": 0,
    }
    status, error = "completed", None
    run_row = None
    try:
        if due:
            store = get_store()  # before any search: no raw store, no spend
            async with AsyncSessionLocal() as db:
                run_row = await crud.create_run(db)
            for t in due:
                async with AsyncSessionLocal() as db:
                    result = await scheduler.fetch_target(
                        db, store, t, now, run_id=run_row.id, transport=transport
                    )
                counts[result.status] += 1
                counts["alerts_sent"] += result.alerts_sent
                counts["alerts_dry_run"] += result.alerts_dry_run
                counts["method_changed"] += int(result.method_changed)
    except Exception as exc:
        logger.exception("price tracking run failed")
        status, error = "error", f"{type(exc).__name__}: {exc}"
    finally:
        # Daily rows are written whatever happened above: a day with no
        # successful fetch still gets its carried-forward row.
        async with AsyncSessionLocal() as db:
            counts["daily_rows"] = await scheduler.write_daily_rows(db, now.date())
        if run_row is not None:
            async with AsyncSessionLocal() as db:
                await crud.finalize_run(
                    db,
                    run_row.id,
                    status=status,
                    error_detail=error,
                    parts_checked=counts["priced"],
                    alerts_sent=counts["alerts_sent"],
                    searches_used=sum(
                        counts[k] for k in ("priced", "no_estimate", "failed", "stale")
                    ),
                )
    logger.info("price tracking: %s", counts)
    return counts


if __name__ == "__main__":
    asyncio.run(run())
