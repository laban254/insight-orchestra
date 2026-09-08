"""
Smoke tests: /process and /nlq must handle every demo dataset's real shape
without crashing, independent of whether an LLM is actually reachable.

The LLM call boundary is patched to fail fast (simulating "no provider
configured") rather than mocked to return realistic completions — each
agent's LLM-success path is already covered individually in
test_adk_agents.py / test_nlq_agent.py with proper mocks. What this file
adds is coverage for real, dataset-shape-dependent code (cleaning, stats,
chart-selection heuristics) that a synthetic small DataFrame in those other
tests wouldn't exercise — e.g. a demo dataset's specific column types,
nulls, or cardinality tripping up something downstream.
"""

from unittest.mock import patch

import pytest
from app.api import endpoints
from app.api.endpoints import NLQRequest, ProcessRequest
from app.services.dataset_registry import get_dataset_registry
from app.utils.demo_data import DEMO_DATASETS, get_demo_dataset


@pytest.fixture
def demo_dataset_id(request, tmp_path):
    """Register a real demo dataset's CSV, the same way /demo/load does."""
    df, metadata = get_demo_dataset(request.param)
    path = tmp_path / f"{request.param}.csv"
    df.to_csv(path, index=False)
    registry = get_dataset_registry()
    dataset_id = registry.register(str(path), name=metadata["name"], source=f"demo:{request.param}")
    yield dataset_id
    registry.delete(dataset_id, remove_file=False)


@pytest.mark.parametrize("demo_dataset_id", list(DEMO_DATASETS.keys()), indirect=True)
class TestDemoDatasetSmoke:
    @pytest.mark.asyncio
    async def test_process_succeeds_without_llm(self, demo_dataset_id):
        with patch(
            "app.services.llm_service.LLMService.complete_json",
            side_effect=RuntimeError("no LLM configured in test env"),
        ):
            response = await endpoints.process_data(ProcessRequest(dataset_id=demo_dataset_id))

        assert response["degraded"] is True
        assert response["preview"]["columns"]
        assert response["viz"]["chart_info"] is not None
        assert isinstance(response["hypothesis"]["hypotheses"], list)

    @pytest.mark.asyncio
    async def test_nlq_succeeds_without_llm(self, demo_dataset_id):
        with patch(
            "app.services.llm_service.LLMService.complete_json",
            side_effect=RuntimeError("no LLM configured in test env"),
        ):
            response = await endpoints.natural_language_query(
                NLQRequest(dataset_id=demo_dataset_id, question="What stands out in this data?")
            )

        # The LLM is unreachable, so this is expected to fail *gracefully* —
        # a normal returned dict with an actionable message, not a crash.
        assert response["execution_success"] is False
        assert response["answer"]
