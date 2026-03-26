import logging
import uvicorn
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from routers.chat import router as chat_router
from services.rag import build_index, close_http_client

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await build_index()
    yield
    close_http_client()


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
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

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
