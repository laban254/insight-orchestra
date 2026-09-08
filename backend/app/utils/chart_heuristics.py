"""Deterministic, non-LLM chart-type selection for a DataFrame.

Used wherever a caller needs *some* reasonable visualization of a result
without waiting on (or paying for) another LLM call — the NLQ agent's plot
fallback and the database NLQ agent share this rather than each keeping
their own copy of the same category/numeric-column heuristic.
"""

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


def pick_fallback_chart(df: pd.DataFrame) -> go.Figure | None:
    """Bar for one categorical + one numeric column, scatter for two numeric
    columns, histogram for one — in that preference order. None if nothing
    in `df` fits any of those shapes."""
    if df is None or df.empty:
        return None

    numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
    categorical_cols = df.select_dtypes(include=["object", "string", "category"]).columns.tolist()

    if categorical_cols and numeric_cols:
        return px.bar(df, x=categorical_cols[0], y=numeric_cols[0])
    if len(numeric_cols) >= 2:
        return px.scatter(df, x=numeric_cols[0], y=numeric_cols[1])
    if len(numeric_cols) == 1:
        return px.histogram(df, x=numeric_cols[0])
    return None
