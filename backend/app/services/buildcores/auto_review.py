"""Decide which staged BuildCores items can skip a human reviewer.

Nobody can hand-review ~29,000 OpenDB records, so an item is approved without
a reviewer only when every check below passes. An auto-approved part always
enters the catalog inactive: it exists for pricing and inspection, but the
recommender cannot pick it until someone switches it on in the admin.

An item stays in the manual queue when any of these hold:

- it failed validation, or the converter flagged a source placeholder
  (`review_holds`, e.g. a GPU whose memory bus width is 0);
- dedup matched an existing part, or a part of that type already has its name
  (the admin approval refuses the same collision);
- it needs a group (RAM, storage, PSU, GPU chipset) and not exactly one
  existing group fits. Groups are never created automatically. A gpu_chipset
  candidate is itself a new group, so it always waits for a person.

Group fit uses two sets of fields. IDENTITY fields must be known on both sides
and equal: they are what the existing group names are built from, plus the
compatibility fields the recommender filters on. The group's other stored
fields must not contradict a value the item knows. A value the item lacks is
inherited from the group, exactly as when a reviewer picks an existing group.
"""

from __future__ import annotations

import math
import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from app.services.buildcores.convert import ConvertedItem

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

# category -> (identity fields, fields that must not conflict)
GROUP_RULES: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "ram_kit": (
        (
            "ddr_generation",
            "speed_mhz",
            "capacity_gb",
            "modules",
            "cas_latency",
            "module_type",
        ),
        ("module_capacity_gb", "voltage", "is_ecc"),
    ),
    "storage_drive": (
        ("storage_type", "form_factor", "interface", "capacity_gb"),
        (
            "read_speed_mbps",
            "write_speed_mbps",
            "has_dram_cache",
            "endurance_tbw",
            "rpm",
        ),
    ),
    "psu": (
        ("wattage", "form_factor", "efficiency_rating", "modular"),
        (
            "is_fanless",
            "fan_size_mm",
            "pcie_8pin_connectors",
            "pcie_12pin_connectors",
            "pcie_16pin_connectors",
            "eps_connectors",
        ),
    ),
}
GROUP_KEYS = {
    "ram_kit": "ram_group_id",
    "storage_drive": "storage_group_id",
    "psu": "psu_group_id",
    "gpu_variant": "gpu_chipset_id",
}
GROUP_LABELS = {
    "ram_kit": "RAM group",
    "storage_drive": "storage group",
    "psu": "PSU group",
    "gpu_variant": "GPU chipset",
}
# Columns approval never takes from the source record.
_RESERVED = {"id", "part_type", "is_active", "created_at", "updated_at"}
# "GeForce RTX 3080" and the catalog's "RTX 3080 10GB" are the same chip; VRAM
# is compared as its own field rather than as part of the name.
_CHIP_NOISE = re.compile(r"\b(?:nvidia|amd|intel|geforce|radeon)\b|\b\d+\s*gb\b")


