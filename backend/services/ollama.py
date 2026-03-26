import json
from typing import AsyncIterator

import httpx

from config import settings


async def stream_chat(
    messages: list[dict],
    context_chunks: list[str] | None = None,
) -> AsyncIterator[str]:
    """Yield raw text tokens from Ollama's streaming /api/chat endpoint."""
    if context_chunks:
        context = "\n\n---\n\n".join(context_chunks)
        system_msg = {
            "role": "system",
            "content": (
                "You are a helpful assistant. Answer ONLY based on the information provided below. "
                "If the answer is not in the provided information, say you don't have that information. "
                "Do not use general knowledge. Do not make up information.\n\n"
                f"DOCUMENTS:\n{context}"
            ),
        }
        messages = [system_msg, *messages]

    payload = {
        "model": settings.model,
        "messages": messages,
        "stream": True,
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
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
