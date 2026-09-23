"""Preview or stage a pinned local OpenDB checkout. See docs/buildcores-import.md."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from pathlib import Path
from typing import Any

from app.services.buildcores.convert import CATEGORIES, ConvertedItem
from app.services.buildcores.importer import read_snapshot, report, stage

logger = logging.getLogger(__name__)


async def _stage(
    revision: str, items: list[ConvertedItem], auto_approve: bool, dry_run: bool
) -> dict[str, Any]:
    from app.core.db import AsyncSessionLocal, async_engine

    try:
        async with AsyncSessionLocal() as db:
            return await stage(
                db, revision, items, auto_approve=auto_approve, dry_run=dry_run
            )
    finally:
        await async_engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source", type=Path, required=True, help="Clean BuildCores git checkout"
    )
    parser.add_argument(
        "--category",
        action="append",
        choices=list(CATEGORIES),
        help="Repeat to select categories; defaults to all PC components",
    )
    parser.add_argument(
        "--report",
        type=Path,
        required=True,
        help="JSON conversion report, including failed records",
    )
    parser.add_argument(
        "--stage",
        action="store_true",
        help="Write to discovery review queue; default is DB-free preview",
    )
    parser.add_argument(
        "--auto-approve",
        action="store_true",
        help="With --stage: approve items that pass every auto-review rule, "
        "as inactive parts assigned to an existing group",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="With --stage: run staging and auto-approval, report, then roll back",
    )
    args = parser.parse_args()
    if (args.auto_approve or args.dry_run) and not args.stage:
        parser.error("--auto-approve and --dry-run require --stage")
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    revision, items, rejected = read_snapshot(
        args.source, args.category or list(CATEGORIES)
    )
    output = report(revision, items, rejected)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(output, indent=2, allow_nan=False) + "\n")
    logger.info(
        "Snapshot %s: %s; malformed records: %d",
        revision,
        json.dumps(output["counts"]),
        len(rejected),
    )
    if args.stage:
        output["staging"] = asyncio.run(
            _stage(revision, items, args.auto_approve, args.dry_run)
        )
        args.report.write_text(json.dumps(output, indent=2, allow_nan=False) + "\n")
        logger.info("Staged: %s", json.dumps(output["staging"]))
    logger.info("Report: %s", args.report)


if __name__ == "__main__":
    main()
