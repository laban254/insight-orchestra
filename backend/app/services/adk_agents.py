import importlib.util
import json
import logging
import re
from typing import Any

import pandas as pd
from google.adk import Agent

from app.services.llm_service import DataFrameSchema, LLMService
from app.utils.log_utils import safe_log_value

logger = logging.getLogger(__name__)


def _as_frame(data: Any) -> pd.DataFrame:
    """Accept either a DataFrame or the legacy list-of-dicts.

    The pipeline passes DataFrames between agents — converting to records
    and back cost ~7x the dataset's memory and several seconds per step on
    a mid-sized file. The list form is still accepted so callers (and
    tests) that hand over records keep working.
    """
    return data if isinstance(data, pd.DataFrame) else pd.DataFrame(data)


# plotly express imports statsmodels itself when trendline="ols" is requested;
# we only need to know whether it's installed to decide whether to ask for one.
_HAS_STATSMODELS = importlib.util.find_spec("statsmodels") is not None

# Grouping a metric by a near-unique column ("average salary by employee_name") produces
# one group per row — arithmetically valid, analytically worthless. Cap the group count.
MAX_GROUP_CARDINALITY = 20
# Separate, stricter cap for charts: a box plot stops being readable well before 20 categories.
MAX_CHART_CATEGORIES = 12

_ID_EXACT = {"id", "index", "idx", "rowid", "row_id", "key", "pk", "uuid", "guid", "passengerid"}


def _normalize_col(col: str) -> str:
    """camelCase/PascalCase/spaced -> snake_case, for name-based column heuristics."""
    s = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", str(col).strip())
    return re.sub(r"[\s\-]+", "_", s).lower()


def is_id_like(col: str, series: pd.Series | None = None) -> bool:
    """True if a column looks like an identifier rather than a measurable quantity.

    Name-based: exact matches ('id', 'uuid') plus '*_id' / 'id_*' affixes, so real foreign
    keys like ``employee_id`` or ``customerId`` are caught — the previous exact-match set
    let every one of those through and they got averaged as if they were metrics.

    Value-based: an integer column that covers a contiguous range with no repeats is a
    row counter. Uniqueness alone is not enough — salaries and revenues are usually unique
    too, and excluding them would throw away the only real metrics in the table.
    """
    name = _normalize_col(col)
    if name in _ID_EXACT or name.endswith("_id") or name.startswith("id_"):
        return True
    if series is not None and len(series) > 1:
        try:
            if not pd.api.types.is_integer_dtype(series):
                return False
            if series.nunique(dropna=False) != len(series):
                return False
            # A dense 1..N (in any order) is a surrogate key; a spread-out unique column
            # such as salary is not.
            span = int(series.max()) - int(series.min()) + 1
            return span == len(series)
        except (TypeError, ValueError, OverflowError):
            return False
    return False


# Below this many rows the distinct/row ratio says more about sample size than about the
# column, so the cardinality cap alone decides.
_RATIO_GUARD_MIN_ROWS = 30


def is_groupable(series: pd.Series, max_cardinality: int = MAX_GROUP_CARDINALITY) -> bool:
    """True if a categorical column has few enough distinct values to aggregate over."""
    n = len(series)
    if n == 0:
        return False
    distinct = int(series.nunique(dropna=False))
    # Need at least two groups to compare, and few enough that each pools multiple rows.
    if not (2 <= distinct <= max_cardinality):
        return False
    if n >= _RATIO_GUARD_MIN_ROWS and distinct / n > 0.5:
        return False
    return distinct < n


