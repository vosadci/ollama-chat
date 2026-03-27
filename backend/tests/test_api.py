"""Functional tests for the FastAPI endpoints.

All tests run against the real app (via ASGI transport — no server needed).
External dependencies are mocked:
  - RAGService.retrieve  → overridden via app.dependency_overrides
  - services.ollama.stream_chat → patched via unittest.mock

This keeps tests fast and fully offline.
"""

import json
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
import httpx
from httpx import ASGITransport

from dependencies import get_rag_service
from main import app
from services.rag import RAGService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def parse_sse(body: bytes) -> list[dict | str]:
    """Parse an SSE response body into a list of payloads.

    Returns strings for non-JSON events (e.g. "[DONE]"), dicts for JSON ones.
    """
    events = []
    for line in body.decode().splitlines():
        if line.startswith("data: "):
            payload = line[len("data: "):]
            try:
                events.append(json.loads(payload))
            except json.JSONDecodeError:
                events.append(payload)
    return events


async def _fake_stream(*_args, **_kwargs):
    """Async generator that yields three tokens."""
    for token in ["Bună", " ziua", "!"]:
        yield token


FAKE_CHUNKS = ["DemoBank offers Visa and Mastercard debit and credit cards."]
FAKE_META = [{"title": "Carduri", "source": "carduri/carduri-de-debit"}]


def _make_mock_rag(chunks=FAKE_CHUNKS, meta=FAKE_META) -> RAGService:
    """Return a mock RAGService whose retrieve() returns the given canned data."""
    mock = AsyncMock(spec=RAGService)
    mock.retrieve = AsyncMock(return_value=(chunks, meta))
    return mock


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True, scope="session")
def prime_app_state():
    """Initialise app.state.rag so the dependency resolver never hits a
    missing-attribute error on tests that don't set dependency_overrides.

    Tests that need specific retrieve() behaviour override the dependency
    themselves; this fixture just provides a safe no-op fallback.
    """
    app.state.rag = AsyncMock(spec=RAGService)


@pytest_asyncio.fixture
async def client():
    """Async httpx client wired directly to the FastAPI ASGI app.

    build_index() is skipped — the lifespan is not invoked here because we
    use the app directly rather than through a lifespan-aware transport.
    """
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# ---------------------------------------------------------------------------
# /health
# ---------------------------------------------------------------------------

class TestHealth:
    async def test_returns_200(self, client):
        r = await client.get("/health")
        assert r.status_code == 200

    async def test_response_shape(self, client):
        r = await client.get("/health")
        body = r.json()
        assert body["status"] == "ok"
        assert "model" in body

    async def test_content_type_json(self, client):
        r = await client.get("/health")
        assert "application/json" in r.headers["content-type"]


# ---------------------------------------------------------------------------
# /api/v1/chat — SSE stream structure
# ---------------------------------------------------------------------------

class TestChatStream:
    @pytest.fixture(autouse=True)
    def mock_deps(self):
        mock_rag = _make_mock_rag()
        app.dependency_overrides[get_rag_service] = lambda: mock_rag
        with patch("routers.chat.stream_chat", side_effect=_fake_stream):
            yield mock_rag
        app.dependency_overrides.pop(get_rag_service, None)

    async def test_returns_200(self, client):
        r = await client.post(
            "/api/v1/chat",
            json={"messages": [{"role": "user", "content": "Salut"}]},
        )
        assert r.status_code == 200

    async def test_content_type_event_stream(self, client):
        r = await client.post(
            "/api/v1/chat",
            json={"messages": [{"role": "user", "content": "Salut"}]},
        )
        assert "text/event-stream" in r.headers["content-type"]

    async def test_stream_contains_tokens(self, client):
        r = await client.post(
            "/api/v1/chat",
            json={"messages": [{"role": "user", "content": "Salut"}]},
        )
        events = parse_sse(r.content)
        tokens = [e["token"] for e in events if isinstance(e, dict) and "token" in e]
        assert tokens == ["Bună", " ziua", "!"]

    async def test_stream_ends_with_done(self, client):
        r = await client.post(
            "/api/v1/chat",
            json={"messages": [{"role": "user", "content": "Salut"}]},
        )
        events = parse_sse(r.content)
        assert events[-1] == "[DONE]"

    async def test_stream_contains_sources(self, client):
        r = await client.post(
            "/api/v1/chat",
            json={"messages": [{"role": "user", "content": "Salut"}]},
        )
        events = parse_sse(r.content)
        source_events = [e for e in events if isinstance(e, dict) and "sources" in e]
        assert len(source_events) == 1
        sources = source_events[0]["sources"]
        assert sources[0]["title"] == "Carduri"
        assert sources[0]["source"] == "carduri/carduri-de-debit"

    async def test_sources_deduplicated(self, client):
        duplicate_meta = FAKE_META * 3  # same source repeated
        mock_rag = _make_mock_rag(meta=duplicate_meta)
        app.dependency_overrides[get_rag_service] = lambda: mock_rag
        r = await client.post(
            "/api/v1/chat",
            json={"messages": [{"role": "user", "content": "Salut"}]},
        )
        events = parse_sse(r.content)
        source_events = [e for e in events if isinstance(e, dict) and "sources" in e]
        assert len(source_events[0]["sources"]) == 1  # deduped to one

    async def test_multi_turn_conversation(self, client):
        r = await client.post(
            "/api/v1/chat",
            json={
                "messages": [
                    {"role": "user", "content": "What services do you offer?"},
                    {"role": "assistant", "content": "O bancă."},
                    {"role": "user", "content": "Ce carduri oferă?"},
                ]
            },
        )
        assert r.status_code == 200
        events = parse_sse(r.content)
        assert any(isinstance(e, dict) and "token" in e for e in events)

    async def test_no_sources_when_none_returned(self, client):
        mock_rag = _make_mock_rag(chunks=[], meta=[])
        app.dependency_overrides[get_rag_service] = lambda: mock_rag
        r = await client.post(
            "/api/v1/chat",
            json={"messages": [{"role": "user", "content": "Salut"}]},
        )
        events = parse_sse(r.content)
        assert not any(isinstance(e, dict) and "sources" in e for e in events)


