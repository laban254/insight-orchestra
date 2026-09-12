"""
Unit tests for API endpoint handlers (function-level).
"""

import json
from io import BytesIO
from unittest.mock import MagicMock, Mock, patch

import pandas as pd
import pytest
from app.api import endpoints
from app.api.endpoints import BigQueryRequest, NLQRequest, ProcessRequest, TransformRequest
from app.main import health_check
from fastapi import HTTPException
from starlette.datastructures import UploadFile


@pytest.fixture
def sample_csv_content():
    return """name,age,department,salary
Alice,25,Engineering,75000
Bob,30,Sales,65000
Charlie,35,Engineering,85000
"""


class TestEndpoints:
    @pytest.mark.asyncio
    async def test_upload_csv_success(self, tmp_path):
        # /upload now parses what it stored, so the path has to be real.
        stored = tmp_path / "test_uploaded.csv"
        stored.write_text("name,age\nAlice,25\nBob,30\n")
        with patch("app.api.endpoints.save_upload_file") as mock_save:
            mock_save.return_value = str(stored)
            upload = UploadFile(filename="test.csv", file=BytesIO(b"name,age\nAlice,25\nBob,30"))
            response = await endpoints.upload_csv(upload)

        assert response["dataset_id"]
        assert "file_path" not in response, "the client must never receive a server path"
        # The upload response describes the data, so the UI never has to
        # show "Unknown rows / Unknown cols".
        assert response["rows"] == 2
        assert response["columns"] == 2
        assert response["column_names"] == ["name", "age"]
        assert len(response["preview"]) == 2

    @pytest.mark.asyncio
    async def test_upload_non_csv_rejected(self):
        upload = UploadFile(filename="test.txt", file=BytesIO(b"not a csv"))
        with pytest.raises(HTTPException) as exc:
            await endpoints.upload_csv(upload)
        assert exc.value.status_code == 400

    @pytest.mark.asyncio
    async def test_process_endpoint_rejects_unknown_dataset(self):
        with pytest.raises(HTTPException) as exc:
            await endpoints.process_data(ProcessRequest(dataset_id="does-not-exist"))
        assert exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_nlq_endpoint_rejects_unknown_dataset(self):
        with pytest.raises(HTTPException) as exc:
            await endpoints.natural_language_query(
                NLQRequest(dataset_id="does-not-exist", question="What is the average age?")
            )
        assert exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_bigquery_requires_valid_credentials(self):
        with pytest.raises(HTTPException) as exc:
            await endpoints.bigquery_fetch(
                BigQueryRequest(credentials_json="invalid json", query="SELECT 1")
            )
        assert exc.value.status_code == 400

    @pytest.mark.asyncio
    async def test_session_endpoints(self):
        session_id = "test-session-id"
        response_get = await endpoints.get_session(session_id)
        assert response_get["history"] == []

        response_delete = await endpoints.clear_session(session_id)
        assert response_delete["status"] == "cleared"

    def test_health_endpoint(self):
        response = health_check()
        assert response["status"] == "ok"


