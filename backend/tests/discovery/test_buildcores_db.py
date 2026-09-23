"""Opt-in PostgreSQL tests. Each run owns and drops a unique scratch schema."""

from __future__ import annotations

import asyncio
import os
import uuid

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.base import Base
from app.models.discovery import DiscoveredItem, DiscoveryRun
from app.models.pcparts import GPU, PSU, Fan, PCPart, RAMGroup, RAMKit, StorageDrive
from app.services.buildcores.convert import convert
from app.services.buildcores.importer import stage

URL = os.environ.get("BUILDCORES_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not URL, reason="Set BUILDCORES_TEST_DATABASE_URL to a scratch PostgreSQL database"
)


def test_staging_idempotency_review_preservation_matching_and_rollback():
    asyncio.run(_scratch(_exercise))


def test_auto_approval_creates_inactive_grouped_parts_and_dry_run_rolls_back():
    asyncio.run(_scratch(_auto_approve))


async def _scratch(body):
    schema = "buildcores_test_" + uuid.uuid4().hex
    engine = create_async_engine(
        URL, connect_args={"server_settings": {"search_path": schema}}
    )
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with engine.begin() as connection:
            await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
            tables = {
                DiscoveredItem.__table__,
                DiscoveryRun.__table__,
                *(m.__table__ for m in (Fan, RAMKit, GPU, PSU, StorageDrive)),
            }
            while True:
                dependencies = {
                    fk.column.table for table in tables for fk in table.foreign_keys
                }
                if dependencies <= tables:
                    break
                tables |= dependencies
            await connection.run_sync(
                lambda sync: Base.metadata.create_all(sync, tables=list(tables))
            )
        await body(factory)
    finally:
        async with engine.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        await engine.dispose()


async def _auto_approve(factory):
    def ram(cas_latency):
        return convert(
            {
                "opendb_id": str(uuid.uuid4()),
                "metadata": {"name": f"Kit CL{cas_latency}"},
                "ram_type": "DDR5",
                "speed": 6000,
                "capacity": 32,
                "modules": {"quantity": 2, "capacity_gb": 16},
                "cas_latency": cas_latency,
                "registered": "Unbuffered",
                "form_factor": "288-pin DIMM",
            },
            "RAM",
            "a" * 40,
        )

    fan = convert(
        {"opendb_id": str(uuid.uuid4()), "metadata": {"name": "Fan"}, "size": 120},
        "CaseFan",
        "a" * 40,
    )
    grouped, ungrouped = ram(36), ram(30)
    async with factory() as db:
        group = RAMGroup(
            name="DDR5-6000 32GB (2x16)",
            ddr_generation="ddr5",
            speed_mhz=6000,
            capacity_gb=32,
            modules=2,
            cas_latency=36,
            module_type="udimm",
        )
        db.add(group)
        await db.commit()
        items = [fan, grouped, ungrouped]
        result = await stage(db, "a" * 40, items, auto_approve=True, dry_run=True)
        assert result["dry_run"] and result["auto_approved"] == 2
        assert await db.get(DiscoveredItem, uuid.UUID(fan.id)) is None
        assert (await db.execute(select(PCPart))).scalars().all() == []
        await db.commit()

        result = await stage(db, "a" * 40, items, auto_approve=True)
        assert result["auto_approved"] == 2 and result["manual_review"] == 1
        assert result["manual_review_reasons"] == {"no existing RAM group matches": 1}
        kit = await db.get(DiscoveredItem, uuid.UUID(grouped.id))
        assert kit.review_status == "approved"
        part = await db.get(RAMKit, kit.created_part_id)
        assert part.is_active is False and part.ram_group_id == group.id
        waiting = await db.get(DiscoveredItem, uuid.UUID(ungrouped.id))
        assert waiting.review_status == "pending"
        assert waiting.field_provenance["_buildcores"]["review"]["reasons"] == [
            "no existing RAM group matches"
        ]
        await db.commit()
        # Approved rows are left alone on the next import.
        result = await stage(db, "b" * 40, items, auto_approve=True)
        assert result["reviewed_skipped"] == 2 and "auto_approved" not in result


async def _exercise(factory):
    source = {
        "opendb_id": str(uuid.uuid4()),
        "metadata": {"name": "Test fan", "part_numbers": ["FAN-120"]},
        "size": 120,
    }
    item = convert(source, "CaseFan", "a" * 40)
    async with factory() as db:
        catalog_part = Fan(name="Test fan", size_mm=120, model_number="FAN-120")
        db.add(catalog_part)
        await db.commit()
        result = await stage(db, "a" * 40, [item])
        assert result["inserted"] == 1
        result = await stage(db, "a" * 40, [item])
        assert result["updated"] == 1
        saved = await db.get(DiscoveredItem, uuid.UUID(item.id))
        assert saved.matched_part_id == catalog_part.id
        saved.extracted_fields = {**saved.extracted_fields, "reference_only": True}
        await db.commit()
        source["metadata"]["name"] = "Renamed test fan"
        renamed = convert(source, "CaseFan", "b" * 40)
        await stage(db, "b" * 40, [renamed])
        await db.refresh(saved)
        assert saved.extracted_fields["reference_only"] is True
        assert saved.extracted_fields["name"] == "Renamed test fan"
        saved.review_status = "approved"
        await db.commit()
        result = await stage(db, "c" * 40, [item])
        assert result["reviewed_skipped"] == 1
        await db.refresh(saved)
        assert saved.extracted_fields["name"] == "Renamed test fan"
        await db.commit()

        # A second source identity with a pending name must not overwrite it.
        source["opendb_id"] = str(uuid.uuid4())
        other = convert(source, "CaseFan", "b" * 40)
        await stage(db, "b" * 40, [other])
        source["opendb_id"] = str(uuid.uuid4())
        collision = convert(source, "CaseFan", "b" * 40)
        result = await stage(db, "b" * 40, [collision])
        assert result["name_conflicts_skipped"] == 1

        # Failure rolls back the run and all preceding inserts together.
        source["metadata"]["name"] = "Will roll back"
        valid = convert(source, "CaseFan", "b" * 40)
        invalid = convert(
            {**source, "opendb_id": str(uuid.uuid4())}, "CaseFan", "b" * 40
        )
        invalid.id = "not-a-uuid"
        runs_before = len((await db.execute(select(DiscoveryRun))).scalars().all())
        await db.commit()
        with pytest.raises(ValueError):
            await stage(db, "b" * 40, [valid, invalid])
        assert await db.get(DiscoveredItem, uuid.UUID(valid.id)) is None
        assert (
            len((await db.execute(select(DiscoveryRun))).scalars().all()) == runs_before
        )
        # Staging has never inserted into the actual parts catalog.
        assert len((await db.execute(select(PCPart))).scalars().all()) == 1
