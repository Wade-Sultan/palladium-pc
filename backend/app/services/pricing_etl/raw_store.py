"""Write-once storage for raw SerpApi responses, in GCS.

WHY RAW, AND WHY FIRST. The rules that turn a response into a price (what is a
coupon, which merchants are membership-only, what condition text means used)
will change as real responses show what Google actually sends. With the raw
bytes kept, a rule change is a re-parse of history. Without them it is a
re-purchase against a 1000/month cap, and the past is simply gone.

OBJECT LAYOUT:
  serpapi/<engine>/q<profile version>/dt=<YYYY-MM-DD>/<fetch id>.json.gz

Partitioned by date so a day can be listed or reprocessed alone, and by profile
version so a change of query conditions never mixes into one prefix. The fetch
id is the price_fetches primary key, so a row and its object find each other
in both directions.

WRITE-ONCE. Uploads carry if_generation_match=0, which GCS rejects if the
object already exists. A raw response is evidence; nothing should be able to
replace one after the fact, including a retried job.

LOCAL. The builder pod on minikube has real Application Default Credentials
mounted (deploy/overlays/local/patches/gcp-adc.yaml), so a client built there
would happily write to the production bucket. get_store() refuses to build one
in a local environment unless STORAGE_EMULATOR_HOST points at the in-cluster
fake-gcs-server, in which case the client uses anonymous credentials.
"""

from __future__ import annotations

import asyncio
import gzip
import hashlib
import logging
import os
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)


class RawStoreConfigError(RuntimeError):
    """Raw capture cannot run, so no search should be spent."""


@dataclass(frozen=True)
class StoredRaw:
    uri: str
    sha256: str
    size: int


def object_name(
    *, engine: str, profile_version: int, fetched_at: datetime, fetch_id: uuid.UUID
) -> str:
    return (
        f"serpapi/{engine}/q{profile_version}/"
        f"dt={fetched_at.date().isoformat()}/{fetch_id}.json.gz"
    )


def _compress(body: bytes) -> bytes:
    # mtime=0 keeps the gzip header free of a timestamp, so identical bodies
    # compress to identical bytes.
    return gzip.compress(body, mtime=0)


class RawStore:
    def __init__(self, bucket_name: str, client: Any = None):
        if client is None:
            from google.cloud import storage

            client = storage.Client()
        self._bucket_name = bucket_name
        self._bucket = client.bucket(bucket_name)

    @property
    def bucket_name(self) -> str:
        return self._bucket_name

    def _put_sync(self, name: str, data: bytes, metadata: dict[str, str]) -> None:
        blob = self._bucket.blob(name)
        blob.metadata = metadata
        blob.upload_from_string(
            data,
            content_type="application/gzip",
            if_generation_match=0,
            timeout=60,
        )

    async def put(self, name: str, body: bytes, metadata: dict[str, str]) -> StoredRaw:
        """Store `body` (the uncompressed response) gzipped at `name`.

        sha256 and size describe the UNCOMPRESSED body: that is what a re-parse
        reads, and it does not change if the compression ever does.
        """
        clean = {k: str(v) for k, v in metadata.items() if v is not None}
        await asyncio.to_thread(self._put_sync, name, _compress(body), clean)
        return StoredRaw(
            uri=f"gs://{self._bucket_name}/{name}",
            sha256=hashlib.sha256(body).hexdigest(),
            size=len(body),
        )

    def _get_sync(self, name: str) -> bytes:
        return gzip.decompress(self._bucket.blob(name).download_as_bytes(timeout=60))

    async def get(self, uri: str) -> bytes:
        """The uncompressed body stored at a gs:// uri from this bucket."""
        prefix = f"gs://{self._bucket_name}/"
        if not uri.startswith(prefix):
            raise ValueError(f"{uri!r} is not in bucket {self._bucket_name!r}")
        return await asyncio.to_thread(self._get_sync, uri[len(prefix) :])


def get_store() -> RawStore:
    """The configured store. Raises rather than returning None: a search whose
    raw response cannot be kept should not be bought at all."""
    bucket = settings.PRICING_RAW_BUCKET
    if not bucket:
        raise RawStoreConfigError("PRICING_RAW_BUCKET is not configured")
    if settings.ENVIRONMENT == "local" and not os.getenv("STORAGE_EMULATOR_HOST"):
        raise RawStoreConfigError(
            "refusing real GCS from a local environment: set STORAGE_EMULATOR_HOST "
            "to the fake-gcs-server (deploy/overlays/local/fake-gcs.yaml)"
        )
    return RawStore(bucket)
