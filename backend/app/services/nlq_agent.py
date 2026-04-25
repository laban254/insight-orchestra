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

CRITICAL RULES - READ CAREFULLY:
1. **DO NOT write import statements** - pandas, plotly, numpy are ALREADY available
2. **DO NOT write**: import pandas | from pandas | import plotly | from plotly
3. **DO NOT use**: df = pd.DataFrame(...) - df is already loaded
4. **ALWAYS assign your final result** to a variable called `result`
5. Use only these pre-loaded variables: df, pd, px
6. Handle edge cases (empty data, missing columns)

AVAILABLE PRE-LOADED MODULES:
- `df`: pandas DataFrame with your data (already exists)
- `pd`: pandas module (already imported)
- `px`: plotly.express module (already imported)
- Python builtins: print, len, range, list, dict, etc.

WHAT TO DO:
- Use df directly without importing
- Use pd.function() for pandas operations
- Use px.function() for plotly visualizations

WHAT NOT TO DO:
- ❌ import pandas as pd
- ❌ from pandas import ...
- ❌ import plotly.express as px
- ❌ df = pd.read_csv(...)
- ❌ df = pd.DataFrame(data)

OUTPUT FORMAT (JSON only):
{{
  "reasoning": "Step-by-step explanation",
  "code": "Python code WITHOUT imports",
  "needs_clarification": false,
  "clarification_question": null
}}

EXAMPLES (NO IMPORTS):

Example 1 - Simple Chart:
Code: result = px.bar(df, x='month', y='revenue')

Example 2 - Grouping and Sorting:
Code: result = df.groupby('category')['sales'].sum().reset_index().sort_values('sales')

Example 3 - Complex Chart:
Code: result = px.scatter(df, x='age', y='salary', color='department')

Example 4 - Filtering:
Code: result = df[df['price'] > 100]
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
        """
        user_prompt = f"""DataFrame Information:
{self._get_schema_prompt(df)}

User Question: {question}

{'Previous Context:' + str(context) if context else ''}

Generate Python code to answer this question. Assign the result to a variable called `result`."""

        system_prompt = self.SYSTEM_PROMPT
        is_plot = any(word in question.lower() for word in ['plot', 'chart', 'graph', 'visualize', 'draw'])
        
        if is_plot:
            system_prompt = """You are a Plotly Chart Generator.
You have access to a pandas DataFrame called `df` and plotly.express as `px`.

CRITICAL RULE:
You MUST generate a Plotly chart using `px` and assign it to `result`.
NEVER use `df.plot()`.

