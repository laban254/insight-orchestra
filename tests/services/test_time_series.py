"""Time-series behaviour across the pipeline.

Before dates were parsed on read, a date column arrived as text and every
agent treated it as categorical: the Janitor mode-imputed it, the Hypothesis
Bot proposed "'2024-03-02' leads 'date' with the highest average revenue",
and Viz Whiz drew a bar chart of 15 arbitrary days. These tests pin the
corrected behaviour.
"""

import json

import numpy as np
import pandas as pd
import pytest

from app.services.adk_agents import DataJanitorAgent, HypothesisBotAgent, VizWhizAgent
from app.utils.json_sanitize import sanitize_json


@pytest.fixture
def trending_frame():
    n = 365
    rng = np.random.RandomState(0)
    return pd.DataFrame(
        {
            "date": pd.date_range("2024-01-01", periods=n, freq="D"),
            "revenue": np.linspace(100, 260, n) + rng.normal(0, 5, n),
            "region": rng.choice(["North", "South"], n),
        }
    )


@pytest.fixture
def flat_frame():
    n = 60
    return pd.DataFrame(
        {
            "day": pd.date_range("2024-01-01", periods=n, freq="D"),
            "value": np.full(n, 50.0),
        }
    )


# --- Data Janitor -------------------------------------------------------


def test_janitor_preserves_datetime_dtype(trending_frame):
    """Filling a datetime column with the 'MISSING' string would upcast it
    to object and undo type detection for everything downstream."""
    frame = trending_frame.copy()
    frame.loc[5:9, "date"] = pd.NaT

    result = DataJanitorAgent(name="j").run(frame.to_dict(orient="records"))
    cleaned = pd.DataFrame(result["cleaned_data"])

    assert pd.api.types.is_datetime64_any_dtype(cleaned["date"])
    assert cleaned["date"].isna().sum() == 0


def test_janitor_leaves_all_null_datetime_as_nat():
    """No median exists, and inventing a date would be worse than a gap."""
    frame = pd.DataFrame({"when": [pd.NaT, pd.NaT], "v": [1, 2]})
    result = DataJanitorAgent(name="j").run(frame.to_dict(orient="records"))
    cleaned = pd.DataFrame(result["cleaned_data"])
    assert cleaned["when"].isna().all()


def test_nat_serializes_as_null_not_the_string_nat():
    """FastAPI's encoder turns NaT into the literal string 'NaT', which
    renders as text in the preview table."""
    assert sanitize_json({"when": pd.NaT}) == {"when": None}
    assert sanitize_json([pd.NaT, 1.0]) == [None, 1.0]


# --- Hypothesis Bot -----------------------------------------------------


def test_trend_hypothesis_is_generated(trending_frame):
    bot = HypothesisBotAgent(name="h", llm_service=None)
    hypotheses = bot._generate_fallback_hypotheses(trending_frame)["hypotheses"]

    trend = [h for h in hypotheses if "rose" in h or "fell" in h]
    assert trend, f"expected a trend hypothesis, got {hypotheses}"
    assert "revenue" in trend[0]
    # Trends lead: they answer the question a reader of time-series data has.
    assert hypotheses[0] == trend[0]


def test_no_trend_claimed_on_flat_data(flat_frame):
    bot = HypothesisBotAgent(name="h", llm_service=None)
    hypotheses = bot._generate_fallback_hypotheses(flat_frame)["hypotheses"]
    assert not [h for h in hypotheses if "rose" in h or "fell" in h]


def test_dates_are_not_treated_as_a_category(trending_frame):
    """The old failure mode: "'2024-03-02' leads 'date' with the highest
    average revenue" — a category claim about a timestamp."""
    bot = HypothesisBotAgent(name="h", llm_service=None)
    summary = bot._generate_fallback_hypotheses(trending_frame)["summary"]
    assert "date" not in summary["categorical_columns"]


def test_stats_summary_reports_time_coverage(trending_frame):
    summary = HypothesisBotAgent._build_stats_summary(trending_frame)
    assert "Time coverage:" in summary
    assert "2024-01-01 to 2024-12-30" in summary
    assert "364 days" in summary


# --- Viz Whiz -----------------------------------------------------------


def _plots(frame, consensus="revenue changes over date", hypotheses=()):
    agent = VizWhizAgent(name="v", llm_service=None)
    result = agent.run(
        frame.to_dict(orient="records"),
        {"hypothesis": consensus},
        hypotheses=list(hypotheses),
    )
    return result["chart_info"]["plots"]


def test_date_plus_measure_draws_a_line_chart(trending_frame):
    plots = _plots(trending_frame)
    assert plots, "a date/measure pair must produce a chart"
    assert plots[0]["type"] == "line"
    assert plots[0]["title"] == "revenue over time"


def test_line_chart_is_aggregated_not_one_point_per_row(trending_frame):
    """A year of daily rows renders as noise; buckets keep it readable."""
    figure = json.loads(_plots(trending_frame)[0]["plotly_json"])
    points = len(figure["data"][0]["x"])
    assert 2 <= points <= 60, f"expected aggregated buckets, got {points} points"


def test_lone_date_column_plots_volume_over_time():
    frame = pd.DataFrame({"signup": pd.date_range("2024-01-01", periods=100, freq="D")})
    plots = _plots(frame, consensus="signup activity")
    assert plots and plots[0]["type"] == "line"
    assert "Records over time" in plots[0]["title"]


def test_time_series_wins_the_structured_fallback(trending_frame):
    """With no usable hypothesis text, a dataset with a time axis should
    still lead with the trend rather than a category breakdown."""
    plots = _plots(trending_frame, consensus="")
    assert plots[0]["type"] == "line"


def test_short_series_does_not_produce_a_one_point_chart():
    frame = pd.DataFrame({"date": pd.to_datetime(["2024-01-01"]), "v": [1.0]})
    plots = _plots(frame, consensus="v over date")
    assert all(p["type"] != "line" for p in plots)
