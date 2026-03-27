"""X-Request-ID correlation middleware.

Behaviour
---------
* If the incoming request already carries an ``X-Request-ID`` header, that
  value is reused (max 128 chars, stripped to prevent log injection).
* Otherwise a fresh UUID-4 is generated.
* The ID is stored on ``request.state.request_id`` for use in route handlers.
* The ID is stored in a ``ContextVar`` so that *every* log record emitted
  during the request lifecycle carries a ``request_id`` extra field — even
  records from background tasks that don't have access to the request object.
* The ID is echoed back in the ``X-Request-ID`` response header so that
  callers (and their own logs) can correlate requests end-to-end.
"""

import logging
import uuid
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)

_HEADER = "X-Request-ID"
_MAX_LEN = 128

# ---------------------------------------------------------------------------
# Context variable — set once per request by the middleware, readable from
# anywhere in the same async context (including tasks spawned via to_thread).
# ---------------------------------------------------------------------------

_request_id_var: ContextVar[str] = ContextVar("request_id", default="-")


def get_request_id() -> str:
    """Return the current request's correlation ID, or '-' outside a request."""
    return _request_id_var.get()


# ---------------------------------------------------------------------------
# Logging filter — injects the ContextVar value into every log record
# ---------------------------------------------------------------------------

class RequestIDFilter(logging.Filter):
    """Add ``request_id`` to every log record for structured log sinks.

    Attach to the root logger (or any handler) once at startup::

        import logging
        from middleware.request_id import RequestIDFilter

        logging.getLogger().addFilter(RequestIDFilter())
    """

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: A003
        record.request_id = _request_id_var.get()
        return True


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------

class RequestIDMiddleware(BaseHTTPMiddleware):
    """Attach a correlation ID to every request/response pair."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        raw = request.headers.get(_HEADER, "")
        request_id = raw[:_MAX_LEN].strip() if raw.strip() else str(uuid.uuid4())

        # Store on request state for explicit access in handlers
        request.state.request_id = request_id

        # Propagate to all log records via ContextVar
        token = _request_id_var.set(request_id)
        try:
            response = await call_next(request)
        finally:
            _request_id_var.reset(token)

        response.headers[_HEADER] = request_id
        return response
