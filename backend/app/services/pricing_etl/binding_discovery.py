"""Find the Google Shopping product id for a catalog SKU.

One google_shopping search per SKU, by name. Every result is run through the
gates the free-text ETL already trusts, then the survivors decide what happens:

  auto_confirm   a match good enough that a human would only rubber-stamp it
  review         plausible candidates, written for an admin to choose from
  none           nothing survived; an admin can still bind by hand

WHAT THE FIRST REAL SEARCH TAUGHT (2026-10-21, "AMD Ryzen 7 9800X3D", 40
results): the bare CPU never appeared. Google returned sibling SKUs (7800X3D,
9850X3D, 9900X3D, 9950X3D) and about 35 prebuilt PCs containing the chip. Two
consequences shaped this module:
  - Identity rules alone are not enough. A $2,749 "ASUS ROG GM700 Gaming
    Desktop AMD Ryzen 7 9800X3D" passes the model check, because it does
    contain that exact model. The whole-system disqualifier and the MSRP price
    gate are what reject it, so both are mandatory here.
  - "No binding found" is a normal outcome, not an error. The search is still
    recorded (price_fetches, purpose=discovery) so the cooldown in
    tracking.parts_needing_discovery stops it being re-bought every run.

CONTAINMENT, NOT SIMILARITY. title_match.similarity (token sort) is the wrong
measure here: Google's catalog titles append "8-Core, 16-Thread Desktop
Processor" to the name, which drags the right product down to 51-68 while a
sibling SKU scores 64. The question discovery asks is whether every word of
the part's name is in the title, which is a token-set ratio ("coverage"): 100
for both correct 7800X3D titles, 84 for the 9800X3D.

Coverage cannot tell a product from a bigger one that contains its name:
"Fractal Design North" covers "Fractal Design North XL" at 100. That is why
auto-confirm needs something that CAN tell them apart.

AUTO-CONFIRM IS DELIBERATELY NARROW. All of:
  - exactly one distinct product id survived every gate
  - Google aggregates it across sellers (multiple_sources), i.e. a catalog
    product rather than one marketplace listing
  - coverage of at least AUTO_MIN_COVERAGE
  - the identity rules recognized a model or capacity in the part's name (so
    they compared something real), or the part's model_number appears in the
    title. A case, cooler or fan with neither always goes to review.
  - the price sits within AUTO_PRICE_BAND of the part's MSRP (or street price)
  - an admin has not already rejected that product id for this part
A confirmed binding is re-checked on its first offers fetch against the title
google_product returns, so a wrong auto-confirm is caught by the next fetch
rather than living forever.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.price_tracking import GoogleProductBinding
from app.services.pricing_etl import product_identity, title_match

logger = logging.getLogger(__name__)

# Gate: an implausible price against the part's own anchor. Same ratios as
# stats.ANCHOR_MIN_RATIO / ANCHOR_MAX_RATIO.
PRICE_MIN_RATIO = 0.35
PRICE_MAX_RATIO = 2.5

# Gate: share of the part name's tokens found in the title (token-set ratio).
GATE_MIN_COVERAGE = 80.0

# Auto-confirm thresholds, tighter than the gates.
AUTO_MIN_COVERAGE = 95.0
AUTO_PRICE_BAND = (0.6, 1.6)

# A model_number this short is more likely a label we made up ("ARC-A750")
# than a manufacturer part number, and matching it proves little.
MIN_MODEL_NUMBER_LEN = 8

# How many candidates an admin is shown for one part.
MAX_REVIEW_CANDIDATES = 3

REASON_NO_PRODUCT_ID = "no_product_id"
REASON_LOW_COVERAGE = "low_coverage"
REASON_NO_PRICE = "no_price"
REASON_IMPLAUSIBLE_PRICE = "implausible_price"

DECISION_AUTO = "auto_confirm"
DECISION_REVIEW = "review"
DECISION_NONE = "none"

# Appended to the search so Google ranks the part above systems built around
# it: catalog titles say "8-Core Processor", "Graphics Card", "Mid Tower Case".
# UNVERIFIED: chosen from the titles in the first capture, not measured. The
# query text is not a frozen price condition (discovery produces no price), so
# changing these is safe; the stored raw responses show what each one returned.
_TYPE_NOUN = {
    "cpu": "processor",
    "gpu": "graphics card",
    "motherboard": "motherboard",
    "ramkit": "memory",
    "storagedrive": "ssd",
    "psu": "power supply",
    "cpucooler": "cpu cooler",
    "case": "case",
    "fan": "case fan",
    "system": "",
}


@dataclass
class PartRef:
    """What discovery needs to know about a SKU, decoupled from the ORM row."""

    id: uuid.UUID
    name: str
    manufacturer: str | None
    part_type: str
    msrp_cents: int | None = None
    street_price_cents: int | None = None
    model_number: str | None = None

    @property
    def title(self) -> str:
        """Brand plus name, the form both identity and similarity compare."""
        name = self.name.strip()
        brand = (self.manufacturer or "").strip()
        if brand and not name.lower().startswith(brand.lower()):
            return f"{brand} {name}"
        return name

    @property
    def anchor_cents(self) -> int | None:
        return self.msrp_cents or self.street_price_cents

    @classmethod
    def of(cls, part: Any) -> PartRef:
        return cls(
            id=part.id,
            name=part.name,
            manufacturer=part.manufacturer,
            part_type=part.part_type,
            msrp_cents=part.msrp_cents,
            street_price_cents=part.street_price_cents,
            model_number=part.model_number,
        )


@dataclass
class Candidate:
    product_id: str | None
    title: str
    source: str | None
    position: int | None
    price_cents: int | None
    multiple_sources: bool
    coverage: float
    similarity: float
    price_ratio: float | None
    model_number_in_title: bool = False
    rejected: str | None = None


@dataclass
class DiscoveryResult:
    query: str
    decision: str
    identity: str | None
    survivors: list[Candidate]
    rejected: list[Candidate] = field(default_factory=list)
    why_not_auto: list[str] = field(default_factory=list)

    @property
    def chosen(self) -> Candidate | None:
        return self.survivors[0] if self.decision == DECISION_AUTO else None


def discovery_query(part: PartRef) -> str:
    noun = _TYPE_NOUN.get(part.part_type, "")
    return f"{part.title} {noun}".strip()


def _price_cents(result: dict) -> int | None:
    value = result.get("extracted_price")
    if isinstance(value, int | float) and not isinstance(value, bool) and value > 0:
        return int(round(value * 100))
    return None


def coverage(part_title: str, result_title: str) -> float:
    """How much of the part's name the title contains, 0-100."""
    from rapidfuzz import fuzz  # lazy, as in title_match

    return fuzz.token_set_ratio(
        product_identity.normalize_for_similarity(part_title),
        product_identity.normalize_for_similarity(result_title),
    )


