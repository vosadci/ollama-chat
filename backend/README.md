# Ollama Chat — Backend

FastAPI backend for Ollama Chat. Provides a streaming chat API powered by a local [Ollama](https://ollama.com) LLM, with a RAG (Retrieval-Augmented Generation) pipeline over HTML documents.

## Architecture

- **FastAPI + uvicorn** — HTTP server with Server-Sent Events (SSE) for streaming
- **Ollama** — local LLM inference (`llama3.1:8b` for chat, `nomic-embed-text` for embeddings)
- **ChromaDB** — persistent vector store for semantic search
- **BM25 + RRF fusion** — hybrid keyword + semantic retrieval
- **MMR reranking** — diversity-aware result reranking

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
| `DATA_PATH` | `./data/sample` | Directory of HTML files to index |
| `CHROMA_PATH` | `./chroma_db` | ChromaDB persistence directory |
| `RAG_TOP_K` | `5` | Number of chunks returned per query |
| `RAG_MMR_LAMBDA` | `0.7` | MMR relevance/diversity balance (0–1) |

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
pytest           # all 60 tests
pytest -v        # verbose output
```

All tests are fully offline — no Ollama, no ChromaDB, no running server required.

| File | What it tests |
|---|---|
| `tests/test_rag.py` | RAG pipeline: HTML extraction, chunking, BM25, RRF, MMR (37 tests) |
| `tests/test_api.py` | API endpoints: SSE stream structure, input validation, error handling, OpenAPI schema (23 tests) |

API tests use `httpx.AsyncClient` with `ASGITransport` — the app is tested in-process without starting a server. External dependencies (Ollama, ChromaDB) are mocked.