def chip_key(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", _CHIP_NOISE.sub("", name.lower()))


def _same(a: Any, b: Any) -> bool:
    if isinstance(a, str) and isinstance(b, str):
        return a.strip().lower() == b.strip().lower()
    if isinstance(a, float) or isinstance(b, float):
        return (
            isinstance(a, int | float)
            and isinstance(b, int | float)
            and math.isclose(a, b, abs_tol=1e-3)
        )
    return bool(a == b)


def group_fits(
    fields: dict[str, Any],
    group: dict[str, Any],
    identity: tuple[str, ...],
    other: tuple[str, ...],
) -> bool:
    for key in identity:
        if fields.get(key) is None or group.get(key) is None:
            return False
        if not _same(fields[key], group[key]):
            return False
    return all(
        fields.get(key) is None
        or group.get(key) is None
        or _same(fields[key], group[key])
        for key in other
    )


@dataclass
class Catalog:
    """The parts of the live catalog a decision reads, loaded once per import."""

    groups: dict[str, list[dict[str, Any]]]
    # part_type -> lowercased names, updated as this import approves parts.
    names: dict[str, set[str]]
    part_types: dict[str, str]

    def matching_groups(self, item: ConvertedItem) -> list[uuid.UUID]:
        rows = self.groups[item.category]
        if item.category == "gpu_variant":
            evidence = item.field_provenance["_buildcores"]["chipset_evidence"]
            chip, vram = evidence.get("chipset"), evidence.get("memory")
            if not isinstance(chip, str) or not isinstance(vram, int | float):
                return []
            vram_type = evidence.get("memory_type")
            return [
                row["id"]
                for row in rows
                if chip_key(row["name"]) == chip_key(chip)
                and row["vram_gb"] == vram
                and (
                    not isinstance(vram_type, str)
                    or row["vram_type"] is None
                    or _same(row["vram_type"], vram_type)
                )
            ]
        identity, other = GROUP_RULES[item.category]
        return [
            row["id"]
            for row in rows
            if group_fits(item.extracted_fields, row, identity, other)
        ]


@dataclass
class Decision:
    reasons: list[str]
    group_id: uuid.UUID | None = None

    @property
    def approve(self) -> bool:
        return not self.reasons


async def load_catalog(db: AsyncSession) -> Catalog:
    from sqlalchemy import func, select

    from app.crud.discovery import _PART_MODEL_BY_CATEGORY
    from app.models.pcparts import (
        GPUChipset,
        PCPart,
        PSUGroup,
        RAMGroup,
        StorageGroup,
    )

    groups: dict[str, list[dict[str, Any]]] = {}
    group_models: dict[str, Any] = {
        "ram_kit": RAMGroup,
        "storage_drive": StorageGroup,
        "psu": PSUGroup,
        "gpu_variant": GPUChipset,
    }
    for category, model in group_models.items():
        keys = [attr.key for attr in model.__mapper__.column_attrs]
        groups[category] = [
            {key: getattr(row, key) for key in keys}
            for row in (await db.execute(select(model))).scalars()
        ]
    names: dict[str, set[str]] = {}
    for part_type, name in await db.execute(
        select(PCPart.part_type, func.lower(PCPart.name))
    ):
        names.setdefault(part_type, set()).add(name)
    part_types = {
        category: str(model.__mapper__.polymorphic_identity)
        for category, model in _PART_MODEL_BY_CATEGORY.items()
    }
    return Catalog(groups, names, part_types)


def decide(item: ConvertedItem, matched: bool, catalog: Catalog) -> Decision:
    if item.category not in catalog.part_types:
        return Decision(["new GPU chipset groups are always reviewed by hand"])
    reasons = list(item.review_holds)
    if item.validation_status != "passed":
        reasons.append("failed validation")
    if matched:
        reasons.append("possible duplicate of an existing catalog part")
    name = str(item.extracted_fields.get("name") or "").lower()
    if name in catalog.names.get(catalog.part_types[item.category], set()):
        reasons.append("a part with this name already exists")
    group_id = None
    if item.category in GROUP_KEYS:
        fits = catalog.matching_groups(item)
        label = GROUP_LABELS[item.category]
        if len(fits) == 1:
            group_id = fits[0]
        elif fits:
            reasons.append(f"more than one existing {label} matches")
        else:
            reasons.append(f"no existing {label} matches")
    return Decision(reasons, group_id)


async def approve(
    db: AsyncSession, item_id: uuid.UUID, item: ConvertedItem, decision: Decision
) -> uuid.UUID:
    """Insert the part inactive and mark the queue row approved.

    Mirrors the admin approval: the same subtype columns, the group chosen by
    FK, and the audit link on the queue row. Runs in a savepoint so a row the
    database rejects falls back to manual review instead of aborting the
    whole import.
    """
    from sqlalchemy import inspect, update

    from app.crud.discovery import _PART_MODEL_BY_CATEGORY
    from app.models.discovery import DiscoveredItem

    model = _PART_MODEL_BY_CATEGORY[item.category]
    columns = {attr.key for attr in inspect(model).column_attrs} - _RESERVED
    values = {k: v for k, v in item.extracted_fields.items() if k in columns}
    if item.category in GROUP_KEYS:
        values[GROUP_KEYS[item.category]] = decision.group_id
    async with db.begin_nested():
        part = model(**values, is_active=False)
        db.add(part)
        await db.flush()
        await db.execute(
            update(DiscoveredItem)
            .where(DiscoveredItem.id == item_id)
            .values(
                review_status="approved",
                reviewed_at=datetime.now(UTC),
                created_part_id=part.id,
            )
        )
    # Keep the session small; nothing reads the part back.
    db.expunge(part)
    return uuid.UUID(str(part.id))
