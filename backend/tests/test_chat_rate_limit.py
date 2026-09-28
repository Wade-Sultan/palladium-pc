"""The /chat rate limit (app/core/ratelimit.py).

Cost tests in the same sense as test_loadtest_blocker.py: a regression that
stops counting bills OpenRouter quietly, and one that counts the wrong thing
(every guest under one address) takes /chat down for everybody. Both directions
are asserted.

Backed by fakeredis with Lua enabled. It has no INCREX, so the SDK falls back to
its Lua window counter, which is the same path a real Valkey takes.
"""

from __future__ import annotations

import fakeredis
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.api.routes.chat import router as chat_router
from app.core import ratelimit, valkey
from app.core.auth import optional_firebase_token
from app.core.config import settings
from app.core.loadtest import LoadTestMiddleware

SECRET = "test-secret-value"
LB = "34.120.0.1"


def _xff(client_ip: str, supplied: str | None = None) -> dict[str, str]:
    """X-Forwarded-For as the external Application Load Balancer delivers it."""
    hops = [supplied] if supplied else []
    return {"X-Forwarded-For": ", ".join([*hops, client_ip, LB])}


@pytest.fixture
def redis_server() -> fakeredis.FakeServer:
    return fakeredis.FakeServer()


@pytest.fixture
def app(monkeypatch, redis_server) -> FastAPI:
    fake = fakeredis.FakeAsyncRedis(server=redis_server, decode_responses=True)

    async def _get_client():
        return fake

    monkeypatch.setattr(valkey, "get_client", _get_client)
    monkeypatch.setattr(ratelimit, "_cached", None)
    monkeypatch.setattr(ratelimit, "CHAT_RATES", ratelimit.parse_rates("3/minute"))
    monkeypatch.setattr(settings, "TRUSTED_PROXY_HOPS", 2)
    monkeypatch.setattr(settings, "LOAD_TEST_SECRET", SECRET, raising=False)

    app = FastAPI()
    app.add_middleware(LoadTestMiddleware)

    @app.post("/chat", dependencies=[Depends(ratelimit.limit_chat)])
    async def chat() -> dict:
        return {"ok": True}

    return app


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


def _statuses(client: TestClient, n: int, **kwargs) -> list[int]:
    return [client.post("/chat", **kwargs).status_code for _ in range(n)]


def test_real_chat_route_is_limited() -> None:
    """The dependency is only worth anything if the production route carries it."""
    route = next(r for r in chat_router.routes if getattr(r, "path", None) == "/chat")
    assert any(d.call is ratelimit.limit_chat for d in route.dependant.dependencies)


def test_rejects_past_the_limit_with_retry_after(client: TestClient) -> None:
    assert _statuses(client, 3, headers=_xff("1.1.1.1")) == [200, 200, 200]
    rejected = client.post("/chat", headers=_xff("1.1.1.1"))
    assert rejected.status_code == 429
    assert 0 < int(rejected.headers["Retry-After"]) <= 60


def test_guests_are_counted_separately(client: TestClient) -> None:
    """The failure this guards: every guest keyed on the load balancer's hop."""
    assert _statuses(client, 3, headers=_xff("1.1.1.1")) == [200, 200, 200]
    assert client.post("/chat", headers=_xff("2.2.2.2")).status_code == 200


def test_client_supplied_forwarded_for_cannot_pick_a_bucket(client: TestClient) -> None:
    """Rotating a spoofed left-hand entry must not buy a fresh allowance."""
    for i in range(3):
        assert (
            client.post("/chat", headers=_xff("1.1.1.1", f"10.0.0.{i}")).status_code
            == 200
        )
    assert client.post("/chat", headers=_xff("1.1.1.1", "10.0.0.99")).status_code == 429


def test_signed_in_users_are_keyed_by_uid_not_address(app: FastAPI) -> None:
    """Two people behind one NAT must not share a limit once signed in."""
    client = TestClient(app)
    assert _statuses(client, 3, headers=_xff("1.1.1.1")) == [200, 200, 200]
    assert client.post("/chat", headers=_xff("1.1.1.1")).status_code == 429

    app.dependency_overrides[optional_firebase_token] = lambda: {"uid": "alice"}
    assert client.post("/chat", headers=_xff("1.1.1.1")).status_code == 200


def test_load_test_requests_are_not_counted(client: TestClient) -> None:
    headers = {**_xff("1.1.1.1"), "X-Palladium-Load-Test": SECRET}
    assert set(_statuses(client, 10, headers=headers)) == {200}
    # And they spent nothing: an ordinary request still has its full allowance.
    assert _statuses(client, 3, headers=_xff("1.1.1.1")) == [200, 200, 200]


def test_short_window_rejection_does_not_spend_the_long_one(
    monkeypatch, client: TestClient, redis_server
) -> None:
    monkeypatch.setattr(
        ratelimit, "CHAT_RATES", ratelimit.parse_rates("5/hour, 2/minute")
    )
    assert _statuses(client, 4, headers=_xff("1.1.1.1")) == [200, 200, 429, 429]
    # The two rejected requests never reached the hourly counter.
    counters = fakeredis.FakeRedis(server=redis_server, decode_responses=True)
    assert counters.get("redis:fastapi:ratelimit:chat:5per3600s:ip:1.1.1.1") == "2"


def test_no_valkey_means_no_limit(monkeypatch, client: TestClient) -> None:
    async def _none():
        return None

    monkeypatch.setattr(valkey, "get_client", _none)
    assert set(_statuses(client, 10, headers=_xff("1.1.1.1"))) == {200}


def test_fails_open_when_valkey_errors(client: TestClient, redis_server) -> None:
    redis_server.connected = False
    assert set(_statuses(client, 10, headers=_xff("1.1.1.1"))) == {200}


def test_unreadable_address_is_not_pooled(client: TestClient) -> None:
    """A header shorter than our proxies guarantee is skipped, never shared."""
    assert set(_statuses(client, 10, headers={"X-Forwarded-For": LB})) == {200}


def test_rates_parse_shortest_window_first_and_empty_disables() -> None:
    assert [r.window for r in ratelimit.parse_rates("60/hour,10/minute")] == [60, 3600]
    assert ratelimit.parse_rates("") == ()
    with pytest.raises(ValueError):
        ratelimit.parse_rates("lots/minute")
