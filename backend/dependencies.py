"""FastAPI dependency functions shared across routers."""

from fastapi import Request

from services.rag import RAGService


def get_rag_service(request: Request) -> RAGService:
    """Return the application-scoped RAGService instance.

    The instance is created in main.py's lifespan handler and stored on
    app.state.rag.  Inject into route handlers via Depends(get_rag_service).
    """
    return request.app.state.rag
