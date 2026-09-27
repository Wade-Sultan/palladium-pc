"""Per-caller rate limit on /chat, counted in Valkey.

A COST GUARD. /chat accepts guests and every turn bills OpenRouter, so without
this a loop over one endpoint is a loop over the invoice.

THE COUNTER IS fastapi-redis-sdk's RateLimitBackend; THE WIRING IS OURS. The
SDK's own path (FastAPIRedis(app).lifespan().rate_limiting() plus rate_limit())
was the obvious choice and is wrong here twice over:

  - It builds its own pool from REDIS_* settings and, left unconfigured, points
    at localhost:6379. get_client() already encodes this app's rule that no
    Valkey means "degrade", which is what keeps the test suite and the inline
    /chat fallback working. A second pool with a second opinion would warn on
    every request in exactly those environments.
  - Its default identifier is the socket peer. Behind the external Application
    Load Balancer that is always a Google front end, so every guest on the
    internet would share one bucket and one guest could lock out all of them.

What the backend does contribute is the part worth not hand-writing: an atomic
window counter that probes for INCREX (Redis 8.8+) once, then runs an equivalent
Lua script, which is the path Valkey always takes since it has no INCREX.

FAILS OPEN, everywhere. No Valkey, an unreachable Valkey, a Valkey error
mid-check, or a request whose client address cannot be read: the turn runs
uncounted. A broken limiter taking /chat down would cost more than a window of
uncounted turns.

Keys land under the SDK's default prefix, `redis:fastapi:ratelimit:`, because it
reads that from its own settings rather than from an argument.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import Depends, HTTPException, Request, status
from redis_fastapi import Rate, RateLimitBackend, parse_rate

from app.core import valkey
from app.core.auth import optional_firebase_token
from app.core.config import settings
from app.core.loadtest import is_load_test

logger = logging.getLogger(__name__)


def parse_rates(spec: str) -> tuple[Rate, ...]:
    """Parse "10/minute,60/hour" into Rates, shortest window first.

    Shortest first so that a burst rejected by the short window never reaches
    (and never spends) the long one. A caller who double-clicks should lose a
    second of patience, not a slot of their hourly allowance.
    """
    rates = [parse_rate(part.strip()) for part in spec.split(",") if part.strip()]
    return tuple(sorted(rates, key=lambda r: r.window))


# At import, so a malformed CHAT_RATE_LIMITS fails the pod at startup instead of
# failing every /chat request after it is already serving traffic.
CHAT_RATES = parse_rates(settings.CHAT_RATE_LIMITS)

# One backend per client, not per request. The backend carries the INCREX probe
# result, and a fresh one would re-ask the server on every call.
_cached: tuple[Any, RateLimitBackend] | None = None


async def _backend() -> RateLimitBackend | None:
    global _cached
    client = await valkey.get_client()
    if client is None:
        return None
    if _cached is None or _cached[0] is not client:
        _cached = (client, RateLimitBackend(client))
    return _cached[1]


def client_ip(request: Request) -> str | None:
    """The caller's address, read from X-Forwarded-For per TRUSTED_PROXY_HOPS.

    Counted from the RIGHT, never the left. The load balancer appends to any
    X-Forwarded-For the client sent, so the left end is whatever the caller
    chose to write there; keying on it would let anyone pick their own bucket.

    None when the header is shorter than our own proxies guarantee, which a
    request that came through them cannot produce.
    """
    hops = settings.TRUSTED_PROXY_HOPS
    if hops <= 0:
        return request.client.host if request.client else None
    # getlist, not get: a second X-Forwarded-For header line must not let a
    # client push our appended entries out of view.
    entries = [
        e.strip()
        for line in request.headers.getlist("x-forwarded-for")
        for e in line.split(",")
        if e.strip()
    ]
    if len(entries) < hops:
        return None
    return entries[-hops]


def caller_identity(request: Request, user: dict | None) -> str | None:
    """Firebase uid when signed in, client IP otherwise.

    The uid first so people sharing an address (an office, a carrier NAT) are
    not throttled as one. The prefixes keep the two namespaces from colliding.
    """
    if user and user.get("uid"):
        return f"uid:{user['uid']}"
    ip = client_ip(request)
    return f"ip:{ip}" if ip else None


async def limit_chat(
    request: Request, user: dict | None = Depends(optional_firebase_token)
) -> None:
    """Dependency for /chat: raise 429 when the caller is over any CHAT_RATES.

    Shares optional_firebase_token with the route, and FastAPI caches a
    dependency per request, so the token is verified once, not twice.
    """
    # Load runs drive thousands of turns from a handful of addresses and cost
    # nothing (stub LMs), so counting them would only fail the run.
    if not CHAT_RATES or is_load_test():
        return
    backend = await _backend()
    if backend is None:
        return
    identity = caller_identity(request, user)
    if identity is None:
        logger.warning(
            "chat rate limit skipped: no client address (TRUSTED_PROXY_HOPS=%s)",
            settings.TRUSTED_PROXY_HOPS,
        )
        return

    for rate in CHAT_RATES:
        result = await backend.hit(
            identity,
            limit=rate.limit,
            window=rate.window,
            scope=f"chat:{rate.limit}per{rate.window}s",
        )
        if not result.allowed:
            logger.info(
                "chat rate limited",
                extra={
                    "identity": identity,
                    "limit": rate.limit,
                    "window_s": rate.window,
                },
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many messages. Please wait a moment and try again.",
                headers={"Retry-After": str(result.retry_after)},
            )
