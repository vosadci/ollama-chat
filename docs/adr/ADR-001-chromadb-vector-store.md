# ADR-001 — Use ChromaDB as the vector store

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2024-01 |
| Deciders | Project team |

## Context

The RAG pipeline needs a vector store to persist document embeddings and execute approximate nearest-neighbour (ANN) queries at retrieval time.  The store must work without any cloud dependency, run inside a Docker container without a separate process, and support cosine-similarity search over hundreds of thousands of embeddings.

Candidates evaluated:

| Store | Deployment | Persistence | Python API | Notes |
|---|---|---|---|---|
| **ChromaDB** | In-process (Python) | Local filesystem | First-class | MIT licence; persistent HNSW index |
| **Qdrant** | Separate Docker service | Local or cloud | gRPC/REST | Richer filtering; heavier ops |
| **Weaviate** | Separate Docker service | Local or cloud | REST | GraphQL API; more complex |
| **FAISS** | In-process | Manual (numpy) | Lower-level | No metadata store; needs wrapper |
| **pgvector** | Separate PostgreSQL | Full SQL | psycopg2 | Adds a DB dep; overkill for this scale |

## Decision

Use **ChromaDB** (`chromadb` ≥ 0.4) with `PersistentClient` storing the HNSW index on a Docker volume.

Key reasons:

1. **Zero external processes**: ChromaDB runs in-process as a Python library.  No extra service to orchestrate, health-check, or secure.
2. **Persistent by default**: `PersistentClient(path=...)` writes to disk; the index survives container restarts when the path is a named volume.
3. **HNSW cosine similarity**: The built-in HNSW index (`hnsw:space=cosine`) is fast enough for corpora up to ≈ 500 k chunks without tuning.
4. **Metadata filtering**: Every document can carry arbitrary key-value metadata (source path, title) that can be filtered at query time — used for deduplication in the MMR step.
5. **Custom embedding functions**: The `embedding_function` hook lets us back ChromaDB with our own Ollama `/api/embed` call, avoiding a second embedding library.

## Consequences

**Positive**:
- Single-file deployment (`docker-compose.yml` with one volume mount).
- No network round-trips to an external store; lower latency.
- Simple to reset: delete the volume and restart.

**Negative / trade-offs**:
- **Single-process only**: ChromaDB's `PersistentClient` is not safe for concurrent writes from multiple workers.  Uvicorn must run with `--workers 1` (the default).  If horizontal scaling is needed, migrate to Qdrant or pgvector behind a connection pool.
- **No built-in filtering at query time on arbitrary metadata**: metadata filters are possible but use a Chroma-specific DSL that may change across minor versions.
- **HNSW rebuilds on large bulk upserts**: the index is rebuilt in place; for corpora > 1 M chunks consider batch-upsert strategies or an offline import.

## Alternatives rejected

- **Qdrant**: better for multi-replica deployments; not justified for a single-node local assistant.
- **FAISS**: no metadata storage; would require a parallel SQLite or dict, adding complexity.
- **pgvector**: adds a full PostgreSQL dependency for a feature that ChromaDB covers adequately.
