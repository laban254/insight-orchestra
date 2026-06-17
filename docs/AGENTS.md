# Agent Pipeline Guide

Complete reference for Insight Orchestra's multi-agent system.

---

## Overview

Insight Orchestra uses a **4-stage agent pipeline** where each specialized agent handles one processing stage. Agents execute sequentially, passing data between stages. The pipeline is orchestrated by [`InsightOrchestraWorkflow`](backend/app/services/adk_agents.py:226) and progress is streamed to the frontend via SSE.

```
┌─────────────────┐
│ User Input      │
│ (CSV/Database)  │
└────────┬────────┘
         │
         ▼
┌──────────────────────────────────┐
│ [1] Data Janitor Agent           │
│ Clean, validate, detect issues   │
└────────┬─────────────────────────┘
         │
         ▼
┌──────────────────────────────────┐
│ [2] Hypothesis Bot Agent         │
│ Generate testable hypotheses     │
│ (LLM-powered)                    │
└────────┬─────────────────────────┘
         │
         ▼
┌──────────────────────────────────┐
│ [3] Debate Manager Agent         │
│ Score & rank hypotheses          │
│ (LLM-powered)                    │
└────────┬─────────────────────────┘
         │
         ▼
┌──────────────────────────────────┐
│ [4] Viz Whiz Agent               │
│ Create Plotly visualizations     │
└────────┬─────────────────────────┘
         │
         ▼
┌──────────────────────────────────┐
│ Results                          │
│ (Insights + Charts)              │
└──────────────────────────────────┘
```

---

## Stage 1: Data Janitor Agent

**File**: [`adk_agents.py`](backend/app/services/adk_agents.py:8) → `DataJanitorAgent`

**Purpose**: Preprocess and validate raw data before analysis.

### Workflow

```
Input: Raw DataFrame (from CSV or database)
  ↓
[1] Check for duplicate rows → count + remove
  ↓
[2] Identify missing values per column → count + flag
  ↓
[3] Flag bias: columns with >30% missing values
  ↓
[4] Impute missing values:
    - Numeric columns → fill with column MEDIAN (robust to skewed data)
    - Categorical columns → fill with column mode (or "MISSING" if none)
  ↓
[5] Outlier detection via IQR method (flags but does NOT remove)
  ↓
[6] Detect constant columns (single unique value)
  ↓
Output: Cleaned DataFrame + metadata report
```

### Example

**Input**:
```python
DataFrame:
   name    age   salary    department
0  Alice   25    100000    Engineering
1  Bob     NaN   95000     Sales
2  Charlie 30    98000     Sales
3  Alice   25    100000    Engineering    # Duplicate
4  Diana   NaN   NaN       Marketing      # High missing
```

**Processing**:
```
1. Duplicates: Found 1, removed
2. Missing values: age (2), salary (1), department (0)
3. Imputation:
   - age: Filled with median (27.5)
   - salary: Filled with median (97000)
4. Bias flags:
   - 'salary' missing 20% → flagged
5. Outlier detection (IQR):
   - salary: 0 outliers detected
6. Constant columns: None found
```

**Output**:
```json
{
  "cleaned_data": [...],
  "report": {
    "initial_shape": [5, 4],
    "duplicates_found": 1,
    "duplicates_removed": 1,
    "missing_values": {"age": 2, "salary": 1, "department": 0},
    "total_missing": 3,
    "bias_flags": ["Column 'salary' missing for 20.0% of rows."],
    "outlier_flags": ["salary: 0 outlier(s) detected (IQR method)"],
    "constant_columns": [],
    "final_shape": [4, 4]
  }
}
```

### Implementation

The agent inherits from `google.adk.Agent` and implements a single `run(data, **kwargs)` method.

```python
class DataJanitorAgent(Agent):
    def run(self, data, **kwargs):
        df = pd.DataFrame(data)
        # Duplicate detection & removal
        # Missing value imputation (median for numeric, mode for categorical)
        # Bias flagging (>30% missing)
        # Outlier detection via IQR
        # Constant column detection
        return {"cleaned_data": [...], "report": {...}}
```

