"""Turn a stored google_product response into offers, history and one estimate.

WHAT A PRICE IS HERE. The item price a store lists: pre-tax, without shipping,
and not conditional on a coupon, a rebate or a membership. The first real
capture (tests/pricing/fixtures/serpapi/google_product_*.json) settled the
first two: every store reports `"additional_costs": "+tax"` and gives shipping
as its own field, so `extracted_price` is already pre-tax and shipping-free.
An ordinary sale (`original_price` above `price`) is a real public price and
counts.

WHAT IS NOT YET SEEN IN REAL DATA. No coupon, rebate, membership or
used/refurbished offer appeared in that capture. The rules for them below are
conservative text checks written ahead of the evidence, and they are the part
most likely to need revising. That is why PARSER_VERSION exists and why
responses are stored raw: when a real example arrives, the fix is a version
bump and a re-parse (reparse_fetch), not a lost history. Where the text only
says a coupon or rebate is *available*, the offer is kept and flagged, since
the listed price is then the pre-coupon one. Only text saying the price is
*after* or *with* one excludes it.

THE ESTIMATE, sized for 3 stores. google_product shows 3 stores per page and
each further page is another search, so the old rule (3 usable samples or no
price) would discard a fetch every time one offer was excluded. Instead:
  2+ usable offers   median of them
  1 usable offer     only if it sits inside Google's price_range, which is a
                     smoothed "typical price" band and the one independent
                     check available on a single number
  0                  no estimate; the last price carries forward
Offers far outside the band are excluded first, the way stats.py rejects
outliers. The band is never published as the price itself.
"""

from __future__ import annotations

import logging
import math
import re
import statistics
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.price_tracking import (
    PriceFetch,
    PriceHistoryPoint,
    PriceMerchantRule,
    PriceOffer,
)

logger = logging.getLogger(__name__)

PARSER_VERSION = 1

# Outlier band around Google's price_range: an offer above high * 1.75 or below
# low * 0.5 is excluded. Same ratios as stats.BAND_MAX_RATIO / BAND_MIN_RATIO:
# wide enough for a real sale or a real shortage, aimed at mis-listed bundles.
BAND_HIGH_RATIO = 1.75
BAND_LOW_RATIO = 0.5

# How far outside the band a lone offer may sit and still be accepted. Not
# zero, because the band lags the market: in the first capture Best Buy's live
# $420.00 sat 1% above a $416 top.
LONE_OFFER_TOLERANCE = 0.05

# Exclusion reasons and flags written to price_offers.
REASON_NO_PRICE = "no_price"
REASON_NOT_NEW = "not_new"
REASON_COUPON_PRICE = "coupon_price"
REASON_REBATE_PRICE = "rebate_price"
REASON_MEMBERSHIP_PRICE = "membership_price"
REASON_MEMBERSHIP_MERCHANT = "membership_merchant"
REASON_MERCHANT_EXCLUDED = "merchant_excluded"
REASON_ABOVE_BAND = "above_typical_range"
REASON_BELOW_BAND = "below_typical_range"

FLAG_SALE = "sale"
FLAG_GIFT = "gift_promo"
FLAG_COUPON_AVAILABLE = "coupon_available"
FLAG_REBATE_AVAILABLE = "rebate_available"

