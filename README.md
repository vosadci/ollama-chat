# Ollama Chat

![CI](https://github.com/vosadci/ollama-chat/actions/workflows/ci.yml/badge.svg)

A local RAG-powered chat app — Flutter frontend + FastAPI backend with local LLM inference via [Ollama](https://ollama.com) and a hybrid retrieval pipeline over your own HTML documents.

## Architecture

```
┌─────────────────────────────────────────────┐
│  Docker Compose                              │
│                                             │
│  frontend (nginx :3000) ──▶ backend (:8000) │
│                                    │        │
└────────────────────────────────────┼────────┘
                                     │ host.docker.internal:11434
                           Ollama (native, Metal GPU)
```

- **Frontend** — Flutter web, served by nginx, proxies API calls to the backend
- **Backend** — FastAPI with SSE streaming, ChromaDB vector store, BM25 hybrid search
- **Ollama** — runs natively on the host (GPU acceleration); containers reach it via `host.docker.internal`

## Quick Start

**Prerequisites:** [Docker Desktop](https://www.docker.com/products/docker-desktop/), [Ollama](https://ollama.com)

```bash
git clone <repo> && cd ollama-chat
make setup   # copies .env, pulls Ollama models (~5GB, one-time)
make run     # builds and starts both containers
open http://localhost:3000
```

The app comes with sample HTML documents in `backend/data/sample/` so it works out of the box. To use your own content, drop HTML files into that directory (or point `DATA_PATH` elsewhere) and restart the backend to re-index.

## Make Commands

| Command | Description |
|---|---|
| `make setup` | First-time setup: copy `.env`, pull Ollama models |
| `make run` | Start backend + frontend via Docker Compose |
| `make stop` | Stop all containers |
| `make logs` | Tail container logs |
| `make build` | Rebuild images without cache |
| `make dev` | Run backend natively with hot reload |
| `make dev-web` | Run Flutter web in Chrome (hot reload, connects to local backend) |
| `make test` | Run all tests — backend (60) + frontend (50) |
| `make test-backend` | Backend tests only — fully offline, ~1s |
| `make test-frontend` | Flutter widget tests only — fully offline, ~3s |
| `make e2e` | End-to-end tests in visible macOS window against the live backend |
| `make clean` | Remove containers and local images |

## Development Workflow

**Backend changes** — skip Docker, use hot reload:
```bash
make dev
# Edit any .py file → instant reload
```

**Flutter web changes** — hot reload in Chrome:
```bash
make dev-web
# Connects to localhost:8000 directly
```

**Flutter iOS:**
```bash
cd frontend && flutter run -d "iPhone 17 Pro Max" --no-enable-impeller
```

## Testing

```bash
make test           # all 110 tests (offline, ~5s)
make test-backend   # 60 backend tests: RAG pipeline + API endpoints
make test-frontend  # 50 Flutter widget tests: model, widgets, ChatScreen flows
```

End-to-end tests drive the real app in a desktop window against the live backend:
```bash
make dev &          # start backend
make e2e            # opens desktop window, runs 7 full-stack scenarios
```

## Configuration

Copy `.env.example` to `.env` (done automatically by `make setup`) and adjust as needed. Key variables:

| Variable | Default | Description |
|---|---|---|
| `OLLAMA_URL` | `http://host.docker.internal:11434` | Ollama endpoint (Docker) |
| `MODEL` | `llama3.1:8b` | Chat model |
| `EMBED_MODEL` | `nomic-embed-text` | Embedding model |
| `DATA_PATH` | `./data/sample` | Directory of HTML files to index |

See [backend/README.md](backend/README.md) for the full variable reference.

## Using Your Own Data

1. Drop HTML files into `backend/data/sample/` (or set `DATA_PATH` to any directory)
2. Delete `backend/chroma_db/` to clear the existing index
3. Restart the backend — it re-indexes on startup

The RAG pipeline extracts text from `<body>`, strips navigation/footer boilerplate, chunks content into ~800-character segments, and builds a hybrid ChromaDB + BM25 index.

## Docs

- [backend/README.md](backend/README.md) — API reference, RAG pipeline, backend setup
- [frontend/README.md](frontend/README.md) — Flutter setup, builds, configuration
