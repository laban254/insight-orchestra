"""
Unit tests for API endpoints.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import pandas as pd
import os
import tempfile


class TestEndpoints:
    """Test cases for API endpoints."""
    
    @pytest.fixture
    def mock_file_utils(self):
        """Mock file_utils.save_upload_file."""
        with patch('app.api.endpoints.save_upload_file') as mock:
            mock.return_value = '/tmp/test_uploaded.csv'
            yield mock
    
    @pytest.fixture
    def sample_csv_content(self):
        """Create sample CSV content."""
        return """name,age,department,salary
Alice,25,Engineering,75000
Bob,30,Sales,65000
Charlie,35,Engineering,85000
"""
    
    def test_upload_csv_success(self, mock_file_utils):
        """Test successful CSV upload."""
        from fastapi.testclient import TestClient
        from app.api.endpoints import router
        from app.main import app
        
        app.include_router(router)
        client = TestClient(app)
        
        # Create a temporary CSV file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write("name,age\nAlice,25\nBob,30")
            temp_path = f.name
        
        try:
            with open(temp_path, 'rb') as f:
                response = client.post("/upload", files={"file": ("test.csv", f, "text/csv")})
            
            assert response.status_code == 200
            assert "file_path" in response.json()
        finally:
            os.unlink(temp_path)
    
    def test_upload_non_csv_rejected(self):
        """Test that non-CSV files are rejected."""
        from fastapi.testclient import TestClient
        from app.api.endpoints import router
        from app.main import app
        
        app.include_router(router)
        client = TestClient(app)
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("This is not a CSV")
            temp_path = f.name
        
        try:
            with open(temp_path, 'rb') as f:
                response = client.post("/upload", files={"file": ("test.txt", f, "text/plain")})
            
            assert response.status_code == 400
        finally:
            os.unlink(temp_path)
    
    def test_process_endpoint_requires_file(self):
        """Test that /process requires a valid file."""
        from fastapi.testclient import TestClient
        from app.api.endpoints import router
        from app.main import app
        
        app.include_router(router)
        client = TestClient(app)
        
        response = client.post("/process", json={"file_path": "/nonexistent/file.csv"})
        
        assert response.status_code == 404
    
    def test_nlq_endpoint_requires_file(self):
        """Test that /nlq requires a valid file."""
        from fastapi.testclient import TestClient
        from app.api.endpoints import router
        from app.main import app
        
        app.include_router(router)
        client = TestClient(app)
        
        response = client.post("/nlq", json={
            "file_path": "/nonexistent/file.csv",
            "question": "What is the average age?"
        })
        
        assert response.status_code == 404
    
    def test_bigquery_requires_valid_credentials(self):
        """Test that /bigquery fails with invalid credentials."""
        from fastapi.testclient import TestClient
        from app.api.endpoints import router
        from app.main import app
        
        app.include_router(router)
        client = TestClient(app)
        
        response = client.post("/bigquery", json={
            "credentials_json": "invalid json",
            "query": "SELECT 1"
        })
        
        assert response.status_code == 400
    
    def test_session_endpoints(self):
        """Test session management endpoints."""
        from fastapi.testclient import TestClient
        from app.api.endpoints import router
        from app.main import app
        
        app.include_router(router)
        client = TestClient(app)
        
        # Test get session (non-existent)
        response = client.get("/sessions/test-session-id")
        assert response.status_code == 200
        assert response.json()["history"] == []
        
        # Test delete session (non-existent)
        response = client.delete("/sessions/test-session-id")
        assert response.status_code == 200
        assert response.json()["status"] == "cleared"
    
    def test_health_endpoint(self):
        """Test health check endpoint."""
        from fastapi.testclient import TestClient
        from app.main import app
        
        client = TestClient(app)
        
        response = client.get("/health")
        
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


class TestEndpointsIntegration:
    """Integration-style tests for endpoints."""
    
    @pytest.fixture
    def temp_csv(self, sample_csv_content):
        """Create a temporary CSV file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write(sample_csv_content)
            temp_path = f.name
        
        yield temp_path
        
        if os.path.exists(temp_path):
            os.unlink(temp_path)
    
    @patch('app.api.endpoints.InsightOrchestraWorkflow')
    def test_process_workflow_called(self, mock_workflow, temp_csv):
        """Test that /process calls the workflow."""
        from fastapi.testclient import TestClient
        from app.api.endpoints import router
        from app.main import app
        
        # Setup mock
        mock_instance = MagicMock()
        mock_instance.run.return_value = {
            "cleaner": {},
            "hypothesis": {},
            "debate": {},
            "viz": {},
            "audit_table": "| Test |\n|---|\n",
        }
        mock_workflow.return_value = mock_instance
        
        app.include_router(router)
        client = TestClient(app)
        
        response = client.post("/process", json={"file_path": temp_csv})
        
        assert response.status_code == 200
        mock_instance.run.assert_called_once()
    
    @patch('app.api.endpoints.NaturalLanguageQueryAgent')
    def test_nlq_agent_called(self, mock_agent_class, temp_csv):
        """Test that /nlq calls the NLQ agent."""
        from fastapi.testclient import TestClient
        from app.api.endpoints import router
        from app.main import app
        
        # Setup mock
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
        
        app.include_router(router)
        client = TestClient(app)
        
        response = client.post("/nlq", json={
            "file_path": temp_csv,
            "question": "What is the average age?"
        })
        
        assert response.status_code == 200
        mock_instance.run.assert_called_once()


class TestEndpointsErrorHandling:
    """Test error handling in endpoints."""
    
    def test_upload_handles_value_error(self):
        """Test that upload handles ValueError."""
        from fastapi.testclient import TestClient
        from app.api.endpoints import router
        from app.main import app
        
        with patch('app.api.endpoints.save_upload_file') as mock:
            mock.side_effect = ValueError("Invalid file")
            
            app.include_router(router)
            client = TestClient(app)
            
            with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
                f.write("name,age\nAlice,25")
                temp_path = f.name
            
            try:
                with open(temp_path, 'rb') as f:
                    response = client.post("/upload", files={"file": ("test.csv", f, "text/csv")})
                
                assert response.status_code == 400
            finally:
                os.unlink(temp_path)
    
    def test_process_handles_csv_read_error(self):
        """Test that /process handles CSV read errors."""
        from fastapi.testclient import TestClient
        from app.api.endpoints import router
        from app.main import app
        
        app.include_router(router)
        client = TestClient(app)
        
        # Create a corrupted CSV
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write("this is, not, valid, csv,,,")
            temp_path = f.name
        
        try:
            response = client.post("/process", json={"file_path": temp_path})
            
            assert response.status_code == 400
        finally:
            os.unlink(temp_path)
