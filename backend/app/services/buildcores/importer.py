"""Import a checked-out snapshot into the existing admin discovery queue.

Stable source-derived staging IDs survive renames. Reviewed records are never
reset. A transaction advisory lock serializes concurrent BuildCores imports;
the existing pending-name unique index arbitrates other discovery producers.

Every staged row records its auto-review decision under
`field_provenance._buildcores.review`, so the admin can say why an item is
waiting. Only `auto_approve=True` acts on it; see auto_review.py for the rules.
"""

from __future__ import annotations

import json
import subprocess
import uuid
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

from app.services.buildcores.convert import (
    CATEGORIES,
    LICENSE,
    REPOSITORY,
    VERSION,
    ConvertedItem,
    chipset_items,
    convert,
)


class _DryRun(Exception):
    """Raised inside the staging transaction to roll back a dry run."""


def read_snapshot(
    root: Path, categories: list[str]
) -> tuple[str, list[ConvertedItem], list[dict[str, Any]]]:
    root = root.resolve()
    revision = subprocess.check_output(
        ["git", "-C", str(root), "rev-parse", "HEAD"], text=True
    ).strip()
    dirty = subprocess.check_output(
        ["git", "-C", str(root), "status", "--porcelain", "--", "open-db"], text=True
    )
    if dirty:
        raise ValueError(
            "OpenDB checkout has local data changes; use a clean committed snapshot for reproducible provenance."
        )
    items, rejected = [], []
    for directory in categories:
        if directory not in CATEGORIES:
            raise ValueError(f"Unsupported category: {directory}")
        files = sorted((root / "open-db" / directory).glob("*.json"))
        if not files:
            raise ValueError(f"No component JSON files found in open-db/{directory}")
        for path in files:
            try:
                record = json.loads(path.read_text())
                if (
                    not isinstance(record, dict)
                    or str(uuid.UUID(record["opendb_id"])) != path.stem
                ):
                    raise ValueError("opendb_id must match the UUID filename")
                items.append(convert(record, directory, revision))
            except (ValueError, TypeError, KeyError, AttributeError) as exc:
                rejected.append(
                    {"path": str(path.relative_to(root)), "error": str(exc)}
                )
    return revision, chipset_items(items) + items, rejected


def report(
    revision: str, items: list[ConvertedItem], rejected: list[dict[str, Any]]
) -> dict[str, Any]:
    counts: dict[str, Counter[str]] = {}
    for item in items:
        counts.setdefault(item.category, Counter())[item.validation_status] += 1
    return {
        "repository": REPOSITORY,
        "revision": revision,
        "converter": VERSION,
        "license": LICENSE,
        "attribution": "Contains information from BuildCores OpenDB, available under ODC-By v1.0.",
        "counts": counts,
        "rejected": rejected,
        "items": [item.as_dict() for item in items],
    }


