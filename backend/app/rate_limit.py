"""
In-memory, per-client-IP fixed-window rate limiting.

Safe as in-memory state because the backend always runs as a single uvicorn
worker (see backend/Dockerfile's comment on why — the SSE progress queue is
process-local too). If that ever changes, this needs to move to Redis
(already used elsewhere in the app for shared state) instead.
"""

import time

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.config import settings

_WINDOW_SECONDS = 60.0

# Paths exempt from rate limiting entirely — polled automatically (Docker
# healthcheck) rather than driven by a user, so limiting them protects
# nothing and risks false-positive outage alerts.
_EXEMPT_PATHS = {"/health"}


def _bucket_for(path: str) -> tuple[str, int]:
    if path.startswith("/process"):
        return "process", settings.rate_limit_process_per_minute
    if path.startswith("/nlq"):
        return "nlq", settings.rate_limit_nlq_per_minute
    return "default", settings.rate_limit_default_per_minute


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        # (client_ip, bucket_name) -> (window_start_monotonic, count)
        self._counters: dict[tuple[str, str], tuple[float, int]] = {}

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if not settings.rate_limit_enabled or request.url.path in _EXEMPT_PATHS:
            return await call_next(request)

        bucket, limit = _bucket_for(request.url.path)
        if limit <= 0:  # 0 disables limiting for that bucket
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        key = (client_ip, bucket)
        now = time.monotonic()
        window_start, count = self._counters.get(key, (now, 0))
        if now - window_start >= _WINDOW_SECONDS:
            window_start, count = now, 0
        count += 1
        self._counters[key] = (window_start, count)

        if count > limit:
            retry_after = max(1, int(_WINDOW_SECONDS - (now - window_start)))
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Please slow down and try again shortly."},
                headers={"Retry-After": str(retry_after)},
            )

        return await call_next(request)
