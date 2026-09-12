"""
Multi-table natural-language-to-SQL agent for database connections.

Separate from NaturalLanguageQueryAgent (nlq_agent.py), which is scoped to
one materialized pandas DataFrame (an upload, demo dataset, or a single
table already pulled out of a database via /connectors/load-table). This
agent instead generates and executes live, read-only SQL directly against
the connected database — JOIN-capable across every table in scope — through
the connectors' existing SELECT-only safety layer (read-only session +
keyword blocklist + no multi-statement; see connectors/postgresql.py).
"""

import logging
import re
from dataclasses import dataclass

import pandas as pd

from app.connectors.base import BaseConnector
from app.services.llm_service import LLMService
from app.utils.chart_heuristics import pick_fallback_chart
from app.utils.log_utils import safe_log_value
from app.utils.markdown import df_to_markdown_table

logger = logging.getLogger(__name__)

# Above this many tables, dumping the full schema into the SQL-generation
# prompt burns tokens on tables that are almost certainly irrelevant to any
# one question, and risks pushing a local/small model past what it can
# usefully attend to. Below it, shortlisting is a wasted extra round trip.
SHORTLIST_THRESHOLD = 50
SHORTLIST_SIZE = 5

# Same defense-in-depth shape as each connector's own check (e.g.
# connectors/postgresql.py) — the read-only DB session is the real control;
# this exists so a blocked query fails with a clear agent-level message
# rather than surfacing the connector's lower-level error.
_BLOCKED_KEYWORDS = re.compile(
    r"\b(DROP|DELETE|INSERT|UPDATE|ALTER|TRUNCATE|CREATE|GRANT|REVOKE|EXEC|EXECUTE|CALL)\b"
)

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

Schema = dict[str, list[dict[str, str]]]


@dataclass
class DatabaseNLQResponse:
    answer: str
    sql: str
    reasoning: str = ""
    plot_json: str | None = None
    tables_used: list[str] | None = None
    needs_clarification: bool = False
    clarification_question: str | None = None
    execution_success: bool = False
    error: str | None = None


def _schema_to_prompt(schema: Schema) -> str:
    lines = []
    for table, columns in schema.items():
        col_desc = ", ".join(f"{c['name']} ({c['type']})" for c in columns)
        lines.append(f"- {table}: {col_desc}")
    return "\n".join(lines)


def shortlist_tables(schema: Schema, question: str, llm: LLMService) -> Schema:
    """Narrow a large schema to the ~5 tables actually relevant to `question`.

    A fast LLM call over table/column *names* only (no data, no types) —
    schema-linking, not query generation. Falls back to the full schema on
    any failure or an empty/unusable pick, so a shortlisting hiccup
    degrades to "the old, slower prompt" rather than a failed query.
    """
    if len(schema) <= SHORTLIST_THRESHOLD:
        return schema

    lines = [
        f"- {table}: {', '.join(c['name'] for c in columns)}" for table, columns in schema.items()
    ]
    system = f"""You are choosing which database tables are relevant to a question.
Given the table/column names below, pick the {SHORTLIST_SIZE} tables most likely needed to
answer it — including any join/lookup tables a query would need even if the question
doesn't name them directly.

OUTPUT (JSON only):
{{"tables": ["table1", "table2", ...]}}"""
    user = "Tables:\n" + "\n".join(lines) + f"\n\nQuestion: {question}"

    try:
        result = llm.complete_json(system, user)
        picked = [t for t in result.get("tables", []) if t in schema]
        if picked:
            return {t: schema[t] for t in picked}
    except Exception as e:
        logger.warning(f"Table shortlisting failed, using full schema: {safe_log_value(e)}")
    return schema


