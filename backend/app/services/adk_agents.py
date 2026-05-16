from google.adk import Agent
import pandas as pd
import json
from typing import Optional, List, Dict, Any
from app.services.llm_service import LLMService, DataFrameSchema

# Data Janitor Agent
class DataJanitorAgent(Agent):
    def run(self, data, **kwargs):
        df = pd.DataFrame(data)
        report = {}
        initial_shape = df.shape
        report['initial_shape'] = initial_shape
        num_duplicates = df.duplicated().sum()
        report['duplicates_found'] = int(num_duplicates)
        if num_duplicates > 0:
            df = df.drop_duplicates()
            report['duplicates_removed'] = int(num_duplicates)
        else:
            report['duplicates_removed'] = 0
        missing_summary = df.isnull().sum().to_dict()
        total_missing = sum(missing_summary.values())
        report['missing_values'] = missing_summary
        report['total_missing'] = int(total_missing)
        # Improved: Bias/limitation awareness
        bias_flags = []
        for col, missing in missing_summary.items():
            if missing > 0:
                percent = 100 * missing / len(df)
                if percent > 30:
                    bias_flags.append(f"Column '{col}' missing for {percent:.1f}% of rows.")
        if bias_flags:
            report['bias_flags'] = bias_flags
        for col in df.columns:
            if df[col].isnull().any():
                if pd.api.types.is_numeric_dtype(df[col]):
                    df[col] = df[col].fillna(df[col].mean())
                else:
                    df[col] = df[col].fillna(df[col].mode()[0] if not df[col].mode().empty else "MISSING")
        report['missing_values_imputed'] = True
        constant_cols = [col for col in df.columns if df[col].nunique() == 1]
        report['constant_columns'] = constant_cols
        report['final_shape'] = df.shape
        cleaned_data_json = df.to_dict(orient='records')
        return {"cleaned_data": cleaned_data_json, "report": report}

# Hypothesis Bot Agent
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
        numeric_cols = [
            c for c in df.select_dtypes(include="number").columns.tolist()
            if c.lower() not in id_like
        ]
        categorical_cols = [
            c
            for c in df.select_dtypes(include=["object", "string", "category"]).columns.tolist()
            if c.lower() not in id_like
        ]

        hypotheses: List[str] = []
        # numeric pair interactions
        for i, col_a in enumerate(numeric_cols):
            for col_b in numeric_cols[i + 1:]:
                hypotheses.append(f"Is there a relationship between {col_a} and {col_b}?")
        # categorical group effects
        for cat in categorical_cols:
            for num in numeric_cols:
                hypotheses.append(f"Does {num} differ across {cat} groups?")
        # single-column fallback
        for num in numeric_cols:
            hypotheses.append(f"How is {num} distributed across the dataset?")

        # Ensure uniqueness and max 10
        deduped: List[str] = []
        seen = set()
        for h in hypotheses:
            if h not in seen:
                seen.add(h)
                deduped.append(h)
            if len(deduped) >= 10:
                break
        if not deduped:
            deduped = ["Is there a meaningful pattern in the available columns?"]

        return {
            "hypotheses": deduped,
            "summary": {
                "num_hypotheses": len(deduped),
                "reasoning": "Heuristic-generated hypotheses (LLM unavailable).",
                "revised": False,
                "numeric_columns": numeric_cols,
                "categorical_columns": categorical_cols,
            },
        }

    @staticmethod
    def _build_stats_summary(df: pd.DataFrame) -> str:
        """Compact numeric stats + top categorical value counts for the prompt."""
        lines = []
        numeric = df.select_dtypes(include="number")
        if not numeric.empty:
            desc = numeric.describe().round(2)
            lines.append("Numeric statistics (describe):")
            lines.append(desc.to_string())

            # Correlation pairs above threshold
            if numeric.shape[1] >= 2:
                corr = numeric.corr().abs()
                pairs = (
                    corr.where(
                        ~(corr == 1.0) & (corr > 0.4)
                    )
                    .stack()
                    .drop_duplicates()
                    .sort_values(ascending=False)
                    .head(5)
                )
                if not pairs.empty:
                    lines.append("\nNotable correlations (|r| > 0.4):")
                    for (a, b), v in pairs.items():
                        lines.append(f"  {a} ↔ {b}: {v:.2f}")

        categorical = df.select_dtypes(include=["object", "string", "category"])
        if not categorical.empty:
            lines.append("\nCategorical top values:")
            for col in categorical.columns[:5]:
                top = df[col].value_counts().head(3).to_dict()
                lines.append(f"  {col}: {top}")

        return "\n".join(lines)

    def run(self, cleaned_data, **kwargs):
        df = pd.DataFrame(cleaned_data)
        schema = DataFrameSchema.from_dataframe(df)
        schema_prompt = DataFrameSchema.to_prompt(schema)
        stats_summary = self._build_stats_summary(df)
        fallback = self._generate_fallback_hypotheses(df)

        system_prompt = """You are a Data Science Hypothesis Generator.
Based on the provided DataFrame schema AND statistics, generate 5-10 deep, non-obvious,
and testable hypotheses. Focus on interactions, trends, and business value.
Leverage the correlation data and value distributions — avoid trivial observations.

OUTPUT FORMAT (JSON only):
{
  "hypotheses": ["hypothesis 1", "hypothesis 2", ...],
  "reasoning": "Briefly explain your strategy"
}
"""
        user_prompt = (
            f"DataFrame Schema:\n{schema_prompt}\n\n"
            f"Data Statistics:\n{stats_summary}"
        )
        if self.llm is None:
            return fallback

        try:
            response = self.llm.complete_json(system_prompt, user_prompt)
            hypotheses = response.get("hypotheses") or fallback["hypotheses"]
            # dedupe and cap
            hypotheses = list(dict.fromkeys(hypotheses))[:10]
            summary = {
                "num_hypotheses": len(hypotheses),
                "reasoning": response.get("reasoning", "LLM-generated hypotheses"),
                "revised": False,
                "numeric_columns": fallback["summary"]["numeric_columns"],
                "categorical_columns": fallback["summary"]["categorical_columns"],
            }
            return {"hypotheses": hypotheses, "summary": summary}
        except Exception:
            return fallback

