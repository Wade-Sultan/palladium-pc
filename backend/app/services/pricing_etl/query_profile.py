"""The frozen SerpApi query conditions every product-bound fetch is made under.

WHY FROZEN. A price series is only a series if every point was measured the
same way. Country, language, cache behaviour and engine all change what Google
returns, so they are fixed here, once, and nothing else in the ETL is allowed
to add or override a parameter. The only per-call value is the thing being
looked up: a product id, or (for binding discovery) a search query.

CHANGING ANYTHING HERE MEANS BUMPING QUERY_PROFILE_VERSION. Every fetch row
stores the version and a hash of these conditions, so a change shows up in the
data as a visible break in the series instead of a silent shift in level.
test_query_profile.py pins the hash for exactly that reason: an edit that
forgets the bump fails a test.

WHAT CANNOT BE PINNED. `google_product` documents no `location` or `device`
parameter, so the geography behind a fetch is whatever SerpApi's proxy uses.
Each fetch keeps SerpApi's search id, which is the handle on that if prices
ever look regionally odd.

`no_cache` is on so a fetch is always a fresh measurement at the time recorded
against it, not a copy of one made up to an hour earlier by someone else.
"""

from __future__ import annotations

import hashlib
import json

QUERY_PROFILE_VERSION = 1

ENGINE_OFFERS = "google_product"
ENGINE_DISCOVERY = "google_shopping"

_FROZEN: dict[str, dict[str, str]] = {
    # Per-store offers for one bound Google product. offer_view is deliberately
    # left out of v1: SerpApi documents it as adding ratings, reviews and
    # variants, none of which a price needs, and an undocumented effect on the
    # store list would be a condition nobody chose.
    ENGINE_OFFERS: {
        "engine": ENGINE_OFFERS,
        "gl": "us",
        "hl": "en",
        "no_cache": "true",
    },
    # Binding discovery only: finds the product id for a SKU by name. Never
    # used for a price.
    ENGINE_DISCOVERY: {
        "engine": ENGINE_DISCOVERY,
        "gl": "us",
        "hl": "en",
        "google_domain": "google.com",
        "device": "desktop",
        "no_cache": "true",
    },
}


def frozen(engine: str) -> dict[str, str]:
    """A copy of one engine's fixed conditions."""
    return dict(_FROZEN[engine])


def conditions_hash(engine: str) -> str:
    """SHA-256 over the engine's fixed conditions and the profile version.

    Excludes the per-call value on purpose: one hash per engine across every
    run is the evidence that the conditions never moved.
    """
    payload = {"version": QUERY_PROFILE_VERSION, "params": _FROZEN[engine]}
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def offers_params(google_product_id: str) -> dict[str, str]:
    if not google_product_id.strip():
        raise ValueError("google_product_id is empty")
    return {**frozen(ENGINE_OFFERS), "product_id": google_product_id.strip()}


def discovery_params(query: str) -> dict[str, str]:
    if not query.strip():
        raise ValueError("discovery query is empty")
    return {**frozen(ENGINE_DISCOVERY), "q": query.strip()}
