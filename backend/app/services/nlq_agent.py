"""
Natural Language Query (NLQ) Agent

This agent:
1. Takes user questions in natural language
2. Generates Python code using LLM
3. Executes code safely in sandbox
4. Returns results with visualizations
"""

import json
import logging
import numbers
import re
from dataclasses import dataclass
from typing import Any

import pandas as pd
import plotly.express as px
import requests

from app.services.llm_service import DataFrameSchema, LLMProvider, LLMService
from app.services.sandbox_executor import SandboxExecutor
from app.utils.log_utils import safe_log_value

logger = logging.getLogger(__name__)

# Keywords that indicate the user wants a visualization
_PLOT_KEYWORDS = {
    "plot",
    "chart",
    "graph",
    "visualize",
    "visualise",
    "draw",
    "display",
    "show",
    "bar",
    "histogram",
    "scatter",
    "pie",
    "heatmap",
    "line",
    "trend",
    "distribution",
}


@dataclass
class NLQResponse:
    """Response from NLQ Agent."""

    answer: str
    code: str
    reasoning: str = ""
    plot_json: str | None = None
    data_result: Any | None = None
    needs_clarification: bool = False
    clarification_question: str | None = None
    execution_success: bool = False
    error: str | None = None
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

    # Stripped-down prompt for small Ollama models (< 2 B params).
    # Uses ~60 % fewer tokens, leaving the model more room for its completion.
    COMPACT_SYSTEM_PROMPT = (
        "Python data analyst. `df` is already loaded. `pd` and `px` are imported.\n"
        "Rules: no imports, no df= reassignment, assign final answer to `result`.\n"
        "Respond with JSON only — no markdown:\n"
        '{"reasoning":"<one line>","code":"result = ...","needs_clarification":false,'
        '"clarification_question":null}'
    )

    def __init__(
        self,
        llm_service: LLMService | None = None,
        sandbox: SandboxExecutor | None = None,
        max_retries: int = 2,
    ):
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

    @staticmethod
    def _is_plot_question(question: str) -> bool:
        """Return True if any word in the question signals a visualization request."""
        words = set(re.findall(r"[a-z]+", question.lower()))
        return bool(words & _PLOT_KEYWORDS)

    def _get_schema_prompt(self, df: pd.DataFrame) -> str:
        """Generate schema prompt from DataFrame, capped at 50 columns."""
        schema = DataFrameSchema.from_dataframe(df, max_columns=50)
        return DataFrameSchema.to_prompt(schema)

    def _build_few_shot_examples(self, df: pd.DataFrame) -> str:
        """Generate 1–2 concrete examples using the actual column names."""
        numeric = df.select_dtypes(include="number").columns.tolist()
        categorical = df.select_dtypes(include=["object", "string", "category"]).columns.tolist()

        examples: list[str] = []
        if categorical and numeric:
            c, n = categorical[0], numeric[0]
            examples.append(
                f"# Group and aggregate\nresult = df.groupby('{c}')['{n}'].sum().reset_index()"
            )
            examples.append(
                f"# Bar chart\n"
                f"result = px.bar("
                f"df.groupby('{c}')['{n}'].mean().reset_index(), "
                f"x='{c}', y='{n}')"
            )
        elif len(numeric) >= 2:
            a, b = numeric[0], numeric[1]
            examples.append(f"# Scatter\nresult = px.scatter(df, x='{a}', y='{b}')")
            examples.append(f"# Correlation\nresult = df[['{a}', '{b}']].corr()")
        elif numeric:
            n = numeric[0]
            examples.append(f"# Mean\nresult = df['{n}'].mean()")
            examples.append(f"# Histogram\nresult = px.histogram(df, x='{n}')")
        return "\n\n".join(examples)

    def _pick_system_prompt(self, is_plot: bool) -> str:
        """
        Return the shortest effective system prompt for the active provider.
        Ollama with small models gets the compact version to preserve token budget.
        """
        is_ollama = hasattr(self.llm, "config") and self.llm.config.provider == LLMProvider.OLLAMA
        if is_ollama:
            return self.COMPACT_SYSTEM_PROMPT
        if is_plot:
            return (
                "You are a Plotly Chart Generator.\n"
                "You have access to a pandas DataFrame called `df` and plotly.express as `px`.\n\n"
                "CRITICAL RULE: generate a Plotly chart with `px` and assign it to `result`.\n"
                "NEVER use `df.plot()`.\n\n"
                "OUTPUT FORMAT (JSON only):\n"
                '{{"reasoning":"...","code":"result = px.bar(...)","needs_clarification":false,'
                '"clarification_question":null}}'
            )
        return self.SYSTEM_PROMPT

    @staticmethod
    def _fix_matplotlib_code(code: str) -> str:
        """
        Replace matplotlib plt.* calls with plotly express px.* equivalents.
        Small models often generate matplotlib code instead of plotly.
        """
        replacements = [
            (r"plt\.bar\s*\(", "px.bar("),
            (r"plt\.barh\s*\(", "px.bar("),
            (r"plt\.hist\s*\(", "px.histogram("),
            (r"plt\.scatter\s*\(", "px.scatter("),
            (r"plt\.plot\s*\(", "px.line("),
            (r"plt\.pie\s*\(", "px.pie("),
            (r"plt\.boxplot\s*\(", "px.box("),
        ]
        for pattern, replacement in replacements:
            code = re.sub(pattern, replacement, code)
        # Remove plt.* calls that have no px equivalent (show, title, xlabel, etc.)
        code = re.sub(r"^\s*plt\.[a-zA-Z_]+\(.*\)\s*$", "", code, flags=re.MULTILINE)
        return code

    @staticmethod
    def _fix_column_names(code: str, df: pd.DataFrame) -> str:
        """
        Scan quoted string literals in generated code and replace any value that
        isn't a real column name with the closest real one.

        Matching strategy (in order):
          1. Exact match — leave it alone.
          2. Case-insensitive match — fix capitalisation.
          3. Substring match — model used part of a column name.
          4. Difflib edit-distance (cutoff 0.75) — catches typos like 'revnue'.
          5. No match — leave as-is so sandbox can report the real error.
        """
        import difflib

        columns = df.columns.tolist()
        col_lower = {c.lower(): c for c in columns}

        def _closest(token: str) -> str:
            if token in columns:
                return token
            tl = token.lower()
            if tl in col_lower:
                return str(col_lower[tl])
            for col in columns:
                if tl in str(col).lower() or str(col).lower() in tl:
                    return str(col)
            close = difflib.get_close_matches(tl, col_lower.keys(), n=1, cutoff=0.75)
            if close:
                return str(col_lower[close[0]])
            return token

        def _replace(match: re.Match) -> str:
            quote, token = match.group(1), match.group(2)
            return f"{quote}{_closest(token)}{quote}"

        return re.sub(r"(['\"])([A-Za-z0-9_ ]+)\1", _replace, code)

    @staticmethod
    def _recover_truncated_code(code: str) -> str:
        """
        When a small model cuts off mid-expression the result is a SyntaxError.
        Walk backwards line by line until we find a syntactically valid prefix,
        then return that prefix so at least a partial result is attempted.
        """
        lines = code.split("\n")
        for end in range(len(lines), 0, -1):
            fragment = "\n".join(lines[:end]).strip()
            if not fragment:
                continue
            try:
                compile(fragment, "<recovery>", "exec")
                return fragment
            except SyntaxError:
                continue
        return code  # nothing worked; return original so sandbox can report it

    def _generate_code(
        self,
        df: pd.DataFrame,
        question: str,
        context: list[dict] | None = None,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        """Generate Python code from a natural language question."""
        is_plot = self._is_plot_question(question)
        few_shot = self._build_few_shot_examples(df)

        user_prompt = (
            f"DataFrame Information:\n{self._get_schema_prompt(df)}\n\n"
            f"Examples using these exact columns:\n{few_shot}\n\n"
            f"User Question: {question}\n\n"
            + (f"Previous Context:\n{context}\n\n" if context else "")
            + "Generate Python code to answer this question. Assign the result to `result`."
        )

        system_prompt = self._pick_system_prompt(is_plot)

        use_fallback = len(question) > 200 or any(
            w in question.lower() for w in ("complex", "compare", "analyze")
        )

        try:
            response = self.llm.complete_json(system_prompt, user_prompt, use_fallback=use_fallback)
            return response
        except Exception as e:
            logger.error(f"[session={session_id}] LLM call failed: {e}")
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
        lines = code.split("\n")
        filtered_lines = []

        for line in lines:
            stripped = line.strip()
            # Skip import and from statements
            if stripped.startswith("import ") or stripped.startswith("from "):
                continue

            # Skip lines that try to recreate/load the dataframe from files or placeholder data
            if (
                "pd.DataFrame(" in stripped
                or "pd.read_csv(" in stripped
                or "pd.read_excel(" in stripped
                or "pd.read_parquet(" in stripped
                or "pd.read_json(" in stripped
                or "pd.read_table(" in stripped
                or "path_to_your_file" in stripped
                or "your_file.csv" in stripped
                or stripped.startswith("df = pd.")
                or stripped.startswith("df = data")
            ):
                continue
            filtered_lines.append(line)

        code = "\n".join(filtered_lines).strip()

        # Remove any trailing print statements or comments
        lines = code.split("\n")
        clean_lines = []
        last_non_comment_idx = -1

        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                last_non_comment_idx = i
            clean_lines.append(line)

        # If last line is an expression (not assignment), wrap it
        # Match simple assignment: identifier (optionally subscripted) followed by =
        # but NOT ==, !=, <=, >=
        _ASSIGN_RE = re.compile(r"^[A-Za-z_]\w*(\[.*?\])?\s*(?<![=!<>])=(?!=)")
        if last_non_comment_idx >= 0:
            last_line = clean_lines[last_non_comment_idx].strip()

            is_assignment = bool(_ASSIGN_RE.match(last_line))
            is_control = last_line.startswith(
                ("if ", "for ", "while ", "with ", "try", "def ", "class ")
            )

            if not is_assignment and not is_control:
                indent = len(clean_lines[last_non_comment_idx]) - len(
                    clean_lines[last_non_comment_idx].lstrip()
                )
                clean_lines[last_non_comment_idx] = " " * indent + f"result = {last_line}"

        return "\n".join(clean_lines)

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

        elif isinstance(result, int | float):
            return (
                f"The answer is {result:,.2f}"
                if isinstance(result, float)
                else f"The answer is {result}"
            )

        elif isinstance(result, dict):
            return f"Results: {json.dumps(result, indent=2)}"

        elif result is None:
            return "Query executed but no result was returned."

        module = (type(result).__module__ or "").lower()
        if "matplotlib" in module:
            return "Here's the chart for your question — see the Canvas."
        # Plotly figures stringify into a huge binary blob; never surface that.
        if "plotly" in module or hasattr(result, "to_plotly_json"):
            return self._describe_chart(result)

        return str(result)

    @staticmethod
    def _to_list(value: Any) -> list:
        """`list(value) if value is not None else []` — plain `value or []` raises
        on numpy arrays, whose truthiness is ambiguous for more than one element."""
        return [] if value is None else list(value)

    @classmethod
    def _describe_chart(cls, fig: Any) -> str:
        """Best-effort plain-English narration of a Plotly figure's underlying data.

        Falls back to a generic pointer to the Canvas if the figure shape isn't
        one we know how to summarize (e.g. multi-trace or 3D charts).
        """
        fallback = "Here's the chart for your question — see the Canvas."
        try:
            traces = getattr(fig, "data", None)
            if not traces:
                return fallback
            trace = traces[0]
            trace_type = getattr(trace, "type", "")

            if trace_type == "pie":
                labels = cls._to_list(getattr(trace, "labels", None))
                values = [
                    float(v)
                    for v in cls._to_list(getattr(trace, "values", None))
                    if isinstance(v, numbers.Real)
                ]
                if labels and values and len(labels) == len(values):
                    total = sum(values)
                    top_label, top_value = max(zip(labels, values, strict=True), key=lambda p: p[1])
                    share = (top_value / total * 100) if total else 0
                    return f"{top_label} is the largest share at {share:.0f}% ({top_value:,.2f})."
                return fallback

            if trace_type == "histogram":
                xs = [
                    float(v)
                    for v in cls._to_list(getattr(trace, "x", None))
                    if isinstance(v, numbers.Real)
                ]
                if xs:
                    return (
                        f"Values range from {min(xs):,.2f} to {max(xs):,.2f}, "
                        f"averaging {sum(xs) / len(xs):,.2f} across {len(xs)} points."
                    )
                return fallback

            xs = cls._to_list(getattr(trace, "x", None))
            ys = [
                float(v)
                for v in cls._to_list(getattr(trace, "y", None))
                if isinstance(v, numbers.Real)
            ]
            if xs and ys and len(xs) == len(ys):
                pairs = sorted(zip(xs, ys, strict=True), key=lambda p: p[1], reverse=True)
                top_x, top_y = pairs[0]
                if len(pairs) == 1:
                    return f"{top_x} is {top_y:,.2f}."
                bottom_x, bottom_y = pairs[-1]
                return (
                    f"{top_x} is highest at {top_y:,.2f}, {bottom_x} is lowest at {bottom_y:,.2f}."
                )
        except Exception as e:
            # Best-effort summary only — fall back to the generic caption below
            # if the trace data doesn't have the shape we expect.
            logger.debug("Could not summarize chart trace: %s", safe_log_value(e))
        return fallback

    def _build_fallback_plot(self, df: pd.DataFrame, result_obj: Any):
        """Build a Plotly chart when chart mode returns a non-Plotly object."""
        # If query result is a DataFrame, prefer plotting that.
        if isinstance(result_obj, pd.DataFrame) and not result_obj.empty:
            numeric_cols = result_obj.select_dtypes(include=["number"]).columns.tolist()
            categorical_cols = result_obj.select_dtypes(
                include=["object", "string", "category"]
            ).columns.tolist()
            if categorical_cols and numeric_cols:
                return px.bar(result_obj, x=categorical_cols[0], y=numeric_cols[0])
            if len(numeric_cols) >= 2:
                return px.scatter(result_obj, x=numeric_cols[0], y=numeric_cols[1])
            if len(numeric_cols) == 1:
                return px.histogram(result_obj, x=numeric_cols[0])

        # Fallback to original dataset
        numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
        categorical_cols = df.select_dtypes(
            include=["object", "string", "category"]
        ).columns.tolist()
        if categorical_cols and numeric_cols:
            grouped = df.groupby(categorical_cols[0])[numeric_cols[0]].mean().reset_index()
            return px.bar(grouped, x=categorical_cols[0], y=numeric_cols[0])
        if len(numeric_cols) >= 2:
            return px.scatter(df, x=numeric_cols[0], y=numeric_cols[1])
        if len(numeric_cols) == 1:
            return px.histogram(df, x=numeric_cols[0])
        return None

    _PLOTLY_FALLBACK = (
        "\nif hasattr(result, 'columns') and len(result.columns) >= 2:\n"
        "    str_cols = result.select_dtypes(include=['object', 'string']).columns\n"
        "    num_cols = result.select_dtypes(include=['number']).columns\n"
        "    if len(str_cols) > 0 and len(num_cols) > 0:\n"
        "        result = px.bar(result, x=str_cols[0], y=num_cols[-1])\n"
        "    else:\n"
        "        result = px.bar(result, x=result.columns[1], y=result.columns[-1])\n"
    )

    def run(
        self,
        df: pd.DataFrame,
        question: str,
        context: list[dict] | None = None,
        session_id: str | None = None,
    ) -> NLQResponse:
        """Process a natural language query against the DataFrame."""
        sid = session_id or "?"
        logger.info(
            "[session=%s] Processing NLQ: %r",
            safe_log_value(sid),
            safe_log_value(question[:100]),
        )

        try:
            # Step 1: Generate code
            llm_response = self._generate_code(df, question, context, session_id)

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

            # Step 2: Pre-process generated code
            # Replace matplotlib plt.* with plotly px.* equivalents
            code = self._fix_matplotlib_code(code)
            # Fix hallucinated column names before anything else
            code = self._fix_column_names(code, df)
            # Recover from model truncation (unclosed parens / syntax errors)
            code = self._recover_truncated_code(code)

            executed_code = self._ensure_result_assignment(code)
            is_plot = self._is_plot_question(question)
            logger.info(f"[session={sid}] is_plot={is_plot}")

            if is_plot and "px." not in executed_code and "plotly" not in executed_code:
                logger.info(f"[session={sid}] Auto-injecting plotly fallback")
                executed_code += self._PLOTLY_FALLBACK

            exec_result = self.sandbox.execute_with_retry(
                executed_code, df, max_retries=self.max_retries
            )

            if not exec_result.success:
                logger.error(f"[session={sid}] Sandbox failed: {exec_result.error}")
                valid_cols = df.columns.tolist()
                retry_prompt = (
                    f"Original question: {question}\n\n"
                    f"VALID column names (use ONLY these): {valid_cols}\n\n"
                    f"Previous code failed with error: {exec_result.error}\n\n"
                    "Generate simpler, corrected Python code. "
                    "Assign the result to `result`. Use basic pandas operations only."
                )
                try:
                    retry_response = self.llm.complete_json(
                        system_prompt=self.SYSTEM_PROMPT,
                        user_prompt=retry_prompt,
                    )
                    retry_code = retry_response.get("code", "")
                    if retry_code:
                        logger.info(f"[session={sid}] Retrying with simplified code")
                        executed_code = self._ensure_result_assignment(retry_code)
                        exec_result = self.sandbox.execute_with_retry(
                            executed_code, df, max_retries=self.max_retries
                        )
                        if not exec_result.success:
                            logger.error(f"[session={sid}] Retry also failed: {exec_result.error}")
                except Exception as e:
                    logger.error(f"[session={sid}] Retry code generation failed: {e}")

            # Step 3: Build answer
            answer = self._build_answer(exec_result.result, question)

            # Step 4: Extract plot JSON if result is a Plotly figure.
            # NOTE: pandas DataFrames also have to_json(), so we MUST check the module
            # name before calling it — otherwise we send pandas JSON to the frontend
            # and the chart never renders.
            plot_json = None
            result_obj = exec_result.result
            if (
                result_obj is not None
                and hasattr(result_obj, "to_plotly_json")
                and "plotly" in type(result_obj).__module__
            ):
                plot_json = result_obj.to_json()

            if is_plot and not plot_json:
                try:
                    fallback_fig = self._build_fallback_plot(df, result_obj)
                    if fallback_fig is not None:
                        plot_json = fallback_fig.to_json()
                        answer = "Chart generated successfully."
                except Exception as e:
                    logger.error(f"Fallback chart generation failed: {e}")

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
            logger.error(f"[session={sid}] NLQ processing failed: {e}")
            return NLQResponse(
                answer=self._friendly_error(e),
                code="",
                reasoning="",
                error=str(e),
                tokens_used=self.llm.total_tokens,
                cost_usd=self.llm.total_cost,
            )

    def _friendly_error(self, e: Exception) -> str:
        """Map a raw LLM provider exception to an actionable message.

        Auth failures are detected by shape (a `status_code` of 401, or
        "AuthenticationError" in the exception's class name) rather than
        importing any specific SDK's error types, so this covers every cloud
        provider — including ones added later — without needing an update
        here. Ollama is the one provider called over plain HTTP instead of
        an SDK, so a dead/unreachable container surfaces as a
        `requests.exceptions.ConnectionError` instead — checked separately
        since neither signal above would catch it. Either way, the raw
        `str()` is a provider JSON error body or a urllib3 retry trace,
        neither of which is actionable for a user, so surface what to
        actually do instead.
        """
        is_auth_error = (
            getattr(e, "status_code", None) == 401
            or "authenticationerror" in type(e).__name__.lower()
        )
        if is_auth_error:
            provider = self.llm.config.provider
            env_var = {
                LLMProvider.OPENAI: "OPENAI_API_KEY",
                LLMProvider.ANTHROPIC: "ANTHROPIC_API_KEY",
                LLMProvider.DEEPSEEK: "DEEPSEEK_API_KEY",
            }.get(provider)
            if env_var:
                return (
                    f"Your {provider.value} API key is missing or invalid. "
                    f"Add it to backend/.env ({env_var}=...) and restart the backend "
                    "(docker compose up -d --build backend)."
                )

        if (
            isinstance(e, requests.exceptions.ConnectionError)
            and self.llm.config.provider == LLMProvider.OLLAMA
        ):
            return (
                f"Can't reach Ollama at {self.llm.config.base_url}. Make sure the ollama "
                "container is running (docker compose up -d ollama) and the model is pulled "
                f"(docker compose exec ollama ollama pull {self.llm.config.model})."
            )
        return f"Error processing your question: {str(e)}"

    def get_cost_summary(self) -> dict[str, Any]:
        """Get cost summary from LLM service."""
        return self.llm.get_cost_summary()


# Example usage
if __name__ == "__main__":
    import os

    import pandas as pd

    # Check for API key
    if not os.getenv("OPENAI_API_KEY"):
        print("Note: Set OPENAI_API_KEY to test LLM integration")
        print("Running in demo mode...\n")

    # Create sample DataFrame
    df = pd.DataFrame(
        {
            "Name": ["Alice", "Bob", "Charlie", "Diana"],
            "Age": [25, 30, 35, 28],
            "Department": ["Engineering", "Sales", "Engineering", "Marketing"],
            "Salary": [75000, 65000, 85000, 70000],
        }
    )

    agent = NaturalLanguageQueryAgent()

    # Test questions
    questions = [
        "What is the average age?",
        "Show me salary by department",
        "How many people are in each department?",
    ]

    for question in questions:
        print(f"\n{'=' * 50}")
        print(f"Question: {question}")
        print(f"{'=' * 50}")

        response = agent.run(df, question)

        print(f"Answer: {response.answer}")
        print(f"\nCode:\n{response.code}")
        print(f"\nReasoning: {response.reasoning}")
        print(f"Execution: {'Success' if response.execution_success else 'Failed'}")
        if response.error:
            print(f"Error: {response.error}")
        print(f"Tokens: {response.tokens_used}, Cost: ${response.cost_usd:.4f}")
