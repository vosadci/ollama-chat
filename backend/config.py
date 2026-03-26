from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    ollama_url: str = "http://localhost:11434"
    model: str = "llama3.1:8b"
    host: str = "0.0.0.0"
    port: int = 8000

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

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
