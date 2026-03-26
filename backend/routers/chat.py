import json
import logging
from typing import AsyncIterator, Literal

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from services.ollama import stream_chat
from services.rag import retrieve

router = APIRouter()
logger = logging.getLogger(__name__)


class ChatMessage(BaseModel):
    role: Literal["user", "assistant", "system"] = Field(
        description="Message author role."
    )
    content: str = Field(
        max_length=32_000,
        description="Message text. Maximum 32 000 characters.",
    )


class ChatRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "messages": [
                    {"role": "user", "content": "Ce carduri oferă Victoriabank?"}
                ]
            }
        }
    )
    messages: list[ChatMessage] = Field(
        min_length=1,
        description="Conversation history. The last message must have role 'user'.",
    )


async def event_generator(
    messages: list[dict],
    context_chunks: list[str],
    sources: list[dict],
) -> AsyncIterator[str]:
    try:
        async for token in stream_chat(messages, context_chunks=context_chunks):
            yield f"data: {json.dumps({'token': token})}\n\n"
    except Exception as e:
        logger.error("Stream error: %s", e)
        yield f"data: {json.dumps({'error': 'An error occurred. Please try again.'})}\n\n"
    finally:
        if sources:
            # Deduplicate by source path, preserve order
            seen: set[str] = set()
            unique_sources = []
            for m in sources:
                key = m.get("source", "")
                if key and key not in seen:
                    seen.add(key)
                    unique_sources.append({"title": m.get("title", key), "source": key})
            if unique_sources:
                yield f"data: {json.dumps({'sources': unique_sources})}\n\n"
        yield "data: [DONE]\n\n"


@router.post(
    "/chat",
    tags=["chat"],
    summary="Stream a chat response",
    response_description="Server-Sent Event stream (text/event-stream)",
    responses={
        200: {"description": "SSE stream — see streaming protocol in the API overview."},
        422: {"description": "Validation error (e.g. content too long, invalid role)."},
    },
)
async def chat(request: ChatRequest):
    """
    Send a conversation history and receive a streaming response.

    The response is a `text/event-stream` where each `data:` line contains a JSON
    object. See the API overview for the full event schema.

    The last message in `messages` must have `role: "user"` — it is used as the
    RAG retrieval query to fetch relevant context from the knowledge base.
    """
    messages = [m.model_dump() for m in request.messages]

    user_query = next(
        (m.content for m in reversed(request.messages) if m.role == "user"),
        "",
    )
    context_chunks, context_meta = await retrieve(user_query) if user_query else ([], [])

    return StreamingResponse(
        event_generator(messages, context_chunks, context_meta),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