_CONDITIONS = (
    (
        re.compile(r"\b(refurbished|renewed|remanufactured|reconditioned)\b"),
        "refurbished",
    ),
    (re.compile(r"\bopen[\s-]?box\b"), "open_box"),
    (re.compile(r"\b(used|pre[\s-]?owned|second[\s-]?hand)\b"), "used"),
)
_COUPON_PRICE = re.compile(
    r"\b(with|after|using)\s+(a\s+|the\s+)?(digital\s+)?(coupon|promo\s+code|code)\b"
    r"|\bcoupon\s+applied\b"
)
_REBATE_PRICE = re.compile(r"\b(with|after)\s+(a\s+)?(mail[\s-]?in\s+)?rebate\b")
_MEMBERSHIP_PRICE = re.compile(
    r"\bmember(ship)?s?'?\s+(price|pricing|only|exclusive|deal)\b"
    r"|\bwith\s+(a\s+)?(paid\s+)?membership\b"
    r"|\bmembers\s+only\b"
)
_COUPON_MENTION = re.compile(r"\b(coupon|promo\s+code)\b")
_REBATE_MENTION = re.compile(r"\brebate\b")
# "Free ASRock Pro 850B Power Supply" is a gift; "Free delivery" is not.
_GIFT = re.compile(
    r"^free\s+(?!(\w+\s+)?(delivery|shipping|returns?|pickup|pick-up|"
    r"\d+[\s-]?day|installation|assembly|setup|gift\s+wrap))"
)
_MONEY = re.compile(r"\$\s*([\d,]+(?:\.\d{1,2})?)")


@dataclass
class ParsedOffer:
    position: int | None
    merchant_name: str | None
    merchant_id: str | None
    title: str | None
    link: str | None
    price_cents: int | None
    original_price_cents: int | None
    shipping_cents: int | None
    total_cents: int | None
    condition: str = "new"
    flags: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)
    included: bool = True
    exclusion_reason: str | None = None

    def exclude(self, reason: str) -> None:
        if self.included:
            self.included = False
            self.exclusion_reason = reason


@dataclass(frozen=True)
class HistoryPoint:
    merchant_name: str
    price_date: date
    price_cents: int


@dataclass
class ParsedFetch:
    product_title: str | None
    offers: list[ParsedOffer]
    band: tuple[int, int] | None
    history: list[HistoryPoint]
    estimate_cents: int | None
    estimate_method: str

    @property
    def n_used(self) -> int:
        return sum(1 for o in self.offers if o.included)


# --- small parsers --------------------------------------------------------------


def _cents(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int | float):
        return int(round(value * 100)) if value > 0 else None
    if isinstance(value, str):
        m = _MONEY.search(value)
        if m:
            return int(round(float(m.group(1).replace(",", "")) * 100))
    return None


def _shipping_cents(store: dict) -> int | None:
    for key in ("shipping_extracted", "extracted_shipping"):
        if isinstance(store.get(key), int | float):
            return int(round(store[key] * 100))
    text = store.get("shipping")
    if isinstance(text, str):
        if text.strip().lower().startswith("free"):
            return 0
        return _cents(text)
    return None


def parse_band(value: Any) -> tuple[int, int] | None:
    """'$349-$416' (or with an en dash, or one figure) -> (34900, 41600)."""
    if not isinstance(value, str):
        return None
    found = [int(round(float(m.replace(",", "")) * 100)) for m in _MONEY.findall(value)]
    found = [c for c in found if c > 0]
    if not found or len(found) > 2:
        return None
    low, high = min(found), max(found)
    return low, high