async def stage(
    db: AsyncSession,
    revision: str,
    items: list[ConvertedItem],
    *,
    auto_approve: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Stage items, optionally auto-approving; a dry run rolls everything back."""
    counts: Counter[str] = Counter()
    reasons: Counter[str] = Counter()
    by_category: Counter[str] = Counter()
    summary = {
        "manual_review_reasons": reasons,
        "auto_approved_by_category": by_category,
    }
    try:
        run_id = await _stage(
            db, revision, items, auto_approve, dry_run, counts, reasons, by_category
        )
    except _DryRun:
        return {"dry_run": True, **counts, **summary}
    return {"run_id": run_id, **counts, **summary}


async def _stage(
    db: AsyncSession,
    revision: str,
    items: list[ConvertedItem],
    auto_approve: bool,
    dry_run: bool,
    counts: Counter[str],
    reasons: Counter[str],
    by_category: Counter[str],
) -> str:
    # Lazy imports keep preview independent of app settings and DB libraries.
    from sqlalchemy import select, text, update
    from sqlalchemy.dialects.postgresql import insert
    from sqlalchemy.exc import DBAPIError

    from app.crud.components import _normalize
    from app.crud.discovery import get_dedup_candidates
    from app.models.discovery import DiscoveredItem, DiscoveryRun
    from app.services.buildcores.auto_review import approve, decide, load_catalog
    from app.services.discovery.dedup import match_columns, match_item

    async with db.begin():
        await db.execute(text("SELECT pg_advisory_xact_lock(734102691)"))
        run: Any = DiscoveryRun(
            run_type="hardware",
            status="running",
            pipeline_version=f"{VERSION}:{revision}",
            model_name="buildcores-opendb (no LLM)",
        )
        db.add(run)
        await db.flush()
        run_id = run.id
        # Lock pending rows against simultaneous approval while refreshing.
        # Plain rows, not ORM objects: tens of thousands of tracked instances
        # made every per-item flush rescan the whole session.
        existing: dict[Any, Any] = {
            row.id: row
            for row in await db.execute(
                select(
                    DiscoveredItem.id,
                    DiscoveredItem.category,
                    DiscoveredItem.name_normalized,
                    DiscoveredItem.review_status,
                    DiscoveredItem.extracted_fields["reference_only"]
                    .as_boolean()
                    .label("reference_only"),
                ).with_for_update()
            )
        }
        pending: dict[Any, Any] = {
            (row.category, row.name_normalized): row.id
            for row in existing.values()
            if row.review_status == "pending"
        }
        candidates = {
            category: await get_dedup_candidates(db, category)
            for category in {i.category for i in items}
        }
        catalog = await load_catalog(db)
        for item in items:
            item_id = uuid.UUID(item.id)
            old = existing.get(item_id)
            if old is not None and old.review_status != "pending":
                counts["reviewed_skipped"] += 1
                continue
            name = _normalize(str(item.extracted_fields.get("name") or ""))
            if not name:
                counts["unnamed_skipped"] += 1
                continue
            key = (item.category, name)
            if key in pending and pending[key] != item_id:
                counts["name_conflicts_skipped"] += 1
                continue
            match_id, method, score = match_item(
                item.extracted_fields["name"],
                item.extracted_fields.get("model_number"),
                candidates[item.category],
            )
            fields = dict(item.extracted_fields)
            if old is not None and old.reference_only is True:
                fields["reference_only"] = True
            decision = decide(item, match_id is not None, catalog)
            provenance = {
                **item.field_provenance,
                "_buildcores": {
                    **item.field_provenance["_buildcores"],
                    "review": {
                        "auto_approvable": decision.approve,
                        "reasons": decision.reasons,
                    },
                },
            }
            values = dict(
                run_id=run_id,
                category=item.category,
                name_normalized=name,
                model_number=fields.get("model_number"),
                extracted_fields=fields,
                field_provenance=provenance,
                source_urls=item.source_urls,
                extraction_confidence=None,
                **match_columns(item.category, match_id),
                match_method=method,
                match_score=score,
                validation_status=item.validation_status,
                validation_errors=item.validation_errors,
            )
            if old is not None:
                pending.pop((old.category, old.name_normalized), None)
                await db.execute(
                    update(DiscoveredItem)
                    .where(DiscoveredItem.id == item_id)
                    .values(**values)
                )
                counts["updated"] += 1
            else:
                inserted = await db.execute(
                    insert(DiscoveredItem)
                    .values(id=item_id, **values)
                    .on_conflict_do_nothing()
                    .returning(DiscoveredItem.id)
                )
                if inserted.scalar_one_or_none() is None:
                    counts["name_conflicts_skipped"] += 1
                    continue
                counts["inserted"] += 1
            pending[key] = item_id
            if not auto_approve:
                continue
            if decision.approve:
                try:
                    await approve(db, item_id, item, decision)
                except DBAPIError as exc:
                    decision.reasons.append(f"catalog insert failed: {exc.orig}")
                    await db.execute(
                        update(DiscoveredItem)
                        .where(DiscoveredItem.id == item_id)
                        .values(field_provenance=provenance)
                    )
                else:
                    pending.pop(key)
                    catalog.names.setdefault(
                        catalog.part_types[item.category], set()
                    ).add(name_lower(item))
                    counts["auto_approved"] += 1
                    by_category[item.category] += 1
                    continue
            counts["manual_review"] += 1
            reasons.update(decision.reasons)
        run.status = "completed"
        run.sources_checked = sum(i.category != "gpu_chipset" for i in items)
        run.items_found = len(items)
        run.items_new = counts["inserted"]
        run.finished_at = datetime.now(UTC)
        if dry_run:
            raise _DryRun
    return str(run_id)


def name_lower(item: ConvertedItem) -> str:
    return str(item.extracted_fields.get("name") or "").lower()