class DataJanitorAgent(Agent):
    def run(self, data, **kwargs):
        df = _as_frame(data).copy()
        report = {}
        report["initial_shape"] = df.shape

        # Duplicates
        num_duplicates = int(df.duplicated().sum())
        report["duplicates_found"] = num_duplicates
        if num_duplicates > 0:
            df = df.drop_duplicates()
        report["duplicates_removed"] = num_duplicates

        # Missing value analysis
        missing_summary = df.isnull().sum().to_dict()
        report["total_missing"] = int(sum(missing_summary.values()))
        report["missing_values"] = missing_summary

        # Bias flags for high-missingness columns
        bias_flags = []
        for col, missing in missing_summary.items():
            pct = 100 * missing / max(len(df), 1)
            if pct > 30:
                bias_flags.append(
                    f"Column '{col}' missing {pct:.1f}% of rows — results may be biased."
                )
        if bias_flags:
            report["bias_flags"] = bias_flags

        # Impute — median for numerics (more robust than mean on skewed data)
        for col in df.columns:
            if df[col].isnull().any():
                if pd.api.types.is_numeric_dtype(df[col]):
                    median = df[col].median()
                    # An all-null column has no median (NaN) — fall back to 0
                    # rather than leaving NaN, which isn't valid JSON and
                    # crashes response serialization downstream.
                    df[col] = df[col].fillna(median if pd.notna(median) else 0)
                elif pd.api.types.is_datetime64_any_dtype(df[col]):
                    # Dates have no meaningful mode to fall back on, and
                    # filling one with the "MISSING" sentinel below would
                    # upcast the column to object — silently undoing the type
                    # detection every time-series check depends on. Use the
                    # median timestamp; an all-empty column stays NaT, which
                    # sanitize_json renders as null.
                    median_ts = df[col].median()
                    if pd.notna(median_ts):
                        df[col] = df[col].fillna(median_ts)
                else:
                    mode = df[col].mode()
                    df[col] = df[col].fillna(mode[0] if not mode.empty else "MISSING")

        # Outlier summary (IQR, for context — we don't remove, just flag)
        outlier_flags = []
        for col in df.select_dtypes(include="number").columns:
            q1, q3 = df[col].quantile(0.25), df[col].quantile(0.75)
            iqr = q3 - q1
            n_out = int(((df[col] < q1 - 1.5 * iqr) | (df[col] > q3 + 1.5 * iqr)).sum())
            if n_out > 0:
                outlier_flags.append(f"{col}: {n_out} outlier(s) detected (IQR method)")
        if outlier_flags:
            report["outlier_flags"] = outlier_flags

        report["constant_columns"] = [c for c in df.columns if df[c].nunique() == 1]
        report["final_shape"] = df.shape
        report["missing_values_imputed"] = report["total_missing"] > 0
        return {"cleaned_df": df, "report": report}


# Caps on the columns fed into the fallback's groupby/correlation loops
# (used when no LLM is configured, or the LLM call fails). Uncapped, a
# categorical x numeric double loop of full-frame groupbys, plus a pairwise
# O(numeric^2) correlation loop, turns a wide CSV (a couple hundred columns,
# not unusual for an exported data warehouse table) into thousands of
# full-frame passes before a single hypothesis is produced. The LLM-authored
# path, which is what actually runs whenever a provider is configured, sees
# every column via the schema prompt regardless of this cap.
_MAX_HYPOTHESIS_NUMERIC_COLS = 20
_MAX_HYPOTHESIS_CATEGORICAL_COLS = 20


