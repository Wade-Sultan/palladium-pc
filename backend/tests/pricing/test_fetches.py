"""perform_fetch: call, count, store raw, record, in that order.

The network is an httpx.MockTransport and the store and session are fakes, so
these pin the ordering and failure handling. mk-verify-pricing-raw.sh runs the
same function against the in-cluster Postgres and fake-gcs-server.
"""

from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from app.core.config import settings
from app.models.price_tracking import PriceFetch
from app.services.pricing_etl import fetches, query_profile, quota
from app.services.pricing_etl.raw_store import StoredRaw

_BODY = {
    "search_metadata": {"id": "6716f0c1", "status": "Success"},
    "product_results": {"title": "AMD Ryzen 7 9800X3D", "stores": []},
}


class _Session:
    def __init__(self, events):
        self.events = events
        self.added = []

    def add(self, row):
        self.added.append(row)
        self.events.append("db_add")

    async def commit(self):
        self.events.append("db_commit")


class _Store:
    def __init__(self, events, fail=False):
        self.events = events
        self.fail = fail
        self.puts = []

    async def put(self, name, body, metadata):
        self.events.append("store_put")
        if self.fail:
            raise RuntimeError("gcs unavailable")
        self.puts.append((name, body, metadata))
        return StoredRaw(uri=f"gs://b/{name}", sha256="sha", size=len(body))


@pytest.fixture
def events(monkeypatch):
    log = []

    async def _record(_db):
        log.append("quota")

    monkeypatch.setattr(quota, "record_search", _record)
    monkeypatch.setattr(settings, "SERPAPI_KEY", "test-key")
    return log


def _transport(events, status=200, body=None, raw=None):
    def handler(request):
        events.append("http")
        assert request.url.params["api_key"] == "test-key"
        assert request.url.params["engine"] == "google_product"
        content = raw if raw is not None else json.dumps(body or _BODY).encode()
        return httpx.Response(status, content=content)

    return httpx.MockTransport(handler)


def _run(events, *, store=None, transport=None):
    db = _Session(events)
    store = store or _Store(events)
    outcome = asyncio.run(
        fetches.perform_fetch(
            db,
            store,
            purpose="offers",
            params=query_profile.offers_params("19637827"),
            transport=transport or _transport(events),
        )
    )
    return outcome, db, store


def test_the_order_is_call_count_store_record(events):
    outcome, db, store = _run(events)

    assert events == ["http", "quota", "store_put", "db_add", "db_commit"]
    assert outcome.ok
    assert outcome.payload["search_metadata"]["id"] == "6716f0c1"


def test_the_stored_bytes_are_exactly_what_serpapi_sent(events):
    raw = b'{"search_metadata": {"id": "x"},   "odd spacing": true}'
    _outcome, _db, store = _run(events, transport=_transport(events, raw=raw))
    assert store.puts[0][1] == raw


def test_the_row_points_at_the_object_and_never_holds_the_key(events):
    outcome, db, store = _run(events)
    row = db.added[0]

    assert isinstance(row, PriceFetch)
    assert row.id == outcome.fetch_id
    assert row.raw_uri == f"gs://b/{store.puts[0][0]}"
    assert str(outcome.fetch_id) in row.raw_uri
    assert row.params_hash == query_profile.conditions_hash("google_product")
    assert row.query_profile_version == query_profile.QUERY_PROFILE_VERSION
    assert row.serpapi_search_id == "6716f0c1"
    assert "api_key" not in row.params
    assert row.error_detail is None


def test_a_failed_raw_write_keeps_the_paid_response(events):
    """The search is already billed. The row says the raw is missing, and the
    caller still gets a usable payload."""
    outcome, db, _store = _run(events, store=_Store(events, fail=True))

    assert outcome.ok
    assert outcome.payload is not None
    assert outcome.raw_uri is None
    assert "raw_store" in outcome.store_error
    assert db.added[0].raw_uri is None
    assert "raw_store" in db.added[0].error_detail


def test_an_http_error_is_stored_and_counted_but_not_ok(events):
    body = {"error": "Your account has run out of searches."}
    outcome, db, store = _run(
        events, transport=_transport(events, status=429, body=body)
    )

    assert not outcome.ok
    assert "quota" in events
    assert store.puts, "an error body is still evidence worth keeping"
    assert "http 429" in db.added[0].error_detail
    assert "run out of searches" in db.added[0].error_detail


def test_a_transport_failure_is_still_counted(events):
    def boom(_request):
        raise httpx.ConnectError("no route")

    outcome, db, store = _run(events, transport=httpx.MockTransport(boom))

    assert events.count("quota") == 1
    assert not store.puts, "nothing came back, so there is nothing to store"
    assert outcome.payload is None
    assert outcome.http_status is None
    assert "transport" in db.added[0].error_detail


def test_a_non_json_body_is_stored_but_yields_no_payload(events):
    outcome, _db, store = _run(
        events, transport=_transport(events, status=502, raw=b"<html>bad gateway")
    )
    assert store.puts
    assert outcome.payload is None
    assert not outcome.ok
