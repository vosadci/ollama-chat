"""
IP-based sliding-window rate limiter.

Implemented as a FastAPI dependency rather than Starlette middleware so it can
return a structured 429 JSON body and integrate cleanly with the OpenAPI schema.

No external packages required; uses only asyncio and stdlib.
"""
from __future__ import annotations

import asyncio
import time
from collections import defaultdict, deque
from typing import Callable

from fastapi import Request, HTTPException

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_WINDOW_SECONDS = 60       # rolling window length
_DEFAULT_LIMIT = 10        # max requests per IP per window
_MAX_LEN = 10              # max IP length accepted from forwarded headers (safety)

# Global in-process store — safe for a single-worker uvicorn deployment.
# Keys are client IP strings; values are deques of monotonic timestamps.
_COUNTS: dict[str, deque] = defaultdict(deque)
_LOCK = asyncio.Lock()


# ---------------------------------------------------------------------------
# Public factory
# ---------------------------------------------------------------------------

def rate_limit(max_calls: int = _DEFAULT_LIMIT, window: int = _WINDOW_SECONDS) -> Callable:
    """Return a FastAPI dependency that enforces per-IP rate limiting.

    Usage::

        @router.post("/chat")
        async def chat(
            request: ChatRequest,
            rag: RAGService = Depends(get_rag_service),
            _: None = Depends(rate_limit()),   # ← inject with defaults
        ): ...

    Args:
        max_calls: Maximum requests allowed per ``window`` seconds. Default 10.
        window:    Rolling window length in seconds. Default 60.

    Raises:
        HTTPException(429): When the caller exceeds the limit.
    """
    async def _check(request: Request) -> None:
        ip = _client_ip(request)
        now = time.monotonic()
        cutoff = now - window

        async with _LOCK:
            timestamps = _COUNTS[ip]
            # Drop timestamps that have fallen outside the window
            while timestamps and timestamps[0] < cutoff:
                timestamps.popleft()

            if len(timestamps) >= max_calls:
                oldest = timestamps[0]
                retry_after = int(oldest + window - now) + 1
                raise HTTPException(
                    status_code=429,
                    detail={
                        "error": "rate_limit_exceeded",
                        "message": f"Too many requests. Retry after {retry_after}s.",
                        "retry_after": retry_after,
                    },
                    headers={"Retry-After": str(retry_after)},
                )

            timestamps.append(now)

    return _check


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _client_ip(request: Request) -> str:
    """Return the most accurate client IP available."""
    # Trust X-Forwarded-For only for the first token (edge sets it).
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()[:64]
    if request.client:
        return request.client.host
    return "unknown"