class HypothesisBotAgent(Agent):
    def __init__(self, name: str, llm_service: LLMService | None = None):
        super().__init__(name=name)
        llm = llm_service
        if llm is None:
            try:
                llm = LLMService()
            except Exception:
                llm = None
        object.__setattr__(self, "llm", llm)

    def _generate_fallback_hypotheses(self, df: pd.DataFrame) -> dict[str, Any]:
        numeric_cols = [
            c for c in df.select_dtypes(include="number").columns if not is_id_like(c, df[c])
        ]
        categorical_cols = [
            c
            for c in df.select_dtypes(include=["object", "string", "category"]).columns
            if not is_id_like(c, df[c])
        ]
        datetime_cols = list(df.select_dtypes(include="datetime").columns)

        numeric_cols = numeric_cols[:_MAX_HYPOTHESIS_NUMERIC_COLS]
        categorical_cols = categorical_cols[:_MAX_HYPOTHESIS_CATEGORICAL_COLS]

        # Only columns that pool rows into a handful of groups are worth aggregating over.
        groupable_cols = [c for c in categorical_cols if is_groupable(df[c])]

        hypotheses: list[str] = []

        # Trends first: on a dataset with a time axis, "what changed over
        # time" is the question a reader actually has, and it used to be
        # unaskable because dates arrived as text.
        for date_col in datetime_cols[:1]:
            ordered = df.dropna(subset=[date_col]).sort_values(date_col)
            if len(ordered) < 4:
                continue
            span = ordered[date_col].iloc[-1] - ordered[date_col].iloc[0]
            half = len(ordered) // 2
            for num in numeric_cols:
                first = ordered[num].iloc[:half].mean()
                second = ordered[num].iloc[half:].mean()
                if pd.isna(first) or pd.isna(second) or abs(first) < 1e-9:
                    continue
                change = (second - first) / abs(first) * 100
                if abs(change) >= 10:
                    hypotheses.append(
                        f"{num} {'rose' if change > 0 else 'fell'} {abs(change):.0f}% "
                        f"between the first and second half of the {span.days}-day period "
                        f"covered by {date_col} (mean {first:,.1f} → {second:,.1f})."
                    )
        for cat in groupable_cols:
            for num in numeric_cols:
                top = df.groupby(cat)[num].mean().sort_values(ascending=False)
                if len(top) >= 2:
                    best, worst = top.index[0], top.index[-1]
                    best_val, worst_val = top.iloc[0], top.iloc[-1]
                    # Express the gap against the overall mean, which stays stable when the
                    # bottom group sits near zero. Phrasing must match the denominator.
                    gap_pct = abs(best_val - worst_val) / max(abs(top.mean()), 1e-9) * 100
                    hypotheses.append(
                        f"'{best}' has the highest average {num} in '{cat}' "
                        f"({best_val:,.2f} vs {worst_val:,.2f} for '{worst}' — "
                        f"a gap of {gap_pct:.0f}% of the overall mean) — "
                        f"worth investigating whether this gap is structural."
                    )
        for i, a in enumerate(numeric_cols):
            for b in numeric_cols[i + 1 :]:
                try:
                    r = df[[a, b]].corr().iloc[0, 1]
                    if abs(r) > 0.3:
                        direction = "positively" if r > 0 else "negatively"
                        hypotheses.append(
                            f"{a} and {b} are {direction} correlated (r={r:.2f}) — "
                            f"higher {a} tends to mean {'higher' if r > 0 else 'lower'} {b}."
                        )
                except Exception as e:
                    # Correlation can fail on non-numeric-looking columns (e.g. all-NaN
                    # after coercion) — skip that pair and keep collecting hypotheses.
                    logger.debug(
                        "Skipping correlation for %s/%s: %s",
                        safe_log_value(a),
                        safe_log_value(b),
                        safe_log_value(e),
                    )

        deduped: list[str] = list(dict.fromkeys(hypotheses))[:8]
        if not deduped:
            deduped = [
                "No strong patterns detected in the available columns — try asking specific questions."
            ]
        return {
            "hypotheses": deduped,
            "llm_used": False,
            "summary": {
                "num_hypotheses": len(deduped),
                "reasoning": "Heuristic patterns from column statistics (no LLM).",
                "numeric_columns": numeric_cols,
                # Only groupable columns — downstream consumers build "X by Y" prompts from
                # this list, and a near-unique column makes those meaningless.
                "categorical_columns": groupable_cols,
            },
        }

    @staticmethod
    def _build_stats_summary(df: pd.DataFrame) -> str:
        lines = []
        numeric = df.select_dtypes(include="number")
        if not numeric.empty:
            desc = numeric.describe().round(2)
            lines.append("Numeric statistics:\n" + desc.to_string())
            if numeric.shape[1] >= 2:
                corr = numeric.corr().abs()
                pairs = (
                    corr.where(~(corr == 1.0) & (corr > 0.3))
                    .stack()
                    .drop_duplicates()
                    .sort_values(ascending=False)
                    .head(8)
                )
                if not pairs.empty:
                    lines.append("\nStrong correlations (|r| > 0.3):")
                    for (a, b), _v in pairs.items():
                        raw_r = numeric.corr().loc[a, b]
                        direction = "positive" if raw_r > 0 else "negative"
                        lines.append(f"  {a} ↔ {b}: r={raw_r:.2f} ({direction})")

        datetimes = df.select_dtypes(include="datetime")
        if not datetimes.empty:
            lines.append("\nTime coverage:")
            for col in datetimes.columns[:3]:
                values = df[col].dropna()
                if values.empty:
                    continue
                lo, hi = values.min(), values.max()
                lines.append(
                    f"  {col}: {lo:%Y-%m-%d} to {hi:%Y-%m-%d} "
                    f"({(hi - lo).days} days, {values.nunique()} distinct values)"
                )

        categorical = df.select_dtypes(include=["object", "string", "category"])
        if not categorical.empty:
            lines.append("\nCategorical distributions:")
            for col in categorical.columns[:6]:
                top = df[col].value_counts().head(4).to_dict()
                lines.append(f"  {col}: {top}")

        return "\n".join(lines)

    def run(self, cleaned_data, stats_summary: str | None = None, **kwargs):
        df = _as_frame(cleaned_data)
        schema_prompt = DataFrameSchema.to_prompt(DataFrameSchema.from_dataframe(df))
        # Reuse a caller-supplied summary when present (the /process and
        # workflow paths build it once and share it with the Debate Manager).
        if stats_summary is None:
            stats_summary = self._build_stats_summary(df)
        fallback = self._generate_fallback_hypotheses(df)

        system_prompt = """You are a senior data scientist generating insights for a business audience.

Given a dataset's schema and statistics, produce 5-8 SPECIFIC, DIRECTIONAL insights.

RULES:
- Each insight must name exact column(s) from the schema
- State the direction: higher/lower/increases/decreases/leads/lags
- Cite actual numbers from the statistics where possible (e.g. "r=0.72", "34% higher")
- Focus on business-actionable findings, not textbook observations
- Prioritise findings supported by correlation data

BAD: "Does revenue differ by region?"
GOOD: "The West region generates 34% more revenue per customer than the national average (mean=$4,210 vs $3,140), suggesting untapped potential in other regions."

BAD: "There may be a relationship between age and salary."
GOOD: "Age and Salary are strongly positively correlated (r=0.68) — each additional year of age corresponds to roughly $1,200 more in annual salary."

OUTPUT (JSON only):
{"hypotheses": ["insight 1", "insight 2", ...], "reasoning": "one-line strategy"}"""

        user_prompt = f"Schema:\n{schema_prompt}\n\nStatistics:\n{stats_summary}"

        if self.llm is None:
            return fallback

        try:
            response = self.llm.complete_json(system_prompt, user_prompt)
            hypotheses = response.get("hypotheses") or fallback["hypotheses"]
            hypotheses = list(dict.fromkeys(hypotheses))[:8]
            return {
                "hypotheses": hypotheses,
                "llm_used": True,
                "summary": {
                    "num_hypotheses": len(hypotheses),
                    "reasoning": response.get("reasoning", "LLM-generated insights"),
                    "numeric_columns": fallback["summary"]["numeric_columns"],
                    "categorical_columns": fallback["summary"]["categorical_columns"],
                },
            }
        except Exception:
            logger.warning(
                "Hypothesis generation via LLM failed; using heuristic fallback", exc_info=True
            )
            return fallback


