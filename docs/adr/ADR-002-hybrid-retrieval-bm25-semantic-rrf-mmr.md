# ADR-002 — Hybrid retrieval: BM25 + semantic search, fused via RRF, reranked via MMR

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2024-01 |
| Deciders | Project team |

## Context

A RAG pipeline needs a retrieval strategy that surfaces the most relevant chunks from the indexed corpus for a given user query.  Pure dense (embedding-based) retrieval is strong on semantic similarity but misses exact-term matches.  Pure BM25 is good at keyword recall but cannot understand paraphrase or conceptual similarity.

Domain-specific corpora (bank websites, product catalogues, error-code documentation) contain many proper nouns, product codes, and exact strings that dense retrieval often ranks poorly.

Retrieval quality also benefits from diversity: if the top-k chunks are near-duplicates of the same paragraph the model sees little additional information.

Strategies evaluated:

| Strategy | Strengths | Weaknesses |
|---|---|---|
| Dense only | Handles paraphrase; robust to spelling variation | Misses exact-term matches; embedding quality varies by model |
| BM25 only | Exact-term recall; fast; no embedding overhead | No semantic understanding; sensitive to query wording |
| **Hybrid (dense + BM25) + RRF** | Best of both; RRF is parameter-free | Two index structures to maintain |
| Cross-encoder reranking | State-of-the-art reranking | Requires a second model; slow; more ops complexity |
| MMR (Maximal Marginal Relevance) | Reduces redundancy in top-k | Adds a post-fusion step; configurable λ |

## Decision

Use a **hybrid retrieval pipeline**:

1. **Dense retrieval** via ChromaDB HNSW (cosine) → top `RAG_SEMANTIC_CANDIDATES` chunks.
2. **BM25** (`rank_bm25.BM25Okapi`) built in-memory over the full corpus at startup → top `RAG_BM25_CANDIDATES` chunks.
3. **Reciprocal Rank Fusion (RRF, k=60)** merges the two ranked lists into one fused ranking without requiring score normalisation.
4. **MMR reranking** selects the final `RAG_TOP_K` chunks maximising `λ × relevance − (1−λ) × max_redundancy`, using Jaccard similarity on tokens as a cheap proxy.

All parameters are configurable via environment variables (see `config.py`).

### Why RRF over score normalisation

Score normalisation (e.g. min-max across the two retrievers) requires that cosine scores and BM25 scores live on a comparable scale, which they do not.  RRF avoids this entirely: it only uses rank positions, making it robust to score distribution differences and requiring zero hyperparameter tuning beyond the standard `k=60`.

### Why in-memory BM25 rather than a persistent BM25 store

`rank_bm25` builds the index from the ChromaDB document collection at startup (one `collection.get()` call).  For corpora up to ≈ 100 k chunks this fits comfortably in RAM (< 200 MB) and avoids a second persistent store.  Startup time for 10 k chunks is < 1 s.  For larger corpora a persistent BM25 store (e.g. Elasticsearch, Tantivy) would be appropriate.

### Why MMR rather than a cross-encoder

Cross-encoder reranking (e.g. `cross-encoder/ms-marco-MiniLM-L-6-v2`) would improve relevance ranking further, but requires downloading and running a second model, adds ≈ 200–500 ms of inference latency per query, and cannot be served by Ollama.  MMR achieves meaningful diversity gains with zero additional model dependencies, using only tokenised Jaccard overlap.

## Consequences

**Positive**:
- Proper noun / code recall is substantially improved over dense-only retrieval on domain corpora.
- Diversity in the context window reduces "repetition loops" in LLM outputs.
- All parameters are runtime-configurable; no reindex required for tuning retrieval behaviour.
- No additional model or service dependency beyond ChromaDB and Ollama.

**Negative / trade-offs**:
- BM25 index is rebuilt in-memory on every cold start.  For corpora > 100 k chunks this may add several seconds to startup.
- MMR's Jaccard proxy is approximate.  A dense MMR (using cosine of cached embeddings) would be more accurate but requires caching all candidate embeddings.
- RRF `k=60` is a literature-standard default; it is not exposed as a config parameter.  For highly asymmetric retrieval distributions it may need tuning.

## References

- Cormack, G. V. et al. (2009). "Reciprocal Rank Fusion outperforms Condorcet and individual Rank Learning Methods." *SIGIR*.
- Carbonell, J. & Goldstein, J. (1998). "The use of MMR, diversity-based reranking for reordering documents and producing summaries." *SIGIR*.
