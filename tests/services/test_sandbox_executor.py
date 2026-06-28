"""
Unit tests for Sandbox Executor.
"""

import pandas as pd
import pytest
from app.services.sandbox_executor import SandboxExecutor


class TestSandboxExecutor:
    """Test cases for SandboxExecutor."""

    @pytest.fixture
    def executor(self):
        """Create a SandboxExecutor instance."""
        return SandboxExecutor(timeout_seconds=10)

    def test_execute_simple_calculation(self, executor, sample_dataframe):
        """Test executing simple pandas calculations."""
        code = """
result = df['age'].mean()
"""
        result = executor.execute(code, sample_dataframe)

        assert result.success is True
        assert result.error == ""
        assert isinstance(result.result, float)

    def test_execute_groupby(self, executor, sample_dataframe):
        """Test executing groupby operations."""
        code = """
result = df.groupby('department')['salary'].mean()
"""
        result = executor.execute(code, sample_dataframe)

        assert result.success is True
        assert result.error == ""
        assert hasattr(result.result, '__iter__')

    def test_execute_with_conditionals(self, executor, sample_dataframe):
        """Test executing code with conditionals."""
        code = """
avg_age = df['age'].mean()
if avg_age > 25:
    result = "Above 25"
else:
    result = "25 or below"
"""
        result = executor.execute(code, sample_dataframe)

        assert result.success is True
        assert result.result == "Above 25"

    def test_blocked_import_os(self, executor, sample_dataframe):
        """Test that os import is blocked."""
        code = """
import os
result = os.getcwd()
"""
        result = executor.execute(code, sample_dataframe)

        assert result.success is False
        assert "Safety check failed" in result.error or "Blocked pattern" in result.error

    def test_blocked_import_subprocess(self, executor, sample_dataframe):
        """Test that subprocess import is blocked."""
        code = """
import subprocess
result = subprocess.run(['ls'], capture_output=True)
"""
        result = executor.execute(code, sample_dataframe)

        assert result.success is False
        assert "Blocked pattern" in result.error

    def test_blocked_eval(self, executor, sample_dataframe):
        """Test that eval is blocked."""
        code = """
result = eval("1 + 1")
"""
        result = executor.execute(code, sample_dataframe)

        assert result.success is False
        assert "Blocked pattern" in result.error

    def test_blocked_exec(self, executor, sample_dataframe):
        """Test that exec is blocked."""
        code = """
exec("print('hello')")
"""
        result = executor.execute(code, sample_dataframe)

        assert result.success is False
        assert "Blocked pattern" in result.error

    def test_blocked_file_operations(self, executor, sample_dataframe):
        """Test that file operations are blocked."""
        code = """
with open('test.txt', 'w') as f:
    f.write('hello')
"""
        result = executor.execute(code, sample_dataframe)

        assert result.success is False
        assert "Blocked pattern" in result.error

    def test_execution_timeout(self):
        """Test that long-running code times out."""
        executor = SandboxExecutor(timeout_seconds=1)
        code = """
import time
time.sleep(10)
result = 1
"""
        result = executor.execute(code, pd.DataFrame({'a': [1, 2, 3]}))

        assert result.success is False
        assert "timed out" in result.error.lower()

    def test_execution_with_syntax_error(self, executor, sample_dataframe):
        """Test that syntax errors are caught at compile time."""
        code = """
result = df['age].mean()  # Missing quote
"""
        result = executor.execute(code, sample_dataframe)

        assert result.success is False
        assert "Compilation error" in result.error

    def test_execution_with_runtime_error(self, executor, sample_dataframe):
        """Test that runtime errors are caught."""
        code = """
result = df['nonexistent_column'].sum()
"""
        result = executor.execute(code, sample_dataframe)

        assert result.success is False
        assert "Execution error" in result.error

    def test_execution_result_to_dict(self, executor, sample_dataframe):
        """Test ExecutionResult serialization."""
        code = """
result = df['age'].mean()
"""
        result = executor.execute(code, sample_dataframe)
        result_dict = result.to_dict()

        assert 'success' in result_dict
        assert 'output' in result_dict
        assert 'error' in result_dict
        assert 'result' in result_dict
        assert 'execution_time_ms' in result_dict

    def test_execute_with_retry_success(self, executor, sample_dataframe):
        """Test retry mechanism with eventual success."""
        code = """
result = df['age'].mean()
"""
        result = executor.execute_with_retry(code, sample_dataframe, max_retries=2)

        assert result.success is True

    def test_safe_builtins_available(self, executor, sample_dataframe):
        """Test that safe builtins are available."""
        code = """
result = len(df)
avg = sum(df['age']) / len(df['age'])
"""
        result = executor.execute(code, sample_dataframe)

        assert result.success is True

    def test_plotly_available(self, executor, sample_dataframe):
        """Test that plotly is available."""
        code = """
import plotly.express as px
fig = px.bar(df, x='department', y='salary')
result = fig is not None
"""
        result = executor.execute(code, sample_dataframe)

        assert result.success is True
        assert result.result is True
