"""Checks that the product in a google_product response is the bound part.

Both the scheduled fetch (scheduler.fetch_target) and the re-parse of a
stored response (offers.reparse_fetch) use this check. A response that fails
it gets no estimate.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.services.pricing_etl import binding_discovery, product_identity, title_match

if TYPE_CHECKING:
    from app.models.pcparts import PCPart
    from app.services.pricing_etl.offers import ParsedFetch

# Below this name coverage, a returned product title is not this part.
VERIFY_MIN_COVERAGE = 80.0

REASON_PRODUCT_MISMATCH = "product_mismatch"


def verify_product(part: PCPart, product_title: str | None) -> str | None:
    """Return the reason the product is not this part, or None if it matches.
    A missing title returns None: nothing contradicts the binding."""
    if not product_title:
        return None
    ref = binding_discovery.PartRef.of(part)
    reason = title_match.disqualifier(product_title)
    if reason is None:
        reason = product_identity.exclusion_reason(ref.title, product_title)
    if (
        reason is None
        and binding_discovery.coverage(ref.title, product_title) < VERIFY_MIN_COVERAGE
    ):
        reason = binding_discovery.REASON_LOW_COVERAGE
    return reason


def reject_mismatch(part: PCPart, parsed: ParsedFetch) -> str | None:
    """Remove the estimate from `parsed` if its product is not `part`.
    The offers stay as evidence. Return the mismatch reason, or None."""
    mismatch = verify_product(part, parsed.product_title)
    if mismatch:
        parsed.estimate_cents = None
        parsed.estimate_method = REASON_PRODUCT_MISMATCH
    return mismatch
