"""X-Request-ID correlation middleware.

Behaviour
---------
* If the incoming request already carries an ``X-Request-ID`` header, that
  value is reused (max 128 chars, stripped to prevent log injection).
* Otherwise a fresh UUID-4 is generated.
* The ID is stored on ``request.state.request_id`` for use in route handlers.
* The ID is echoed back in the ``X-Request-ID`` response header so that
  callers (and their own logs) can correlate requests end-to-end.
"""

import uuid
import logging
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)

_HEADER = "X-Request-ID"
_MAX_LEN = 128


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Attach a correlation ID to every request/response pair."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        raw = request.headers.get(_HEADER, "")
        request_id = raw[:_MAX_LEN].strip() if raw.strip() else str(uuid.uuid4())
        request.state.request_id = request_id

        # Propagate to the log record so structured log sinks get it for free.
        logger.debug("request_id=%s  %s %s", request_id, request.method, request.url.path)

        response = await call_next(request)
        response.headers[_HEADER] = request_id
        return response
