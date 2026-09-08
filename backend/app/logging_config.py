"""
Structured (JSON-line) logging with per-request ID tracing.

Call `configure_logging()` once at startup. `RequestIDMiddleware` stamps
every request with an id (reusing an inbound `X-Request-ID` if a caller or
upstream proxy already set one) and echoes it back on the response; every
log line emitted while handling that request carries the same id via a
ContextVar, so a single request's logs can be pulled out of an otherwise
interleaved single-process log stream.
"""

import contextvars
import json
import logging
import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")


class _RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "request_id": getattr(record, "request_id", "-"),
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def configure_logging(level: str = "INFO") -> None:
    """Set up a single JSON-line handler on the root logger.

    Idempotent — safe to call more than once (e.g. under a dev auto-reload)
    since it replaces any handlers it previously installed rather than
    stacking duplicates.
    """
    root = logging.getLogger()
    root.setLevel(level.upper())
    root.handlers.clear()

    handler = logging.StreamHandler()
    handler.setFormatter(_JsonFormatter())
    handler.addFilter(_RequestIdFilter())
    root.addHandler(handler)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Assigns a request id, exposes it on the response, and makes it
    available to every log call made while handling this request."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        incoming = request.headers.get("x-request-id")
        request_id = (incoming or uuid.uuid4().hex[:12])[:64]
        token = request_id_var.set(request_id)
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            request_id_var.reset(token)
