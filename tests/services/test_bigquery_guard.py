"""BigQuery is an optional, experimental dependency.

It is advertised nowhere in the UI and `google-cloud-bigquery` is not in
requirements.txt, so the endpoint must say so clearly rather than surfacing
an ImportError as a generic 500.
"""

import builtins

import pytest
from app.utils.bigquery_utils import BigQueryUnavailableError, run_bigquery_query

CREDENTIALS = '{"type": "service_account", "project_id": "p"}'


def test_missing_dependency_raises_a_clear_error(monkeypatch):
    real_import = builtins.__import__

    def blocked(name, *args, **kwargs):
        if name.startswith("google.cloud"):
            raise ImportError("No module named 'google.cloud.bigquery'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", blocked)

    with pytest.raises(BigQueryUnavailableError, match="pip install google-cloud-bigquery"):
        run_bigquery_query(CREDENTIALS, "SELECT 1")


def test_query_validation_runs_before_the_dependency_check():
    """A bad query should be reported as a bad query regardless."""
    with pytest.raises(ValueError, match="Only SELECT"):
        run_bigquery_query(CREDENTIALS, "DROP TABLE t")


def test_credentials_are_validated_first():
    with pytest.raises(ValueError, match="service account"):
        run_bigquery_query('{"type": "user", "project_id": "p"}', "SELECT 1")
