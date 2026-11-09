"""Which SKU stands for each price target, and which SKUs still need a binding.

ONE SKU PER TARGET. A pc_parts target (CPU, motherboard, cooler, case, fan,
complete system) is priced through itself. A group (GPU chipset, PSU, RAM or
storage group) is priced through ONE active variant, because every extra bound
variant is another search per run against a 1000/month cap. The default pick
is the variant with the lowest MSRP (for a GPU chipset that is usually the
reference or Founders board, the one whose price means "an RTX 5080"), then
lowest street price, then name. An admin can point tracked_part_id elsewhere,
and ensure_tracking_state never overrides a pick whose part is still active.

Bins start at "medium" here. Moving targets between bins is the scheduler's
job (step 4); this module only makes sure every target has a row.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, exists, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.pricing_etl import GROUP_SPECS, NON_GROUPED_MODELS
from app.models.pcparts import PCPart
from app.models.price_tracking import (
    GoogleProductBinding,
    PriceFetch,
    PriceTrackingState,
)

# A part searched within this window without producing a binding is not
# searched again: Google not having it this week usually means Google not
# having it next week either, and each retry is a search. An admin can still
# bind it by hand at any time.
DISCOVERY_COOLDOWN = timedelta(days=30)

# Discovery order when the budget cannot cover everything at once: the part
# types the recommender leans on hardest first (the same split as the old
# runner's _HIGH_* lists), then the rest.
_PRIORITY = {
    "cpu": 0,
    "gpu": 0,
    "motherboard": 0,
    "ramkit": 0,
    "storagedrive": 0,
    "system": 0,
    "cpucooler": 1,
    "case": 1,
    "psu": 1,
    "fan": 1,
}


def _pick(variants: list) -> uuid.UUID:
    big = 1 << 62
    return min(
        variants,
        key=lambda v: (
            v.msrp_cents if v.msrp_cents is not None else big,
            v.street_price_cents if v.street_price_cents is not None else big,
            v.name or "",
            str(v.id),
        ),
    ).id


async def ensure_tracking_state(db: AsyncSession) -> int:
    """Create a price_tracking_state row for every active target that lacks
    one, and re-pick the tracked SKU wherever it has gone missing or inactive.
    Returns how many rows were created or re-pointed."""
    wanted: dict[tuple[str, uuid.UUID], uuid.UUID] = {}

    parts = await db.execute(
        select(PCPart.id).where(
            PCPart.part_type.in_(list(NON_GROUPED_MODELS)),
            PCPart.is_active.is_(True),
        )
    )
    for (part_id,) in parts:
        wanted[("pc_part", part_id)] = part_id

    for kind, (_group_model, variants_rel) in GROUP_SPECS.items():
        variant = variants_rel.property.mapper.class_
        group_col = _group_fk(variant, kind)
        rows = await db.execute(
            select(
                variant.id,
                group_col.label("group_id"),
                variant.msrp_cents,
                variant.street_price_cents,
                variant.name,
            ).where(variant.is_active.is_(True), group_col.is_not(None))
        )
        by_group: dict[uuid.UUID, list] = {}
        for row in rows:
            by_group.setdefault(row.group_id, []).append(row)
        for group_id, variants in by_group.items():
            wanted[(kind, group_id)] = _pick(variants)

    if not wanted:
        return 0

    existing = {
        (r.target_kind, r.target_id): r.tracked_part_id
        for r in await db.execute(
            select(
                PriceTrackingState.target_kind,
                PriceTrackingState.target_id,
                PriceTrackingState.tracked_part_id,
            )
        )
    }
    tracked = [p for p in existing.values() if p is not None]
    active_parts: set[uuid.UUID] = set()
    if tracked:
        rows = await db.execute(
            select(PCPart.id).where(PCPart.id.in_(tracked), PCPart.is_active.is_(True))
        )
        active_parts = {pid for (pid,) in rows}

    created = [
        {"target_kind": k, "target_id": t, "tracked_part_id": p}
        for (k, t), p in wanted.items()
        if (k, t) not in existing
    ]
    if created:
        await db.execute(
            insert(PriceTrackingState).values(created).on_conflict_do_nothing()
        )

    repointed = 0
    for (kind, target_id), current in existing.items():
        pick = wanted.get((kind, target_id))
        if pick is not None and current not in active_parts and current != pick:
            await db.execute(
                update(PriceTrackingState)
                .where(
                    PriceTrackingState.target_kind == kind,
                    PriceTrackingState.target_id == target_id,
                )
                .values(tracked_part_id=pick)
            )
            repointed += 1

    await db.commit()
    return len(created) + repointed


def _group_fk(variant, kind: str):
    """The variant table's column pointing at its group, e.g. gpus.gpu_chipset_id."""
    column = {
        "gpu_chipset": "gpu_chipset_id",
        "psu_group": "psu_group_id",
        "ram_group": "ram_group_id",
        "storage_group": "storage_group_id",
    }[kind]
    return getattr(variant, column)


async def parts_needing_discovery(
    db: AsyncSession, limit: int, *, now: datetime | None = None
) -> list[PCPart]:
    """Tracked SKUs with no confirmed or pending binding, not searched within
    the cooldown, highest-priority part types first."""
    if limit <= 0:
        return []
    cutoff = (now or datetime.now(UTC)) - DISCOVERY_COOLDOWN
    has_binding = exists().where(
        GoogleProductBinding.part_id == PCPart.id,
        GoogleProductBinding.status.in_(("confirmed", "candidate")),
    )
    recently_searched = exists().where(
        and_(
            PriceFetch.part_id == PCPart.id,
            PriceFetch.purpose == "discovery",
            PriceFetch.fetched_at > cutoff,
        )
    )
    rows = await db.execute(
        select(PCPart)
        .join(PriceTrackingState, PriceTrackingState.tracked_part_id == PCPart.id)
        .where(PCPart.is_active.is_(True), ~has_binding, ~recently_searched)
        .distinct()
    )
    parts = list(rows.scalars().all())
    parts.sort(key=lambda p: (_PRIORITY.get(p.part_type, 2), p.part_type, p.name))
    return parts[:limit]
