"""
Unit tests for the shared deterministic chart-type heuristic.
"""

import pandas as pd
from app.utils.chart_heuristics import pick_fallback_chart


class TestPickFallbackChart:
    def test_none_for_empty_dataframe(self):
        assert pick_fallback_chart(pd.DataFrame()) is None

    def test_none_for_none_input(self):
        assert pick_fallback_chart(None) is None

    def test_categorical_plus_numeric_gives_a_bar_chart(self):
        df = pd.DataFrame({"region": ["North", "South"], "revenue": [100, 200]})
        fig = pick_fallback_chart(df)
        assert fig is not None
        assert fig.data[0].type == "bar"

    def test_two_numeric_columns_gives_a_scatter_chart(self):
        df = pd.DataFrame({"age": [25, 30, 35], "salary": [50000, 60000, 70000]})
        fig = pick_fallback_chart(df)
        assert fig is not None
        assert fig.data[0].type == "scatter"

    def test_one_numeric_column_gives_a_histogram(self):
        df = pd.DataFrame({"age": [25, 30, 35, 40]})
        fig = pick_fallback_chart(df)
        assert fig is not None
        assert fig.data[0].type == "histogram"

    def test_only_categorical_columns_gives_no_chart(self):
        df = pd.DataFrame({"name": ["Alice", "Bob"], "city": ["NYC", "LA"]})
        assert pick_fallback_chart(df) is None

    def test_categorical_plus_numeric_is_preferred_over_scatter(self):
        df = pd.DataFrame({"region": ["N", "S"], "revenue": [1, 2], "cost": [3, 4]})
        fig = pick_fallback_chart(df)
        assert fig.data[0].type == "bar"
