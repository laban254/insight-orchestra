"""
Tests for server-side workspace persistence (/workspaces) and
chart embedding in server-side exports.
"""

import json

import pytest
from app.api import export as export_api
from app.api import workspaces as workspaces_api
from app.services.workspace_store import MAX_WORKSPACES, WorkspaceStore
from fastapi import HTTPException


@pytest.fixture
def store(monkeypatch):
    """Fresh in-memory store wired into the router for each test."""
    s = WorkspaceStore()
    s._use_redis = False  # force in-memory regardless of environment
    monkeypatch.setattr(workspaces_api, "_store", s)
    return s


def _payload(name="Sales Analytics", state=None):
    return workspaces_api.WorkspaceUpsert(
        datasetName=name,
        datasetId="abc123def456",
        createdAt=None,
        state=state or {"analysisResult": None, "messages": [], "results": [], "pinned": []},
    )


class TestWorkspaceEndpoints:
    @pytest.mark.asyncio
    async def test_upsert_and_get_roundtrip(self, store):
        meta = await workspaces_api.upsert_workspace("ws-1", _payload())
        assert meta["id"] == "ws-1"
        assert meta["datasetName"] == "Sales Analytics"
        assert meta["createdAt"] == meta["updatedAt"]

        record = await workspaces_api.get_workspace("ws-1")
        assert record["state"]["pinned"] == []
        assert record["datasetId"] == "abc123def456"

    @pytest.mark.asyncio
    async def test_update_preserves_created_at(self, store):
        first = await workspaces_api.upsert_workspace("ws-1", _payload())
        second = await workspaces_api.upsert_workspace("ws-1", _payload(name="Renamed"))
        assert second["createdAt"] == first["createdAt"]
        assert second["datasetName"] == "Renamed"

    @pytest.mark.asyncio
    async def test_list_newest_first(self, store):
        await workspaces_api.upsert_workspace("ws-old", _payload())
        await workspaces_api.upsert_workspace("ws-new", _payload())
        result = await workspaces_api.list_workspaces()
        ids = [w["id"] for w in result["workspaces"]]
        assert ids.index("ws-new") < ids.index("ws-old")
        # Metadata only — no state payloads in the listing
        assert all("state" not in w for w in result["workspaces"])

    @pytest.mark.asyncio
    async def test_get_missing_404(self, store):
        with pytest.raises(HTTPException) as exc:
            await workspaces_api.get_workspace("nope")
        assert exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_delete(self, store):
        await workspaces_api.upsert_workspace("ws-1", _payload())
        await workspaces_api.delete_workspace("ws-1")
        with pytest.raises(HTTPException):
            await workspaces_api.get_workspace("ws-1")

    @pytest.mark.asyncio
    async def test_invalid_id_rejected(self, store):
        with pytest.raises(HTTPException) as exc:
            await workspaces_api.get_workspace("../etc/passwd")
        assert exc.value.status_code == 400

    @pytest.mark.asyncio
    async def test_eviction_beyond_cap(self, store):
        for i in range(MAX_WORKSPACES + 3):
            await workspaces_api.upsert_workspace(f"ws-{i}", _payload())
        result = await workspaces_api.list_workspaces()
        assert len(result["workspaces"]) == MAX_WORKSPACES
        # The oldest (first-inserted) ones were evicted
        remaining = {w["id"] for w in result["workspaces"]}
        assert "ws-0" not in remaining
        assert f"ws-{MAX_WORKSPACES + 2}" in remaining


class TestExportCharts:
    def _fig_json(self):
        return json.dumps(
            {
                "data": [{"type": "bar", "x": ["East", "West"], "y": [1, 2]}],
                "layout": {"title": {"text": "Revenue by region"}},
            }
        )

    def test_build_session_collects_charts(self, monkeypatch):
        history = [
            {
                "role": "analysis",
                "narrative": "Summary.",
                "hypotheses": ["h1"],
                "charts": [{"title": "Pipeline chart", "plotly_json": self._fig_json()}],
            },
            {
                "question": "Sales by region?",
                "answer": "West leads.",
                "code": "df.groupby('region')...",
                "plot_json": self._fig_json(),
            },
        ]
        fake_manager = type("M", (), {"get": lambda self, sid: history})()
        monkeypatch.setattr(export_api, "_session_manager", fake_manager)

        session = export_api._build_session("sid-1")
        assert len(session["charts"]) == 2
        assert session["charts"][0]["title"] == "Pipeline chart"
        assert session["charts"][1]["title"] == "Sales by region?"
        assert session["charts"][0]["data"][0]["type"] == "bar"

    def test_build_session_skips_bad_chart_json(self, monkeypatch):
        history = [
            {"question": "q", "answer": "a", "code": "", "plot_json": "{not valid json"},
        ]
        fake_manager = type("M", (), {"get": lambda self, sid: history})()
        monkeypatch.setattr(export_api, "_session_manager", fake_manager)

        session = export_api._build_session("sid-1")
        assert session["charts"] == []

    def test_html_export_embeds_chart(self, monkeypatch):
        history = [
            {
                "question": "Sales by region?",
                "answer": "West leads.",
                "code": "",
                "plot_json": self._fig_json(),
            },
        ]
        fake_manager = type("M", (), {"get": lambda self, sid: history})()
        monkeypatch.setattr(export_api, "_session_manager", fake_manager)

        html = export_api.export_service.to_html(export_api._build_session("sid-1"))
        assert "Plotly.newPlot" in html
        assert "Revenue by region" in html

    def test_markdown_export_lists_charts(self, monkeypatch):
        history = [
            {
                "question": "Sales by region?",
                "answer": "West leads.",
                "code": "",
                "plot_json": self._fig_json(),
            },
        ]
        fake_manager = type("M", (), {"get": lambda self, sid: history})()
        monkeypatch.setattr(export_api, "_session_manager", fake_manager)

        md = export_api.export_service.to_markdown(export_api._build_session("sid-1"))
        assert "## Visualisations" in md
        assert "Sales by region?" in md
