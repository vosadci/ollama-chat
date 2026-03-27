import asyncio
import logging
import pickle
from html.parser import HTMLParser
from pathlib import Path

import chromadb
import httpx
from rank_bm25 import BM25Okapi

from config import settings

logger = logging.getLogger(__name__)


def _get_excluded_dirs() -> frozenset[str]:
    """Parse DATA_EXCLUDED_DIRS from settings into a frozenset.

    Evaluated lazily so that test overrides applied after import take effect.
    """
    raw = settings.data_excluded_dirs
    return frozenset(d.strip() for d in raw.split(",") if d.strip())


# ---------------------------------------------------------------------------
# HTML parsing
# ---------------------------------------------------------------------------

class _BankHTMLExtractor(HTMLParser):
    _SKIP_TAGS = frozenset(["script", "style", "svg", "noscript"])
    _STRUCTURAL_SKIP = frozenset(["nav", "header", "footer"])
    _BLOCK_TAGS = frozenset([
        "p", "h1", "h2", "h3", "h4", "h5", "li", "td", "th",
        "dt", "dd", "blockquote", "section", "article", "div",
    ])

    def __init__(self) -> None:
        super().__init__()
        self._skip_depth = 0
        self._structural_depth = 0
        self._buf: list[str] = []
        self._blocks: list[str] = []
        self.title = ""
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag in self._SKIP_TAGS:
            self._skip_depth += 1
        elif tag in self._STRUCTURAL_SKIP:
            self._structural_depth += 1
        elif tag == "title":
            self._in_title = True
        elif tag in self._BLOCK_TAGS:
            self._flush()

    def handle_endtag(self, tag: str) -> None:
        if tag in self._SKIP_TAGS:
            self._skip_depth = max(0, self._skip_depth - 1)
        elif tag in self._STRUCTURAL_SKIP:
            self._structural_depth = max(0, self._structural_depth - 1)
        elif tag == "title":
            self._in_title = False
        elif tag in self._BLOCK_TAGS:
            self._flush()

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if not text:
            return
        if self._in_title and not self.title:
            self.title = text
            return
        if self._skip_depth > 0 or self._structural_depth > 0:
            return
        self._buf.append(text)

    def _flush(self) -> None:
        text = " ".join(self._buf).strip()
        if text:
            self._blocks.append(text)
        self._buf = []

    def get_text(self) -> str:
        self._flush()
        return "\n\n".join(self._blocks)


# ---------------------------------------------------------------------------
# Pure functions — stateless, no globals
# ---------------------------------------------------------------------------

def extract_html_text(path: Path) -> tuple[str, str]:
    """Parse an HTML file and return (title, clean_text). Returns ('', '') on error."""
    try:
        html = path.read_text(encoding="utf-8", errors="ignore")
        parser = _BankHTMLExtractor()
        parser.feed(html)
        return parser.title, parser.get_text()
    except Exception as exc:
        logger.warning("Failed to extract text from %s: %s", path, exc)
        return "", ""


def chunk_text(
    text: str,
    source: str,
    title: str,
    chunk_size: int,
    overlap: int,
) -> list[dict]:
    chunks = []
    start = 0
    step = chunk_size - overlap

    while start < len(text):
        end = start + chunk_size
        if end >= len(text):
            fragment = text[start:]
        else:
            boundary = text.rfind(" ", start, end)
            if boundary == -1 or boundary <= start:
                boundary = end
            fragment = text[start:boundary]

        if fragment.strip():
            prefix = f"{title}: " if (chunks == [] and title) else ""
            chunks.append({
                "text": prefix + fragment.strip(),
                "source": source,
                "title": title,
                "chunk_index": len(chunks),
            })

        if end >= len(text):
            break
        start += step

    return chunks


def get_html_files(data_path: Path) -> list[Path]:
    excluded = _get_excluded_dirs()
    files = []
    for path in data_path.rglob("*.html"):
        parts = set(path.relative_to(data_path).parts[:-1])
        if parts & excluded:
            continue
        files.append(path)
    return files


def _rrf(rankings: list[list[str]], k: int = 60) -> list[str]:
    scores: dict[str, float] = {}
    for ranked_ids in rankings:
        for rank, doc_id in enumerate(ranked_ids):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank + 1)
    return sorted(scores, key=lambda x: scores[x], reverse=True)


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _mmr_rerank(
    candidates: list[tuple[str, dict, float]],
    query_tokens: set[str],
    top_k: int,
    lam: float,
) -> list[tuple[str, dict]]:
    """Select top_k chunks maximising relevance and minimising redundancy."""
    selected: list[tuple[str, dict]] = []
    remaining = list(candidates)

    while len(selected) < top_k and remaining:
        best_idx = 0
        best_score = float("-inf")
        for i, (text, meta, rrf_score) in enumerate(remaining):
            tokens = set(text.lower().split())
            relevance = _jaccard(tokens, query_tokens) * 0.3 + rrf_score * 0.7
            if selected:
                redundancy = max(
                    _jaccard(tokens, set(s.lower().split()))
                    for s, _ in selected
                )
            else:
                redundancy = 0.0
            score = lam * relevance - (1 - lam) * redundancy
            if score > best_score:
                best_score = score
                best_idx = i
        text, meta, _ = remaining.pop(best_idx)
        selected.append((text, meta))

    return selected