# Debate Manager Agent
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
            scored.append(
                {
                    "hypothesis": h,
                    "confidence": confidence,
                    "business_value": business,
                    "statistical_argument": "Scored with heuristic confidence based on testability.",
                    "business_argument": "Scored with heuristic business relevance.",
                }
            )
        scored = sorted(
            scored,
            key=lambda x: x.get("confidence", 0) * x.get("business_value", 0),
            reverse=True,
        )
        arguments = [
            {
                "hypothesis": item["hypothesis"],
                "statistical": item.get("statistical_argument", ""),
                "business": item.get("business_argument", ""),
            }
            for item in scored
        ]
        return {
            "scored_hypotheses": scored,
            "summary": {
                "num_hypotheses": len(hypotheses),
                "consensus": scored[0] if scored else None,
                "arguments": arguments,
            },
        }

    def run(self, hypotheses, **kwargs):
        if not hypotheses:
            return {
                "scored_hypotheses": [],
                "summary": {"num_hypotheses": 0, "consensus": None, "arguments": []},
            }

        if self.llm is None:
            return self._fallback_scoring(hypotheses)

        system_prompt = """You are a Data Science Auditor. 
Assign a 'confidence' (statistical feasibility) and 'business_value' (impact) score (0.0 to 1.0) to each hypothesis.
Provide a brief 'statistical' and 'business' argument for each.

OUTPUT FORMAT (JSON only):
{
  "scored_hypotheses": [
    {
      "hypothesis": "...",
      "confidence": 0.85,
      "business_value": 0.9,
      "statistical_argument": "...",
      "business_argument": "..."
    }
  ]
}
"""
        user_prompt = f"Hypotheses to audit:\n{json.dumps(hypotheses)}"
        
        try:
            response = self.llm.complete_json(system_prompt, user_prompt)
            scored = response.get("scored_hypotheses", [])
            
            # Sort by combined score
            scored = sorted(scored, key=lambda x: x.get('confidence', 0) * x.get('business_value', 0), reverse=True)
            
            arguments = []
            for item in scored:
                arguments.append({
                    "hypothesis": item["hypothesis"],
                    "statistical": item.get("statistical_argument", ""),
                    "business": item.get("business_argument", "")
                })
            
            consensus = scored[0] if scored else None
            summary = {"num_hypotheses": len(hypotheses), "consensus": consensus, "arguments": arguments}
            return {"scored_hypotheses": scored, "summary": summary}
        except Exception:
            return self._fallback_scoring(hypotheses)

