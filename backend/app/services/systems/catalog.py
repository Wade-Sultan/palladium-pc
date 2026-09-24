"""Everything fit.py needs from the database, gathered for one profile.

Kept apart from fit.py so the rules stay pure and testable without Postgres,
and so the one place that spends an embedding call (catalog requirements) is
easy to see. That call only happens on the memory path; a creative profile
has no model names to resolve.

DEGRADES TO "NO OFFER". A failure anywhere here returns None and the turn goes
on to build a custom PC exactly as it did before systems existed. An offer is
an addition to the flow, never something the flow can fail on.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.db import AsyncSessionLocal
from app.models.pcparts import GPUChipset
from app.models.systems import System
from app.schemas.chat import BuildProfile
from app.services.systems.fit import Assessment, DiscreteGpu, SystemOption, assess

logger = logging.getLogger(__name__)


def _option(system: System) -> SystemOption | None:
    price = system.street_price_cents or system.msrp_cents
    family = system.family
    if not price or family is None:
        return None
    return SystemOption(
        part_id=str(system.id),
        name=system.name,
        manufacturer=system.manufacturer,
        family_id=str(family.id),
        family_name=family.name,
        platform=family.platform,
        gpu_backend=family.gpu_backend,
        os=family.os,
        chip=system.chip,
        unified_memory_gb=system.unified_memory_gb,
        gpu_memory_gb=system.gpu_addressable_memory_gb,
        bandwidth_gbps=system.memory_bandwidth_gbps,
        storage_gb=system.storage_gb,
        price_cents=price,
        suited_for=tuple(family.suited_for or ()),
        image_url=system.image_url,
        image_credit=system.image_credit,
        summary=family.summary,
        strengths=tuple(family.strengths or ()),
        limitations=tuple(family.limitations or ()),
    )


async def load_systems(db) -> list[SystemOption]:
    rows = (
        (
            await db.execute(
                select(System)
                .where(System.is_active == True)  # noqa: E712
                .options(selectinload(System.family))
            )
        )
        .scalars()
        .all()
    )
    return [o for o in (_option(r) for r in rows) if o is not None]


async def load_gpus(db) -> list[DiscreteGpu]:
    rows = (
        await db.execute(
            select(
                GPUChipset.name, GPUChipset.vram_gb, GPUChipset.street_price_cents
            ).where(GPUChipset.street_price_cents.is_not(None))
        )
    ).all()
    return [DiscreteGpu(name=n, vram_gb=v, price_cents=p) for n, v, p in rows]


def _reference_split(build: dict | None) -> tuple[int | None, int]:
    """(total, GPU share) of a reference build, in cents."""
    if not build:
        return None, 0
    gpu = sum(
        int(p.get("approx_price") or 0)
        for p in build.get("parts") or []
        if (p.get("component") or "").upper() == "GPU"
    )
    return int(build.get("total_approx") or 0) or None, gpu


async def assess_profile(
    profile: BuildProfile,
    reference_build: Callable[[], Awaitable[dict | None]],
) -> Assessment | None:
    """The system offer for this profile, or None. Never raises.

    `reference_build` is only awaited once there are systems to compare, so a
    catalog with none costs this turn one indexed query and nothing else.
    """
    from app.services import chat_pipeline as cp
    from app.services.systems.fit import excluded

    if excluded(profile):
        return None
    try:
        async with AsyncSessionLocal() as db:
            systems = await load_systems(db)
            if not systems:
                return None
            budget = await cp._budget_for_async(profile, db)

            floor: int | None = None
            backends: set[str] = set()
            gpus: list[DiscreteGpu] = []
            if profile.primary_use == "ai":
                gpus = await load_gpus(db)
                floor, backends = await _catalog_floor(db, profile)

        total, gpu_share = _reference_split(await reference_build())
        return assess(
            profile,
            systems,
            gpus,
            budget_usd=budget,
            catalog_floor_gb=floor,
            catalog_backends=backends,
            platform_cents=(total or 0) - gpu_share,
            reference_total_cents=total,
            reference_gpu_cents=gpu_share,
        )
    except Exception:
        logger.warning("system assessment failed; building custom", exc_info=True)
        return None


async def _catalog_floor(db, profile: BuildProfile) -> tuple[int | None, set[str]]:
    from app.services.recommender.catalog_match import resolve_requirements

    terms: list[Any] = list(profile.workloads or [])
    if not terms:
        return None, set()
    req = await resolve_requirements(db, terms, ai_workload=profile.ai_workload)
    return req.min_vram_gb, set(req.gpu_backends)