class TestEndpointsIntegration:
    @pytest.fixture
    def temp_csv(self, sample_csv_content, tmp_path):
        """A registered dataset id — endpoints no longer take paths."""
        from app.services.dataset_registry import get_dataset_registry

        path = tmp_path / "integration.csv"
        path.write_text(sample_csv_content)
        registry = get_dataset_registry()
        dataset_id = registry.register(str(path), name="integration.csv", source="upload")
        yield dataset_id
        registry.delete(dataset_id, remove_file=False)

    @pytest.mark.asyncio
    @patch("app.api.endpoints.InsightOrchestraWorkflow")
    async def test_process_workflow_called(self, mock_workflow, temp_csv):
        mock_instance = MagicMock()
        mock_instance.cleaner.run.return_value = {
            "cleaned_df": pd.DataFrame([{"x": 1}]),
            "report": {"duplicates_removed": 0, "total_missing": 0},
        }
        mock_instance.hypothesis.run.return_value = {"hypotheses": ["h1"]}
        mock_instance.debate.run.return_value = {
            "summary": {"consensus": {"hypothesis": "h1"}},
            "scored_hypotheses": [],
        }
        mock_instance.viz.run.return_value = {"chart_info": {"plots": []}}
        mock_workflow.return_value = mock_instance

        response = await endpoints.process_data(ProcessRequest(dataset_id=temp_csv))
        assert "cleaner" in response
        mock_instance.cleaner.run.assert_called_once()
        mock_instance.hypothesis.run.assert_called_once()
        mock_instance.debate.run.assert_called_once()
        mock_instance.viz.run.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.api.endpoints.InsightSummarizerAgent")
    @patch("app.api.endpoints.InsightOrchestraWorkflow")
    async def test_process_response_is_json_safe_with_nan(
        self, mock_workflow, mock_summarizer, temp_csv
    ):
        """Real databases routinely have all-null numeric columns, which
        (pre-fix) left NaN in the response and crashed serialization with
        Starlette's allow_nan=False JSONResponse. The endpoint's own
        response should never contain a raw NaN/Infinity."""
        mock_instance = MagicMock()
        mock_instance.cleaner.run.return_value = {
            "cleaned_df": pd.DataFrame([{"x": 1, "processed_at": float("nan")}]),
            "report": {"duplicates_removed": 0, "total_missing": 1},
        }
        mock_instance.hypothesis.run.return_value = {"hypotheses": ["h1"]}
        mock_instance.debate.run.return_value = {
            "summary": {"consensus": {"hypothesis": "h1"}},
            "scored_hypotheses": [],
        }
        mock_instance.viz.run.return_value = {"chart_info": {"plots": []}}
        mock_workflow.return_value = mock_instance
        mock_summarizer.return_value.run.return_value = {
            "narrative": "Summary text.",
            "suggested_questions": ["What drives x?"],
        }

        response = await endpoints.process_data(ProcessRequest(dataset_id=temp_csv))

        # Would raise ValueError before the sanitize_json fix, matching the
        # real crash from Starlette's JSONResponse renderer.
        json.dumps(response, allow_nan=False)
        # The full cleaned dataset is no longer returned (nothing in the UI
        # read it); the preview carries the same guarantee.
        assert response["preview"]["rows"][0]["processed_at"] is None
        assert "cleaned_data" not in response["cleaner"]

    @pytest.mark.asyncio
    async def test_dataset_rows_first_page(self, temp_csv):
        response = await endpoints.get_dataset_rows(temp_csv, offset=0, limit=2)
        assert response["total_rows"] == 3
        assert response["offset"] == 0
        assert response["limit"] == 2
        assert len(response["rows"]) == 2
        assert response["rows"][0]["name"] == "Alice"
        assert response["has_more"] is True

    @pytest.mark.asyncio
    async def test_dataset_rows_last_page_has_no_more(self, temp_csv):
        response = await endpoints.get_dataset_rows(temp_csv, offset=2, limit=2)
        assert len(response["rows"]) == 1
        assert response["rows"][0]["name"] == "Charlie"
        assert response["has_more"] is False

    @pytest.mark.asyncio
    async def test_dataset_rows_offset_past_the_end_is_empty(self, temp_csv):
        response = await endpoints.get_dataset_rows(temp_csv, offset=100, limit=50)
        assert response["rows"] == []
        assert response["has_more"] is False

    @pytest.mark.asyncio
    async def test_transform_normalize_scales_to_zero_one(self, temp_csv):
        response = await endpoints.transform_dataset(
            temp_csv, TransformRequest(column="age", operation="normalize")
        )
        assert response["new_column"] == "age_normalize"
        values = [row["age_normalize"] for row in response["preview"]]
        assert min(values) == 0.0
        assert max(values) == 1.0
        # Non-destructive: a new dataset id, original untouched.
        assert response["dataset_id"] != temp_csv

    @pytest.mark.asyncio
    async def test_transform_scale_is_zero_mean(self, temp_csv):
        response = await endpoints.transform_dataset(
            temp_csv, TransformRequest(column="salary", operation="scale")
        )
        values = [row["salary_scale"] for row in response["preview"]]
        assert sum(values) == pytest.approx(0.0, abs=1e-9)

    @pytest.mark.asyncio
    async def test_transform_encode_maps_categories_to_integers(self, temp_csv):
        response = await endpoints.transform_dataset(
            temp_csv, TransformRequest(column="department", operation="encode")
        )
        rows = response["preview"]
        # Alice=Engineering, Bob=Sales, Charlie=Engineering — first-seen order.
        assert rows[0]["department_encode"] == rows[2]["department_encode"]
        assert rows[0]["department_encode"] != rows[1]["department_encode"]

    @pytest.mark.asyncio
    async def test_transform_respects_custom_new_column_name(self, temp_csv):
        response = await endpoints.transform_dataset(
            temp_csv,
            TransformRequest(column="age", operation="normalize", new_column="age_0to1"),
        )
        assert response["new_column"] == "age_0to1"
        assert "age_0to1" in response["preview"][0]

    @pytest.mark.asyncio
    async def test_transform_unknown_column_is_400(self, temp_csv):
        with pytest.raises(HTTPException) as exc:
            await endpoints.transform_dataset(
                temp_csv, TransformRequest(column="nope", operation="normalize")
            )
        assert exc.value.status_code == 400

    @pytest.mark.asyncio
    async def test_transform_normalize_on_text_column_is_400(self, temp_csv):
        with pytest.raises(HTTPException) as exc:
            await endpoints.transform_dataset(
                temp_csv, TransformRequest(column="department", operation="normalize")
            )
        assert exc.value.status_code == 400

    @pytest.mark.asyncio
    async def test_transform_constant_column_does_not_divide_by_zero(self, tmp_path):
        from app.services.dataset_registry import get_dataset_registry

        path = tmp_path / "constant.csv"
        path.write_text("value\n5\n5\n5\n")
        registry = get_dataset_registry()
        dataset_id = registry.register(str(path), name="constant.csv", source="upload")
        try:
            normalized = await endpoints.transform_dataset(
                dataset_id, TransformRequest(column="value", operation="normalize")
            )
            assert all(row["value_normalize"] == 0.5 for row in normalized["preview"])

            scaled = await endpoints.transform_dataset(
                dataset_id, TransformRequest(column="value", operation="scale")
            )
            assert all(row["value_scale"] == 0.0 for row in scaled["preview"])
        finally:
            registry.delete(dataset_id, remove_file=False)

    @pytest.mark.asyncio
    @patch("app.api.endpoints.NaturalLanguageQueryAgent")
    async def test_nlq_agent_called(self, mock_agent_class, temp_csv):
        mock_instance = MagicMock()
        mock_instance.run.return_value = Mock(
            answer="Test answer",
            code="print('test')",
            reasoning="reasoning",
            plot_json=None,
            needs_clarification=False,
            clarification_question=None,
            execution_success=True,
            error=None,
        )
        mock_agent_class.return_value = mock_instance

        response = await endpoints.natural_language_query(
            NLQRequest(dataset_id=temp_csv, question="What is the average age?")
        )
        assert response["answer"] == "Test answer"
        mock_instance.run.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.api.endpoints.NaturalLanguageQueryAgent")
    async def test_nlq_answer_is_cached_for_a_repeated_question(self, mock_agent_class, temp_csv):
        """Same dataset + same question + same provider/model should skip
        the second LLM call and sandbox execution entirely."""
        import app.services.query_cache as qc_module

        qc_module._query_cache = None  # fresh cache, isolated from other tests

        mock_instance = MagicMock()
        mock_instance.run.return_value = Mock(
            answer="Test answer",
            code="print('test')",
            reasoning="reasoning",
            plot_json=None,
            needs_clarification=False,
            clarification_question=None,
            execution_success=True,
            error=None,
        )
        mock_agent_class.return_value = mock_instance

        question = "What is the average age?"
        first = await endpoints.natural_language_query(
            NLQRequest(dataset_id=temp_csv, question=question)
        )
        second = await endpoints.natural_language_query(
            NLQRequest(dataset_id=temp_csv, question=question)
        )

        assert first["answer"] == "Test answer"
        assert second["answer"] == "Test answer"
        mock_instance.run.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.api.endpoints.InsightOrchestraWorkflow")
    async def test_process_timeout_returns_504(self, mock_workflow, temp_csv):
        """A pipeline stage that outruns process_timeout_seconds fails fast
        with a clean 504 instead of hanging until the client gives up."""
        import time as time_module

        mock_instance = MagicMock()
        mock_instance.cleaner.run.side_effect = lambda frame: (
            time_module.sleep(0.2) or {"cleaned_df": pd.DataFrame([{"x": 1}]), "report": {}}
        )
        mock_workflow.return_value = mock_instance

        original_timeout = endpoints.settings.process_timeout_seconds
        endpoints.settings.process_timeout_seconds = 0.01
        try:
            with pytest.raises(HTTPException) as exc:
                await endpoints.process_data(ProcessRequest(dataset_id=temp_csv))
        finally:
            endpoints.settings.process_timeout_seconds = original_timeout

        assert exc.value.status_code == 504

    @pytest.mark.asyncio
    @patch("app.api.endpoints.NaturalLanguageQueryAgent")
    async def test_nlq_timeout_returns_friendly_response(self, mock_agent_class, temp_csv):
        """A query that outruns nlq_timeout_seconds returns a friendly
        timeout answer (200, not a raw exception) instead of hanging."""
        import time as time_module

        mock_instance = MagicMock()

        def slow_run(df, question, context, sid):
            time_module.sleep(0.2)
            return Mock(answer="unreachable", code="", plot_json=None, execution_success=True)

        mock_instance.run.side_effect = slow_run
        mock_agent_class.return_value = mock_instance

        original_timeout = endpoints.settings.nlq_timeout_seconds
        endpoints.settings.nlq_timeout_seconds = 0.01
        try:
            response = await endpoints.natural_language_query(
                NLQRequest(dataset_id=temp_csv, question="slow question?")
            )
        finally:
            endpoints.settings.nlq_timeout_seconds = original_timeout

        assert response["error"] == "timeout"
        assert "took too long" in response["answer"]

    @pytest.mark.asyncio
    @patch("app.api.endpoints.InsightOrchestraWorkflow")
    async def test_process_unexpected_error_returns_502_not_a_raw_500(
        self, mock_workflow, temp_csv
    ):
        """An unhandled exception anywhere in the pipeline used to propagate
        as a bare 500 with no useful message; it should now surface as a
        502 with an actionable detail."""
        mock_instance = MagicMock()
        mock_instance.cleaner.run.side_effect = RuntimeError("cleaner blew up")
        mock_workflow.return_value = mock_instance

        with pytest.raises(HTTPException) as exc:
            await endpoints.process_data(ProcessRequest(dataset_id=temp_csv))

        assert exc.value.status_code == 502
        assert exc.value.detail

    @pytest.mark.asyncio
    @patch("app.api.endpoints.InsightOrchestraWorkflow")
    async def test_process_http_exception_is_not_masked_as_502(self, mock_workflow, temp_csv):
        """A deliberate HTTPException raised deeper in the pipeline (e.g. a
        dataset that fails to read) keeps its own status/message rather than
        being caught by the generic error handler and turned into a 502."""
        mock_instance = MagicMock()
        mock_instance.cleaner.run.side_effect = HTTPException(status_code=400, detail="bad dataset")
        mock_workflow.return_value = mock_instance

        with pytest.raises(HTTPException) as exc:
            await endpoints.process_data(ProcessRequest(dataset_id=temp_csv))

        assert exc.value.status_code == 400
        assert exc.value.detail == "bad dataset"


