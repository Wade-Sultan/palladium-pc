"""Resolve publisher-named hardware without confusing neighboring SKUs."""

import re
import uuid

from app.services.discovery.dedup import CatalogCandidate


def reference_key(name: str) -> str:
    # Only remove vendor/description words, never model numbers or suffixes.
    name = re.sub(
        r"\b(?:amd|intel|nvidia|geforce|radeon|processor|desktop|graphics|card)\b",
        "",
        name.casefold(),
    )
    return re.sub(r"[^a-z0-9]", "", name)


def match_reference(name: str, candidates: list[CatalogCandidate]) -> uuid.UUID | None:
    matches = {c.id for c in candidates if reference_key(c.name) == reference_key(name)}
    return next(iter(matches)) if len(matches) == 1 else None
