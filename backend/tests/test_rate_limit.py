"""Unit tests for the sliding-window rate limiter.

Tests run entirely offline — no server, no external services.
"""
import asyncio
import time

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

from middleware.rate_limit import _COUNTS, rate_limit

# ---------------------------------------------------------------------------
# Minimal app for isolation
# ---------------------------------------------------------------------------

_app = FastAPI()


@_app.get("/limited", dependencies=[Depends(rate_limit(max_calls=3, window=60))])
async def limited_endpoint():
    return {"ok": True}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_client(ip: str = "1.2.3.4") -> TestClient:
    """Return a sync TestClient that fakes a specific client IP."""
    client = TestClient(_app)
    # Override the ASGI scope so request.client.host reflects `ip`
    client.headers.update({})
    # We'll use X-Forwarded-For instead (simpler with TestClient)
    return client


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestRateLimitDependency:
    def setup_method(self) -> None:
        """Clear global state before each test."""
        _COUNTS.clear()

    def test_allows_requests_within_limit(self):
        client = TestClient(_app)
        for _ in range(3):
            resp = client.get("/limited", headers={"X-Forwarded-For": "10.0.0.1"})
            assert resp.status_code == 200

    def test_rejects_request_over_limit(self):
        client = TestClient(_app)
        for _ in range(3):
            client.get("/limited", headers={"X-Forwarded-For": "10.0.0.2"})
        resp = client.get("/limited", headers={"X-Forwarded-For": "10.0.0.2"})
        assert resp.status_code == 429

    def test_429_body_contains_retry_after(self):
        client = TestClient(_app)
        for _ in range(3):
            client.get("/limited", headers={"X-Forwarded-For": "10.0.0.3"})
        resp = client.get("/limited", headers={"X-Forwarded-For": "10.0.0.3"})
        body = resp.json()
        assert body["detail"]["error"] == "rate_limit_exceeded"
        assert "retry_after" in body["detail"]
        assert int(body["detail"]["retry_after"]) > 0

    def test_429_response_has_retry_after_header(self):
        client = TestClient(_app)
        for _ in range(3):
            client.get("/limited", headers={"X-Forwarded-For": "10.0.0.4"})
        resp = client.get("/limited", headers={"X-Forwarded-For": "10.0.0.4"})
        assert "Retry-After" in resp.headers

    def test_different_ips_have_independent_counters(self):
        client = TestClient(_app)
        # Exhaust limit for IP A
        for _ in range(3):
            client.get("/limited", headers={"X-Forwarded-For": "10.0.0.5"})
        assert client.get("/limited", headers={"X-Forwarded-For": "10.0.0.5"}).status_code == 429
        # IP B should still be allowed
        assert client.get("/limited", headers={"X-Forwarded-For": "10.0.0.6"}).status_code == 200

    def test_old_timestamps_expire(self):
        """Requests older than the window should not count."""
        from collections import deque

        from middleware.rate_limit import _COUNTS

        ip = "10.0.0.7"
        # Plant 3 old timestamps (well outside the window)
        _COUNTS[ip] = deque([time.monotonic() - 120] * 3)

        client = TestClient(_app)
        resp = client.get("/limited", headers={"X-Forwarded-For": ip})
        assert resp.status_code == 200

    async def test_concurrent_requests_counted_correctly(self):
        """asyncio.Lock ensures concurrent hits are counted atomically.

        Fire 5 requests simultaneously against a limit-3 endpoint.  Exactly 3
        must succeed and 2 must be rejected — no races that let extra requests
        slip through.
        """
        _COUNTS.clear()
        ip = "10.0.0.8"
        transport = ASGITransport(app=_app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            responses = await asyncio.gather(
                *[c.get("/limited", headers={"X-Forwarded-For": ip}) for _ in range(5)]
            )
        statuses = [r.status_code for r in responses]
        assert statuses.count(200) == 3
        assert statuses.count(429) == 2
