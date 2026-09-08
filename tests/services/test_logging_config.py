"""
Unit tests for structured logging + request-ID tracing.
"""

import io
import json
import logging

import pytest
from app.logging_config import (
    RequestIDMiddleware,
    _JsonFormatter,
    _RequestIdFilter,
    configure_logging,
    request_id_var,
)
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient


def _build_app() -> Starlette:
    async def echo_request_id(request):
        return PlainTextResponse(request_id_var.get())

    app = Starlette(routes=[Route("/", echo_request_id)])
    app.add_middleware(RequestIDMiddleware)
    return app


class TestRequestIDMiddleware:
    def test_generates_an_id_when_none_provided(self):
        client = TestClient(_build_app())
        resp = client.get("/")
        assert resp.headers["X-Request-ID"]
        # The handler saw the same id the response carries — proves the
        # ContextVar propagates through BaseHTTPMiddleware's call_next.
        assert resp.text == resp.headers["X-Request-ID"]

    def test_reuses_an_inbound_request_id(self):
        client = TestClient(_build_app())
        resp = client.get("/", headers={"X-Request-ID": "caller-supplied-id"})
        assert resp.headers["X-Request-ID"] == "caller-supplied-id"
        assert resp.text == "caller-supplied-id"

    def test_truncates_an_oversized_inbound_id(self):
        client = TestClient(_build_app())
        huge = "x" * 500
        resp = client.get("/", headers={"X-Request-ID": huge})
        assert len(resp.headers["X-Request-ID"]) == 64

    def test_different_requests_get_different_ids(self):
        client = TestClient(_build_app())
        first = client.get("/").headers["X-Request-ID"]
        second = client.get("/").headers["X-Request-ID"]
        assert first != second

    def test_context_resets_after_the_request(self):
        client = TestClient(_build_app())
        client.get("/", headers={"X-Request-ID": "leaked-id"})
        assert request_id_var.get() == "-"


class TestJsonFormatter:
    def test_formats_a_record_as_valid_json_with_expected_fields(self):
        record = logging.LogRecord(
            name="app.test",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="hello %s",
            args=("world",),
            exc_info=None,
        )
        _RequestIdFilter().filter(record)
        line = _JsonFormatter().format(record)
        payload = json.loads(line)

        assert payload["level"] == "INFO"
        assert payload["logger"] == "app.test"
        assert payload["message"] == "hello world"
        assert payload["request_id"] == "-"
        assert "timestamp" in payload

    def test_includes_request_id_set_on_the_contextvar(self):
        token = request_id_var.set("test-req-id")
        try:
            record = logging.LogRecord(
                name="app.test",
                level=logging.INFO,
                pathname=__file__,
                lineno=1,
                msg="hi",
                args=(),
                exc_info=None,
            )
            _RequestIdFilter().filter(record)
            payload = json.loads(_JsonFormatter().format(record))
        finally:
            request_id_var.reset(token)
        assert payload["request_id"] == "test-req-id"

    def test_includes_exc_info_when_present(self):
        try:
            raise ValueError("boom")
        except ValueError:
            record = logging.LogRecord(
                name="app.test",
                level=logging.ERROR,
                pathname=__file__,
                lineno=1,
                msg="failed",
                args=(),
                exc_info=True,
                sinfo=None,
            )
            import sys

            record.exc_info = sys.exc_info()
        payload = json.loads(_JsonFormatter().format(record))
        assert "ValueError: boom" in payload["exc_info"]


class TestConfigureLogging:
    @pytest.fixture(autouse=True)
    def _restore_root_logger(self):
        root = logging.getLogger()
        saved_handlers = list(root.handlers)
        saved_level = root.level
        yield
        root.handlers.clear()
        for h in saved_handlers:
            root.addHandler(h)
        root.setLevel(saved_level)

    def test_installs_a_single_json_handler_on_the_root_logger(self):
        configure_logging("DEBUG")
        root = logging.getLogger()
        assert root.level == logging.DEBUG
        assert len(root.handlers) == 1
        assert isinstance(root.handlers[0].formatter, _JsonFormatter)

    def test_is_idempotent_and_does_not_stack_handlers(self):
        configure_logging("INFO")
        configure_logging("INFO")
        assert len(logging.getLogger().handlers) == 1

    def test_emitted_record_is_parseable_json_on_the_stream(self):
        configure_logging("INFO")
        stream = io.StringIO()
        logging.getLogger().handlers[0].stream = stream
        logging.getLogger("app.something").info("a real log line")
        line = stream.getvalue().strip()
        payload = json.loads(line)
        assert payload["message"] == "a real log line"
        assert payload["logger"] == "app.something"
