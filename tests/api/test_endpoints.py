"""
Unit tests for API endpoint handlers (function-level).
"""

import json
import os
import tempfile
from io import BytesIO
from unittest.mock import MagicMock, Mock, patch

import pandas as pd
import pytest
from app.api import endpoints
from app.api.endpoints import BigQueryRequest, NLQRequest, ProcessRequest
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

        assert response["file_path"] == str(stored)
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
    async def test_process_endpoint_requires_file(self):
        with pytest.raises(HTTPException) as exc:
            await endpoints.process_data(ProcessRequest(file_path="/nonexistent/file.csv"))
        assert exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_nlq_endpoint_requires_file(self):
        with pytest.raises(HTTPException) as exc:
            await endpoints.natural_language_query(
                NLQRequest(file_path="/nonexistent/file.csv", question="What is the average age?")
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
    def temp_csv(self, sample_csv_content):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(sample_csv_content)
            temp_path = f.name
        yield temp_path
        if os.path.exists(temp_path):
            os.unlink(temp_path)

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

        response = await endpoints.process_data(ProcessRequest(file_path=temp_csv))
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

        response = await endpoints.process_data(ProcessRequest(file_path=temp_csv))

        # Would raise ValueError before the sanitize_json fix, matching the
        # real crash from Starlette's JSONResponse renderer.
        json.dumps(response, allow_nan=False)
        # The full cleaned dataset is no longer returned (nothing in the UI
        # read it); the preview carries the same guarantee.
        assert response["preview"]["rows"][0]["processed_at"] is None
        assert "cleaned_data" not in response["cleaner"]

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
            NLQRequest(file_path=temp_csv, question="What is the average age?")
        )
        assert response["answer"] == "Test answer"
        mock_instance.run.assert_called_once()


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
    async def test_process_handles_csv_read_error(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write("name,age\nAlice,25")
            temp_path = f.name
        try:
            with patch("app.utils.dataset_io.pd.read_csv", side_effect=Exception("read failed")):
                with pytest.raises(HTTPException) as exc:
                    await endpoints.process_data(ProcessRequest(file_path=temp_path))
            assert exc.value.status_code == 400
        finally:
            os.unlink(temp_path)