class DatabaseNLQAgent:
    SYSTEM_PROMPT = """You are a SQL analyst. Given a database schema and a question, write
a single read-only SQL SELECT query (JOINs allowed) that answers it.

RULES:
- Only a SELECT statement. Never write INSERT/UPDATE/DELETE/DROP/ALTER/CREATE.
- One statement only — no semicolons, no multiple queries.
- Use only the tables/columns given below; never invent a name.
- Prefer explicit JOIN ... ON over comma joins.
- Add a LIMIT (e.g. 200) unless the question clearly asks for an exact row count or
  aggregate, to avoid an accidental full-table scan.
- If the question is too ambiguous to answer from this schema, set needs_clarification.

OUTPUT (JSON only):
{"reasoning": "one-line explanation", "sql": "SELECT ...", "needs_clarification": false,
 "clarification_question": null}"""

    def __init__(self, llm_service: LLMService | None = None):
        self.llm = llm_service
        if self.llm is None:
            try:
                self.llm = LLMService()
            except Exception:
                # No heuristic fallback exists for "write SQL" the way the
                # other agents fall back to statistics — run() below turns
                # this into a clean error response instead of a raw crash.
                self.llm = None

    @staticmethod
    def _is_plot_question(question: str) -> bool:
        words = set(re.findall(r"[a-z]+", question.lower()))
        return bool(words & _PLOT_KEYWORDS)

    @staticmethod
    def _check_safety(sql: str) -> None:
        if ";" in sql:
            raise ValueError("Multiple statements are not permitted.")
        match = _BLOCKED_KEYWORDS.search(sql.upper())
        if match:
            raise ValueError(f"Generated SQL used a disallowed keyword: {match.group()}.")

    @staticmethod
    def _build_answer(df: pd.DataFrame) -> str:
        if df.empty:
            return "No results found for your query."
        if df.shape == (1, 1):
            v = df.iat[0, 0]
            return f"The answer is {v:,.2f}." if isinstance(v, float) else f"The answer is {v}."
        table = df_to_markdown_table(df)
        return table if len(df) <= 12 else f"{len(df):,} rows — showing the first 12:\n\n{table}"

    def run(
        self,
        connector: BaseConnector,
        schema: Schema,
        question: str,
    ) -> DatabaseNLQResponse:
        if self.llm is None:
            return DatabaseNLQResponse(
                answer=(
                    "No LLM provider is configured, so questions can't be turned into SQL. "
                    "Set an API key in backend/.env and restart the backend."
                ),
                sql="",
                tables_used=list(schema.keys()),
                error="no_llm_configured",
            )

        used_schema = shortlist_tables(schema, question, self.llm)
        user_prompt = f"Schema:\n{_schema_to_prompt(used_schema)}\n\nQuestion: {question}"
        tables_used = list(used_schema.keys())
        sql = ""

        try:
            result = self.llm.complete_json(self.SYSTEM_PROMPT, user_prompt)
            reasoning = result.get("reasoning", "")

            if result.get("needs_clarification"):
                question_text = (
                    result.get("clarification_question") or "Could you clarify your question?"
                )
                return DatabaseNLQResponse(
                    answer=question_text,
                    sql="",
                    reasoning=reasoning,
                    tables_used=tables_used,
                    needs_clarification=True,
                    clarification_question=question_text,
                )

            sql = (result.get("sql") or "").strip().rstrip(";")
            if not sql:
                raise ValueError("The model returned no SQL for this question.")

            self._check_safety(sql)
            df = connector.execute_query(sql)

            plot_json = None
            if self._is_plot_question(question) and not df.empty:
                fig = pick_fallback_chart(df)
                if fig is not None:
                    plot_json = fig.to_json()

            return DatabaseNLQResponse(
                answer=self._build_answer(df),
                sql=sql,
                reasoning=reasoning,
                plot_json=plot_json,
                tables_used=tables_used,
                execution_success=True,
            )
        except Exception as e:
            logger.error(f"Database NLQ failed: {safe_log_value(e)}")
            return DatabaseNLQResponse(
                answer=f"Could not answer that: {e}",
                sql=sql,
                tables_used=tables_used,
                error=str(e),
            )
