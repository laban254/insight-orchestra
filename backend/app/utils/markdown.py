"""Small helpers for turning query results into chat-friendly markdown."""

from __future__ import annotations

import pandas as pd


def df_to_markdown_table(df: pd.DataFrame, max_rows: int = 12) -> str:
    """A GitHub-flavoured markdown table. Numbers get thousands separators;
    floats round to 2dp. The chat renderer styles these properly, unlike a
    flat ``DataFrame.to_string()`` dump."""
    show = df.head(max_rows).copy()
    for col in show.columns:
        s = show[col]
        if pd.api.types.is_float_dtype(s):
            show[col] = s.map(lambda v: "" if pd.isna(v) else f"{v:,.2f}")
        elif pd.api.types.is_integer_dtype(s):
            show[col] = s.map(lambda v: "" if pd.isna(v) else f"{v:,}")
        else:
            show[col] = s.astype(str)
    cols = [str(c).replace("|", "\\|") for c in show.columns]
    rows = [
        "| " + " | ".join(str(x).replace("|", "\\|") for x in row) + " |"
        for row in show.itertuples(index=False, name=None)
    ]
    return "\n".join(
        ["| " + " | ".join(cols) + " |", "| " + " | ".join(["---"] * len(cols)) + " |", *rows]
    )