---

## Stage 2: Hypothesis Bot Agent

**File**: [`adk_agents.py`](backend/app/services/adk_agents.py:60) → `HypothesisBotAgent`

**Purpose**: Generate 5–8 specific, directional, evidence-backed insights from the cleaned dataset using an LLM grounded in actual statistics.

### Workflow

```
Input: Cleaned DataFrame
  ↓
[1] Extract schema via DataFrameSchema helper
  ↓
[2] Build statistics summary via _build_stats_summary():
    - Descriptive stats (mean, std, min, max, quartiles) for all numeric cols
    - Pearson correlations with |r| > 0.3 (labelled positive/negative)
    - Top category distributions for up to 6 categorical cols
  ↓
[3] Call LLM with system + stats prompts:
    System: forces directional insights with actual numbers
            e.g. "West region generates 34% more revenue (r=0.72)"
    User: DataFrame schema + full statistics summary
  ↓
[4] Parse LLM JSON response → deduplicate → cap at 8
  ↓
[5] On LLM failure: compute fallback from actual group means + correlations
  ↓
Output: {hypotheses: [...], summary: {num_hypotheses, reasoning, numeric_columns, categorical_columns}}
```

### Example

**LLM Output** (directional, evidence-backed):
```json
{
  "hypotheses": [
    "Age and Salary are strongly positively correlated (r=0.68) — each additional year of age corresponds to roughly $1,200 more in annual salary.",
    "'Engineering' leads 'department' with the highest average salary (42% above 'Marketing') — worth investigating whether this gap is structural.",
    "Performance scores plateau after 10 years of experience — the top quartile of experience shows only 0.3 point advantage over the median."
  ],
  "reasoning": "Grounded in correlation matrix and group-level aggregations"
}
```

### Implementation

```python
class HypothesisBotAgent(Agent):
    @staticmethod
    def _build_stats_summary(df: pd.DataFrame) -> str:
        # Descriptive stats, correlations > 0.3, category distributions
        ...

    def run(self, cleaned_data, **kwargs):
        df = pd.DataFrame(cleaned_data)
        schema_prompt = DataFrameSchema.to_prompt(DataFrameSchema.from_dataframe(df))
        stats_summary = self._build_stats_summary(df)
        # Call LLM with both schema and stats
        # Fall back to heuristic group/correlation analysis if LLM fails
```

---

## Stage 3: Debate Manager Agent

**File**: [`adk_agents.py`](backend/app/services/adk_agents.py:193) → `DebateManagerAgent`

**Purpose**: Score and rank hypotheses using an LLM that receives the actual data statistics as evidence — not just the hypothesis text.

### Scoring System

Each hypothesis is evaluated on two dimensions (0–1 scale):

| Dimension | Description |
|-----------|-------------|
| **confidence** | How strongly the hypothesis is supported by the data statistics provided |
| **business_value** | How actionable and impactful the finding is for decision-making |

The LLM also provides a `statistical_argument` (citing specific stats) and `business_argument` for each. Hypotheses are sorted by `confidence × business_value`. The top-scoring hypothesis becomes the **consensus**.

### Workflow

```
Input: List of hypothesis strings + data statistics summary
  ↓
[1] Include full statistics context in LLM prompt
    (same _build_stats_summary output from Hypothesis Bot)
  ↓
[2] LLM scores each hypothesis against the actual evidence
  ↓
[3] Parse LLM JSON response → scored_hypotheses[]
  ↓
[4] Sort by confidence × business_value (descending)
  ↓
[5] Select consensus = scored_hypotheses[0]
  ↓
[6] On LLM failure: positional fallback (0.85 → 0.60 descending)
  ↓
Output: {scored_hypotheses, summary}
```

### Example

