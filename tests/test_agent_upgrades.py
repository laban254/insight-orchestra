
import unittest
from unittest.mock import MagicMock, patch
import sys
import os

# 1. Mock all external dependencies BEFORE anything else
import types

# google.adk
mock_adk = types.ModuleType("google.adk")
class MockAgent:
    def __init__(self, name=None):
        self.name = name
mock_adk.Agent = MockAgent
sys.modules['google.adk'] = mock_adk

# pandas
mock_pd = MagicMock()
sys.modules['pandas'] = mock_pd

# openai
sys.modules['openai'] = MagicMock()

# requests
sys.modules['requests'] = MagicMock()

# RestrictedPython
sys.modules['RestrictedPython'] = MagicMock()
sys.modules['RestrictedPython.Guards'] = MagicMock()

import json

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

# 2. Now import the agents
from app.services.adk_agents import HypothesisBotAgent, DebateManagerAgent
from app.services.llm_service import LLMService

class TestAgentUpgrades(unittest.TestCase):
    def setUp(self):
        self.mock_llm = MagicMock(spec=LLMService)
        self.hypothesis_agent = HypothesisBotAgent(name="TestHypothesis", llm_service=self.mock_llm)
        self.debate_agent = DebateManagerAgent(name="TestDebate", llm_service=self.mock_llm)

        self.sample_data = [
            {"Name": "Alice", "Age": 25, "Salary": 75000},
            {"Name": "Bob", "Age": 30, "Salary": 65000}
        ]

    def test_hypothesis_bot_llm_integration(self):
        # Mock LLM response
        self.mock_llm.complete_json.return_value = {
            "hypotheses": ["Age correlates with Salary"],
            "reasoning": "Standard trend analysis"
        }

        # Mock schema response to avoid index errors with MagicMock
        with patch('app.services.llm_service.DataFrameSchema.from_dataframe') as mock_schema:
            mock_schema.return_value = {"shape": [2, 3], "columns": [], "null_counts": {}}
            with patch('app.services.llm_service.DataFrameSchema.to_prompt') as mock_prompt:
                mock_prompt.return_value = "Mock Prompt"

                result = self.hypothesis_agent.run(self.sample_data)

                self.assertIn("hypotheses", result)
                self.assertEqual(len(result["hypotheses"]), 1)
                self.assertEqual(result["hypotheses"][0], "Age correlates with Salary")
                self.assertEqual(result["summary"]["num_hypotheses"], 1)

    def test_debate_manager_llm_integration(self):
        # Mock LLM response
        self.mock_llm.complete_json.return_value = {
            "scored_hypotheses": [
                {
                    "hypothesis": "Age correlates with Salary",
                    "confidence": 0.9,
                    "business_value": 0.8,
                    "statistical_argument": "Strong correlation in subsets",
                    "business_argument": "High impact for retention"
                }
            ]
        }

        result = self.debate_agent.run(["Age correlates with Salary"])

        self.assertIn("scored_hypotheses", result)
        scored = result["scored_hypotheses"][0]
        self.assertEqual(scored["confidence"], 0.9)
        self.assertEqual(result["summary"]["consensus"]["hypothesis"], "Age correlates with Salary")
        self.assertIn("statistical", result["summary"]["arguments"][0])

if __name__ == "__main__":
    unittest.main()
