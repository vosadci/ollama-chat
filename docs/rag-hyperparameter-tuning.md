# RAG Hyperparameter Tuning Guide

This guide explains every tunable parameter in the retrieval pipeline, what each one controls, how to diagnose problems, and recommended starting points for corpora of different sizes.

---

## Pipeline overview

```
User query
    │
    ├──► Semantic search  (ChromaDB / HNSW cosine)  → top rag_semantic_candidates
    │
    ├──► BM25 keyword search                         → top rag_bm25_candidates
    │
    ├──► RRF fusion  (k = 60)
    │
    ├──► MMR reranking  (λ = rag_mmr_lambda)         → top rag_top_k
    │
    └──► Context passed to Ollama
```

All parameters are set via environment variables (or `.env`) and map 1-to-1 to settings in `config.py`.

---

## Parameters

### `RAG_CHUNK_SIZE` (default: `800`)

**What it controls**: Maximum number of characters per indexed chunk.

Larger chunks preserve more surrounding context per retrieval hit, but the
model's context window fills faster and individual chunks become less
topically focused (hurting precision).  Smaller chunks are sharper but may
split a sentence or argument mid-way, losing meaning.

| Corpus type | Recommended range |
|---|---|
| Dense technical / legal prose | 600–900 |
| FAQ / short paragraphs | 300–500 |
| Mixed / unknown | 700–900 (default) |

Increase if retrieved chunks frequently feel truncated mid-sentence.
Decrease if answers contain irrelevant flanking text.

---

### `RAG_CHUNK_OVERLAP` (default: `80`)

**What it controls**: Number of characters repeated between adjacent chunks.

Overlap prevents a sentence from being split exactly at a chunk boundary and
"lost" from both halves.  A typical value is 10–15 % of `RAG_CHUNK_SIZE`.

- Too low (< 5 %): boundary sentences are often incomplete.
- Too high (> 25 %): index size grows noticeably with diminishing returns.

**Rule of thumb**: `RAG_CHUNK_OVERLAP = round(RAG_CHUNK_SIZE * 0.10)`.

---

### `RAG_SEMANTIC_CANDIDATES` (default: `15`)

**What it controls**: How many chunks ChromaDB returns for the embedding
(cosine similarity) query before fusion.

Higher values give RRF more material to work with at the cost of more
ChromaDB I/O.  Below 10 the BM25 signal is often suppressed entirely;
above 30 you're unlikely to recover anything useful from the tail.

| Index size | Recommended |
|---|---|
| < 500 chunks | 10–15 |
| 500–5 000 | 15–20 |
| > 5 000 | 20–30 |

---

### `RAG_BM25_CANDIDATES` (default: `15`)

**What it controls**: How many chunks the BM25 index nominates per query.

BM25 excels at exact-term recall (model names, error codes, proper nouns).
Keep it equal to `RAG_SEMANTIC_CANDIDATES` as a starting point — there is
little reason to diverge unless your corpus is predominantly keyword-heavy
(increase BM25) or entirely conceptual / conversational (decrease BM25).

---

### `RAG_TOP_K` (default: `5`)

**What it controls**: The final number of chunks sent to the LLM as context.

This is the most impactful parameter for answer quality and cost.

- **Too low (1–2)**: model lacks breadth; multi-part questions are poorly
  served; sources list looks sparse.
- **Too high (> 8)**: model context fills up; latency increases; the model
  may fixate on irrelevant chunks that sneaked through reranking.
- **5** is a well-supported default across the RAG literature.

Increase to 7–8 when questions are consistently multi-faceted.  Decrease to
3–4 for very focused single-document corpora.

`RAG_SEMANTIC_CANDIDATES` and `RAG_BM25_CANDIDATES` should both remain
larger than `RAG_TOP_K` (the pipeline uses `RAG_TOP_K * 3` as the MMR
candidate pool internally).

---

### `RAG_MMR_LAMBDA` (default: `0.7`)

**What it controls**: Trade-off between relevance and diversity in the
Maximal Marginal Relevance reranking step.

```
score = λ × relevance  −  (1 − λ) × max_redundancy_to_selected
```

- `λ = 1.0` — pure relevance; top-k chunks may all be near-duplicates.
- `λ = 0.0` — pure diversity; may select chunks unrelated to the query.
- `λ = 0.7` — 70 % relevance, 30 % diversity (default, good general starting
  point).

Lower `λ` (0.5–0.6) when you see the model repeating itself because several
retrieved chunks contain the same paragraph (common in mirrored or templated
HTML).  Raise `λ` (0.8–0.9) when the corpus is highly varied and relevance
is more important than coverage.

---

## Diagnosing common problems

### "The model ignores my documents"
- Check `DATA_PATH` contains parseable `.html` files. Directories listed in `DATA_EXCLUDED_DIRS` are skipped (default: `en,ru,language,themes,plugins,modules,storage,combine`).
- Run with `LOG_LEVEL=DEBUG` and look for `"Index complete: N chunks"` — if N is 0 the index is empty.
- Lower `RAG_CHUNK_SIZE` to check whether large chunks are passing the 200-character minimum.

### "Answers are repetitive / the model echoes the same fact"
- Lower `RAG_MMR_LAMBDA` to 0.5–0.6 to boost diversity.
- Verify source HTML does not have near-duplicate pages (language mirrors, pagination).

### "Answers are vague — the model says 'I don't know'"
- Increase `RAG_TOP_K` from 5 to 7.
- Increase `RAG_SEMANTIC_CANDIDATES` and `RAG_BM25_CANDIDATES` by 5 each.
- Check the embed model: `nomic-embed-text` is a strong default; `mxbai-embed-large` can improve dense technical corpora.

### "Retrieval is slow"
- Reduce `RAG_SEMANTIC_CANDIDATES` and `RAG_BM25_CANDIDATES`.
- Ensure ChromaDB's HNSW index is not re-built on every startup (`chroma_db/` volume is persisted in Docker Compose).
- The BM25 index is serialised to `BM25_CACHE_PATH` after the first build and reloaded on subsequent startups — cold-start rebuild only happens when the cache is missing or the index is empty.

### "Sources list contains irrelevant pages"
- Lower `RAG_TOP_K` to 3.
- Raise `RAG_MMR_LAMBDA` slightly.
- Add irrelevant directory names to `DATA_EXCLUDED_DIRS` (comma-separated env var).

---

## Recommended profiles

| Scenario | CHUNK_SIZE | OVERLAP | SEMANTIC | BM25 | TOP_K | MMR_λ |
|---|---|---|---|---|---|---|
| Small FAQ (< 50 pages) | 400 | 40 | 10 | 10 | 3 | 0.7 |
| General knowledge base (default) | 800 | 80 | 15 | 15 | 5 | 0.7 |
| Large technical docs (> 500 pages) | 900 | 90 | 20 | 20 | 7 | 0.6 |
| Keyword-heavy (error codes / IDs) | 700 | 70 | 12 | 20 | 5 | 0.75 |

---

## Rebuilding the index after changing chunk parameters

`RAG_CHUNK_SIZE` or `RAG_CHUNK_OVERLAP` changes invalidate the stored
embeddings.  Delete the ChromaDB directory and restart:

```bash
# Docker Compose
docker compose down
rm -rf ./chroma_db          # or the volume path in docker-compose.yml
docker compose up
```

Changing `RAG_TOP_K`, `RAG_MMR_LAMBDA`, `RAG_SEMANTIC_CANDIDATES`, or
`RAG_BM25_CANDIDATES` does **not** require a reindex — they affect only query
time behaviour.
