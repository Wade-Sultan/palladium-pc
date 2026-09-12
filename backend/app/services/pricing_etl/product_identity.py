"""Product identity checks that fuzzy title similarity cannot provide.

Recognized processor families must match exactly, including SKU suffixes.
Capacity and memory-kit checks use the specifications stated in the query.
Unrecognized model naming schemes still use the caller's similarity gate;
these rules are intentionally not a universal catalog/model-number parser.
"""

from __future__ import annotations

import re
import unicodedata
from decimal import Decimal

REASON_MODEL_MISMATCH = "model_mismatch"
REASON_MODEL_MISSING = "model_missing"
REASON_CAPACITY_MISMATCH = "capacity_mismatch"
REASON_CAPACITY_MISSING = "capacity_missing"
REASON_MEMORY_SPEC_MISMATCH = "memory_spec_mismatch"

# Restrict suffixes to each family: board names such as "Gaming X" and "OC"
# must not become part of a chipset's identity. Boundaries prevent matching
# the base number inside an unrecognized attached suffix.
_MODEL_PATTERNS = [
    re.compile(
        r"\b(?P<family>rtx|gtx)[\s-]*(?P<number>\d{3,4})"
        r"[\s-]*(?P<suffix>ti[\s-]*super|super|ti)?\b"
    ),
    re.compile(
        r"\b(?P<family>rx)[\s-]*(?P<number>\d{3,4})" r"[\s-]*(?P<suffix>xtx|xt|gre)?\b"
    ),
    re.compile(r"\b(?P<family>arc)[\s-]*(?P<number>[ab]\d{3})\b" r"(?P<suffix>)"),
    re.compile(
        r"\b(?P<family>ryzen)\s+(?:[3579]\s+)?(?P<number>\d{4})"
        r"[\s-]*(?P<suffix>x3d|xt|x|ge|gt|g|f|hx|hs|h|u)?\b"
    ),
    re.compile(
        r"\b(?P<family>i[3579])[\s-]*(?P<number>\d{4,5})"
        r"[\s-]*(?P<suffix>kf|ks|k|f|t|hx|hk|h|u)?\b"
    ),
    re.compile(
        r"\bcore\s+(?P<family>(?:ultra\s+)?[3579])[\s-]+"
        r"(?P<number>\d{3})[\s-]*(?P<suffix>kf|k|f|t|hx|h|u|v)?\b"
    ),
    re.compile(
        r"\b(?P<family>threadripper(?:\s+pro)?)\s+(?P<number>\d{4})"
        r"[\s-]*(?P<suffix>wx|x)?\b"
    ),
]

_CAPACITY = re.compile(r"\b(\d+(?:\.\d+)?)\s*(gb|tb)\b")
_KIT = re.compile(r"\b(\d+)\s*[x×]\s*(\d+(?:\.\d+)?)\s*(gb|tb)\b")
_DDR = re.compile(r"\bddr[\s-]*([3456])\b")
_MEMORY_SPEED = re.compile(r"\b(\d{3,5})\s*(?:mhz|mt/s)\b|\bddr[3456][\s-]+(\d{3,5})\b")
_LATENCY = re.compile(r"\bcl[\s-]*(\d{2,3})\b")


def _normalize(title: str) -> str:
    title = title.replace("™", "").replace("®", "")
    title = unicodedata.normalize("NFKC", title).casefold()
    return re.sub(r"[‐‑‒–—−]", "-", title)


def normalize_for_similarity(title: str) -> str:
    """Make case and SKU spacing irrelevant to the companion fuzzy gate."""
    title = _normalize(title)
    for pattern in _MODEL_PATTERNS:
        title = pattern.sub(
            lambda m: " ".join(
                (m["family"], m["number"], re.sub(r"[\s-]+", "", m["suffix"] or ""))
            )
            + " ",
            title,
        )
    return re.sub(r"[\W_]+", " ", title).strip()


def _models(title: str) -> set[tuple[str, str, str]]:
    return {
        (
            re.sub(r"[\s-]+", "", match["family"]),
            match["number"],
            re.sub(r"[\s-]+", "", match["suffix"] or ""),
        )
        for pattern in _MODEL_PATTERNS
        for match in pattern.finditer(title)
    }


def _gb(amount: str, unit: str) -> Decimal:
    return Decimal(amount) * (1024 if unit == "tb" else 1)


def _capacities(title: str) -> set[Decimal]:
    # A 32GB (2x16GB) kit has 32GB total, not two competing capacities.
    capacities = {
        Decimal(match[1]) * _gb(match[2], match[3]) for match in _KIT.finditer(title)
    }
    title = _KIT.sub(" ", title)
    capacities.update(_gb(match[1], match[2]) for match in _CAPACITY.finditer(title))
    return capacities


def exclusion_reason(part_title: str, result_title: str) -> str | None:
    expected = _normalize(part_title)
    actual = _normalize(result_title)

    expected_models = _models(expected)
    actual_models = _models(actual)
    if expected_models:
        if not actual_models:
            return REASON_MODEL_MISSING
        # Set equality also rejects a title advertising several different
        # models, even when the requested one is among them.
        if actual_models != expected_models:
            return REASON_MODEL_MISMATCH

    expected_capacity = _capacities(expected)
    if expected_capacity:
        actual_capacity = _capacities(actual)
        if not actual_capacity:
            return REASON_CAPACITY_MISSING
        if actual_capacity != expected_capacity:
            return REASON_CAPACITY_MISMATCH

    expected_ddr = set(_DDR.findall(expected))
    if expected_ddr:
        # A missing detail is not an explicit contradiction. Model and total
        # capacity above are mandatory when known; secondary RAM specs only
        # reject conflicting evidence.
        for pattern in (_DDR, _MEMORY_SPEED, _LATENCY):
            wanted = {"".join(m.groups(default="")) for m in pattern.finditer(expected)}
            found = {"".join(m.groups(default="")) for m in pattern.finditer(actual)}
            if wanted and found and wanted != found:
                return REASON_MEMORY_SPEC_MISMATCH
        wanted_modules = {m[1] for m in _KIT.finditer(expected)}
        found_modules = {m[1] for m in _KIT.finditer(actual)}
        if wanted_modules and found_modules and wanted_modules != found_modules:
            return REASON_MEMORY_SPEC_MISMATCH

    return None
