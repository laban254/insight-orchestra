import json
import re

import pandas as pd
from google.cloud import bigquery
from pydantic import BaseModel


class BigQueryRequest(BaseModel):
    credentials_json: str  # JSON string of service account credentials
    query: str


def _strip_sql_comments(query: str) -> str:
    """Remove -- line comments and /* block comments */ from SQL."""
    query = re.sub(r"--[^\n]*", " ", query)
    query = re.sub(r"/\*.*?\*/", " ", query, flags=re.DOTALL)
    return query


def _validate_select_only(query: str) -> None:
    """
    Reject anything that isn't a single bare SELECT statement.

    Strips comments first, then splits on ; to catch multi-statement
    injections like 'SELECT 1; DROP TABLE foo'.
    """
    cleaned = _strip_sql_comments(query).strip()

    # Split on semicolons, ignore trailing empty fragments
    statements = [s.strip() for s in cleaned.split(";") if s.strip()]
    if len(statements) != 1:
        raise ValueError(
            f"Only a single SELECT statement is permitted; got {len(statements)} statements."
        )

    stmt = statements[0].upper()
    if not stmt.startswith("SELECT"):
        raise ValueError("Only SELECT queries are permitted.")

    # Block DDL/DML keywords anywhere in the statement
    dangerous = re.compile(
        r"\b(INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|TRUNCATE|MERGE|CALL|EXECUTE|GRANT|REVOKE)\b",
        re.IGNORECASE,
    )
    match = dangerous.search(statements[0])
    if match:
        raise ValueError(f"Forbidden keyword '{match.group()}' found in query.")


# Utility to run a BigQuery query and return a DataFrame
def run_bigquery_query(credentials_json: str, query: str) -> pd.DataFrame:
    # Validate credentials JSON
    if not credentials_json or not credentials_json.strip():
        raise ValueError("Credentials JSON is required")

    try:
        credentials_dict = json.loads(credentials_json)
    except json.JSONDecodeError as e:
        raise ValueError("Invalid JSON format for credentials") from e

    required_fields = ["type", "project_id"]
    missing_fields = [f for f in required_fields if f not in credentials_dict]
    if missing_fields:
        raise ValueError(f"Missing required credential fields: {', '.join(missing_fields)}")

    if credentials_dict.get("type") != "service_account":
        raise ValueError("Credentials must be a service account JSON")

    # Validate query: single SELECT only, no DDL/DML
    _validate_select_only(query)

    try:
        client = bigquery.Client.from_service_account_info(credentials_dict)
        job = client.query(query)
        df = job.result().to_dataframe()
        return df
    except Exception as e:
        raise RuntimeError(f"BigQuery error: {str(e)}") from e