def _squash(text: str) -> str:
    return "".join(ch for ch in text.lower() if ch.isalnum())


def model_number_in(part: PartRef, title: str) -> bool:
    mpn = _squash(part.model_number or "")
    return len(mpn) >= MIN_MODEL_NUMBER_LEN and mpn in _squash(title)


def _gate(part: PartRef, result: dict) -> Candidate:
    title = str(result.get("title") or "")
    price = _price_cents(result)
    anchor = part.anchor_cents
    ratio = (price / anchor) if price and anchor else None
    covered = coverage(part.title, title)
    candidate = Candidate(
        product_id=(str(result["product_id"]) if result.get("product_id") else None),
        title=title,
        source=result.get("source"),
        position=result.get("position"),
        price_cents=price,
        multiple_sources=bool(result.get("multiple_sources")),
        coverage=round(covered, 1),
        # Kept as evidence for the reviewer; not a gate here (see header).
        similarity=round(title_match.similarity(part.title, title), 1),
        price_ratio=round(ratio, 3) if ratio is not None else None,
        model_number_in_title=model_number_in(part, title),
    )
    if candidate.product_id is None:
        candidate.rejected = REASON_NO_PRODUCT_ID
    elif (reason := title_match.disqualifier(title)) is not None:
        candidate.rejected = reason
    elif (reason := product_identity.exclusion_reason(part.title, title)) is not None:
        candidate.rejected = reason
    elif covered < GATE_MIN_COVERAGE:
        candidate.rejected = REASON_LOW_COVERAGE
    elif price is None:
        candidate.rejected = REASON_NO_PRICE
    elif ratio is not None and not (PRICE_MIN_RATIO <= ratio <= PRICE_MAX_RATIO):
        candidate.rejected = REASON_IMPLAUSIBLE_PRICE
    return candidate