**Output**:
```json
{
  "scored_hypotheses": [
    {
      "hypothesis": "Age and salary correlate strongly",
      "confidence": 0.85,
      "business_value": 0.9,
      "statistical_argument": "Strong correlation expected between continuous variables with sufficient range",
      "business_argument": "Understanding pay equity is critical for compensation planning"
    }
  ],
  "summary": {
    "num_hypotheses": 5,
    "consensus": {"hypothesis": "Age and salary correlate strongly", "confidence": 0.85, "business_value": 0.9},
    "arguments": [{"hypothesis": "Age and salary correlate strongly", "statistical": "...", "business": "..."}]
  }
}
```

---

## Stage 4: Viz Whiz Agent

**File**: [`adk_agents.py`](backend/app/services/adk_agents.py:272) → `VizWhizAgent`

**Purpose**: Auto-select visualization types and generate up to 6 Plotly charts, using LLM-based column selection grounded in the consensus insight.

### Chart Selection Logic

```
Consensus hypothesis
  ↓
[1] LLM column selection (_llm_pick_columns):
    Ask LLM: "Which 1-2 columns best illustrate this insight?"
    → Returns {"x": "col_name", "y": "col_name_or_null"}
  ↓
[2] If LLM selection valid → generate chart(s) based on data types:

  Numeric × Numeric
    → Scatter plot with OLS trendline (if |r| > 0.2)
    → Density heatmap (weak correlation)

  Categorical × Numeric
    → Bar chart (aggregated means, top 15 categories)
    + Box plot (if < 12 unique categories)

  Single Numeric
    → Histogram

  Single Categorical
    → Bar chart (value counts)
  ↓
[3] Fallback 1: Regex extraction from hypothesis text
[4] Fallback 2: Other hypotheses (try each)
[5] Fallback 3: Best categorical × numeric pairs from schema
[6] Fallback 4: Single numeric histograms
```

### Fallback Strategy

1. **LLM column selection** from consensus hypothesis (primary)
2. **Regex** extraction from consensus hypothesis text
3. **Other hypotheses** — try each in order
4. **Schema heuristics** — best categorical × numeric combinations
5. **Single numerics** — histogram for each numeric column

Duplicates are filtered by `(type, title)`. Maximum 6 charts returned.

### Example Output

```json
{
  "chart_info": {
    "success": true,
    "plots": [
      {
        "type": "scatter",
        "title": "Scatter plot of age vs salary",
        "plotly_json": "{...}"
      },
      {
        "type": "density_heatmap",
        "title": "Density heatmap of age vs salary",
        "plotly_json": "{...}"
      }
    ]
  }
}
```

---

## Orchestration: InsightOrchestraWorkflow

**File**: [`adk_agents.py`](backend/app/services/adk_agents.py:437) → `InsightOrchestraWorkflow`

### Sequential Execution

```python
class InsightOrchestraWorkflow:
    def __init__(self, llm_service=None):
        self.llm = llm_service or LLMService()
        self.cleaner    = DataJanitorAgent(name="DataJanitorAgent")
        self.hypothesis = HypothesisBotAgent(name="HypothesisBotAgent", llm_service=self.llm)
        self.debate     = DebateManagerAgent(name="DebateManagerAgent", llm_service=self.llm)
        self.viz        = VizWhizAgent(name="VizWhizAgent", llm_service=self.llm)

    def run(self, data):
        cleaner_result  = self.cleaner.run(data)
        cleaned_data    = cleaner_result["cleaned_data"]
        df              = pd.DataFrame(cleaned_data)

        # Build stats once — shared by Hypothesis Bot AND Debate Manager
        stats_summary     = HypothesisBotAgent._build_stats_summary(df)

        hypothesis_result = self.hypothesis.run(cleaned_data)
        hypotheses        = hypothesis_result["hypotheses"]

        # Debate Manager receives actual data stats for evidence-based scoring
        debate_result  = self.debate.run(hypotheses, data_stats=stats_summary)
        consensus      = debate_result["summary"].get("consensus")

        viz_result = self.viz.run(cleaned_data, consensus, hypotheses=hypotheses)

        return {
            "cleaner":    cleaner_result,
            "hypothesis": hypothesis_result,
            "debate":     debate_result,
            "viz":        viz_result,
            "stats":      stats_summary,
        }
```

