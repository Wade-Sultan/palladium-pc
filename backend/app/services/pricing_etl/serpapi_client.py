from __future__ import annotations

import json
import logging
from dataclasses import dataclass

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

_SERPAPI_URL = "https://serpapi.com/search"


class SerpApiConfigError(RuntimeError):
    """A pricing check can't run because required config is missing."""


@dataclass(frozen=True)
class RawResponse:
    """One SerpApi call exactly as it came back: status and body bytes, before
    any parsing, so the bytes stored in GCS are the bytes SerpApi sent."""

    status: int
    body: bytes

    def json(self) -> dict | None:
        try:
            data = json.loads(self.body)
        except ValueError:
            return None
        return data if isinstance(data, dict) else None


async def fetch_raw(
    params: dict[str, str], *, transport: httpx.AsyncBaseTransport | None = None
) -> RawResponse:
    """One SerpApi call with `params` (from query_profile, never hand-built).

    Does not raise on an HTTP error status: a 4xx/5xx body is still a paid
    response worth keeping. Raises on transport failure, when there is nothing
    to keep. `transport` exists for tests and the minikube verification
    script, which substitute recorded responses for the network and nothing
    else.
    """
    if not settings.SERPAPI_KEY:
        raise SerpApiConfigError("SERPAPI_KEY is not configured")
    async with httpx.AsyncClient(timeout=30.0, transport=transport) as client:
        resp = await client.get(
            _SERPAPI_URL, params={**params, "api_key": settings.SERPAPI_KEY}
        )
    return RawResponse(status=resp.status_code, body=resp.content)


@dataclass
class ShoppingResult:
    title: str
    extracted_price: float
    source: str | None
    product_link: str | None


async def search_shopping(query: str) -> list[ShoppingResult]:
    """One SerpAPI call. The caller is responsible for quota accounting
    (quota.record_search) since that has to happen regardless of whether the
    call succeeds, and exactly once per call, not once per result."""
    if not settings.SERPAPI_KEY:
        raise SerpApiConfigError("SERPAPI_KEY is not configured")

    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.get(
            _SERPAPI_URL,
            params={
                "engine": "google_shopping_light",
                "q": query,
                "gl": "us",
                "hl": "en",
                "api_key": settings.SERPAPI_KEY,
            },
        )
        resp.raise_for_status()

    results = []
    for r in resp.json().get("shopping_results", []):
        price = r.get("extracted_price")
        title = r.get("title")
        if price is None or not title:
            continue
        results.append(
            ShoppingResult(
                title=title,
                extracted_price=float(price),
                source=r.get("source"),
                product_link=r.get("product_link"),
            )
        )
    return results
