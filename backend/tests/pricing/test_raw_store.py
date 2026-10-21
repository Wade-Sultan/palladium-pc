"""Raw SerpApi response storage: layout, write-once, and the local guard."""

from __future__ import annotations

import asyncio
import gzip
import hashlib
import uuid
from datetime import UTC, datetime

import pytest

from app.core.config import settings
from app.services.pricing_etl import raw_store


class _Blob:
    def __init__(self, bucket, name):
        self._bucket = bucket
        self.name = name
        self.metadata = None

    def upload_from_string(self, data, content_type, if_generation_match, timeout):
        assert if_generation_match == 0, "uploads must be write-once"
        if self.name in self._bucket.objects:
            raise RuntimeError("412 precondition failed")
        self._bucket.objects[self.name] = (data, content_type, dict(self.metadata))

    def download_as_bytes(self, timeout):
        return self._bucket.objects[self.name][0]


class _Bucket:
    def __init__(self):
        self.objects = {}

    def blob(self, name):
        return _Blob(self, name)


class _Client:
    def __init__(self):
        self.buckets = {}

    def bucket(self, name):
        return self.buckets.setdefault(name, _Bucket())


def test_object_name_partitions_by_engine_version_and_day():
    fetch_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    name = raw_store.object_name(
        engine="google_product",
        profile_version=1,
        fetched_at=datetime(2026, 10, 20, 23, 59, tzinfo=UTC),
        fetch_id=fetch_id,
    )
    assert name == f"serpapi/google_product/q1/dt=2026-10-20/{fetch_id}.json.gz"


def test_put_stores_gzip_and_describes_the_uncompressed_body():
    client = _Client()
    store = raw_store.RawStore("palladium-shopping-results", client=client)
    body = b'{"search_metadata": {"id": "abc"}}'

    stored = asyncio.run(store.put("a/b.json.gz", body, {"engine": "x", "gone": None}))

    data, content_type, metadata = client.buckets["palladium-shopping-results"].objects[
        "a/b.json.gz"
    ]
    assert gzip.decompress(data) == body
    assert content_type == "application/gzip"
    assert metadata == {"engine": "x"}, "None-valued metadata is dropped"
    assert stored.uri == "gs://palladium-shopping-results/a/b.json.gz"
    assert stored.sha256 == hashlib.sha256(body).hexdigest()
    assert stored.size == len(body)


def test_identical_bodies_compress_identically():
    """No timestamp in the gzip header, so the stored bytes are a function of
    the response alone."""
    assert raw_store._compress(b"same") == raw_store._compress(b"same")


def test_an_existing_object_is_never_overwritten():
    store = raw_store.RawStore("b", client=_Client())
    asyncio.run(store.put("k", b"first", {}))
    with pytest.raises(RuntimeError):
        asyncio.run(store.put("k", b"second", {}))
    assert asyncio.run(store.get("gs://b/k")) == b"first"


def test_get_refuses_another_bucket():
    store = raw_store.RawStore("b", client=_Client())
    with pytest.raises(ValueError):
        asyncio.run(store.get("gs://other/k"))


def test_no_bucket_means_no_store(monkeypatch):
    monkeypatch.setattr(settings, "PRICING_RAW_BUCKET", "")
    with pytest.raises(raw_store.RawStoreConfigError):
        raw_store.get_store()


def test_local_environment_refuses_real_gcs(monkeypatch):
    """The local builder pod has real credentials mounted. Without the
    emulator, a client built there would write to the production bucket."""
    monkeypatch.setattr(settings, "PRICING_RAW_BUCKET", "palladium-shopping-results")
    monkeypatch.setattr(settings, "ENVIRONMENT", "local")
    monkeypatch.delenv("STORAGE_EMULATOR_HOST", raising=False)
    with pytest.raises(raw_store.RawStoreConfigError, match="STORAGE_EMULATOR_HOST"):
        raw_store.get_store()
