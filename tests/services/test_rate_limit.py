"""
Unit tests for the in-memory rate-limit middleware.
"""

from app.config import settings
from app.rate_limit import RateLimitMiddleware
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient


def _build_app() -> Starlette:
    async def ok(request):
        return PlainTextResponse("ok")

    app = Starlette(
        routes=[
            Route("/process", ok, methods=["POST"]),
            Route("/nlq", ok, methods=["POST"]),
            Route("/upload", ok, methods=["POST"]),
            Route("/health", ok),
        ]
    )
    app.add_middleware(RateLimitMiddleware)
    return app


class TestRateLimitMiddleware:
    def setup_method(self):
        # Each test gets a clean, deterministic set of limits regardless of
        # what other tests (or the real .env) set them to.
        self._saved = {
            "rate_limit_enabled": settings.rate_limit_enabled,
            "rate_limit_default_per_minute": settings.rate_limit_default_per_minute,
            "rate_limit_process_per_minute": settings.rate_limit_process_per_minute,
            "rate_limit_nlq_per_minute": settings.rate_limit_nlq_per_minute,
        }
        settings.rate_limit_enabled = True
        settings.rate_limit_default_per_minute = 3
        settings.rate_limit_process_per_minute = 2
        settings.rate_limit_nlq_per_minute = 2

    def teardown_method(self):
        for key, value in self._saved.items():
            setattr(settings, key, value)

    def test_requests_within_limit_succeed(self):
        client = TestClient(_build_app())
        for _ in range(2):
            resp = client.post("/process")
            assert resp.status_code == 200

    def test_exceeding_limit_returns_429_with_retry_after(self):
        client = TestClient(_build_app())
        for _ in range(2):
            client.post("/process")
        resp = client.post("/process")
        assert resp.status_code == 429
        assert "Retry-After" in resp.headers
        assert "detail" in resp.json()

    def test_buckets_are_independent_per_path(self):
        client = TestClient(_build_app())
        for _ in range(2):
            assert client.post("/process").status_code == 200
        # /process is now exhausted, but /nlq has its own bucket.
        assert client.post("/nlq").status_code == 200

    def test_default_bucket_covers_unlisted_paths(self):
        client = TestClient(_build_app())
        for _ in range(3):
            assert client.post("/upload").status_code == 200
        assert client.post("/upload").status_code == 429

    def test_health_endpoint_is_exempt(self):
        client = TestClient(_build_app())
        settings.rate_limit_default_per_minute = 1
        for _ in range(5):
            assert client.get("/health").status_code == 200

    def test_different_client_ips_are_tracked_separately(self):
        client = TestClient(_build_app())
        for _ in range(2):
            assert (
                client.post("/process", headers={"X-Forwarded-For": "1.1.1.1"}).status_code == 200
            )
        # TestClient always presents the same client IP regardless of headers
        # (no trust-proxy parsing here), so this call still hits the same
        # bucket and should be rejected — proving the limiter keys off the
        # actual connecting IP, not a spoofable header.
        assert client.post("/process").status_code == 429

    def test_disabled_bypasses_limiting_entirely(self):
        settings.rate_limit_enabled = False
        client = TestClient(_build_app())
        for _ in range(10):
            assert client.post("/process").status_code == 200

    def test_zero_limit_disables_that_bucket(self):
        settings.rate_limit_process_per_minute = 0
        client = TestClient(_build_app())
        for _ in range(10):
            assert client.post("/process").status_code == 200

    def test_window_resets_after_expiry(self, monkeypatch):
        import app.rate_limit as rate_limit_module

        clock = {"t": 1000.0}
        monkeypatch.setattr(rate_limit_module.time, "monotonic", lambda: clock["t"])

        client = TestClient(_build_app())
        for _ in range(2):
            assert client.post("/process").status_code == 200
        assert client.post("/process").status_code == 429

        clock["t"] += 61  # past the 60s fixed window
        assert client.post("/process").status_code == 200
