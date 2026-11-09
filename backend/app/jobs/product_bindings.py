"""On-demand job: `python -m app.jobs.product_bindings`.

Finds Google Shopping product ids for tracked SKUs that have none: one
google_shopping search per SKU (app/services/pricing_etl/binding_discovery.py).
Strong matches are confirmed automatically; the rest wait in the admin's
Product Bindings page.

RUN BY HAND, capped per run. Discovery is a one-time cost per SKU (about one
search each across the catalog), so it has no schedule of its own; the
scheduler will fold rediscovery of stale bindings into the daily run later.

  PRODUCT_BINDING_LIMIT    SKUs to search this run (default 25)
  PRODUCT_BINDING_DRY_RUN  "1" lists what would be searched and spends nothing

QUOTA. The free-text pricing ETL still spends up to 20 searches a day from the
same 1000/month account until product-bound pricing replaces it. This job stops
while fewer than QUOTA_RESERVE searches remain this month, so a large discovery
run can never leave the existing price updates without budget.
"""

import asyncio
import logging
import os

from app.core.db import AsyncSessionLocal
from app.core.logging import configure_logging
from app.crud import pricing_etl as crud
from app.services.pricing_etl import binding_discovery, fetches, quota, tracking
from app.services.pricing_etl.query_profile import discovery_params
from app.services.pricing_etl.raw_store import get_store

configure_logging()
logger = logging.getLogger(__name__)

QUOTA_RESERVE = 150

_LIMIT = int(os.getenv("PRODUCT_BINDING_LIMIT") or "25")
_DRY_RUN = (os.getenv("PRODUCT_BINDING_DRY_RUN") or "").strip() == "1"


async def run(limit: int = _LIMIT, dry_run: bool = _DRY_RUN) -> dict[str, int]:
    async with AsyncSessionLocal() as db:
        changed = await tracking.ensure_tracking_state(db)
        logger.info("tracking state: %d target rows created or re-pointed", changed)
        parts = await tracking.parts_needing_discovery(db, limit)
        remaining = await quota.get_remaining(db)

    affordable = max(0, remaining - QUOTA_RESERVE)
    logger.info(
        "%d SKUs need a binding (limit %d); %d searches left this month, %d usable "
        "after the %d reserve",
        len(parts),
        limit,
        remaining,
        affordable,
        QUOTA_RESERVE,
    )
    parts = parts[:affordable]

    if dry_run:
        for part in parts:
            ref = binding_discovery.PartRef.of(part)
            logger.info(
                "DRY RUN would search: %r for %s %s",
                binding_discovery.discovery_query(ref),
                part.part_type,
                part.id,
            )
        return {"would_search": len(parts)}

    store = get_store()  # before any search: no raw store, no spend
    async with AsyncSessionLocal() as db:
        run_row = await crud.create_run(db)
    counts = {"searched": 0, "auto_confirm": 0, "review": 0, "none": 0, "failed": 0}
    status, error = "completed", None
    try:
        for part in parts:
            ref = binding_discovery.PartRef.of(part)
            async with AsyncSessionLocal() as db:
                outcome = await fetches.perform_fetch(
                    db,
                    store,
                    purpose="discovery",
                    params=discovery_params(binding_discovery.discovery_query(ref)),
                    run_id=run_row.id,
                    part_id=part.id,
                )
                counts["searched"] += 1
                if not outcome.ok:
                    counts["failed"] += 1
                    logger.warning(
                        "discovery search failed for %s: %s",
                        part.id,
                        outcome.response_error,
                    )
                    continue
                result = binding_discovery.score_results(ref, outcome.payload)
                written = await binding_discovery.record_discovery(
                    db, part_id=part.id, fetch_id=outcome.fetch_id, result=result
                )
                counts[written] += 1
                logger.info(
                    "%s %r: %s (%d candidates; %s)",
                    part.part_type,
                    ref.title,
                    written,
                    len(result.survivors),
                    "; ".join(result.why_not_auto) or "all auto-confirm checks passed",
                )
    except Exception as exc:
        logger.exception("product binding run %s failed", run_row.id)
        status, error = "error", f"{type(exc).__name__}: {exc}"
    finally:
        async with AsyncSessionLocal() as db:
            await crud.finalize_run(
                db,
                run_row.id,
                status=status,
                error_detail=error,
                parts_checked=counts["auto_confirm"] + counts["review"],
                searches_used=counts["searched"],
            )
    logger.info("product binding run %s: %s", run_row.id, counts)
    return counts


if __name__ == "__main__":
    asyncio.run(run())
