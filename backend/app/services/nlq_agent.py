"""
Natural Language Query (NLQ) Agent

This agent:
1. Takes user questions in natural language
2. Generates Python code using LLM
3. Executes code safely in sandbox
4. Returns results with visualizations
"""

import pandas as pd
import plotly.express as px
import json
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

from app.services.llm_service import LLMService, LLMConfig, DataFrameSchema
from app.services.sandbox_executor import SandboxExecutor, ExecutionResult

logger = logging.getLogger(__name__)


@dataclass
class NLQResponse:
    """Response from NLQ Agent."""
    answer: str
    code: str
    reasoning: str
    plot_json: Optional[str] = None
    data_result: Optional[Any] = None
    needs_clarification: bool = False
    clarification_question: Optional[str] = None
    execution_success: bool = False
    error: Optional[str] = None
    tokens_used: int = 0
    cost_usd: float = 0.0


class NaturalLanguageQueryAgent:
    """
    Agent that converts natural language to Python code.
    
    Features:
    - Schema-first prompting
    - Safe code execution
    - Error recovery with retries
    - Plotly visualization generation
    """
    
    # Default system prompt
    SYSTEM_PROMPT = """You are a Python Data Analyst. You have access to a pandas DataFrame called `df`.

Your task is to:
1. Understand the user's question about the data
2. Generate Python code to answer the question
3. Handle visualizations when requested

RULES:
1. Always assign your final answer to a variable called `result`
2. For visualizations, create a Plotly figure and assign to `result`
3. Handle edge cases (empty data, missing columns)
4. If the question is ambiguous, set needs_clarification=true

OUTPUT FORMAT (JSON only):
{{
  "reasoning": "Step-by-step explanation of your approach",
  "code": "Complete Python code to execute",
  "needs_clarification": false,
  "clarification_question": null
}}
"""
    
    def __init__(self, llm_service: Optional[LLMService] = None,
                 sandbox: Optional[SandboxExecutor] = None,
                 max_retries: int = 2):
        """
        Initialize NLQ Agent.
        
        Args:
            llm_service: Optional LLMService instance
            sandbox: Optional SandboxExecutor instance
            max_retries: Maximum code execution retries
        """
        self.llm = llm_service or LLMService()
        self.sandbox = sandbox or SandboxExecutor(timeout_seconds=30)
        self.max_retries = max_retries
    
    def _get_schema_prompt(self, df: pd.DataFrame) -> str:
        """Generate schema prompt from DataFrame."""
        schema = DataFrameSchema.from_dataframe(df)
        return DataFrameSchema.to_prompt(schema)
    
    def _generate_code(self, df: pd.DataFrame, question: str,
                       context: Optional[List[Dict]] = None) -> Dict[str, Any]:
        """
        Generate Python code from natural language question.
        
        Args:
            df: pandas DataFrame
            question: User's question
            context: Optional conversation history
            
        Returns:
            Parsed JSON response from LLM
        """
        # Build user prompt with schema
        user_prompt = f"""DataFrame Information:
{self._get_schema_prompt(df)}

User Question: {question}

{'Previous Context:' + str(context) if context else ''}

Generate Python code to answer this question. Assign the result to a variable called `result`."""

        # Use fallback model for complex queries
        use_fallback = len(question) > 200 or any(
            word in question.lower() for word in ['complex', 'compare', 'analyze']
        )
        
        try:
            response = self.llm.complete_json(
                system_prompt=self.SYSTEM_PROMPT,
                user_prompt=user_prompt,
                use_fallback=use_fallback,
            )
            return response
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            raise
    
    def _execute_code(self, code: str, df: pd.DataFrame) -> ExecutionResult:
        """
        Execute generated code in sandbox.
        
        Args:
            code: Python code to execute
            df: pandas DataFrame
            
        Returns:
            ExecutionResult
        """
        return self.sandbox.execute_with_retry(code, df, max_retries=self.max_retries)
    
    def _build_answer(self, result: Any, question: str) -> str:
        """Build natural language answer from result."""
        if isinstance(result, pd.DataFrame):
            if result.empty:
                return "No results found for your query."
            return f"Found {len(result)} rows with columns: {', '.join(result.columns.tolist())}"
        
        elif isinstance(result, (int, float)):
            return f"The answer is {result:,.2f}" if isinstance(result, float) else f"The answer is {result}"
        
        elif isinstance(result, dict):
            return f"Results: {json.dumps(result, indent=2)}"
        
        elif result is None:
            return "Query executed but no result was returned."
        
        else:
            return str(result)
    
    def run(self, df: pd.DataFrame, question: str,
            context: Optional[List[Dict]] = None) -> NLQResponse:
        """
        Process natural language query.
        
        Args:
            df: pandas DataFrame
            question: User's question
            context: Optional conversation history
            
        Returns:
            NLQResponse object
        """
        logger.info(f"Processing NLQ: {question[:100]}...")
        
        try:
            # Step 1: Generate code
            llm_response = self._generate_code(df, question, context)
            
            reasoning = llm_response.get("reasoning", "")
            code = llm_response.get("code", "")
            needs_clarification = llm_response.get("needs_clarification", False)
            clarification_question = llm_response.get("clarification_question")
            
            if needs_clarification:
                return NLQResponse(
                    answer=clarification_question or "Could you clarify your question?",
                    code=code,
                    reasoning=reasoning,
                    needs_clarification=True,
                    clarification_question=clarification_question,
                    tokens_used=self.llm.total_tokens,
                    cost_usd=self.llm.total_cost,
                )
            
            # Step 2: Execute code
            exec_result = self._execute_code(code, df)
            
            if not exec_result.success:
                # Try to fix code on error (basic retry)
                error_code = f"# Error: {exec_result.error}\n{code}"
                exec_result = self._execute_code(error_code, df)
            
            # Step 3: Build answer
            answer = self._build_answer(exec_result.result, question)
            
            # Step 4: Extract plot JSON if result is a figure
            plot_json = None
            if hasattr(exec_result.result, 'to_json'):
                plot_json = exec_result.result.to_json()
            
            return NLQResponse(
                answer=answer,
                code=code,
                reasoning=reasoning,
                plot_json=plot_json,
                data_result=exec_result.result,
                execution_success=exec_result.success,
                error=exec_result.error if not exec_result.success else None,
                tokens_used=self.llm.total_tokens,
                cost_usd=self.llm.total_cost,
            )
            
        except Exception as e:
            logger.error(f"NLQ processing failed: {e}")
            return NLQResponse(
                answer=f"Error processing your question: {str(e)}",
                code="",
                reasoning="",
                error=str(e),
                tokens_used=self.llm.total_tokens,
                cost_usd=self.llm.total_cost,
            )
    
    def get_cost_summary(self) -> Dict[str, Any]:
        """Get cost summary from LLM service."""
        return self.llm.get_cost_summary()