def _parse_date(text: Any) -> date | None:
    if not isinstance(text, str):
        return None
    cleaned = text.strip().replace("Sept ", "Sep ")
    for fmt in ("%b %d, %Y", "%B %d, %Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(cleaned, fmt).date()
        except ValueError:
            continue
    return None


def parse_history(price_insights: Any) -> list[HistoryPoint]:
    """price_insights.stores[].prices[] -> points; the last price reported for
    a (store, date) wins, unparseable rows are skipped rather than guessed."""
    if not isinstance(price_insights, dict):
        return []
    points: dict[tuple[str, date], int] = {}
    for store in price_insights.get("stores") or []:
        name = (store or {}).get("name")
        if not name:
            continue
        for row in store.get("prices") or []:
            day = _parse_date((row or {}).get("date"))
            cents = _cents((row or {}).get("price"))
            if day is not None and cents is not None:
                points[(name, day)] = cents
    return [HistoryPoint(n, d, c) for (n, d), c in sorted(points.items())]


# --- the rules ------------------------------------------------------------------


def _text_of(store: dict) -> str:
    parts = [store.get("title"), store.get("tag"), store.get("discount")]
    parts += list(store.get("details_and_offers") or [])
    return " | ".join(p for p in parts if isinstance(p, str)).lower()


def _classify(
    offer: ParsedOffer, store: dict, merchant_rules: list[tuple[str, str]]
) -> None:
    text = _text_of(store)
    details = [
        d.lower() for d in store.get("details_and_offers") or [] if isinstance(d, str)
    ]

    if offer.price_cents is None:
        offer.exclude(REASON_NO_PRICE)

    for pattern, condition in _CONDITIONS:
        if pattern.search(text):
            offer.condition = condition
            offer.exclude(REASON_NOT_NEW)
            break

    name = (offer.merchant_name or "").lower()
    for merchant_pattern, rule in merchant_rules:
        if merchant_pattern and merchant_pattern in name:
            offer.exclude(
                REASON_MEMBERSHIP_MERCHANT
                if rule == "membership"
                else REASON_MERCHANT_EXCLUDED
            )
            break

    if _MEMBERSHIP_PRICE.search(text):
        offer.exclude(REASON_MEMBERSHIP_PRICE)
    if _COUPON_PRICE.search(text):
        offer.exclude(REASON_COUPON_PRICE)
    elif _COUPON_MENTION.search(text):
        offer.flags.append(FLAG_COUPON_AVAILABLE)
    if _REBATE_PRICE.search(text):
        offer.exclude(REASON_REBATE_PRICE)
    elif _REBATE_MENTION.search(text):
        offer.flags.append(FLAG_REBATE_AVAILABLE)

    if any(_GIFT.search(d) for d in details):
        offer.flags.append(FLAG_GIFT)
    if (
        offer.original_price_cents
        and offer.price_cents
        and offer.original_price_cents > offer.price_cents
    ):
        offer.flags.append(FLAG_SALE)


def _apply_band(offers: list[ParsedOffer], band: tuple[int, int] | None) -> None:
    if band is None:
        return
    low, high = band
    for o in offers:
        if not o.included or o.price_cents is None:
            continue
        if o.price_cents > high * BAND_HIGH_RATIO:
            o.exclude(REASON_ABOVE_BAND)
        elif o.price_cents < low * BAND_LOW_RATIO:
            o.exclude(REASON_BELOW_BAND)


def estimate(prices: list[int], band: tuple[int, int] | None) -> tuple[int | None, str]:
    if len(prices) >= 2:
        # Half-up rounding: statistics.median of an even count can land on .5.
        return math.floor(statistics.median(prices) + 0.5), f"median_of_{len(prices)}"
    if len(prices) == 1:
        if band is None:
            return None, "single_no_band"
        low, high = band
        lone = prices[0]
        if (
            low * (1 - LONE_OFFER_TOLERANCE)
            <= lone
            <= high * (1 + LONE_OFFER_TOLERANCE)
        ):
            return lone, "single_in_band"
        return None, "single_outside_band"
    return None, "no_usable_offers"


def parse_product_response(
    payload: dict, merchant_rules: list[tuple[str, str]] | None = None
) -> ParsedFetch:
    """A google_product response -> offers (every store, kept or not), Google's
    band, the per-store history, and the estimate. Pure: no I/O."""
    rules = [(p.lower(), r) for p, r in (merchant_rules or [])]
    product = payload.get("product_results") or {}
    offers: list[ParsedOffer] = []
    for store in product.get("stores") or []:
        if not isinstance(store, dict):
            continue
        offer = ParsedOffer(
            position=store.get("position"),
            merchant_name=store.get("name"),
            merchant_id=(
                str(store["merchant_id"]) if store.get("merchant_id") else None
            ),
            title=store.get("title"),
            link=store.get("link"),
            price_cents=_cents(store.get("extracted_price"))
            or _cents(store.get("price")),
            original_price_cents=_cents(store.get("extracted_original_price"))
            or _cents(store.get("original_price")),
            shipping_cents=_shipping_cents(store),
            total_cents=_cents(store.get("extracted_total"))
            or _cents(store.get("total")),
            details={
                k: store[k]
                for k in (
                    "details_and_offers",
                    "tag",
                    "discount",
                    "additional_costs",
                    "shipping",
                    "rating",
                    "reviews",
                )
                if k in store
            },
        )
        _classify(offer, store, rules)
        offers.append(offer)

    band = parse_band(product.get("price_range"))
    _apply_band(offers, band)
    cents, method = estimate(
        [o.price_cents for o in offers if o.included and o.price_cents is not None],
        band,
    )
    return ParsedFetch(
        product_title=product.get("title"),
        offers=offers,
        band=band,
        history=parse_history(product.get("price_insights")),
        estimate_cents=cents,
        estimate_method=method,
    )


# --- persistence ----------------------------------------------------------------


async def load_merchant_rules(db: AsyncSession) -> list[tuple[str, str]]:
    rows = await db.execute(
        select(PriceMerchantRule.merchant_pattern, PriceMerchantRule.rule)
    )
    return list(rows.tuples())


async def record_parsed(
    db: AsyncSession,
    *,
    fetch_id: uuid.UUID,
    binding_id: uuid.UUID | None,
    parsed: ParsedFetch,
) -> None:
    """Write one parse of one fetch. Idempotent per fetch: a re-parse replaces
    that fetch's offers and figures rather than adding to them."""
    fetch = await db.get(PriceFetch, fetch_id)
    if fetch is None:
        raise LookupError(f"price_fetches row {fetch_id} not found")

    await db.execute(delete(PriceOffer).where(PriceOffer.fetch_id == fetch_id))
    for o in parsed.offers:
        db.add(
            PriceOffer(
                fetch_id=fetch_id,
                position=o.position,
                merchant_name=o.merchant_name,
                merchant_id=o.merchant_id,
                title=o.title,
                link=o.link,
                price_cents=o.price_cents,
                original_price_cents=o.original_price_cents,
                shipping_cents=o.shipping_cents,
                total_cents=o.total_cents,
                condition=o.condition,
                flags=o.flags,
                details=o.details,
                included=o.included,
                exclusion_reason=o.exclusion_reason,
            )
        )

    fetch.estimate_cents = parsed.estimate_cents
    fetch.estimate_method = parsed.estimate_method
    fetch.n_offers_total = len(parsed.offers)
    fetch.n_offers_used = parsed.n_used
    fetch.parser_version = PARSER_VERSION
    fetch.price_range_low_cents = parsed.band[0] if parsed.band else None
    fetch.price_range_high_cents = parsed.band[1] if parsed.band else None

    if binding_id is not None and parsed.history:
        stmt = insert(PriceHistoryPoint).values(
            [
                {
                    "binding_id": binding_id,
                    "merchant_name": p.merchant_name,
                    "price_date": p.price_date,
                    "price_cents": p.price_cents,
                    "first_seen_fetch_id": fetch_id,
                    "last_seen_fetch_id": fetch_id,
                }
                for p in parsed.history
            ]
        )
        await db.execute(
            stmt.on_conflict_do_update(
                index_elements=["binding_id", "merchant_name", "price_date"],
                set_={
                    "price_cents": stmt.excluded.price_cents,
                    "last_seen_fetch_id": stmt.excluded.last_seen_fetch_id,
                },
            )
        )

    await db.commit()


async def reparse_fetch(
    db: AsyncSession, store: Any, fetch_id: uuid.UUID
) -> ParsedFetch:
    """Re-run the current rules over a stored response, from GCS. The payoff
    of storing raw: a rule change re-prices history without a single search."""
    import json

    fetch = await db.get(PriceFetch, fetch_id)
    if fetch is None or not fetch.raw_uri:
        raise LookupError(f"fetch {fetch_id} has no stored raw response")
    payload = json.loads(await store.get(fetch.raw_uri))
    parsed = parse_product_response(payload, await load_merchant_rules(db))
    await record_parsed(
        db, fetch_id=fetch_id, binding_id=fetch.binding_id, parsed=parsed
    )
    return parsed
