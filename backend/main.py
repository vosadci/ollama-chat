import asyncio
import logging
import os
import uvicorn
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from middleware.request_id import RequestIDMiddleware
from routers.chat import router as chat_router
from services.rag import RAGService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _check_ollama_sync() -> None:
    """Blocking connectivity probe — intended to run inside asyncio.to_thread."""
    try:
        with httpx.Client(timeout=5.0) as client:
            resp = client.get(f"{settings.ollama_url}/api/tags")
            resp.raise_for_status()
        logger.info("Ollama reachable at %s", settings.ollama_url)
    except Exception as exc:
        logger.warning(
            "Ollama not reachable at %s: %s — will retry on first request.",
            settings.ollama_url,
            exc,
        )


async def _validate_config() -> None:
    """Fail fast on obvious misconfigurations before starting the server.

    Fatal conditions (raise RuntimeError):
      - DATA_PATH does not exist or is not a directory
      - CHROMA_PATH parent directory is not writable

    Non-fatal conditions (log a warning):
      - OLLAMA_URL is not reachable (Ollama may still be starting up)
    """
    # --- DATA_PATH ---
    data_path = Path(settings.data_path)
    if not data_path.exists():
        raise RuntimeError(
            f"DATA_PATH '{data_path}' does not exist. "
            "Mount the directory or update DATA_PATH in .env."
        )
    if not data_path.is_dir():
        raise RuntimeError(f"DATA_PATH '{data_path}' exists but is not a directory.")

    # --- CHROMA_PATH (writable) ---
    chroma_path = Path(settings.chroma_path)
    chroma_parent = chroma_path.parent
    if not os.access(chroma_parent, os.W_OK):
        raise RuntimeError(
            f"CHROMA_PATH parent '{chroma_parent}' is not writable. "
            "Check volume mount permissions."
        )

    # --- OLLAMA_URL reachability (non-fatal: Ollama may still be starting) ---
    # Run the blocking httpx call off the event loop to avoid stalling uvicorn.
    await asyncio.to_thread(_check_ollama_sync)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await _validate_config()
    rag = RAGService()
    app.state.rag = rag
    await rag.build_index()
    yield
    await rag.aclose()


app = FastAPI(
    title="Ollama Chat API",
    summary="Local RAG-powered chat assistant — streams answers from your own HTML documents.",
    description="""
## Overview
Streams answers to user questions using a local LLM (Ollama) augmented with a
Retrieval-Augmented Generation (RAG) pipeline over your own HTML content.

## Streaming protocol
Responses are delivered as **Server-Sent Events** (`text/event-stream`).
Each event is a JSON object on a `data:` line followed by a blank line:

| Event | Shape | Description |
|---|---|---|
| token | `{"token": "..."}` | Incremental text chunk |
| sources | `{"sources": [{"title": "...", "source": "..."}]}` | RAG attribution, sent once at end |
| error | `{"error": "..."}` | Stream-level error message |
| done | `[DONE]` | Stream complete marker |
""",
    version="1.0.0",
    openapi_tags=[
        {"name": "chat", "description": "Streaming chat endpoint."},
        {"name": "health", "description": "Liveness probe."},
    ],
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-Request-ID"],
    expose_headers=["X-Request-ID"],
)
app.add_middleware(RequestIDMiddleware)

app.include_router(chat_router, prefix="/api/v1")


@app.get("/health", tags=["health"], summary="Liveness probe")
async def health():
    """Returns 200 when the service is up. Used by the Docker healthcheck."""
    return {"status": "ok", "model": settings.model}


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=True,
    )