Example:
result = px.bar(df.head(5), x='director', y='box_office_million')
"""

        use_fallback = len(question) > 200 or any(
            word in question.lower() for word in ['complex', 'compare', 'analyze']
        )
        
        try:
            response = self.llm.complete_json(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                use_fallback=use_fallback,
            )
            return response
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            raise
    
    def _ensure_result_assignment(self, code: str) -> str:
        """
        Ensure generated code assigns to `result` variable.
        
        If code doesn't contain `result =`, wrap the last expression.
        Also removes import statements since modules are pre-loaded.
        
        Args:
            code: Generated Python code
            
        Returns:
            Modified code with guaranteed `result` assignment and no imports
        """
        code = code.strip()
        
        # Remove all import statements and broken data-loading lines
        lines = code.split('\n')
        filtered_lines = []
        
        for line in lines:
            stripped = line.strip()
            # Skip import and from statements
            if stripped.startswith('import ') or stripped.startswith('from '):
                continue

            # Skip lines that try to recreate/load the dataframe from files or placeholder data
            if (
                'pd.DataFrame(' in stripped
                or 'pd.read_csv(' in stripped
                or 'pd.read_excel(' in stripped
                or 'pd.read_parquet(' in stripped
                or 'pd.read_json(' in stripped
                or 'pd.read_table(' in stripped
                or 'path_to_your_file' in stripped
                or 'your_file.csv' in stripped
                or stripped.startswith('df = pd.')
                or stripped.startswith('df = data')
            ):
                continue
            filtered_lines.append(line)
        
        code = '\n'.join(filtered_lines).strip()
        
        # Remove any trailing print statements or comments
        lines = code.split('\n')
        clean_lines = []
        last_non_comment_idx = -1
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped and not stripped.startswith('#'):
                last_non_comment_idx = i
            clean_lines.append(line)
        
        # If last line is an expression (not assignment), wrap it
        if last_non_comment_idx >= 0:
            last_line = clean_lines[last_non_comment_idx].strip()
            
            # Check if last line is an assignment
            if '=' not in last_line or last_line.startswith(('if ', 'for ', 'while ')):
                # It's an expression, wrap it
                indent = len(clean_lines[last_non_comment_idx]) - len(clean_lines[last_non_comment_idx].lstrip())
                clean_lines[last_non_comment_idx] = ' ' * indent + f'result = {last_line}'
        
        return '\n'.join(clean_lines)
    
    def _execute_code(self, code: str, df: pd.DataFrame) -> ExecutionResult:
        """
        Execute generated code in sandbox.
        
        Args:
            code: Python code to execute
            df: pandas DataFrame
            
        Returns:
            ExecutionResult
        """
        # Ensure code assigns to result
        code = self._ensure_result_assignment(code)
        return self.sandbox.execute_with_retry(code, df, max_retries=self.max_retries)
    
    def _build_answer(self, result: Any, question: str) -> str:
        """Build natural language answer from result."""
        if isinstance(result, pd.DataFrame):
            if result.empty:
                return "No results found for your query."

            preview_rows = result.head(5)
            preview_text = preview_rows.to_string(index=False)
            return (
                f"Found {len(result)} rows with columns: {', '.join(result.columns.tolist())}\n\n"
                f"Top {min(5, len(result))} rows:\n{preview_text}"
            )
        
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
            executed_code = self._ensure_result_assignment(code)
            
            is_plot = any(word in question.lower() for word in ['plot', 'chart', 'graph', 'visualize', 'draw'])
            logger.info(f"is_plot={is_plot}, generated_code:\n{executed_code}")
            
            if is_plot and "px." not in executed_code and "plotly" not in executed_code:
                logger.info("Auto-injecting plotly fallback into executed_code.")
                executed_code += "\nif hasattr(result, 'columns') and len(result.columns) >= 2:\n"
                executed_code += "    # Auto-generate fallback bar chart if there are columns\n"
                executed_code += "    # using the first string column as x and first numeric as y\n"
                executed_code += "    str_cols = result.select_dtypes(include=['object', 'string']).columns\n"
                executed_code += "    num_cols = result.select_dtypes(include=['number']).columns\n"
                executed_code += "    if len(str_cols) > 0 and len(num_cols) > 0:\n"
                executed_code += "        result = px.bar(result, x=str_cols[0], y=num_cols[-1])\n"
                executed_code += "    else:\n"
                executed_code += "        result = px.bar(result, x=result.columns[1], y=result.columns[-1])\n"

            logger.info("Starting sandbox execution for code.")
            exec_result = self.sandbox.execute_with_retry(executed_code, df, max_retries=self.max_retries)
            
            if not exec_result.success:
                logger.error(f"Sandbox execution failed: {exec_result.error}")
                # On error, try once more with a simplified approach
                simplified_prompt = f"""Previous code failed with error: {exec_result.error}\n\nGenerate simpler, more robust Python code that assigns the result to a variable called `result`.\nUse basic pandas operations only."""
                
                try:
                    retry_response = self.llm.complete_json(
                        system_prompt=self.SYSTEM_PROMPT,
                        user_prompt=simplified_prompt,
                    )
                    retry_code = retry_response.get("code", "")
                    if retry_code:
                        logger.info(f"Retrying with simplified code:\n{retry_code}")
                        executed_code = self._ensure_result_assignment(retry_code)
                        exec_result = self.sandbox.execute_with_retry(executed_code, df, max_retries=self.max_retries)
                        if not exec_result.success:
                            logger.error(f"Retry execution also failed: {exec_result.error}")
                except Exception as e:
                    logger.error(f"Failed to generate retry code: {e}")
            
            # Step 3: Build answer
            answer = self._build_answer(exec_result.result, question)
            
            # Step 4: Extract plot JSON if result is a figure
            plot_json = None
            result_obj = exec_result.result
            if hasattr(result_obj, "to_plotly_json") and "plotly" in type(result_obj).__module__:
                plot_json = result_obj.to_json()
            
            return NLQResponse(
                answer=answer,
                code=executed_code,
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