def score_results(part: PartRef, payload: dict) -> DiscoveryResult:
    """A google_shopping response -> the decision and its evidence. Pure."""
    candidates = [
        _gate(part, r)
        for r in payload.get("shopping_results") or []
        if isinstance(r, dict)
    ]
    rejected = [c for c in candidates if c.rejected]

    # One entry per product id: the same product can appear at several
    # positions; keep its best-scoring appearance.
    best: dict[str, Candidate] = {}
    for c in candidates:
        if c.rejected:
            continue
        held = best.get(c.product_id)
        if held is None or (c.coverage, -(c.position or 0)) > (
            held.coverage,
            -(held.position or 0),
        ):
            best[c.product_id] = c
    survivors = sorted(
        best.values(), key=lambda c: (-c.coverage, -c.similarity, c.position or 0)
    )

    identity = product_identity.recognized_identity(part.title)
    result = DiscoveryResult(
        query=discovery_query(part),
        decision=DECISION_NONE,
        identity=identity,
        survivors=survivors[:MAX_REVIEW_CANDIDATES],
        rejected=rejected,
    )
    if not survivors:
        return result

    top = survivors[0]
    why: list[str] = []
    if len(survivors) > 1:
        why.append(f"{len(survivors)} distinct products survived")
    if not top.multiple_sources:
        why.append("single-seller listing, not an aggregated catalog product")
    if top.coverage < AUTO_MIN_COVERAGE:
        why.append(f"coverage {top.coverage} < {AUTO_MIN_COVERAGE}")
    if identity is None and not top.model_number_in_title:
        why.append(
            "nothing in the part name the identity rules can verify (no model "
            "or capacity), and its model number is not in the title"
        )
    if top.price_ratio is None:
        why.append("no MSRP or street price to check the price against")
    elif not (AUTO_PRICE_BAND[0] <= top.price_ratio <= AUTO_PRICE_BAND[1]):
        why.append(f"price ratio {top.price_ratio} outside {AUTO_PRICE_BAND}")

    result.why_not_auto = why
    result.decision = DECISION_REVIEW if why else DECISION_AUTO
    return result


def _evidence(result: DiscoveryResult, candidate: Candidate) -> dict:
    return {
        "query": result.query,
        "decision": result.decision,
        "identity": result.identity,
        "why_not_auto": result.why_not_auto,
        "candidate": asdict(candidate),
        "other_candidates": [
            c.product_id for c in result.survivors if c is not candidate
        ],
        "n_rejected": len(result.rejected),
    }


async def record_discovery(
    db: AsyncSession,
    *,
    part_id: uuid.UUID,
    fetch_id: uuid.UUID,
    result: DiscoveryResult,
) -> str:
    """Write the decision as binding rows. Returns what actually happened,
    which can be weaker than the decision: an auto-confirm of a product id an
    admin already rejected for this part, or for a part that already has a
    confirmed binding, is written as a candidate instead."""
    if result.decision == DECISION_NONE:
        await db.commit()
        return DECISION_NONE

    rows = await db.execute(
        select(
            GoogleProductBinding.google_product_id, GoogleProductBinding.status
        ).where(GoogleProductBinding.part_id == part_id)
    )
    existing = dict(rows.tuples().all())
    has_confirmed = "confirmed" in existing.values()

    outcome = DECISION_REVIEW
    written = 0
    for candidate in result.survivors:
        if candidate.product_id in existing:
            continue
        written += 1
        confirm = (
            result.decision == DECISION_AUTO
            and candidate is result.chosen
            and not has_confirmed
        )
        await db.execute(
            insert(GoogleProductBinding)
            .values(
                id=uuid.uuid4(),
                part_id=part_id,
                google_product_id=candidate.product_id,
                status="confirmed" if confirm else "candidate",
                confirmed_by="auto" if confirm else None,
                google_title=candidate.title,
                match_evidence=_evidence(result, candidate),
                discovery_fetch_id=fetch_id,
            )
            .on_conflict_do_nothing()
        )
        if confirm:
            outcome = DECISION_AUTO
    if written == 0:
        # Every survivor is already known for this part (most often: rejected
        # by an admin). Nothing new to review.
        outcome = DECISION_NONE
    if result.decision == DECISION_AUTO and outcome != DECISION_AUTO:
        logger.info(
            "binding discovery for part %s: auto-confirm downgraded to review "
            "(already rejected, already present, or part already confirmed)",
            part_id,
        )
    await db.commit()
    return outcome
