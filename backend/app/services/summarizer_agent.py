from typing import Optional, List, Dict, Any
from app.services.llm_service import LLMService
import logging

logger = logging.getLogger(__name__)


class InsightSummarizerAgent:
    def __init__(self, llm_service: Optional[LLMService] = None):
        self.llm = llm_service
        if self.llm is None:
            try:
                self.llm = LLMService()
            except Exception:
                self.llm = None

    def _fallback_summary(self, workflow_results: Dict[str, Any]) -> Dict[str, Any]:
        """Template-based summary when LLM is unavailable."""
        cleaner   = workflow_results.get("cleaner", {})
        hypothesis = workflow_results.get("hypothesis", {})
        debate    = workflow_results.get("debate", {})
        viz       = workflow_results.get("viz", {})

        parts = []
        report = cleaner.get("report", {})
        rows = report.get("final_shape", [0])[0]
        parts.append(f"Analysed {rows:,} rows.")
        if report.get("duplicates_removed", 0):
            parts.append(f"Removed {report['duplicates_removed']} duplicate rows.")

        hyps = hypothesis.get("hypotheses", [])
        if hyps:
            parts.append(f"Found {len(hyps)} insights in your data.")

        consensus = debate.get("summary", {}).get("consensus")
        if consensus:
            parts.append(f"Top insight: {consensus.get('hypothesis', '')}")

        plots = viz.get("chart_info", {}).get("plots", [])
        if plots:
            parts.append(f"Generated {len(plots)} chart(s).")

        narrative = " ".join(parts) or "Analysis complete."

        # Generic suggested questions using actual column names from the summary
        num_cols = hypothesis.get("summary", {}).get("numeric_columns", [])
        cat_cols = hypothesis.get("summary", {}).get("categorical_columns", [])
        questions: List[str] = []
        if cat_cols and num_cols:
            questions.append(f"Show me a bar chart of {num_cols[0]} by {cat_cols[0]}")
            questions.append(f"Which {cat_cols[0]} has the highest {num_cols[0]}?")
        if len(num_cols) >= 2:
            questions.append(f"Is there a correlation between {num_cols[0]} and {num_cols[1]}?")
        if num_cols:
            questions.append(f"What is the distribution of {num_cols[0]}?")
        questions.append("What are the key trends in this dataset?")

        return {"narrative": narrative, "suggested_questions": questions[:5]}

    def run(self, workflow_results: Dict[str, Any]) -> Dict[str, Any]:
        cleaner    = workflow_results.get("cleaner", {})
        hypothesis = workflow_results.get("hypothesis", {})
        debate     = workflow_results.get("debate", {})
        viz        = workflow_results.get("viz", {})
        stats      = workflow_results.get("stats", "")

        # Build structured context for the LLM
        report    = cleaner.get("report", {})
        rows      = report.get("final_shape", [0])[0]
        hyps      = hypothesis.get("hypotheses", [])
        consensus = debate.get("summary", {}).get("consensus") or {}
        plots     = viz.get("chart_info", {}).get("plots", [])
        num_cols  = hypothesis.get("summary", {}).get("numeric_columns", [])
        cat_cols  = hypothesis.get("summary", {}).get("categorical_columns", [])

        if self.llm is None:
            return self._fallback_summary(workflow_results)

        context = (
            f"Dataset: {rows:,} rows\n"
            f"Duplicates removed: {report.get('duplicates_removed', 0)}\n"
            f"Missing values handled: {report.get('total_missing', 0)}\n"
            f"Charts generated: {len(plots)}\n\n"
            f"Top insight (consensus):\n{consensus.get('hypothesis', 'None')}\n"
            f"Confidence: {consensus.get('confidence', 0):.0%}, "
            f"Business value: {consensus.get('business_value', 0):.0%}\n\n"
            f"All insights found:\n" + "\n".join(f"- {h}" for h in hyps[:6]) + "\n\n"
            f"Numeric columns: {num_cols}\n"
            f"Categorical columns: {cat_cols}"
        )

        system = """You are a data analyst presenting findings to a business user.
Write a concise, friendly narrative (3-5 sentences) summarising the key findings.
Then list 4-5 specific follow-up questions the user should ask to explore further.
Use plain English — no jargon. Reference actual column names and numbers where possible.

OUTPUT (JSON only):
{
  "narrative": "3-5 sentence summary",
  "suggested_questions": ["question 1", "question 2", "question 3", "question 4", "question 5"]
}"""

        try:
            result = self.llm.complete_json(system, context)
            narrative  = result.get("narrative", "")
            questions  = result.get("suggested_questions", [])
            if not narrative:
                raise ValueError("empty narrative")
            return {
                "narrative": narrative,
                "suggested_questions": questions[:5],
            }
        except Exception as e:
            logger.warning(f"LLM summarizer failed: {e}, using fallback")
            return self._fallback_summary(workflow_results)
