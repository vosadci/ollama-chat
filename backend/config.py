from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    ollama_url: str = "http://localhost:11434"
    model: str = "llama3.1:8b"
    host: str = "0.0.0.0"  # nosec B104 — intentional: containerised service binds all interfaces
    port: int = 8000
    # Comma-separated list of allowed CORS origins.
    # Use "*" only for fully local/private deployments.
    # Example: CORS_ORIGINS=http://localhost:3000,https://chat.example.com
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:8080"]

    embed_model: str = "nomic-embed-text"
    chroma_path: str = "./chroma_db"
    chroma_collection: str = "ollama_chat"
    rag_top_k: int = 5
    rag_semantic_candidates: int = 15
    rag_bm25_candidates: int = 15
    rag_mmr_lambda: float = 0.7
    rag_chunk_size: int = 800
    rag_chunk_overlap: int = 80
    data_path: str = "./data/sample"

    @field_validator("rag_top_k", "rag_semantic_candidates", "rag_bm25_candidates")
    @classmethod
    def _positive_int(cls, v: int, info) -> int:
        if v <= 0:
            raise ValueError(f"{info.field_name} must be a positive integer, got {v}")
        return v

    @field_validator("rag_mmr_lambda")
    @classmethod
    def _lambda_range(cls, v: float) -> float:
        if not (0.0 <= v <= 1.0):
            raise ValueError(f"rag_mmr_lambda must be in [0, 1], got {v}")
        return v

    @field_validator("rag_chunk_size")
    @classmethod
    def _chunk_size_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError(f"rag_chunk_size must be positive, got {v}")
        return v

    @field_validator("rag_chunk_overlap")
    @classmethod
    def _overlap_non_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError(f"rag_chunk_overlap must be non-negative, got {v}")
        return v

    @model_validator(mode="after")
    def _overlap_less_than_chunk_size(self) -> "Settings":
        if self.rag_chunk_overlap >= self.rag_chunk_size:
            raise ValueError(
                f"rag_chunk_overlap ({self.rag_chunk_overlap}) must be less than "
                f"rag_chunk_size ({self.rag_chunk_size}); otherwise chunk_text() "
                "would loop forever."
            )
        return self

    # System prompt prepended to every chat request when RAG context is present.
    # Override in .env or via SYSTEM_PROMPT environment variable.
    system_prompt: str = (
        "You are a helpful assistant. Answer ONLY based on the information provided below. "
        "If the answer is not in the provided information, say you don't have that information. "
        "Do not use general knowledge. Do not make up information.\n\n"
        "DOCUMENTS:\n{context}"
    )

    # Comma-separated list of subdirectory names to skip during HTML indexing.
    # Useful for excluding language mirrors, theme files, and plugin assets.
    # Example: DATA_EXCLUDED_DIRS=en,ru,themes,plugins
    data_excluded_dirs: str = "en,ru,language,themes,plugins,modules,storage,combine"

    # Path for the persisted BM25 index (relative to the working directory or absolute).
    # Stored alongside the ChromaDB data so both survive container restarts.
    bm25_cache_path: str = "./chroma_db/bm25_index.pkl"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
