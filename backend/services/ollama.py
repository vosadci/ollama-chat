import json
from typing import AsyncIterator

import httpx

from config import settings


async def stream_chat(
    messages: list[dict],
    context_chunks: list[str] | None = None,
    http_client: httpx.AsyncClient | None = None,
) -> AsyncIterator[str]:
    """Yield raw text tokens from Ollama's streaming /api/chat endpoint.

    Args:
        messages:      Conversation history in Ollama's message format.
        context_chunks: RAG-retrieved text chunks to inject as a system message.
        http_client:   Optional shared AsyncClient. When provided, the caller
                       is responsible for its lifecycle; no new client is created.
                       When omitted, a temporary client is created per call
                       (intended only for unit tests / standalone use).
    """
    if context_chunks:
        context = "\n\n---\n\n".join(context_chunks)
        system_content = settings.system_prompt.format(context=context)
        messages = [{"role": "system", "content": system_content}, *messages]

    payload = {
        "model": settings.model,
        "messages": messages,
        "stream": True,
    }

    async def _do_stream(client: httpx.AsyncClient) -> AsyncIterator[str]:
        async with client.stream(
            "POST",
            f"{settings.ollama_url}/api/chat",
            json=payload,
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line:
                    continue
                try:
                    chunk = json.loads(line)
                except json.JSONDecodeError:
                    continue

                content = chunk.get("message", {}).get("content", "")
                if content:
                    yield content

                if chunk.get("done"):
                    break

    if http_client is not None:
        async for token in _do_stream(http_client):
            yield token
    else:
        async with httpx.AsyncClient(timeout=120.0) as client:
            async for token in _do_stream(client):
                yield token
