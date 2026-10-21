"""One product-bound SerpApi fetch, recorded: call, count, store raw, record.

THE ORDER IS THE POINT.
  1. Call SerpApi with parameters from query_profile, never hand-built ones.
  2. Count the search against the monthly quota, whatever happened. SerpApi
     bills the attempt, and an uncounted failure is how a cap gets overrun.
  3. Write the raw body to GCS before anything parses it.
  4. Insert the price_fetches row, pointing at the object.

A GCS failure in step 3 does not discard the response. The search is already
paid for, so the row records raw_uri=NULL with the reason, and the caller still
gets the parsed payload. Losing one fetch's re-parseability is better than
losing the price. A *missing* store is different: get_store() raises before
any search is made, because then every response would be lost.

Nothing here interprets the payload beyond SerpApi's own envelope (its search
id and error field). Turning stores into offers is the offer parser's job, run
against the same bytes that were stored.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.price_tracking import PriceFetch
from app.services.pricing_etl import query_profile, quota, serpapi_client
from app.services.pricing_etl.raw_store import RawStore, object_name

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FetchOutcome:
    fetch_id: uuid.UUID
    http_status: int | None
    # The decoded body, or None when there was no usable JSON (transport
    # failure, non-JSON error page). Present even when raw_uri is None.
    payload: dict | None
    raw_uri: str | None
    # What went wrong with the response itself: transport, HTTP status, or
    # SerpApi's own error field. A response with any of these is not a price.
    response_error: str | None
    # The raw write failing. Does NOT make the response unusable.
    store_error: str | None

    @property
    def ok(self) -> bool:
        return self.payload is not None and self.response_error is None


def _join(*parts: str | None) -> str | None:
    present = [p for p in parts if p]
    return "; ".join(present) if present else None


async def perform_fetch(
    db: AsyncSession,
    store: RawStore,
    *,
    purpose: str,
    params: dict[str, str],
    run_id: uuid.UUID | None = None,
    binding_id: uuid.UUID | None = None,
    part_id: uuid.UUID | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> FetchOutcome:
    engine = params["engine"]
    fetch_id = uuid.uuid4()
    fetched_at = datetime.now(UTC)

    raw: serpapi_client.RawResponse | None = None
    transport_error: str | None = None
    try:
        raw = await serpapi_client.fetch_raw(params, transport=transport)
    except serpapi_client.SerpApiConfigError:
        raise
    except Exception as exc:
        transport_error = f"transport: {type(exc).__name__}: {exc}"
        logger.warning("serpapi %s fetch %s failed: %s", engine, fetch_id, exc)
    finally:
        await quota.record_search(db)

    stored = None
    store_error: str | None = None
    payload: dict | None = None
    search_id: str | None = None
    serp_error: str | None = None
    if raw is not None:
        payload = raw.json()
        if payload is not None:
            search_id = (payload.get("search_metadata") or {}).get("id")
            if payload.get("error"):
                serp_error = f"serpapi: {payload['error']}"
        name = object_name(
            engine=engine,
            profile_version=query_profile.QUERY_PROFILE_VERSION,
            fetched_at=fetched_at,
            fetch_id=fetch_id,
        )
        try:
            stored = await store.put(
                name,
                raw.body,
                {
                    "purpose": purpose,
                    "engine": engine,
                    "http_status": str(raw.status),
                    "serpapi_search_id": search_id,
                    "part_id": str(part_id) if part_id else None,
                    "binding_id": str(binding_id) if binding_id else None,
                    "params_hash": query_profile.conditions_hash(engine),
                    "fetched_at": fetched_at.isoformat(),
                },
            )
        except Exception as exc:
            store_error = f"raw_store: {type(exc).__name__}: {exc}"
            logger.exception(
                "serpapi %s fetch %s: paid for but raw response NOT stored",
                engine,
                fetch_id,
            )

    http_error = f"http {raw.status}" if raw is not None and raw.status >= 400 else None
    response_error = _join(transport_error, http_error, serp_error)
    error_detail = _join(response_error, store_error)

    db.add(
        PriceFetch(
            id=fetch_id,
            run_id=run_id,
            purpose=purpose,
            binding_id=binding_id,
            part_id=part_id,
            engine=engine,
            query_profile_version=query_profile.QUERY_PROFILE_VERSION,
            params=params,
            params_hash=query_profile.conditions_hash(engine),
            serpapi_search_id=search_id,
            http_status=raw.status if raw is not None else None,
            error_detail=error_detail,
            raw_uri=stored.uri if stored else None,
            raw_sha256=stored.sha256 if stored else None,
            raw_bytes=stored.size if stored else None,
            fetched_at=fetched_at,
        )
    )
    await db.commit()

    return FetchOutcome(
        fetch_id=fetch_id,
        http_status=raw.status if raw is not None else None,
        payload=payload,
        raw_uri=stored.uri if stored else None,
        response_error=response_error,
        store_error=store_error,
    )