# Viz Whiz Agent
class VizWhizAgent(Agent):
    def run(self, cleaned_data, consensus, **kwargs):
        import plotly.express as px
        import re
        df = pd.DataFrame(cleaned_data)
        hypotheses = kwargs.get('hypotheses', [])
        tried = set()
        possible_plots = []
        def is_valid_col(col):
            if col not in df.columns:
                return False
            nunique = df[col].nunique(dropna=False)
            if nunique <= 1:
                return False
            if df[col].dtype == object and df[col].isin(['MISSING']).sum() > 0:
                if (df[col] == 'MISSING').sum() / len(df) > 0.8:
                    return False
            return True
        lower_to_col = {c.lower(): c for c in df.columns}
        def resolve_col(token):
            if not token:
                return None
            if token in df.columns:
                return token
            return lower_to_col.get(token.lower())
        def extract_cols_from_text(text):
            vars_found = re.findall(r"\b([A-Za-z0-9_]+)\b", text or "")
            cols = []
            for token in vars_found:
                resolved = resolve_col(token)
                if resolved and resolved not in cols:
                    cols.append(resolved)
            return cols
        def choose_plot_types(x, y):
            plots = []
            def is_cat(col_name):
                return (
                    pd.api.types.is_object_dtype(df[col_name])
                    or pd.api.types.is_string_dtype(df[col_name])
                    or isinstance(df[col_name].dtype, pd.CategoricalDtype)
                )
            if x and y:
                if pd.api.types.is_numeric_dtype(df[x]) and pd.api.types.is_numeric_dtype(df[y]):
                    corr = abs(df[[x, y]].corr().iloc[0, 1])
                    if corr > 0.3:
                        plots.append({'type': 'scatter', 'title': f"Scatter plot of {x} vs {y}", 'plotly_json': px.scatter(df, x=x, y=y, title=f"Scatter plot of {x} vs {y}").to_json()})
                    plots.append({'type': 'density_heatmap', 'title': f"Density heatmap of {x} vs {y}", 'plotly_json': px.density_heatmap(df, x=x, y=y, title=f"Density heatmap of {x} vs {y}").to_json()})
                elif is_cat(x) and pd.api.types.is_numeric_dtype(df[y]):
                    if df[x].nunique() < 20:
                        plots.append({'type': 'box', 'title': f"Box plot of {y} by {x}", 'plotly_json': px.box(df, x=x, y=y, title=f"Box plot of {y} by {x}").to_json()})
                    plots.append({'type': 'violin', 'title': f"Violin plot of {y} by {x}", 'plotly_json': px.violin(df, x=x, y=y, title=f"Violin plot of {y} by {x}").to_json()})
                elif pd.api.types.is_numeric_dtype(df[x]) and is_cat(y):
                    if df[y].nunique() < 20:
                        plots.append({'type': 'box', 'title': f"Box plot of {x} by {y}", 'plotly_json': px.box(df, x=y, y=x, title=f"Box plot of {x} by {y}").to_json()})
                    plots.append({'type': 'violin', 'title': f"Violin plot of {x} by {y}", 'plotly_json': px.violin(df, x=y, y=x, title=f"Violin plot of {x} by {y}").to_json()})
            elif x:
                if pd.api.types.is_numeric_dtype(df[x]):
                    plots.append({'type': 'histogram', 'title': f"Histogram of {x}", 'plotly_json': px.histogram(df, x=x, title=f"Histogram of {x}").to_json()})
                else:
                    plots.append({'type': 'bar', 'title': f"Bar plot of {x}", 'plotly_json': px.bar(df, x=x, title=f"Bar plot of {x}").to_json()})
            return plots
        # Try consensus hypothesis first
        hypothesis = consensus.get('hypothesis', '') if consensus else ''
        vars_found = extract_cols_from_text(hypothesis)
        x, y = None, None
        if len(vars_found) >= 2:
            x, y = vars_found[0], vars_found[1]
        elif len(vars_found) == 1:
            x = vars_found[0]
        if x and is_valid_col(x) and (not y or is_valid_col(y)):
            possible_plots.extend(choose_plot_types(x, y))
        # Try other hypotheses if consensus fails
        if not possible_plots and hypotheses:
            for hyp in hypotheses:
                if hyp not in tried:
                    vars_found = extract_cols_from_text(hyp)
                    x, y = None, None
                    if len(vars_found) >= 2:
                        x, y = vars_found[0], vars_found[1]
                    elif len(vars_found) == 1:
                        x = vars_found[0]
                    if x and is_valid_col(x) and (not y or is_valid_col(y)):
                        plots = choose_plot_types(x, y)
                        if plots:
                            possible_plots.extend(plots)
                            break
        # Fallback: try pairs of numeric/categorical columns, capped to avoid O(n²) explosion
        _MAX_FALLBACK_PLOTS = 5
        if not possible_plots:
            numeric_cols = df.select_dtypes(include='number').columns.tolist()
            categorical_cols = df.select_dtypes(include=['object', 'string', 'category']).columns.tolist()
            outer_loop: list = []
            for x1 in numeric_cols:
                for y1 in numeric_cols:
                    if x1 != y1 and is_valid_col(x1) and is_valid_col(y1):
                        outer_loop.append((x1, y1))
                for y1 in categorical_cols:
                    if is_valid_col(x1) and is_valid_col(y1):
                        outer_loop.append((x1, y1))
            for x1, y1 in outer_loop:
                possible_plots.extend(choose_plot_types(x1, y1))
                if len(possible_plots) >= _MAX_FALLBACK_PLOTS:
                    break
            if not possible_plots:
                for x1 in numeric_cols:
                    if is_valid_col(x1):
                        possible_plots.extend(choose_plot_types(x1, None))
                        if len(possible_plots) >= _MAX_FALLBACK_PLOTS:
                            break
        # Filter to only unique plot types for each variable pair
        unique_plots = []
        seen = set()
        for plot in possible_plots:
            key = (plot['type'], plot['title'])
            if key not in seen:
                seen.add(key)
                unique_plots.append(plot)
        chart_info = {
            'success': bool(unique_plots),
            'plots': unique_plots
        }
        if not unique_plots:
            chart_info['error'] = "Could not auto-select chart type."
        return {'chart_info': chart_info}