class DebateManagerAgent(Agent):
    def __init__(self, name: str, llm_service: LLMService | None = None):
        super().__init__(name=name)
        llm = llm_service
        if llm is None:
            try:
                llm = LLMService()
            except Exception:
                llm = None
        object.__setattr__(self, "llm", llm)

    def _fallback_scoring(self, hypotheses: list[str]) -> dict[str, Any]:
        """Order hypotheses without an LLM — deliberately without inventing scores.

        This path previously synthesised ``confidence = 0.85 - i * 0.05``, which the UI then
        rendered as an authoritative "85% confidence" badge. The numbers described nothing but
        list position, so they are omitted entirely: ``None`` tells every consumer that no
        assessment was made, where a plausible-looking float silently claimed one was.
        """
        scored = [
            {
                "hypothesis": h,
                "confidence": None,
                "business_value": None,
                "statistical_argument": "Not assessed — no LLM available to score this claim.",
                "business_argument": "Not assessed — no LLM available to score this claim.",
            }
            for h in hypotheses
        ]
        # Input order already reflects the heuristic generator's own ordering; keep it rather
        # than re-sorting on scores that no longer exist.
        return {
            "scored_hypotheses": scored,
            "llm_used": False,
            "summary": {
                "num_hypotheses": len(hypotheses),
                "consensus": scored[0] if scored else None,
                "arguments": [
                    {
                        "hypothesis": s["hypothesis"],
                        "statistical": s["statistical_argument"],
                        "business": s["business_argument"],
                    }
                    for s in scored
                ],
            },
        }

    def run(self, hypotheses, data_stats: str | None = None, **kwargs):
        if not hypotheses:
            return {
                "scored_hypotheses": [],
                "llm_used": self.llm is not None,  # type: ignore[attr-defined]
                "summary": {"num_hypotheses": 0, "consensus": None, "arguments": []},
            }
        if self.llm is None:  # type: ignore[attr-defined]
            return self._fallback_scoring(hypotheses)

        system_prompt = """You are a data science auditor evaluating hypotheses against actual data evidence.

Score each hypothesis on:
- confidence (0.0-1.0): how strongly is it supported by the statistics provided?
- business_value (0.0-1.0): how actionable and impactful is it for decision-making?

Use the data statistics to justify your scores — higher confidence when correlations or distributions clearly support the claim.
Be a skeptical auditor, not a cheerleader: reserve confidence above 0.9 for claims backed by strong, unambiguous statistical evidence
(e.g. a correlation with |r| > 0.7 on a reasonably sized sample). Small sample sizes, weak correlations, or descriptive-only
observations should score well below 1.0 — near-certainty is rare and should be justified explicitly in statistical_argument.

OUTPUT (JSON only):
{
  "scored_hypotheses": [
    {
      "hypothesis": "...",
      "confidence": 0.85,
      "business_value": 0.9,
      "statistical_argument": "cite the specific stat that supports this",
      "business_argument": "explain the business impact"
    }
  ]
}"""

        data_context = f"\nData Statistics:\n{data_stats}\n\n" if data_stats else ""
        user_prompt = f"{data_context}Hypotheses to score:\n{json.dumps(hypotheses, indent=2)}"

        try:
            response = self.llm.complete_json(system_prompt, user_prompt)  # type: ignore[attr-defined]
            scored = response.get("scored_hypotheses", [])
            # The model can omit either score; treat a missing one as 0 rather than crashing.
            scored.sort(
                key=lambda x: (x.get("confidence") or 0) * (x.get("business_value") or 0),
                reverse=True,
            )
            return {
                "scored_hypotheses": scored,
                "llm_used": True,
                "summary": {
                    "num_hypotheses": len(hypotheses),
                    "consensus": scored[0] if scored else None,
                    "arguments": [
                        {
                            "hypothesis": s["hypothesis"],
                            "statistical": s.get("statistical_argument", ""),
                            "business": s.get("business_argument", ""),
                        }
                        for s in scored
                    ],
                },
            }
        except Exception:
            logger.warning("Hypothesis scoring via LLM failed; returning unscored", exc_info=True)
            return self._fallback_scoring(hypotheses)


