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
    - Numeric columns → fill with column mean
    - Categorical columns → fill with column mode (or "MISSING" if none)
  ↓
[5] Detect constant columns (single unique value)
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
   - age: Filled with mean (27.5)
   - salary: Filled with median (97000)
4. Bias flags:
   - 'salary' missing 20% → flagged
5. Constant columns: None found
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
    "missing_values_imputed": true,
    "constant_columns": [],
    "final_shape": [4, 4]
  }
}
```

### Implementation

The agent inherits from `google.adk.Agent` and implements a single `run(data, **kwargs)` method. All logic (duplicate detection, missing value imputation, bias flagging) is inline — there are no separate helper methods.

```python
class DataJanitorAgent(Agent):
    def run(self, data, **kwargs):
        df = pd.DataFrame(data)
        # Duplicate detection & removal
        # Missing value imputation (mean/mode)
        # Bias flagging (>30% missing)
        # Constant column detection
        return {"cleaned_data": [...], "report": {...}}
```

---

## Stage 2: Hypothesis Bot Agent

**File**: [`adk_agents.py`](backend/app/services/adk_agents.py:48) → `HypothesisBotAgent`

**Purpose**: Generate 5–10 testable, non-obvious hypotheses from the cleaned dataset using an LLM.

### Workflow

```
Input: Cleaned DataFrame
  ↓
[1] Extract schema via DataFrameSchema helper
    - Column names, data types, sample values
    - Null counts, shape
  ↓
[2] Format schema prompt (human-readable description)
  ↓
[3] Call LLM with system prompt:
    System: "You are a Data Science Hypothesis Generator.
     Generate 5-10 deep, non-obvious, testable hypotheses.
     Focus on interactions, trends, and business value."
    User: DataFrame schema
  ↓
[4] Parse LLM JSON response
  ↓
[5] On LLM failure: return single fallback hypothesis
  ↓
Output: {hypotheses: [...], summary: {num_hypotheses, reasoning}}
```

### Example

**Input Schema** (via `DataFrameSchema.to_prompt()`):
```
DataFrame Shape: 1000 rows × 5 columns

Columns:
  - age: int64 (nulls: 12, samples: [25, 30, 42, 55, 38])
  - salary: float64 (nulls: 3, samples: [50000, 75000, 95000, 120000, 85000])
  - years_experience: int64 (nulls: 0, samples: [0, 5, 15, 25, 40])
  - department: object (nulls: 0, samples: [Engineering, Sales, HR, Marketing])
  - performance_score: float64 (nulls: 0, samples: [3.5, 4.0, 2.5, 5.0, 3.0])
```

**LLM Response**:
```json
{
  "hypotheses": [
    "Age and salary correlate strongly",
    "Engineering department has highest median salary",
    "Performance scores plateau after 10 years of experience",
    "Salary variance is higher in Sales than other departments"
  ],
  "reasoning": "Analyzed numeric distributions and category breakdowns for hidden relationships"
}
```

### Implementation

```python
class HypothesisBotAgent(Agent):
    def __init__(self, name: str, llm_service: Optional[LLMService] = None):
        super().__init__(name=name)
        self.llm = llm_service or LLMService()

    def run(self, cleaned_data, **kwargs):
        df = pd.DataFrame(cleaned_data)
        schema_prompt = DataFrameSchema.to_prompt(
            DataFrameSchema.from_dataframe(df))
        # ... call LLM, parse response ...
```

---

## Stage 3: Debate Manager Agent

**File**: [`adk_agents.py`](backend/app/services/adk_agents.py:83) → `DebateManagerAgent`

**Purpose**: Score and rank hypotheses by asking an LLM to act as a data science auditor.

### Scoring System

Each hypothesis is evaluated by the LLM on two dimensions (0–1 scale):

| Dimension | Description |
|-----------|-------------|
| **confidence** | Statistical feasibility — can this be validated with data? |
| **business_value** | Business impact — does resolving this matter? |

The LLM also provides a `statistical_argument` and `business_argument` for each hypothesis. Hypotheses are sorted by `confidence × business_value` in descending order. The top-scoring hypothesis becomes the **consensus**.

### Workflow

```
Input: List of hypothesis strings
  ↓
[1] Send to LLM with system prompt:
    System: "You are a Data Science Auditor.
     Assign confidence and business_value (0.0 to 1.0)
     to each hypothesis. Provide arguments."
  ↓
[2] Parse LLM JSON response → scored_hypotheses[]
  ↓
[3] Sort by confidence × business_value (descending)
  ↓
[4] Select consensus = scored_hypotheses[0]
  ↓
[5] On LLM failure: return empty array with error
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

**File**: [`adk_agents.py`](backend/app/services/adk_agents.py:130) → `VizWhizAgent`

**Purpose**: Auto-select visualization types and generate Plotly JSON for rendering in the frontend.

### Chart Selection Logic

The agent uses regex to extract variable names from the consensus hypothesis, then checks data types to select chart types:

```
Consensus hypothesis
  ↓
Extract variable names via regex (\b[A-Za-z0-9_]+\b)
  ↓
Validate columns exist and have >1 unique value
  ↓
Determine data types:
  ↓
Match to chart type:

  Numeric × Numeric
    → Scatter plot (if correlation > 0.3)
    → Density heatmap

  Categorical × Numeric
    → Box plot (if categories < 20)
    → Violin plot

  Numeric × Categorical
    → Box plot (swapped axes, if categories < 20)
    → Violin plot (swapped axes)

  Single Numeric
    → Histogram

  Single Categorical
    → Bar chart
```

### Fallback Strategy

1. Try consensus hypothesis variables first
2. Try other hypotheses
3. Try all numeric × numeric column pairs
4. Try all numeric × categorical column pairs
5. Try all single numeric columns

Duplicates are filtered out (unique by type + title).

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

**File**: [`adk_agents.py`](backend/app/services/adk_agents.py:226) → `InsightOrchestraWorkflow`

### Sequential Execution

```python
class InsightOrchestraWorkflow:
    def __init__(self, llm_service=None):
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

        # Self-refinement: revise hypotheses with segmentation suggestions
        revised_hypotheses = []
        for h in hypotheses:
            if 'group' in h or 'association' in h:
                revised_hypotheses.append(h + " (add regional or temporal segmentation)")
            else:
                revised_hypotheses.append(h)

        viz_result = self.viz.run(cleaned_data, consensus, hypotheses=hypotheses)

        return {
            "cleaner": cleaner_result,
            "hypothesis": hypothesis_result,
            "debate": debate_result,
            "viz": viz_result,
            "audit_table": md_table  # Markdown audit summary
        }
```

### Self-Refinement

After the Debate Manager scores hypotheses, the workflow applies a simple keyword-based refinement: hypotheses containing "group" or "association" get a segmentation suggestion appended. This is tracked in the audit table output.

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

**Purpose**: Concatenate workflow results into a text summary. Uses simple string formatting, not LLM.

### Report Generator Agent

**File**: [`report_agent.py`](backend/app/services/report_agent.py:5) → `ReportGeneratorAgent`

**Purpose**: Generate an HTML report from workflow results. Produces a basic HTML document with embedded results.

---

## Configuration

### LLM Service Configuration

The agents use `LLMService` configured via environment variables:

```bash
# In .env (project root)
LLM_PROVIDER=openai              # openai | ollama
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini

# Or for local LLM:
# LLM_PROVIDER=ollama
# OLLAMA_BASE_URL=http://localhost:11434
# OLLAMA_MODEL=llama3.1:8b
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
