from google.adk import Agent
import pandas as pd
import json
from typing import Optional, List, Dict, Any
from app.services.llm_service import LLMService, DataFrameSchema

try:
    import statsmodels.api  # noqa: F401 — enables OLS trendlines in plotly express
    _HAS_STATSMODELS = True
except Exception:
    _HAS_STATSMODELS = False


class DataJanitorAgent(Agent):
    def run(self, data, **kwargs):
        df = pd.DataFrame(data)
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
                bias_flags.append(f"Column '{col}' missing {pct:.1f}% of rows — results may be biased.")
        if bias_flags:
            report["bias_flags"] = bias_flags

        # Impute — median for numerics (more robust than mean on skewed data)
        for col in df.columns:
            if df[col].isnull().any():
                if pd.api.types.is_numeric_dtype(df[col]):
                    df[col] = df[col].fillna(df[col].median())
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
        return {"cleaned_data": df.to_dict(orient="records"), "report": report}


class HypothesisBotAgent(Agent):
    def __init__(self, name: str, llm_service: Optional[LLMService] = None):
        super().__init__(name=name)
        llm = llm_service
        if llm is None:
            try:
                llm = LLMService()
            except Exception:
                llm = None
        object.__setattr__(self, "llm", llm)

    def _generate_fallback_hypotheses(self, df: pd.DataFrame) -> Dict[str, Any]:
        id_like = {"id", "index", "rowid", "passengerid"}
        numeric_cols = [c for c in df.select_dtypes(include="number").columns if c.lower() not in id_like]
        categorical_cols = [c for c in df.select_dtypes(include=["object", "string", "category"]).columns if c.lower() not in id_like]

        hypotheses: List[str] = []
        for cat in categorical_cols:
            for num in numeric_cols:
                top = df.groupby(cat)[num].mean().sort_values(ascending=False)
                if len(top) >= 2:
                    best, worst = top.index[0], top.index[-1]
                    diff_pct = abs(top.iloc[0] - top.iloc[-1]) / max(abs(top.mean()), 1e-9) * 100
                    hypotheses.append(
                        f"'{best}' leads '{cat}' with the highest average {num} "
                        f"({diff_pct:.0f}% above '{worst}') — worth investigating whether this gap is structural."
                    )
        for i, a in enumerate(numeric_cols):
            for b in numeric_cols[i + 1:]:
                try:
                    r = df[[a, b]].corr().iloc[0, 1]
                    if abs(r) > 0.3:
                        direction = "positively" if r > 0 else "negatively"
                        hypotheses.append(
                            f"{a} and {b} are {direction} correlated (r={r:.2f}) — "
                            f"higher {a} tends to mean {'higher' if r > 0 else 'lower'} {b}."
                        )
                except Exception:
                    pass

        deduped: List[str] = list(dict.fromkeys(hypotheses))[:8]
        if not deduped:
            deduped = ["No strong patterns detected in the available columns — try asking specific questions."]
        return {
            "hypotheses": deduped,
            "summary": {
                "num_hypotheses": len(deduped),
                "reasoning": "Heuristic hypotheses from column statistics.",
                "numeric_columns": numeric_cols,
                "categorical_columns": categorical_cols,
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
                    for (a, b), v in pairs.items():
                        raw_r = numeric.corr().loc[a, b]
                        direction = "positive" if raw_r > 0 else "negative"
                        lines.append(f"  {a} ↔ {b}: r={raw_r:.2f} ({direction})")

        categorical = df.select_dtypes(include=["object", "string", "category"])
        if not categorical.empty:
            lines.append("\nCategorical distributions:")
            for col in categorical.columns[:6]:
                top = df[col].value_counts().head(4).to_dict()
                lines.append(f"  {col}: {top}")

        return "\n".join(lines)

    def run(self, cleaned_data, **kwargs):
        df = pd.DataFrame(cleaned_data)
        schema_prompt = DataFrameSchema.to_prompt(DataFrameSchema.from_dataframe(df))
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
                "summary": {
                    "num_hypotheses": len(hypotheses),
                    "reasoning": response.get("reasoning", "LLM-generated insights"),
                    "numeric_columns": fallback["summary"]["numeric_columns"],
                    "categorical_columns": fallback["summary"]["categorical_columns"],
                },
            }
        except Exception:
            return fallback


class DebateManagerAgent(Agent):
    def __init__(self, name: str, llm_service: Optional[LLMService] = None):
        super().__init__(name=name)
        llm = llm_service
        if llm is None:
            try:
                llm = LLMService()
            except Exception:
                llm = None
        object.__setattr__(self, "llm", llm)

    def _fallback_scoring(self, hypotheses: List[str]) -> Dict[str, Any]:
        scored = []
        for i, h in enumerate(hypotheses):
            confidence = max(0.1, min(1.0, 0.85 - i * 0.05))
            business = max(0.1, min(1.0, 0.80 - i * 0.04))
            scored.append({
                "hypothesis": h,
                "confidence": round(confidence, 2),
                "business_value": round(business, 2),
                "statistical_argument": "Ranked by position — LLM unavailable.",
                "business_argument": "Ranked by position — LLM unavailable.",
            })
        scored.sort(key=lambda x: x["confidence"] * x["business_value"], reverse=True)
        return {
            "scored_hypotheses": scored,
            "summary": {
                "num_hypotheses": len(hypotheses),
                "consensus": scored[0] if scored else None,
                "arguments": [{"hypothesis": s["hypothesis"], "statistical": s["statistical_argument"], "business": s["business_argument"]} for s in scored],
            },
        }

    def run(self, hypotheses, data_stats: Optional[str] = None, **kwargs):
        if not hypotheses:
            return {"scored_hypotheses": [], "summary": {"num_hypotheses": 0, "consensus": None, "arguments": []}}
        if self.llm is None:
            return self._fallback_scoring(hypotheses)

        system_prompt = """You are a data science auditor evaluating hypotheses against actual data evidence.

Score each hypothesis on:
- confidence (0.0-1.0): how strongly is it supported by the statistics provided?
- business_value (0.0-1.0): how actionable and impactful is it for decision-making?

Use the data statistics to justify your scores — higher confidence when correlations or distributions clearly support the claim.

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
            response = self.llm.complete_json(system_prompt, user_prompt)
            scored = response.get("scored_hypotheses", [])
            scored.sort(key=lambda x: x.get("confidence", 0) * x.get("business_value", 0), reverse=True)
            return {
                "scored_hypotheses": scored,
                "summary": {
                    "num_hypotheses": len(hypotheses),
                    "consensus": scored[0] if scored else None,
                    "arguments": [{"hypothesis": s["hypothesis"], "statistical": s.get("statistical_argument", ""), "business": s.get("business_argument", "")} for s in scored],
                },
            }
        except Exception:
            return self._fallback_scoring(hypotheses)


class VizWhizAgent(Agent):
    def __init__(self, name: str, llm_service: Optional[LLMService] = None):
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
            f'Which 1-2 columns best illustrate this insight?\n'
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
        import plotly.express as px
        import re
        df = pd.DataFrame(cleaned_data)
        hypotheses = kwargs.get("hypotheses", [])

        def is_valid_col(col):
            if col not in df.columns:
                return False
            if df[col].nunique(dropna=False) <= 1:
                return False
            if df[col].dtype == object and (df[col] == "MISSING").sum() / max(len(df), 1) > 0.8:
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
                return (pd.api.types.is_object_dtype(df[c])
                        or pd.api.types.is_string_dtype(df[c])
                        or isinstance(df[c].dtype, pd.CategoricalDtype))

            if x and y:
                if pd.api.types.is_numeric_dtype(df[x]) and pd.api.types.is_numeric_dtype(df[y]):
                    r = abs(df[[x, y]].corr().iloc[0, 1])
                    if r > 0.2:
                        # OLS trendline needs statsmodels; degrade gracefully if absent.
                        plots.append({"type": "scatter", "title": f"{x} vs {y}",
                                      "plotly_json": px.scatter(df, x=x, y=y,
                                                                 trendline="ols" if _HAS_STATSMODELS else None,
                                                                 title=f"{x} vs {y}").to_json()})
                    else:
                        plots.append({"type": "density_heatmap", "title": f"Density: {x} vs {y}",
                                      "plotly_json": px.density_heatmap(df, x=x, y=y,
                                                                         title=f"Density: {x} vs {y}").to_json()})
                elif is_cat(x) and pd.api.types.is_numeric_dtype(df[y]):
                    agg = df.groupby(x)[y].mean().reset_index().sort_values(y, ascending=False).head(15)
                    plots.append({"type": "bar", "title": f"Average {y} by {x}",
                                  "plotly_json": px.bar(agg, x=x, y=y,
                                                        title=f"Average {y} by {x}").to_json()})
                    if df[x].nunique() < 12:
                        plots.append({"type": "box", "title": f"Distribution of {y} by {x}",
                                      "plotly_json": px.box(df, x=x, y=y,
                                                            title=f"Distribution of {y} by {x}").to_json()})
                elif pd.api.types.is_numeric_dtype(df[x]) and is_cat(df[y] if y else x):
                    agg = df.groupby(y)[x].mean().reset_index().sort_values(x, ascending=False).head(15)
                    plots.append({"type": "bar", "title": f"Average {x} by {y}",
                                  "plotly_json": px.bar(agg, x=y, y=x,
                                                        title=f"Average {x} by {y}").to_json()})
            elif x:
                if pd.api.types.is_numeric_dtype(df[x]):
                    plots.append({"type": "histogram", "title": f"Distribution of {x}",
                                  "plotly_json": px.histogram(df, x=x, title=f"Distribution of {x}").to_json()})
                else:
                    vc = df[x].value_counts().head(15).reset_index()
                    vc.columns = [x, "count"]
                    plots.append({"type": "bar", "title": f"Count by {x}",
                                  "plotly_json": px.bar(vc, x=x, y="count", title=f"Count by {x}").to_json()})
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
            numeric_cols = [c for c in df.select_dtypes(include="number").columns if is_valid_col(c)]
            cat_cols = [c for c in df.select_dtypes(include=["object", "string", "category"]).columns if is_valid_col(c)]
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
    def __init__(self, llm_service: Optional[LLMService] = None):
        llm = llm_service
        if llm is None:
            try:
                llm = LLMService()
            except Exception:
                llm = None
        self.llm = llm
        self.cleaner   = DataJanitorAgent(name="DataJanitorAgent")
        self.hypothesis = HypothesisBotAgent(name="HypothesisBotAgent", llm_service=llm)
        self.debate    = DebateManagerAgent(name="DebateManagerAgent", llm_service=llm)
        self.viz       = VizWhizAgent(name="VizWhizAgent", llm_service=llm)

    def run(self, data):
        cleaner_result = self.cleaner.run(data)
        cleaned_data   = cleaner_result["cleaned_data"]
        df             = pd.DataFrame(cleaned_data)

        # Build stats once — shared by Hypothesis Bot and Debate Manager
        stats_summary = HypothesisBotAgent._build_stats_summary(df)

        hypothesis_result = self.hypothesis.run(cleaned_data)
        hypotheses        = hypothesis_result["hypotheses"]

        # Debate Manager now receives the actual data stats for evidence-based scoring
        debate_result = self.debate.run(hypotheses, data_stats=stats_summary)
        consensus     = debate_result["summary"].get("consensus")

        viz_result = self.viz.run(cleaned_data, consensus, hypotheses=hypotheses)

        return {
            "cleaner":    cleaner_result,
            "hypothesis": hypothesis_result,
            "debate":     debate_result,
            "viz":        viz_result,
            "stats":      stats_summary,
        }
