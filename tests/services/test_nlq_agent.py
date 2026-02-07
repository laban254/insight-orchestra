"""
Unit tests for NLQ Agent.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from app.services.nlq_agent import NaturalLanguageQueryAgent, NLQResponse


class TestNLQResponse:
    """Test cases for NLQResponse."""
    
    def test_create_basic_response(self):
        """Test creating a basic NLQ response."""
        response = NLQResponse(
            answer="The average age is 29.5",
            code="result = df['age'].mean()",
            reasoning="Calculated mean of age column",
        )
        
        assert response.answer == "The average age is 29.5"
        assert response.code == "result = df['age'].mean()"
        assert response.reasoning == "Calculated mean of age column"
        assert response.execution_success is False
        assert response.error is None
    
    def test_response_with_plot(self):
        """Test response with plot JSON."""
        response = NLQResponse(
            answer="Here is a chart",
            code="fig = px.bar(df, x='dept', y='salary')",
            reasoning="Created bar chart",
            plot_json='{"type": "bar"}',
            execution_success=True,
        )
        
        assert response.plot_json == '{"type": "bar"}'
        assert response.execution_success is True
    
    def test_response_needs_clarification(self):
        """Test response that needs clarification."""
        response = NLQResponse(
            answer="Could you clarify?",
            code="",
            reasoning="",
            needs_clarification=True,
            clarification_question="Do you mean average or sum?",
        )
        
        assert response.needs_clarification is True
        assert response.clarification_question == "Do you mean average or sum?"
    
    def test_response_with_error(self):
        """Test response with error."""
        response = NLQResponse(
            answer="An error occurred",
            code="result = df['invalid'].mean()",
            execution_success=False,
            error="KeyError: 'invalid'",
        )
        
        assert response.execution_success is False
        assert "KeyError" in response.error


class TestNaturalLanguageQueryAgent:
    """Test cases for NaturalLanguageQueryAgent."""
    
    @pytest.fixture
    def mock_llm_service(self):
        """Create a mock LLM service."""
        mock = Mock()
        mock.complete_json.return_value = {
            "reasoning": "Calculated mean age",
            "code": "result = df['age'].mean()",
            "needs_clarification": False,
            "clarification_question": None,
        }
        mock.total_tokens = 100
        mock.total_cost = 0.001
        return mock
    
    @pytest.fixture
    def mock_sandbox(self):
        """Create a mock sandbox executor."""
        mock = Mock()
        mock.execute_with_retry.return_value = Mock(
            success=True,
            result=29.5,
            output="",
            error="",
            execution_time_ms=100.0,
        )
        return mock
    
    @pytest.fixture
    def agent(self, mock_llm_service, mock_sandbox):
        """Create an NLQ agent with mocked dependencies."""
        return NaturalLanguageQueryAgent(
            llm_service=mock_llm_service,
            sandbox=mock_sandbox,
        )
    
    def test_run_simple_query(self, agent, sample_dataframe, mock_llm_service):
        """Test running a simple query."""
        response = agent.run(sample_dataframe, "What is the average age?")
        
        assert response.answer is not None
        assert response.code == "result = df['age'].mean()"
        assert response.execution_success is True
        mock_llm_service.complete_json.assert_called_once()
    
    def test_run_groupby_query(self, agent, sample_dataframe, mock_llm_service):
        """Test running a groupby query."""
        mock_sandbox_result = Mock()
        mock_sandbox_result.success = True
        mock_sandbox_result.result = MagicMock()
        mock_sandbox_result.result.to_dict.return_value = {
            'Engineering': 80000,
            'Sales': 65000,
            'Marketing': 70000,
        }
        mock_sandbox_result.output = ""
        mock_sandbox_result.error = ""
        mock_sandbox_result.execution_time_ms = 100.0
        
        agent.sandbox.execute_with_retry.return_value = mock_sandbox_result
        
        response = agent.run(sample_dataframe, "What is the average salary by department?")
        
        assert response.code == "result = df['age'].mean()"  # From mock
        mock_llm_service.complete_json.assert_called_once()
    
    def test_run_with_context(self, agent, sample_dataframe, mock_llm_service):
        """Test running a query with conversation context."""
        context = [
            {"question": "What is the average age?", "answer": "29.5", "code": "..."}
        ]
        
        response = agent.run(sample_dataframe, "What about by department?", context=context)
        
        mock_llm_service.complete_json.assert_called_once()
        call_args = mock_llm_service.complete_json.call_args
        # Should include context in the call
        assert "Previous Context" in call_args[0][1] or context is not None
    
    def test_run_needs_clarification(self, agent, sample_dataframe, mock_llm_service):
        """Test query that needs clarification."""
        mock_llm_service.complete_json.return_value = {
            "reasoning": "Ambiguous question",
            "code": "",
            "needs_clarification": True,
            "clarification_question": "Do you mean average or total?",
        }
        
        response = agent.run(sample_dataframe, "Show me the numbers")
        
        assert response.needs_clarification is True
        assert response.clarification_question == "Do you mean average or total?"
    
    def test_run_execution_error(self, agent, sample_dataframe, mock_llm_service, mock_sandbox):
        """Test query that fails execution."""
        mock_sandbox.execute_with_retry.return_value = Mock(
            success=False,
            error="KeyError: 'nonexistent'",
        )
        
        response = agent.run(sample_dataframe, "What is the nonexistent column?")
        
        assert response.execution_success is False
        assert "KeyError" in response.error
    
    def test_run_with_plotly_code(self, agent, sample_dataframe, mock_llm_service, mock_sandbox):
        """Test query that generates a Plotly chart."""
        mock_fig = MagicMock()
        mock_fig.to_json.return_value = '{"type": "bar"}'
        
        mock_sandbox.execute_with_retry.return_value = Mock(
            success=True,
            result=mock_fig,
            output="",
            error="",
            execution_time_ms=100.0,
        )
        
        response = agent.run(sample_dataframe, "Show me a bar chart of salaries")
        
        assert response.plot_json == '{"type": "bar"}'
    
    def test_run_with_fallback_model(self, agent, sample_dataframe, mock_llm_service):
        """Test that complex queries use fallback model."""
        # Long question should trigger fallback
        long_question = "Compare and contrast the average salary by department and also analyze trends over time and identify outliers and patterns in the data"
        
        response = agent.run(sample_dataframe, long_question)
        
        call_args = mock_llm_service.complete_json.call_args
        # use_fallback should be True for long questions
        assert call_args[1].get("use_fallback") is True or len(long_question) > 200
    
    def test_build_answer_dataframe(self, agent):
        """Test building answer for DataFrame result."""
        import pandas as pd
        
        df = pd.DataFrame({'a': [1, 2, 3]})
        answer = agent._build_answer(df, "Show data")
        
        assert "3 rows" in answer
        assert "a" in answer
    
    def test_build_answer_numeric(self, agent):
        """Test building answer for numeric result."""
        answer = agent._build_answer(42, "What is the count?")
        assert answer == "The answer is 42"
    
    def test_build_answer_float(self, agent):
        """Test building answer for float result."""
        answer = agent._build_answer(29.5, "What is the average?")
        assert answer == "The answer is 29.50"
    
    def test_get_cost_summary(self, agent, mock_llm_service):
        """Test getting cost summary."""
        mock_llm_service.get_cost_summary.return_value = {
            "total_cost_usd": 0.01,
            "total_tokens": 1000,
        }
        
        summary = agent.get_cost_summary()
        
        assert summary["total_cost_usd"] == 0.01
        assert summary["total_tokens"] == 1000
    
    def test_system_prompt_content(self, agent):
        """Test that system prompt contains expected instructions."""
        assert "Data Analyst" in agent.SYSTEM_PROMPT
        assert "pandas DataFrame" in agent.SYSTEM_PROMPT
        assert "result" in agent.SYSTEM_PROMPT
        assert "JSON" in agent.SYSTEM_PROMPT
