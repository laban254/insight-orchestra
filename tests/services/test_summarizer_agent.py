"""
Unit tests for InsightSummarizerAgent — narrative streaming, the separate
suggested-questions call, and the heuristic fallback.
"""

from unittest.mock import MagicMock

import pytest
from app.services.summarizer_agent import InsightSummarizerAgent


@pytest.fixture
def workflow_results():
    return {
        "cleaner": {
            "report": {"final_shape": [100, 5], "duplicates_removed": 3, "total_missing": 2}
        },
        "hypothesis": {
            "hypotheses": ["Sales rise in Q4", "Region North outperforms"],
            "summary": {"numeric_columns": ["revenue"], "categorical_columns": ["region"]},
        },
        "debate": {
            "summary": {
                "consensus": {
                    "hypothesis": "Sales rise in Q4",
                    "confidence": 0.8,
                    "business_value": 0.7,
                }
            }
        },
        "viz": {"chart_info": {"plots": [{"title": "Revenue over time"}]}},
    }


class TestFallbackSummary:
    def test_no_llm_uses_fallback(self, workflow_results):
        agent = InsightSummarizerAgent(llm_service=None)
        agent.llm = None  # force fallback regardless of ambient API keys
        result = agent.run(workflow_results)
        assert result["llm_used"] is False
        assert "100" in result["narrative"]
        assert len(result["suggested_questions"]) <= 5

    def test_fallback_mentions_duplicates_when_present(self, workflow_results):
        agent = InsightSummarizerAgent(llm_service=None)
        agent.llm = None
        result = agent.run(workflow_results)
        assert "3 duplicate" in result["narrative"]


class TestStreamingNarrative:
    def _mock_llm(self, chunks=("The ", "data ", "shows growth.")):
        llm = MagicMock()
        llm.stream_complete.return_value = iter(chunks)
        llm.complete_json.return_value = {"suggested_questions": ["What drove Q4?"]}
        return llm

    def test_on_chunk_receives_growing_accumulated_text(self, workflow_results):
        llm = self._mock_llm()
        agent = InsightSummarizerAgent(llm_service=llm)
        seen = []
        result = agent.run(workflow_results, on_chunk=seen.append)

        assert seen == ["The ", "The data ", "The data shows growth."]
        assert result["narrative"] == "The data shows growth."
        assert result["llm_used"] is True

    def test_works_without_an_on_chunk_callback(self, workflow_results):
        llm = self._mock_llm()
        agent = InsightSummarizerAgent(llm_service=llm)
        result = agent.run(workflow_results)  # no on_chunk
        assert result["narrative"] == "The data shows growth."

    def test_suggested_questions_come_from_a_separate_call(self, workflow_results):
        llm = self._mock_llm()
        agent = InsightSummarizerAgent(llm_service=llm)
        result = agent.run(workflow_results)

        assert result["suggested_questions"] == ["What drove Q4?"]
        llm.complete_json.assert_called_once()
        # The separate call is seeded with the finished narrative, not run
        # concurrently with the stream.
        args, _ = llm.complete_json.call_args
        assert "The data shows growth." in args[1]

    def test_questions_call_failing_does_not_lose_the_narrative(self, workflow_results):
        llm = self._mock_llm()
        llm.complete_json.side_effect = RuntimeError("boom")
        agent = InsightSummarizerAgent(llm_service=llm)
        result = agent.run(workflow_results)

        assert result["narrative"] == "The data shows growth."
        assert result["llm_used"] is True
        assert result["suggested_questions"] == []

    def test_streaming_failure_falls_back_to_heuristic(self, workflow_results):
        llm = MagicMock()
        llm.stream_complete.side_effect = RuntimeError("connection refused")
        agent = InsightSummarizerAgent(llm_service=llm)
        result = agent.run(workflow_results)

        assert result["llm_used"] is False
        assert "100" in result["narrative"]

    def test_empty_narrative_falls_back_to_heuristic(self, workflow_results):
        llm = self._mock_llm(chunks=("   ", "\n"))  # strips to empty
        agent = InsightSummarizerAgent(llm_service=llm)
        result = agent.run(workflow_results)
        assert result["llm_used"] is False