# ---------------------------------------------------------------------------
# /api/v1/chat — input validation (no mocks needed: rejected before handlers)
# ---------------------------------------------------------------------------

class TestChatValidation:
    async def test_invalid_role_returns_422(self, client):
        r = await client.post(
            "/api/v1/chat",
            json={"messages": [{"role": "admin", "content": "Hack"}]},
        )
        assert r.status_code == 422

    async def test_content_too_long_returns_422(self, client):
        r = await client.post(
            "/api/v1/chat",
            json={"messages": [{"role": "user", "content": "x" * 33_000}]},
        )
        assert r.status_code == 422

    async def test_empty_messages_returns_422(self, client):
        r = await client.post("/api/v1/chat", json={"messages": []})
        assert r.status_code == 422

    async def test_missing_messages_field_returns_422(self, client):
        r = await client.post("/api/v1/chat", json={})
        assert r.status_code == 422

    async def test_missing_role_returns_422(self, client):
        r = await client.post(
            "/api/v1/chat",
            json={"messages": [{"content": "Salut"}]},
        )
        assert r.status_code == 422

    async def test_missing_content_returns_422(self, client):
        r = await client.post(
            "/api/v1/chat",
            json={"messages": [{"role": "user"}]},
        )
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# /api/v1/chat — error handling
# ---------------------------------------------------------------------------

class TestChatErrorHandling:
    async def test_stream_error_yields_error_event(self, client):
        async def _boom(*_args, **_kwargs):
            raise RuntimeError("Ollama down")
            yield  # make it an async generator

        mock_rag = _make_mock_rag(chunks=[], meta=[])
        app.dependency_overrides[get_rag_service] = lambda: mock_rag
        try:
            with patch("routers.chat.stream_chat", side_effect=_boom):
                r = await client.post(
                    "/api/v1/chat",
                    json={"messages": [{"role": "user", "content": "Salut"}]},
                )
        finally:
            app.dependency_overrides.pop(get_rag_service, None)

        assert r.status_code == 200  # SSE: HTTP layer is always 200
        events = parse_sse(r.content)
        error_events = [e for e in events if isinstance(e, dict) and "error" in e]
        assert len(error_events) == 1
        assert "error" in error_events[0]


# ---------------------------------------------------------------------------
# OpenAPI schema
# ---------------------------------------------------------------------------

class TestOpenAPISchema:
    async def test_openapi_json_reachable(self, client):
        r = await client.get("/openapi.json")
        assert r.status_code == 200

    async def test_openapi_title(self, client):
        r = await client.get("/openapi.json")
        assert r.json()["info"]["title"] == "Ollama Chat API"

    async def test_openapi_has_chat_path(self, client):
        r = await client.get("/openapi.json")
        assert "/api/v1/chat" in r.json()["paths"]

    async def test_docs_ui_reachable(self, client):
        r = await client.get("/docs")
        assert r.status_code == 200

    async def test_redoc_reachable(self, client):
        r = await client.get("/redoc")
        assert r.status_code == 200
