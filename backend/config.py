from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    ollama_url: str = "http://localhost:11434"
    model: str = "llama3.1:8b"
    host: str = "0.0.0.0"
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

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