class VizWhizAgent(Agent):
    def __init__(self, name: str, llm_service: LLMService | None = None):
        super().__init__(name=name)
        llm = llm_service
        if llm is None:
            try:
                llm = LLMService()
            except Exception:
                llm = None
        object.__setattr__(self, "llm", llm)

    def _llm_pick_columns(self, hypothesis: str, df: pd.DataFrame) -> tuple:
        """Ask LLM which columns best illustrate the consensus hypothesis."""
        llm = object.__getattribute__(self, "llm")
        if llm is None:
            return None, None
        cols = df.columns.tolist()
        system = "You select columns for data visualization. Reply with JSON only."
        user = (
            f'Hypothesis: "{hypothesis}"\n'
            f"Available columns: {cols}\n\n"
            f"Which 1-2 columns best illustrate this insight?\n"
            f'Reply: {{"x": "col_name", "y": "col_name_or_null"}}'
        )
        try:
            result = llm.complete_json(system, user)
            x = result.get("x")
            y = result.get("y")
            return (
                x if x and x in df.columns else None,
                y if y and y in df.columns else None,
            )
        except Exception:
            return None, None

    def run(self, cleaned_data, consensus, **kwargs):
        import re

        import plotly.express as px

        df = _as_frame(cleaned_data)
        hypotheses = kwargs.get("hypotheses", [])

        def is_valid_col(col):
            if col not in df.columns:
                return False
            if df[col].nunique(dropna=False) <= 1:
                return False
            if df[col].dtype == object and (df[col] == "MISSING").sum() / max(len(df), 1) > 0.8:
                return False
            # Charting a surrogate key ("average employee_id by department") is never the
            # insight the user wanted; keep identifiers out of axis selection entirely.
            if is_id_like(col, df[col]):
                return False
            return True

        lower_to_col = {c.lower(): c for c in df.columns}

        def resolve_col(token):
            if not token:
                return None
            if token in df.columns:
                return token
            return lower_to_col.get(token.lower())

        def choose_plot_types(x, y):
            plots = []

            def is_cat(c):
                return (
                    pd.api.types.is_object_dtype(df[c])
                    or pd.api.types.is_string_dtype(df[c])
                    or isinstance(df[c].dtype, pd.CategoricalDtype)
                )

            def is_dt(c):
                return pd.api.types.is_datetime64_any_dtype(df[c])

            def time_series(date_col, value_col=None):
                """Line chart over time, aggregated to a readable granularity.

                Plotting a thousand raw daily points renders as noise, so the
                span decides the bucket: daily inside a quarter, weekly inside
                two years, monthly beyond that.
                """
                cols = [date_col] + ([value_col] if value_col else [])
                frame = df[cols].dropna(subset=[date_col]).sort_values(date_col)
                if frame.empty:
                    return []
                span_days = (frame[date_col].max() - frame[date_col].min()).days
                rule = "D" if span_days <= 90 else "W" if span_days <= 730 else "ME"

                indexed = frame.set_index(date_col)
                if value_col:
                    agg = indexed[value_col].resample(rule).mean().dropna().reset_index()
                    title = f"{value_col} over time"
                    y_col = value_col
                else:
                    agg = indexed.resample(rule).size().reset_index(name="count")
                    title = f"Records over time by {date_col}"
                    y_col = "count"

                if len(agg) < 2:
                    return []
                return [
                    {
                        "type": "line",
                        "title": title,
                        "plotly_json": px.line(
                            agg, x=date_col, y=y_col, markers=len(agg) <= 30, title=title
                        ).to_json(),
                    }
                ]

            if x and y:
                # A date axis paired with a measure is a time series. This has
                # to come first: a datetime column matches neither the numeric
                # nor the categorical branch below, so before this existed a
                # (date, revenue) pair silently produced no chart at all —
                # and once dates were still text, a bar chart of 15 arbitrary
                # days sorted by value.
                if is_dt(x) and pd.api.types.is_numeric_dtype(df[y]):
                    plots.extend(time_series(x, y))
                elif is_dt(y) and pd.api.types.is_numeric_dtype(df[x]):
                    plots.extend(time_series(y, x))
                elif is_dt(x) or is_dt(y):
                    plots.extend(time_series(x if is_dt(x) else y))
                elif pd.api.types.is_numeric_dtype(df[x]) and pd.api.types.is_numeric_dtype(df[y]):
                    r = abs(df[[x, y]].corr().iloc[0, 1])
                    if r > 0.2:
                        # OLS trendline needs statsmodels; degrade gracefully if absent.
                        plots.append(
                            {
                                "type": "scatter",
                                "title": f"{x} vs {y}",
                                "plotly_json": px.scatter(
                                    df,
                                    x=x,
                                    y=y,
                                    trendline="ols" if _HAS_STATSMODELS else None,
                                    title=f"{x} vs {y}",
                                ).to_json(),
                            }
                        )
                    else:
                        plots.append(
                            {
                                "type": "density_heatmap",
                                "title": f"Density: {x} vs {y}",
                                "plotly_json": px.density_heatmap(
                                    df, x=x, y=y, title=f"Density: {x} vs {y}"
                                ).to_json(),
                            }
                        )
                elif is_cat(x) and pd.api.types.is_numeric_dtype(df[y]):
                    agg = (
                        df.groupby(x)[y]
                        .mean()
                        .reset_index()
                        .sort_values(y, ascending=False)
                        .head(15)
                    )
                    plots.append(
                        {
                            "type": "bar",
                            "title": f"Average {y} by {x}",
                            "plotly_json": px.bar(
                                agg, x=x, y=y, title=f"Average {y} by {x}"
                            ).to_json(),
                        }
                    )
                    if df[x].nunique() < MAX_CHART_CATEGORIES:
                        plots.append(
                            {
                                "type": "box",
                                "title": f"Distribution of {y} by {x}",
                                "plotly_json": px.box(
                                    df, x=x, y=y, title=f"Distribution of {y} by {x}"
                                ).to_json(),
                            }
                        )
                elif pd.api.types.is_numeric_dtype(df[x]) and is_cat(y if y else x):
                    agg = (
                        df.groupby(y)[x]
                        .mean()
                        .reset_index()
                        .sort_values(x, ascending=False)
                        .head(15)
                    )
                    plots.append(
                        {
                            "type": "bar",
                            "title": f"Average {x} by {y}",
                            "plotly_json": px.bar(
                                agg, x=y, y=x, title=f"Average {x} by {y}"
                            ).to_json(),
                        }
                    )
                    if df[y].nunique() < MAX_CHART_CATEGORIES:
                        plots.append(
                            {
                                "type": "box",
                                "title": f"Distribution of {x} by {y}",
                                "plotly_json": px.box(
                                    df, x=y, y=x, title=f"Distribution of {x} by {y}"
                                ).to_json(),
                            }
                        )
            elif x:
                if is_dt(x):
                    plots.extend(time_series(x))
                elif pd.api.types.is_numeric_dtype(df[x]):
                    plots.append(
                        {
                            "type": "histogram",
                            "title": f"Distribution of {x}",
                            "plotly_json": px.histogram(
                                df, x=x, title=f"Distribution of {x}"
                            ).to_json(),
                        }
                    )
                else:
                    vc = df[x].value_counts().head(15).reset_index()
                    vc.columns = [x, "count"]
                    plots.append(
                        {
                            "type": "bar",
                            "title": f"Count by {x}",
                            "plotly_json": px.bar(
                                vc, x=x, y="count", title=f"Count by {x}"
                            ).to_json(),
                        }
                    )
            return plots

        possible_plots = []

        # 1. Try LLM column selection from consensus hypothesis
        hypothesis_text = consensus.get("hypothesis", "") if consensus else ""
        if hypothesis_text:
            x, y = self._llm_pick_columns(hypothesis_text, df)
            if x and is_valid_col(x) and (not y or is_valid_col(y)):
                possible_plots.extend(choose_plot_types(x, y))

        # 2. Regex fallback from hypothesis text
        if not possible_plots and hypothesis_text:
            tokens = re.findall(r"\b([A-Za-z0-9_]+)\b", hypothesis_text)
            found = [resolve_col(t) for t in tokens if resolve_col(t)]
            found = list(dict.fromkeys(found))
            x = found[0] if found else None
            y = found[1] if len(found) > 1 else None
            if x and is_valid_col(x) and (not y or is_valid_col(y)):
                possible_plots.extend(choose_plot_types(x, y))

        # 3. Try other hypotheses
        if not possible_plots:
            for hyp in hypotheses[:5]:
                tokens = re.findall(r"\b([A-Za-z0-9_]+)\b", hyp)
                found = list(dict.fromkeys(resolve_col(t) for t in tokens if resolve_col(t)))
                x = found[0] if found else None
                y = found[1] if len(found) > 1 else None
                if x and is_valid_col(x) and (not y or is_valid_col(y)):
                    possible_plots.extend(choose_plot_types(x, y))
                    if possible_plots:
                        break

        # 4. Structured fallback: best categorical × numeric pair
        _MAX = 6
        if not possible_plots:
            numeric_cols = [
                c for c in df.select_dtypes(include="number").columns if is_valid_col(c)
            ]
            cat_cols = [
                c
                for c in df.select_dtypes(include=["object", "string", "category"]).columns
                if is_valid_col(c)
            ]
            date_cols = [c for c in df.select_dtypes(include="datetime").columns if is_valid_col(c)]

            # On a dataset with a time axis, lead with the trend rather than
            # a category breakdown — it's the chart a reader looks for first.
            for date_col in date_cols[:1]:
                for num in numeric_cols[:2]:
                    possible_plots.extend(choose_plot_types(date_col, num))
                if not numeric_cols:
                    possible_plots.extend(choose_plot_types(date_col, None))

            for cat in cat_cols[:3]:
                for num in numeric_cols[:3]:
                    possible_plots.extend(choose_plot_types(cat, num))
                    if len(possible_plots) >= _MAX:
                        break
                if len(possible_plots) >= _MAX:
                    break
            if not possible_plots:
                for num in numeric_cols[:3]:
                    possible_plots.extend(choose_plot_types(num, None))

        # Deduplicate
        seen = set()
        unique_plots = []
        for p in possible_plots:
            key = (p["type"], p["title"])
            if key not in seen:
                seen.add(key)
                unique_plots.append(p)

        chart_info = {"success": bool(unique_plots), "plots": unique_plots[:_MAX]}
        if not unique_plots:
            chart_info["error"] = "Could not auto-select chart columns."
        return {"chart_info": chart_info}


