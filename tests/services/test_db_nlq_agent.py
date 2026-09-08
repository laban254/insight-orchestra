"""
Unit tests for the multi-table database NL-to-SQL agent.
"""

from unittest.mock import MagicMock

import pandas as pd
import pytest
from app.services.db_nlq_agent import (
    SHORTLIST_THRESHOLD,
    DatabaseNLQAgent,
    shortlist_tables,
)


def _schema(n_tables: int) -> dict:
    return {
        f"table_{i}": [{"name": "id", "type": "integer"}, {"name": "value", "type": "text"}]
        for i in range(n_tables)
    }


class TestShortlistTables:
    def test_small_schema_is_returned_unchanged_without_calling_the_llm(self):
        schema = _schema(5)
        llm = MagicMock()
        result = shortlist_tables(schema, "any question", llm)
        assert result == schema
        llm.complete_json.assert_not_called()

    def test_large_schema_is_narrowed_to_the_llm_picked_tables(self):
        schema = _schema(SHORTLIST_THRESHOLD + 1)
        llm = MagicMock()
        llm.complete_json.return_value = {"tables": ["table_0", "table_2"]}

        result = shortlist_tables(schema, "some question", llm)

        assert set(result.keys()) == {"table_0", "table_2"}
        llm.complete_json.assert_called_once()

    def test_large_schema_falls_back_to_full_schema_on_llm_failure(self):
        schema = _schema(SHORTLIST_THRESHOLD + 1)
        llm = MagicMock()
        llm.complete_json.side_effect = RuntimeError("boom")

        result = shortlist_tables(schema, "some question", llm)
        assert result == schema

    def test_large_schema_falls_back_when_llm_picks_nothing_real(self):
        schema = _schema(SHORTLIST_THRESHOLD + 1)
        llm = MagicMock()
        llm.complete_json.return_value = {"tables": ["not_a_real_table"]}

        result = shortlist_tables(schema, "some question", llm)
        assert result == schema


class TestDatabaseNLQAgentRun:
    @pytest.fixture
    def connector(self):
        c = MagicMock()
        c.execute_query.return_value = pd.DataFrame({"id": [1, 2], "name": ["Alice", "Bob"]})
        return c

    @pytest.fixture
    def schema(self):
        return {"users": [{"name": "id", "type": "integer"}, {"name": "name", "type": "text"}]}

    def test_successful_query_returns_sql_and_answer(self, connector, schema):
        llm = MagicMock()
        llm.complete_json.return_value = {
            "reasoning": "look up all users",
            "sql": "SELECT * FROM users",
            "needs_clarification": False,
        }
        agent = DatabaseNLQAgent(llm_service=llm)

        response = agent.run(connector, schema, "who are the users?")

        assert response.execution_success is True
        assert response.sql == "SELECT * FROM users"
        assert "2 row(s)" in response.answer
        assert response.tables_used == ["users"]
        connector.execute_query.assert_called_once_with("SELECT * FROM users")

    def test_trailing_semicolon_is_stripped_before_execution(self, connector, schema):
        llm = MagicMock()
        llm.complete_json.return_value = {
            "sql": "SELECT * FROM users;",
            "needs_clarification": False,
        }
        agent = DatabaseNLQAgent(llm_service=llm)

        agent.run(connector, schema, "who are the users?")
        connector.execute_query.assert_called_once_with("SELECT * FROM users")

    def test_needs_clarification_short_circuits_before_execution(self, connector, schema):
        llm = MagicMock()
        llm.complete_json.return_value = {
            "needs_clarification": True,
            "clarification_question": "Which time period?",
        }
        agent = DatabaseNLQAgent(llm_service=llm)

        response = agent.run(connector, schema, "how much revenue?")

        assert response.needs_clarification is True
        assert response.answer == "Which time period?"
        connector.execute_query.assert_not_called()

    def test_disallowed_keyword_in_generated_sql_is_rejected(self, connector, schema):
        llm = MagicMock()
        llm.complete_json.return_value = {
            "sql": "DELETE FROM users",
            "needs_clarification": False,
        }
        agent = DatabaseNLQAgent(llm_service=llm)

        response = agent.run(connector, schema, "delete inactive users")

        assert response.execution_success is False
        assert response.error is not None
        connector.execute_query.assert_not_called()

    def test_multiple_statements_are_rejected(self, connector, schema):
        llm = MagicMock()
        llm.complete_json.return_value = {
            "sql": "SELECT 1; SELECT 2",
            "needs_clarification": False,
        }
        agent = DatabaseNLQAgent(llm_service=llm)

        response = agent.run(connector, schema, "q")
        assert response.execution_success is False
        connector.execute_query.assert_not_called()

    def test_empty_sql_from_model_is_a_clean_failure(self, connector, schema):
        llm = MagicMock()
        llm.complete_json.return_value = {"sql": "", "needs_clarification": False}
        agent = DatabaseNLQAgent(llm_service=llm)

        response = agent.run(connector, schema, "q")
        assert response.execution_success is False
        assert response.error is not None

    def test_query_execution_failure_is_caught_cleanly(self, connector, schema):
        llm = MagicMock()
        llm.complete_json.return_value = {
            "sql": "SELECT * FROM users",
            "needs_clarification": False,
        }
        connector.execute_query.side_effect = RuntimeError("relation does not exist")
        agent = DatabaseNLQAgent(llm_service=llm)

        response = agent.run(connector, schema, "q")
        assert response.execution_success is False
        assert "relation does not exist" in response.error

    def test_plot_question_with_chartable_result_gets_a_plot(self, connector, schema):
        llm = MagicMock()
        llm.complete_json.return_value = {
            "sql": "SELECT name, id FROM users",
            "needs_clarification": False,
        }
        agent = DatabaseNLQAgent(llm_service=llm)

        response = agent.run(connector, schema, "show me a bar chart of users")
        assert response.plot_json is not None

    def test_non_plot_question_has_no_plot(self, connector, schema):
        llm = MagicMock()
        llm.complete_json.return_value = {
            "sql": "SELECT * FROM users",
            "needs_clarification": False,
        }
        agent = DatabaseNLQAgent(llm_service=llm)

        response = agent.run(connector, schema, "who are the users?")
        assert response.plot_json is None

    def test_no_llm_configured_returns_a_clean_error_not_a_crash(self, connector, schema):
        agent = DatabaseNLQAgent(llm_service=None)
        agent.llm = None  # force regardless of ambient env

        response = agent.run(connector, schema, "who are the users?")

        assert response.execution_success is False
        assert response.error == "no_llm_configured"
        connector.execute_query.assert_not_called()


class TestSafetyCheck:
    def test_select_is_allowed(self):
        DatabaseNLQAgent._check_safety("SELECT * FROM users")  # must not raise

    @pytest.mark.parametrize(
        "sql",
        [
            "DROP TABLE users",
            "DELETE FROM users",
            "INSERT INTO users VALUES (1)",
            "UPDATE users SET name = 'x'",
            "ALTER TABLE users ADD COLUMN x int",
            "TRUNCATE users",
            "GRANT ALL ON users TO public",
        ],
    )
    def test_blocked_keywords_are_rejected(self, sql):
        with pytest.raises(ValueError):
            DatabaseNLQAgent._check_safety(sql)
