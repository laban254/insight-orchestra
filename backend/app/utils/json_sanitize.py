"""
Recursively replace NaN/Infinity floats with None so a payload is valid JSON.

FastAPI's default JSONResponse renders with `allow_nan=False` (Starlette),
so any NaN or +/-Infinity float reaching a response body raises a raw 500
instead of returning a usable error. These values show up routinely in a
pandas-heavy pipeline — an all-null numeric column, a standard deviation
over a single value, a correlation with zero variance — so response payloads
built from plain dicts/lists (rather than `df.to_json()`, which already
handles this) need to be sanitized before being returned.
"""

import math
from typing import Any

import pandas as pd


def sanitize_json(obj: Any) -> Any:
    # pandas' NaT is a datetime subclass, so FastAPI's encoder happily turns
    # it into the literal string "NaT" and it renders as text in the preview
    # table. It means "missing", so it becomes null like any other gap.
    # Compared by identity: NaT is a singleton, and `!=` on an array-like
    # would raise rather than answer.
    if obj is pd.NaT:
        return None
    if isinstance(obj, float):
        return None if (math.isnan(obj) or math.isinf(obj)) else obj
    if isinstance(obj, dict):
        return {k: sanitize_json(v) for k, v in obj.items()}
    if isinstance(obj, list | tuple):
        return [sanitize_json(v) for v in obj]
    return obj