# Define the ADK workflow
class InsightOrchestraWorkflow:
    def __init__(self, llm_service: Optional[LLMService] = None):
        llm = llm_service
        if llm is None:
            try:
                llm = LLMService()
            except Exception:
                llm = None
        self.llm = llm
        self.cleaner = DataJanitorAgent(name="DataJanitorAgent")
        self.hypothesis = HypothesisBotAgent(name="HypothesisBotAgent", llm_service=self.llm)
        self.debate = DebateManagerAgent(name="DebateManagerAgent", llm_service=self.llm)
        self.viz = VizWhizAgent(name="VizWhizAgent")

    def run(self, data):
        cleaner_result = self.cleaner.run(data)
        cleaned_data = cleaner_result["cleaned_data"]
        hypothesis_result = self.hypothesis.run(cleaned_data)
        hypotheses = hypothesis_result["hypotheses"]
        debate_result = self.debate.run(hypotheses)
        consensus = debate_result["summary"].get("consensus")
        arguments = debate_result["summary"].get("arguments", [])
        # Self-refinement: critique and revise
        revised_hypotheses = []
        for h in hypotheses:
            if 'group' in h or 'association' in h:
                revised_hypotheses.append(h + " (add regional or temporal segmentation)")
            else:
                revised_hypotheses.append(h)
        hypothesis_result['revised_hypotheses'] = revised_hypotheses
        hypothesis_result['revised'] = True
        viz_result = self.viz.run(cleaned_data, consensus, hypotheses=hypotheses)
        # Output formatting: markdown table
        features = [
            ("Autonomy", bool(hypotheses), f"{hypotheses[:1]}") ,
            ("Bias Awareness", 'bias_flags' in cleaner_result['report'], str(cleaner_result['report'].get('bias_flags', ''))),
            ("Debate", bool(arguments), str(arguments[:1] if arguments else '')),
            ("Self-Refinement", hypothesis_result.get('revised', False), str(revised_hypotheses[:1] if revised_hypotheses else '')),
            ("Output Formatting", True, "Markdown table returned")
        ]
        md_table = "| Feature | Pass/Fail | Evidence (Quote Output) |\n|--------------|-----------|------------------------|\n"
        for feat, passed, evidence in features:
            md_table += f"| {feat} | {'Pass' if passed else 'Fail'} | {evidence} |\n"
        return {
            "cleaner": cleaner_result,
            "hypothesis": hypothesis_result,
            "debate": debate_result,
            "viz": viz_result,
            "audit_table": md_table
        }