class TestEndpointsErrorHandling:
    @pytest.mark.asyncio
    async def test_upload_handles_value_error(self):
        with patch("app.api.endpoints.save_upload_file") as mock_save:
            mock_save.side_effect = ValueError("Invalid file")
            upload = UploadFile(filename="test.csv", file=BytesIO(b"name,age\nAlice,25"))
            with pytest.raises(HTTPException) as exc:
                await endpoints.upload_csv(upload)
        assert exc.value.status_code == 400

    @pytest.mark.asyncio
    async def test_process_handles_csv_read_error(self, registered_dataset):
        with patch("app.utils.dataset_io.pd.read_csv", side_effect=Exception("read failed")):
            with pytest.raises(HTTPException) as exc:
                await endpoints.process_data(ProcessRequest(dataset_id=registered_dataset))
        assert exc.value.status_code == 400


class TestProviderReadiness:
    """GET /config and POST /config must agree on which providers are usable.

    They previously used different placeholder checks, so GET advertised openai as ready
    while POST rejected the same provider with a 400.
    """

    @pytest.mark.parametrize(
        "placeholder", ["sk-...", "sk-ant-...", "your-openai-api-key-here", "", "   "]
    )
    def test_placeholder_keys_are_not_configured(self, placeholder):
        assert endpoints._api_key_configured(placeholder) is False

    def test_real_key_is_configured(self):
        assert endpoints._api_key_configured("sk-proj-abc123realkey") is True

    @pytest.mark.asyncio
    async def test_get_and_post_agree_when_key_is_a_placeholder(self):
        """The exact contradiction that shipped: GET said ready, POST said 400."""
        with (
            patch.object(endpoints.settings, "openai_api_key", "sk-..."),
            patch.object(endpoints, "_ollama_reachable", return_value=False),
        ):
            config = await endpoints.get_config()
            assert config["ready"]["openai"] is False

            with pytest.raises(HTTPException) as exc:
                await endpoints.update_config(endpoints.ConfigUpdate(provider="openai"))
            assert exc.value.status_code == 400

    @pytest.mark.asyncio
    async def test_ollama_readiness_reflects_the_daemon(self):
        """Readiness used to be hardcoded True whether or not anything was listening."""
        with patch.object(endpoints, "_ollama_reachable", return_value=False):
            config = await endpoints.get_config()
            assert config["ready"]["ollama"] is False

        with patch.object(endpoints, "_ollama_reachable", return_value=True):
            config = await endpoints.get_config()
            assert config["ready"]["ollama"] is True

    @pytest.mark.asyncio
    async def test_cannot_switch_to_unreachable_ollama(self):
        with patch.object(endpoints, "_ollama_reachable", return_value=False):
            with pytest.raises(HTTPException) as exc:
                await endpoints.update_config(endpoints.ConfigUpdate(provider="ollama"))
        assert exc.value.status_code == 400
        assert "not reachable" in exc.value.detail

    def test_unreachable_daemon_reports_false(self):
        import requests as _requests

        with patch.object(
            endpoints.requests, "get", side_effect=_requests.RequestException("refused")
        ):
            assert endpoints._ollama_reachable() is False