# Example usage
if __name__ == "__main__":
    import pandas as pd
    import os
    
    # Check for API key
    if not os.getenv("OPENAI_API_KEY"):
        print("Note: Set OPENAI_API_KEY to test LLM integration")
        print("Running in demo mode...\n")
    
    # Create sample DataFrame
    df = pd.DataFrame({
        'Name': ['Alice', 'Bob', 'Charlie', 'Diana'],
        'Age': [25, 30, 35, 28],
        'Department': ['Engineering', 'Sales', 'Engineering', 'Marketing'],
        'Salary': [75000, 65000, 85000, 70000],
    })
    
    agent = NaturalLanguageQueryAgent()
    
    # Test questions
    questions = [
        "What is the average age?",
        "Show me salary by department",
        "How many people are in each department?",
    ]
    
    for question in questions:
        print(f"\n{'='*50}")
        print(f"Question: {question}")
        print(f"{'='*50}")
        
        response = agent.run(df, question)
        
        print(f"Answer: {response.answer}")
        print(f"\nCode:\n{response.code}")
        print(f"\nReasoning: {response.reasoning}")
        print(f"Execution: {'Success' if response.execution_success else 'Failed'}")
        if response.error:
            print(f"Error: {response.error}")
        print(f"Tokens: {response.tokens_used}, Cost: ${response.cost_usd:.4f}")