The `/process` endpoint runs this workflow, then passes results to `InsightSummarizerAgent` for the narrative and suggested questions. Each agent stage also emits SSE progress events so the UI shows real-time status.

---

## Supporting Agents

### NLQ Agent (Natural Language Query)

**File**: [`nlq_agent.py`](backend/app/services/nlq_agent.py:40) → `NaturalLanguageQueryAgent`

**Purpose**: Answer user questions in real-time by converting natural language to pandas code.

**Process**:
```
User question + DataFrame schema
  ↓
LLM generates pandas code
  ↓
Code validated and assigned to 'result' variable
  ↓
SandboxExecutor.execute_with_retry() (up to 2 retries)
  ↓
On failure: feed error back to LLM for regeneration
  ↓
Return: NLQResponse {answer, code, reasoning, plot_json, success flag}
```

**Features**:
- Ambiguity detection — if the LLM identifies an ambiguous question, it requests clarification
- Retry with error feedback — failed code is sent back to the LLM for fixing
- Plotly fallback — if the code generates a `fig`, it's captured as `plot_json`

### Explain Agent

**File**: [`explain_agent.py`](backend/app/services/explain_agent.py:2) → `ExplainabilityAgent`

**Purpose**: Generate plain-English explanations for Plotly charts using hardcoded rules (not LLM-powered).

**Logic**: Matches chart type and column names against predefined templates. For example, a scatter plot of `age` vs `salary` generates: *"This scatter plot shows the relationship between age and salary. Each point represents an observation."*

### Insight Summarizer Agent

**File**: [`summarizer_agent.py`](backend/app/services/summarizer_agent.py:2) → `InsightSummarizerAgent`

**Purpose**: LLM-powered agent that writes a concise narrative summary of the full pipeline results and generates specific follow-up questions using actual column names.

**Process**:
```
Workflow results (cleaner + hypothesis + debate + viz stats)
  ↓
Build structured context: row count, top insight, all hypotheses, chart count
  ↓
LLM writes 3-5 sentence narrative in plain English
LLM generates 4-5 specific follow-up questions referencing real column names
  ↓
On LLM failure: template-based fallback using actual column names
  ↓
Return: {narrative: "...", suggested_questions: [...]}
```

The narrative and suggested questions are shown to the user in the chat immediately after the pipeline completes.

### Report Generator Agent

**File**: [`report_agent.py`](backend/app/services/report_agent.py:5) → `ReportGeneratorAgent`

**Purpose**: Generate an HTML report from workflow results. Produces a basic HTML document with embedded results.

---

## Configuration

### LLM Service Configuration

The agents use `LLMService` configured via environment variables in `backend/.env`:

```bash
# Cloud (OpenAI)
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini

# Cloud (DeepSeek) — OpenAI-compatible, cheap & fast
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=sk-...
DEEPSEEK_MODEL=deepseek-chat           # or deepseek-reasoner
DEEPSEEK_BASE_URL=https://api.deepseek.com

# Local (Ollama) — default
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://ollama:11434   # Docker internal hostname
OLLAMA_MODEL=qwen2.5:1.5b             # pull: docker compose exec ollama ollama pull qwen2.5:1.5b
REQUEST_TIMEOUT=600                   # 10 min recommended for CPU-only inference
```

### Sandbox Configuration

```bash
SANDBOX_ENABLED=true
SANDBOX_TIMEOUT=30       # seconds
SANDBOX_MEMORY_LIMIT=256 # MB (tracked, not enforced)
```

---

## Testing Individual Agents

```python
# Test Data Janitor
from app.services.adk_agents import DataJanitorAgent
import pandas as pd

df = pd.read_csv('test_data.csv')
agent = DataJanitorAgent()
result = agent.run(df.to_dict(orient='records'))
print(result['report'])
```

See [tests/test_agent_upgrades.py](tests/test_agent_upgrades.py) for unit tests covering Hypothesis Bot and Debate Manager with mocked LLM responses.

---

## References

- [Architecture Overview](ARCHITECTURE.md)
- [API Reference](API_REFERENCE.md)
- [Local Setup Guide](SETUP.md)
