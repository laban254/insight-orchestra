"""
App-level tests: route versioning and the standardized error envelope.
"""

from app.main import app
from starlette.testclient import TestClient

client = TestClient(app)


class TestRouteVersioning:
    def test_health_is_unversioned(self):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    def test_versioned_route_is_reachable(self):
        resp = client.get("/api/v1/demo/list")
        assert resp.status_code == 200
        assert "datasets" in resp.json()

    def test_unversioned_path_is_gone(self):
        resp = client.get("/demo/list")
        assert resp.status_code == 404

    def test_docs_stays_unversioned(self):
        resp = client.get("/docs")
        assert resp.status_code == 200


class TestDatasetRowsPagination:
    """The `limit`/`offset` bounds on GET /datasets/{id}/rows are enforced
    by FastAPI's Query() validation, which only runs over real HTTP — a
    direct function call (as in tests/api/test_endpoints.py) bypasses it."""

    def test_limit_over_the_cap_is_rejected(self):
        resp = client.get("/api/v1/datasets/does-not-matter/rows", params={"limit": 5000})
        assert resp.status_code == 422
        assert isinstance(resp.json()["detail"], str)

    def test_negative_offset_is_rejected(self):
        resp = client.get("/api/v1/datasets/does-not-matter/rows", params={"offset": -1})
        assert resp.status_code == 422

    def test_unknown_dataset_is_404_not_422(self):
        resp = client.get("/api/v1/datasets/does-not-exist/rows")
        assert resp.status_code == 404


class TestErrorEnvelope:
    def test_validation_error_detail_is_a_string_not_a_list(self):
        """FastAPI's default 422 shape is `detail: [{loc, msg, type}, ...]`,
        which every frontend error handler (expecting `detail: string`)
        would render as "[object Object]". The custom handler must collapse
        it to the same string shape as every other error response."""
        resp = client.post("/api/v1/nlq", json={})  # missing required fields
        assert resp.status_code == 422
        assert isinstance(resp.json()["detail"], str)
        assert "dataset_id" in resp.json()["detail"]
        assert "question" in resp.json()["detail"]

    def test_http_exception_detail_is_still_a_string(self):
        resp = client.get("/api/v1/datasets/does-not-exist")
        assert resp.status_code == 404
        assert isinstance(resp.json()["detail"], str)

    def test_response_carries_a_request_id_header(self):
        resp = client.get("/health")
        assert resp.headers["X-Request-ID"]
