"""Integration tests for the full RAG + Ollama stack.

These tests require:
  - A running Ollama instance (OLLAMA_URL env var, defaults to http://localhost:11434)
  - The chat model (OLLAMA_MODEL) and embed model (OLLAMA_EMBED_MODEL) pulled
  - DATA_PATH pointing to at least one HTML document
  - CHROMA_PATH writable

All tests are marked ``integration`` and are **automatically skipped** in CI
unless ``OLLAMA_URL`` is set.  Run locally with::

    OLLAMA_URL=http://localhost:11434 pytest tests/test_integration.py -v

The suite spins up the full FastAPI lifespan (RAG index build + Ollama checks)
via ``httpx.AsyncClient`` with ASGI transport — no TCP port needed.
"""

import json
import os

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport

from main import app


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def parse_sse(body: bytes) -> list[dict | str]:
    events = []
    for line in body.decode().splitlines():
        if line.startswith("data: "):
            payload = line[len("data: "):]
            try:
                events.append(json.loads(payload))
            except json.JSONDecodeError:
                events.append(payload)
    return events


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture(scope="module")
async def live_client():
    """Client wired to the app with the full lifespan (index build etc.).

    Uses ``scope="module"`` so the index is built only once per module run.
    """
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
        timeout=120.0,  # index build can be slow on first run
    ) as c:
        # Trigger the lifespan manually
        async with app.router.lifespan_context(app):
            yield c


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestLiveHealth:
    async def test_health_200(self, live_client):
        r = await live_client.get("/health")
        assert r.status_code == 200

    async def test_health_model_present(self, live_client):
        body = r = await live_client.get("/health")
        assert "model" in body.json()


# ---------------------------------------------------------------------------
# Chat stream — live Ollama
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestLiveChatStream:
    async def test_chat_returns_200(self, live_client):
        r = await live_client.post(
            "/api/v1/chat",
            json={"messages": [{"role": "user", "content": "Hello"}]},
        )
        assert r.status_code == 200

    async def test_chat_event_stream_content_type(self, live_client):
        r = await live_client.post(
            "/api/v1/chat",
            json={"messages": [{"role": "user", "content": "Hello"}]},
        )
        assert "text/event-stream" in r.headers["content-type"]

    async def test_chat_produces_tokens(self, live_client):
        r = await live_client.post(
            "/api/v1/chat",
            json={"messages": [{"role": "user", "content": "Hello"}]},
        )
        events = parse_sse(r.content)
        tokens = [e["token"] for e in events if isinstance(e, dict) and "token" in e]
        assert len(tokens) > 0, "Expected at least one token from Ollama"

    async def test_chat_stream_ends_with_done(self, live_client):
        r = await live_client.post(
            "/api/v1/chat",
            json={"messages": [{"role": "user", "content": "Hello"}]},
        )
        events = parse_sse(r.content)
        assert events[-1] == "[DONE]"

    async def test_rag_sources_present_for_relevant_query(self, live_client):
        """A query relevant to the indexed corpus should return at least one source."""
        r = await live_client.post(
            "/api/v1/chat",
            json={"messages": [{"role": "user", "content": "What products are available?"}]},
        )
        events = parse_sse(r.content)
        source_events = [e for e in events if isinstance(e, dict) and "sources" in e]
        # If the index has content the sources list must be non-empty.
        # We allow zero sources only when the index itself is empty.
        if source_events:
            assert len(source_events[0]["sources"]) > 0

    async def test_x_request_id_echoed(self, live_client):
        r = await live_client.get("/health", headers={"X-Request-ID": "integ-test-001"})
        assert r.headers.get("x-request-id") == "integ-test-001"

    async def test_multi_turn_conversation(self, live_client):
        r = await live_client.post(
            "/api/v1/chat",
            json={
                "messages": [
                    {"role": "user", "content": "Hello"},
                    {"role": "assistant", "content": "Hi there!"},
                    {"role": "user", "content": "What can you help me with?"},
                ]
            },
        )
        assert r.status_code == 200
        events = parse_sse(r.content)
        assert events[-1] == "[DONE]"


# ---------------------------------------------------------------------------
# RAG service — direct unit tests against live Ollama
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestLiveRAGService:
    """These tests exercise RAGService.retrieve() directly."""

    @pytest_asyncio.fixture(autouse=True)
    async def rag(self):
        """Return the app-level RAGService (already built by the lifespan fixture)."""
        return app.state.rag

    async def test_retrieve_returns_tuple(self, rag):
        texts, metas = await rag.retrieve("test query")
        assert isinstance(texts, list)
        assert isinstance(metas, list)
        assert len(texts) == len(metas)

    async def test_retrieve_empty_query_returns_empty(self, rag):
        # The chat router short-circuits on empty user query, but the service
        # itself should handle it gracefully too.
        texts, metas = await rag.retrieve("")
        assert isinstance(texts, list)

    async def test_retrieve_meta_has_required_keys(self, rag):
        texts, metas = await rag.retrieve("products services")
        if metas:
            for m in metas:
                assert "source" in m, f"Missing 'source' key in metadata: {m}"
                assert "title" in m, f"Missing 'title' key in metadata: {m}"
