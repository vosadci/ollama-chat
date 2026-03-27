# Ollama Chat — Backend

FastAPI backend for Ollama Chat. Provides a streaming chat API powered by a local [Ollama](https://ollama.com) LLM, with a RAG (Retrieval-Augmented Generation) pipeline over HTML documents.

## Architecture

- **FastAPI + uvicorn** — HTTP server with Server-Sent Events (SSE) for streaming
- **Ollama** — local LLM inference (`llama3.1:8b` for chat, `nomic-embed-text` for embeddings)
- **ChromaDB** — persistent vector store for semantic search
- **BM25 + RRF fusion** — hybrid keyword + semantic retrieval
- **MMR reranking** — diversity-aware result reranking
- **`RAGService`** — encapsulates all retrieval state; instantiated once at startup via FastAPI lifespan and injected into routes via `dependencies.py`
- **`RequestIDMiddleware`** — attaches an `X-Request-ID` correlation header to every request and response

## Prerequisites

- Python 3.10+
- [Ollama](https://ollama.com) running locally on port 11434

Pull the required models:

```bash
ollama pull llama3.1:8b
ollama pull nomic-embed-text
```

## Docker (recommended)

From the repo root:

```bash
make setup   # copies .env, pulls Ollama models
make run     # starts backend + frontend via Docker Compose
```

The backend is available at `http://localhost:8000`. See the root [README](../README.md) for the full Docker workflow.

## Local Setup (for development)

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

## Configuration

All settings are in [config.py](config.py) and can be overridden via environment variables or a `.env` file (copy from [../.env.example](../.env.example)):

| Variable | Default | Description |
|---|---|---|
| `OLLAMA_URL` | `http://localhost:11434` | Ollama server URL |
| `MODEL` | `llama3.1:8b` | Chat model |
| `EMBED_MODEL` | `nomic-embed-text` | Embedding model |
| `HOST` | `0.0.0.0` | Server bind host |
| `PORT` | `8000` | Server port |
| `CORS_ORIGINS` | `http://localhost:3000,...` | Comma-separated allowed CORS origins |
| `DATA_PATH` | `./data/sample` | Directory of HTML files to index |
| `DATA_EXCLUDED_DIRS` | `en,ru,language,...` | Comma-separated subdirectory names to skip during indexing |
| `CHROMA_PATH` | `./chroma_db` | ChromaDB persistence directory |
| `BM25_CACHE_PATH` | `./chroma_db/bm25_index.pkl` | Path for the persisted BM25 index |
| `RAG_TOP_K` | `5` | Final number of chunks sent to the LLM (must be > 0) |
| `RAG_SEMANTIC_CANDIDATES` | `15` | ChromaDB candidates before RRF fusion (must be > 0) |
| `RAG_BM25_CANDIDATES` | `15` | BM25 candidates before RRF fusion (must be > 0) |
| `RAG_MMR_LAMBDA` | `0.7` | MMR relevance/diversity balance (0–1 inclusive) |
| `RAG_CHUNK_SIZE` | `800` | Maximum characters per indexed chunk (must be > 0) |
| `RAG_CHUNK_OVERLAP` | `80` | Characters of overlap between adjacent chunks (must be ≥ 0) |
| `SYSTEM_PROMPT` | _(see config.py)_ | System prompt template; use `{context}` as placeholder for retrieved docs |

See [../docs/rag-hyperparameter-tuning.md](../docs/rag-hyperparameter-tuning.md) for tuning guidance, recommended profiles, and diagnostics.

## Running Locally

```bash
# Development (hot reload)
make dev

# Or directly:
source .venv/bin/activate
python main.py
```

The server starts on `http://localhost:8000`. On startup it indexes all HTML files under `DATA_PATH` into ChromaDB (incremental — skips files already indexed).

## Using Your Own Data

Drop HTML files into `backend/data/sample/` (or point `DATA_PATH` at any directory), delete `backend/chroma_db/` to clear the existing index, and restart the backend.

## API

Interactive docs are available when the server is running:
- **Swagger UI** — `http://localhost:8000/docs`
- **ReDoc** — `http://localhost:8000/redoc`
- **OpenAPI JSON** — `http://localhost:8000/openapi.json` (importable into Postman / Insomnia)

### `GET /health`
Returns server status and active model.

### `POST /api/v1/chat`
Streams a chat response as Server-Sent Events.

**Request body:**
```json
{
  "messages": [
    { "role": "user", "content": "What types of accounts are available?" }
  ]
}
```

**SSE events emitted:**
| Event | Data |
|---|---|
| `token` | Incremental text chunk |
| `sources` | JSON array of `{ title, source }` source attributions |
| `error` | Error message string |
| `[DONE]` | Stream complete |

## Running Tests

```bash
source .venv/bin/activate
pytest           # 71 unit tests (offline) + 12 integration tests (skipped by default)
pytest -v        # verbose output
```

Unit tests are fully offline — no Ollama, no ChromaDB, no running server required.

| File | What it tests |
|---|---|
| `tests/test_rag.py` | RAG pipeline: HTML extraction, chunking, BM25, RRF, MMR (37 tests) |
| `tests/test_api.py` | API endpoints: SSE stream, input validation, error handling, OpenAPI schema, X-Request-ID middleware (28 tests) |
| `tests/test_rate_limit.py` | Rate limiter: per-IP windowed counting, 429 response shape, expiry (6 tests) |
| `tests/test_integration.py` | Full-stack: health, live SSE chat, RAG retrieve, multi-turn (12 tests — skipped unless `OLLAMA_URL` is set) |

API tests use `httpx.AsyncClient` with `ASGITransport` — the app is tested in-process without starting a server. External dependencies (Ollama, ChromaDB) are mocked via `app.dependency_overrides`.

To run integration tests against a live Ollama instance:

```bash
OLLAMA_URL=http://localhost:11434 pytest tests/test_integration.py -v
```