class InsightOrchestraWorkflow:
    def __init__(self, llm_service: LLMService | None = None):
        llm = llm_service
        if llm is None:
            try:
                llm = LLMService()
            except Exception:
                llm = None
        self.llm = llm
        self.cleaner = DataJanitorAgent(name="DataJanitorAgent")
        self.hypothesis = HypothesisBotAgent(name="HypothesisBotAgent", llm_service=llm)
        self.debate = DebateManagerAgent(name="DebateManagerAgent", llm_service=llm)
        self.viz = VizWhizAgent(name="VizWhizAgent", llm_service=llm)

    def run(self, data):
        cleaner_result = self.cleaner.run(data)
        df = cleaner_result["cleaned_df"]

        # Build stats once — shared by Hypothesis Bot and Debate Manager
        stats_summary = HypothesisBotAgent._build_stats_summary(df)

        hypothesis_result = self.hypothesis.run(df, stats_summary)
        hypotheses = hypothesis_result["hypotheses"]
        hypothesis_result["revised"] = True
        hypothesis_result["revised_hypotheses"] = hypotheses

        # Debate Manager now receives the actual data stats for evidence-based scoring
        debate_result = self.debate.run(hypotheses, data_stats=stats_summary)
        consensus = debate_result["summary"].get("consensus")

        viz_result = self.viz.run(df, consensus, hypotheses=hypotheses)

        report = cleaner_result["report"]
        n_plots = len(viz_result.get("chart_info", {}).get("plots", []))
        top = consensus.get("hypothesis", "None")[:60] if consensus else "None"
        audit_table = "\n".join(
            [
                "| Feature | Value |",
                "|---------|-------|",
                f"| Rows | {report.get('final_shape', (0,))[0]:,} |",
                f"| Columns | {report.get('final_shape', (0, 0))[1]} |",
                f"| Duplicates removed | {report.get('duplicates_removed', 0)} |",
                f"| Missing values handled | {report.get('total_missing', 0)} |",
                f"| Insights found | {len(hypotheses)} |",
                f"| Charts generated | {n_plots} |",
                f"| Top insight | {top} |",
            ]
        )

        return {
            "cleaner": cleaner_result,
            "hypothesis": hypothesis_result,
            "debate": debate_result,
            "viz": viz_result,
            "stats": stats_summary,
            "audit_table": audit_table,
        }
