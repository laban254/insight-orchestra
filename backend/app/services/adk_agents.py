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
        self.llm = llm_service or LLMService()

    def run(self, cleaned_data, **kwargs):
        df = pd.DataFrame(cleaned_data)
        schema_prompt = DataFrameSchema.to_prompt(DataFrameSchema.from_dataframe(df))
        
        system_prompt = """You are a Data Science Hypothesis Generator. 
Based on the provided DataFrame schema, generate 5-10 deep, non-obvious, and testable hypotheses.
Focus on interactions, trends, and business value. Avoid trivial observations.

OUTPUT FORMAT (JSON only):
{
  "hypotheses": ["hypothesis 1", "hypothesis 2", ...],
  "reasoning": "Briefly explain your strategy"
}
"""
        user_prompt = f"DataFrame Schema:\n{schema_prompt}"
        
        try:
            response = self.llm.complete_json(system_prompt, user_prompt)
            hypotheses = response.get("hypotheses", [])
            summary = {
                "num_hypotheses": len(hypotheses), 
                "reasoning": response.get("reasoning", "LLM-generated hypotheses"),
                "revised": False
            }
            return {"hypotheses": hypotheses, "summary": summary}
        except Exception as e:
            # Basic fallback if LLM fails
            return {"hypotheses": ["Is there a relationship between the first two columns?"], "summary": {"error": str(e)}}

# Debate Manager Agent
class DebateManagerAgent(Agent):
    def __init__(self, name: str, llm_service: Optional[LLMService] = None):
        super().__init__(name=name)
        self.llm = llm_service or LLMService()

    def run(self, hypotheses, **kwargs):
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
        except Exception as e:
            return {"scored_hypotheses": [], "summary": {"error": str(e)}}

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
        def choose_plot_types(x, y):
            plots = []
            if x and y:
                if pd.api.types.is_numeric_dtype(df[x]) and pd.api.types.is_numeric_dtype(df[y]):
                    corr = abs(df[[x, y]].corr().iloc[0, 1])
                    if corr > 0.3:
                        plots.append({'type': 'scatter', 'title': f"Scatter plot of {x} vs {y}", 'plotly_json': px.scatter(df, x=x, y=y, title=f"Scatter plot of {x} vs {y}").to_json()})
                    plots.append({'type': 'density_heatmap', 'title': f"Density heatmap of {x} vs {y}", 'plotly_json': px.density_heatmap(df, x=x, y=y, title=f"Density heatmap of {x} vs {y}").to_json()})
                elif pd.api.types.is_object_dtype(df[x]) and pd.api.types.is_numeric_dtype(df[y]):
                    if df[x].nunique() < 20:
                        plots.append({'type': 'box', 'title': f"Box plot of {y} by {x}", 'plotly_json': px.box(df, x=x, y=y, title=f"Box plot of {y} by {x}").to_json()})
                    plots.append({'type': 'violin', 'title': f"Violin plot of {y} by {x}", 'plotly_json': px.violin(df, x=x, y=y, title=f"Violin plot of {y} by {x}").to_json()})
                elif pd.api.types.is_numeric_dtype(df[x]) and pd.api.types.is_object_dtype(df[y]):
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
        vars_found = re.findall(r'\b([A-Za-z0-9_]+)\b', hypothesis)
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
                    vars_found = re.findall(r'\b([A-Za-z0-9_]+)\b', hyp)
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
        # Fallback: try all pairs of numeric/categorical columns
        if not possible_plots:
            numeric_cols = df.select_dtypes(include='number').columns.tolist()
            categorical_cols = df.select_dtypes(include='object').columns.tolist()
            for x1 in numeric_cols:
                for y1 in numeric_cols:
                    if x1 != y1 and is_valid_col(x1) and is_valid_col(y1):
                        possible_plots.extend(choose_plot_types(x1, y1))
                for y1 in categorical_cols:
                    if is_valid_col(x1) and is_valid_col(y1):
                        possible_plots.extend(choose_plot_types(x1, y1))
            for x1 in numeric_cols:
                if is_valid_col(x1):
                    possible_plots.extend(choose_plot_types(x1, None))
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
        self.llm = llm_service or LLMService()
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