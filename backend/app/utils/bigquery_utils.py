from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel
from google.cloud import bigquery
import pandas as pd
import os
import json
import re

class BigQueryRequest(BaseModel):
    credentials_json: str  # JSON string of service account credentials
    query: str

# Utility to run a BigQuery query and return a DataFrame
def run_bigquery_query(credentials_json: str, query: str) -> pd.DataFrame:
    # Validate credentials JSON
    if not credentials_json or not credentials_json.strip():
        raise ValueError("Credentials JSON is required")
    
    # Validate it's actually JSON
    try:
        credentials_dict = json.loads(credentials_json)
    except json.JSONDecodeError:
        raise ValueError("Invalid JSON format for credentials")
    
    # Validate required fields for service account
    required_fields = ["type", "project_id"]
    missing_fields = [f for f in required_fields if f not in credentials_dict]
    if missing_fields:
        raise ValueError(f"Missing required credential fields: {', '.join(missing_fields)}")
    
    # Validate credential type
    if credentials_dict.get("type") != "service_account":
        raise ValueError("Credentials must be a service account JSON")
    
    # Validate query is a SELECT (read-only)
    query_upper = query.strip().upper()
    if not query_upper.startswith("SELECT"):
        raise ValueError("Only SELECT queries are permitted")
    
    try:
        client = bigquery.Client.from_service_account_info(credentials_dict)
        job = client.query(query)
        df = job.result().to_dataframe()
        return df
    except Exception as e:
        raise RuntimeError(f"BigQuery error: {str(e)}")