# ---------------------------------------------------------------------------
# RAGService — encapsulates all mutable RAG state
# ---------------------------------------------------------------------------

class RAGService:
    """Holds the HTTP client, ChromaDB collection, and BM25 index.

    Instantiated once at application startup (see main.py lifespan) and
    injected into route handlers via FastAPI's dependency system.  All
    mutable state lives on the instance, making concurrent access safe
    when uvicorn runs a single worker (the default).
    """

    def __init__(self) -> None:
        # Sync client for embedding (called via asyncio.to_thread)
        self._http_client = httpx.Client(timeout=300.0)
        # Async client shared across all chat-stream requests for connection pooling
        self._async_http_client = httpx.AsyncClient(timeout=120.0)
        self._collection: chromadb.Collection | None = None
        self._bm25: BM25Okapi | None = None
        self._bm25_ids: list[str] = []

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Close the sync HTTP client. Call from the lifespan shutdown hook."""
        self._http_client.close()

    async def aclose(self) -> None:
        """Close both HTTP clients. Called from the async lifespan shutdown hook."""
        self._http_client.close()
        await self._async_http_client.aclose()

    # ------------------------------------------------------------------
    # Embedding (ChromaDB-compatible interface)
    # ------------------------------------------------------------------

    def _embed(self, texts: list[str]) -> list[list[float]]:
        """Call Ollama's /api/embed endpoint and return dense vectors."""
        try:
            response = self._http_client.post(
                f"{settings.ollama_url}/api/embed",
                json={"model": settings.embed_model, "input": texts},
            )
            response.raise_for_status()
            return response.json()["embeddings"]
        except Exception as exc:
            raise RuntimeError(f"Embedding failed: {exc}") from exc

    def _embedding_function(self) -> "RAGService._EmbeddingCallable":
        """Return a ChromaDB-compatible embedding callable backed by this service."""
        return RAGService._EmbeddingCallable(self)

    class _EmbeddingCallable:
        """Thin ChromaDB adapter that delegates to RAGService._embed."""

        def __init__(self, service: "RAGService") -> None:
            self._service = service

        def name(self) -> str:
            return "ollama"

        def embed_query(self, input: str) -> list[float]:
            return self([input])[0]

        def __call__(self, input: list[str]) -> list[list[float]]:
            return self._service._embed(input)

    # ------------------------------------------------------------------
    # ChromaDB collection
    # ------------------------------------------------------------------

    def _get_collection(self) -> chromadb.Collection:
        if self._collection is not None:
            return self._collection
        client = chromadb.PersistentClient(path=settings.chroma_path)
        self._collection = client.get_or_create_collection(
            name=settings.chroma_collection,
            embedding_function=self._embedding_function(),
            metadata={"hnsw:space": "cosine"},
        )
        return self._collection

    # ------------------------------------------------------------------
    # BM25 index
    # ------------------------------------------------------------------

    def _bm25_cache_path(self) -> Path:
        return Path(settings.bm25_cache_path)

    def _load_bm25_from_cache(self) -> bool:
        """Load a previously serialised BM25 index. Returns True on success."""
        cache = self._bm25_cache_path()
        if not cache.exists():
            return False
        try:
            with cache.open("rb") as fh:
                data = pickle.load(fh)
            self._bm25 = data["bm25"]
            self._bm25_ids = data["ids"]
            logger.info("BM25 index loaded from cache (%d chunks).", len(self._bm25_ids))
            return True
        except Exception as exc:
            logger.warning("Failed to load BM25 cache: %s — will rebuild.", exc)
            return False

    def _save_bm25_to_cache(self) -> None:
        """Serialise the current BM25 index to disk for fast cold-start reuse."""
        cache = self._bm25_cache_path()
        try:
            cache.parent.mkdir(parents=True, exist_ok=True)
            with cache.open("wb") as fh:
                pickle.dump({"bm25": self._bm25, "ids": self._bm25_ids}, fh)
            logger.info("BM25 index saved to cache (%s).", cache)
        except Exception as exc:
            logger.warning("Failed to save BM25 cache: %s", exc)

    def _build_bm25(self, collection: chromadb.Collection) -> None:
        result = collection.get(include=["documents"])
        docs = result["documents"]
        ids = result["ids"]
        tokenised = [doc.lower().split() for doc in docs]
        self._bm25 = BM25Okapi(tokenised)
        self._bm25_ids = ids
        logger.info("BM25 index built over %d chunks.", len(ids))
        self._save_bm25_to_cache()

    # ------------------------------------------------------------------
    # Indexing
    # ------------------------------------------------------------------

    async def build_index(self) -> None:
        collection = await asyncio.to_thread(self._get_collection)
        count = await asyncio.to_thread(collection.count)

        if count > 0:
            logger.info("Index already built (%d chunks), loading BM25 cache...", count)
            # Try fast path: load persisted index from disk.
            loaded = await asyncio.to_thread(self._load_bm25_from_cache)
            if not loaded:
                # Cache missing or corrupt — rebuild and re-save.
                logger.info("BM25 cache miss — rebuilding from ChromaDB.")
                await asyncio.to_thread(self._build_bm25, collection)
            return

        data_path = Path(settings.data_path)
        files = get_html_files(data_path)
        logger.info("Indexing %d HTML files...", len(files))

        batch_docs: list[str] = []
        batch_meta: list[dict] = []
        batch_ids: list[str] = []
        total_chunks = 0

        for i, path in enumerate(files):
            title, text = extract_html_text(path)
            if len(text) < 200:
                continue

            rel = str(path.relative_to(data_path))
            chunks = chunk_text(
                text, rel, title,
                settings.rag_chunk_size,
                settings.rag_chunk_overlap,
            )

            for chunk in chunks:
                batch_docs.append(chunk["text"])
                batch_meta.append({"source": chunk["source"], "title": chunk["title"]})
                batch_ids.append(f"{rel}_{chunk['chunk_index']}")

            if len(batch_ids) >= 100:
                await asyncio.to_thread(
                    collection.upsert,
                    documents=batch_docs,
                    metadatas=batch_meta,
                    ids=batch_ids,
                )
                total_chunks += len(batch_ids)
                batch_docs, batch_meta, batch_ids = [], [], []

            if (i + 1) % 50 == 0:
                logger.info("  Processed %d / %d files...", i + 1, len(files))

        if batch_ids:
            await asyncio.to_thread(
                collection.upsert,
                documents=batch_docs,
                metadatas=batch_meta,
                ids=batch_ids,
            )
            total_chunks += len(batch_ids)

        logger.info("Index complete: %d chunks from %d files.", total_chunks, len(files))
        await asyncio.to_thread(self._build_bm25, collection)

    # ------------------------------------------------------------------
    # Retrieval (hybrid: semantic + BM25 + RRF + MMR)
    # ------------------------------------------------------------------

    async def retrieve(self, query: str) -> tuple[list[str], list[dict]]:
        """Return (texts, metadatas) for the top-k most relevant chunks."""
        try:
            collection = await asyncio.to_thread(self._get_collection)

            # --- Semantic retrieval ---
            embeddings = await asyncio.to_thread(self._embed, [query])
            sem_results = await asyncio.to_thread(
                collection.query,
                query_embeddings=embeddings,
                n_results=settings.rag_semantic_candidates,
                include=["documents", "metadatas"],
            )
            sem_ids: list[str] = sem_results["ids"][0]
            sem_docs: list[str] = sem_results["documents"][0]
            sem_meta: list[dict] = sem_results["metadatas"][0]

            # --- BM25 retrieval ---
            bm25_ids: list[str] = []
            if self._bm25 is not None and self._bm25_ids:
                query_tokens = query.lower().split()
                scores = self._bm25.get_scores(query_tokens)
                top_indices = sorted(
                    range(len(scores)), key=lambda i: scores[i], reverse=True
                )[:settings.rag_bm25_candidates]
                bm25_ids = [self._bm25_ids[i] for i in top_indices]

            # --- RRF fusion ---
            fused_ids = _rrf([sem_ids, bm25_ids]) if bm25_ids else sem_ids

            # Build a lookup from what we already have (semantic results)
            id_to_doc = dict(zip(sem_ids, sem_docs))
            id_to_meta = dict(zip(sem_ids, sem_meta))

            # Fetch any BM25-only IDs not already in semantic results
            missing = [i for i in fused_ids[:settings.rag_top_k * 2] if i not in id_to_doc]
            if missing:
                extra = await asyncio.to_thread(
                    collection.get,
                    ids=missing,
                    include=["documents", "metadatas"],
                )
                for doc_id, doc, meta in zip(extra["ids"], extra["documents"], extra["metadatas"]):
                    id_to_doc[doc_id] = doc
                    id_to_meta[doc_id] = meta

            # Build candidates list (text, metadata, rrf_score) in fused order
            rrf_scores = {doc_id: 1.0 / (i + 1) for i, doc_id in enumerate(fused_ids)}
            candidates = [
                (id_to_doc[doc_id], id_to_meta[doc_id], rrf_scores[doc_id])
                for doc_id in fused_ids
                if doc_id in id_to_doc
            ][:settings.rag_top_k * 3]

            # --- MMR reranking ---
            query_tokens_set = set(query.lower().split())
            reranked = _mmr_rerank(candidates, query_tokens_set, settings.rag_top_k, settings.rag_mmr_lambda)

            texts = [t for t, _ in reranked]
            metadatas = [m for _, m in reranked]
            return texts, metadatas

        except Exception as exc:
            logger.warning("RAG retrieval failed: %s", exc)
            return [], []
