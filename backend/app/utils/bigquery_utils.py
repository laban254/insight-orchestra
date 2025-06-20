from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel
from google.cloud import bigquery
import pandas as pd
import os
import json

class BigQueryRequest(BaseModel):
    credentials_json: str  # JSON string of service account credentials
    query: str

# Utility to run a BigQuery query and return a DataFrame
def run_bigquery_query(credentials_json: str, query: str) -> pd.DataFrame:
    try:
        credentials_dict = json.loads(credentials_json)
        client = bigquery.Client.from_service_account_info(credentials_dict)
        job = client.query(query)
        df = job.result().to_dataframe()
        return df
    except Exception as e:
        raise RuntimeError(f"BigQuery error: {e}")
