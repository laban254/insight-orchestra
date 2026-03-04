# Agent Pipeline Guide

Understanding how Insight Orchestra's multi-agent system works.

---

## Overview

Insight Orchestra uses a **4-stage agent pipeline** where each specialized agent handles one critical task. Agents execute sequentially, passing data between stages.

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
└────────┬─────────────────────────┘
         │
         ▼
┌──────────────────────────────────┐
│ [3] Debate Manager Agent         │
│ Score & rank hypotheses          │
└────────┬─────────────────────────┘
         │
         ▼
┌──────────────────────────────────┐
│ [4] Viz Whiz Agent               │
│ Create visualizations            │
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

**Purpose**: Clean data and detect quality issues

**Location**: `backend/app/services/adk_agents.py` → `DataJanitorAgent`

### Workflow

```python
Input: Raw DataFrame (from CSV or database)
  ↓
[1] Check for duplicates
    - Count duplicate rows
    - Remove if found
  ↓
[2] Identify missing values
    - Count per column
    - Calculate percentage
  ↓
[3] Handle missing data
    - Numeric columns: Impute with mean
    - Categorical: Impute with mode
  ↓
[4] Flag data quality issues
    - Column with >30% missing = bias flag
    - Constant columns (single value)
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
   - 'department' has 0 missing → OK
5. Constant columns: None found
```

**Output**:
```json
{
  "cleaned_data": [
    {"name": "Alice", "age": 25, "salary": 100000, "department": "Engineering"},
    {"name": "Bob", "age": 27.5, "salary": 95000, "department": "Sales"},
    {"name": "Charlie", "age": 30, "salary": 98000, "department": "Sales"},
    {"name": "Diana", "age": 27.5, "salary": 97000, "department": "Marketing"}
  ],
  "report": {
    "initial_shape": [5, 4],
    "duplicates_removed": 1,
    "missing_values": {"age": 2, "salary": 1},
    "bias_flags": ["salary missing 20% of values"],
    "final_shape": [4, 4]
  }
}
```

### Key Methods

```python
class DataJanitorAgent(Agent):
    def run(self, data, **kwargs):
        # Main execution method
        # Returns: {"cleaned_data": [...], "report": {...}}
        
    def _detect_duplicates(self, df):
        # Count exact row duplicates
        
    def _handle_missing(self, df):
        # Impute NaN values using statistical methods
        
    def _flag_biases(self, df):
        # Identify problematic data patterns
```

---

## Stage 2: Hypothesis Bot Agent

**Purpose**: Generate testable hypotheses using LLM

**Location**: `backend/app/services/adk_agents.py` → `HypothesisBotAgent`

### Workflow

```
Input: Cleaned DataFrame + schema
  ↓
[1] Extract schema
    - Column names
    - Data types (numeric, categorical, datetime)
    - Data statistics (min, max, mean, unique values)
  ↓
[2] Format schema prompt
    - Create language-friendly description
    - Example: "age (int): 18-75, mean 35"
  ↓
[3] Call LLM with system prompt
    System: "You are a data scientist. Generate 5-10 deep hypotheses..."
    User: "Schema: {columns, types, stats}"
  ↓
[4] Parse LLM response
    - Extract JSON hypothesis list
    - Include reasoning explanation
  ↓
Output: List of hypotheses with metadata
```

### Example

**Input Schema**:
```
DataFrame: 1000 rows, 5 columns

Columns:
- age (int): min=18, max=75, mean=42
- salary (float): min=$25k, max=$200k, mean=$85k
- years_experience (int): min=0, max=40, mean=15
- department (category): Engineering, Sales, HR, Marketing
- performance_score (float): min=1, max=5, mean=3.5
```

**LLM Prompt**:
```
System: "Generate 5-10 deep, non-obvious, testable hypotheses 
based on provided data schema. Focus on interactions and trends."

User Prompt:
"Dataset: 1000 employee records
Columns: age (18-75, mean 42), salary (25k-200k, mean 85k), 
years_experience (0-40, mean 15), department (4 categories), 
performance_score (1-5, mean 3.5)

Generate hypotheses."
```

**LLM Response**:
```json
{
  "hypotheses": [
    "Age and salary correlate strongly (r > 0.7)",
    "Engineering department has highest median salary",
    "Performance scores plateau after 10 years of experience",
    "Salary variance is higher in Sales than other departments",
    "Performance negatively correlates with age over 55"
  ],
  "reasoning": "Analyzed numeric distributions and category breakdowns
    for hidden relationships and interactions"
}
```

### Key Methods

```python
class HypothesisBotAgent(Agent):
    def __init__(self, llm_service: LLMService):
        self.llm = llm_service
        
    def run(self, cleaned_data, **kwargs):
        # Generate hypotheses using LLM
        # Returns: {"hypotheses": [...], "summary": {...}}
        
    def _schema_from_dataframe(self, df):
        # Convert DataFrame to LLM-friendly schema description
        
    def _call_llm(self, schema_text):
        # Invoke LLM with formatted prompt
```

### LLM Configuration

The agent uses settings from `LLMService`:

```bash
# Use Ollama (local)
LLM_PROVIDER=ollama
LLM_MODEL=llama2

# Or use OpenAI (cloud)
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-xxxxx
OPENAI_MODEL=gpt-4
```

---

## Stage 3: Debate Manager Agent

**Purpose**: Score and rank hypotheses by quality

**Location**: `backend/app/services/adk_agents.py` → `DebateManagerAgent`

### Scoring System

Each hypothesis is scored on multiple dimensions (0-1 scale):

```python
score = 0.4 * statistical_confidence +
        0.3 * business_impact +
        0.2 * testability +
        0.1 * novelty
```

| Dimension | Weight | Criteria |
|-----------|--------|----------|
| **Statistical Confidence** | 0.4 | Can it be validated with data? |
| **Business Impact** | 0.3 | Does resolving it matter? |
| **Testability** | 0.2 | Can we write code to verify? |
| **Novelty** | 0.1 | Is it surprising/non-obvious? |

### Workflow

```
Input: List of hypotheses from Hypothesis Bot
  ↓
[1] Validate each hypothesis
    - Check if it's testable
    - Identify required analysis type
  ↓
[2] Score hypothesis
    - Calculate statistical confidence
    - Estimate business impact
    - Assign testability score
    - Rate novelty
  ↓
[3] Rank by score
    - Sort descending by total score
  ↓
[4] Filter & return top N
    - Return top 3-5 hypotheses
  ↓
Output: Ranked, scored hypotheses
```

### Example

**Input Hypotheses**:
```
1. "Age and salary correlate"
2. "Engineering has highest salary"
3. "Salary is over $50k"
4. "Performance plateaus after 10 years"
```

**Scoring Process**:

| Hypothesis | Statistical | Business | Testability | Novelty | **Total** | Rank |
|------------|-------------|----------|-------------|---------|----------|------|
| Age-salary correlation | 0.85 | 0.9 | 0.95 | 0.6 | **0.83** | 1 ⭐ |
| Engineering highest salary | 0.75 | 0.7 | 0.9 | 0.7 | **0.74** | 2 |
| Performance plateaus | 0.70 | 0.8 | 0.85 | 0.85 | **0.77** | 3 |
| Salary over $50k | 0.60 | 0.2 | 0.8 | 0.1 | **0.44** | ❌ Rejected |

**Output**:
```json
{
  "ranked_hypotheses": [
    {
      "rank": 1,
      "hypothesis": "Age and salary correlate",
      "score": 0.83,
      "breakdown": {
        "statistical_confidence": 0.85,
        "business_impact": 0.9,
        "testability": 0.95,
        "novelty": 0.6
      },
      "recommendation": "PURSUE - Strong correlation with high business value"
    },
    {
      "rank": 2,
      "hypothesis": "Engineering has highest salary",
      "score": 0.74,
      ...
    }
  ],
  "filtered_out": ["Salary over $50k (low novelty/impact)"]
}
```

### Key Methods

```python
class DebateManagerAgent(Agent):
    def run(self, hypotheses, data, **kwargs):
        # Score and rank hypotheses
        # Returns: {"ranked_hypotheses": [...]}
        
    def _calculate_statistical_confidence(self, hypothesis, df):
        # Estimate how strongly this hypothesis is supported by data
        
    def _estimate_business_impact(self, hypothesis):
        # Score based on business relevance keywords
        
    def _score_testability(self, hypothesis):
        # Can we write code to verify this?
```

---

## Stage 4: Viz Whiz Agent

**Purpose**: Auto-select visualization and generate Plotly code

**Location**: `backend/app/services/adk_agents.py` → `VizWhizAgent`

### Chart Selection Logic

The agent chooses the best chart type based on data:

```
Hypothesis analysis
  ↓
Extract variables: X (independent), Y (dependent)
  ↓
Determine types:
  - Numeric: continuous values
  - Categorical: discrete categories
  - Datetime: time-based
  ↓
Match to chart type:

  Numeric vs Numeric
    → Scatter plot (show correlation)
    
  Categorical vs Numeric
    → Box plot (show distribution)
    → Bar chart (show averages)
    
  Categorical vs Categorical
    → Grouped bar chart
    → Stacked bar chart
    
  Time vs Numeric
    → Line chart (trend over time)
    
  Distribution
    → Histogram
    → KDE (kernel density estimate)
```

### Example Visualizations

#### Example 1: Age vs Salary (Numeric-Numeric)

```python
# Generated code
import plotly.express as px

fig = px.scatter(
    df,
    x='age',
    y='salary',
    title='Age vs Salary Correlation',
    labels={'age': 'Age', 'salary': 'Salary ($)'},
    trendline='ols'  # Add trend line
)
fig.show()
```

**Output**: Interactive scatter plot with trend line

#### Example 2: Department Salary (Categorical-Numeric)

```python
import plotly.graph_objects as go

fig = go.Figure(data=[
    go.Box(y=df[df['department']=='Engineering']['salary'], name='Engineering'),
    go.Box(y=df[df['department']=='Sales']['salary'], name='Sales'),
    ...
])
fig.update_layout(title='Salary Distribution by Department')
fig.show()
```

**Output**: Box plots showing distribution per department

### Workflow

```
Input: Top hypothesis + cleaned data
  ↓
[1] Parse hypothesis
    - Extract X variable and Y variable
    - Identify relationship type
  ↓
[2] Analyze column types
    - X: numeric? categorical? datetime?
    - Y: numeric? categorical?
  ↓
[3] Select chart type
    - Match type combination to optimal chart
  ↓
[4] Generate Plotly code
    - Create figure object
    - Configure axes and labels
    - Add styling
  ↓
[5] Render to HTML
    - Convert to interactive HTML
  ↓
Output: Chart code + HTML
```

### Key Methods

```python
class VizWhizAgent(Agent):
    def run(self, hypothesis, data, **kwargs):
        # Generate visualization
        # Returns: {"chart_code": "...", "html": "..."}
        
    def _infer_variable_types(self, x_col, y_col, df):
        # Determine if columns are numeric/categorical/time
        
    def _select_chart_type(self, x_type, y_type):
        # Map data types to optimal chart
        
    def _generate_plotly_code(self, chart_type, x, y, df):
        # Create Plotly visualization code
```

---

## Supporting Agents

### NLQ Agent (Natural Language Query)

**Purpose**: Answer user questions in real-time

**Location**: `backend/app/services/nlq_agent.py`

**Process**:
```
User: "What's the correlation between age and salary?"
  ↓
Context: DataFrame + schema
  ↓
LLM generates Python code:
  "from scipy.stats import pearsonr
   corr, p_value = pearsonr(df['age'], df['salary'])"
  ↓
SandboxExecutor runs safely
  ↓
Return: Correlation value + visualization
```

### Explain Agent

**Purpose**: Explain results in plain English

**Location**: `backend/app/services/explain_agent.py`

**Example**:
```
Hypothesis: "Age and salary correlate"
Result: r=0.72, p-value < 0.001
  ↓
Explanation: "There is a strong positive correlation 
between age and salary (r=0.72). This means older 
employees tend to earn more, with statistical 
significance (p < 0.001)."
```

---

## Agent Execution Model

### Sequential Execution

```python
class InsightOrchestraWorkflow:
    def run(self, df):
        # Stage 1: Clean
        cleaned = self.data_janitor.run(df)
        
        # Stage 2: Hypothesize
        hypotheses = self.hypothesis_bot.run(cleaned['cleaned_data'])
        
        # Stage 3: Debate
        ranked = self.debate_manager.run(hypotheses['hypotheses'])
        
        # Stage 4: Visualize
        top_hypothesis = ranked['ranked_hypotheses'][0]
        visualization = self.viz_whiz.run(
            top_hypothesis['hypothesis'],
            cleaned['cleaned_data']
        )
        
        return {
            'cleaned_summary': cleaned['report'],
            'hypotheses': ranked['ranked_hypotheses'],
            'top_insight': visualization
        }
```

### Future: Parallel Execution

Agents 2, 3, 4 can run in parallel.
Parallelization infrastructure is in place; full implementation coming soon.

async def run_parallel(self, df):
    cleaned = self.data_janitor.run(df)
    
    # Run 3 agents in parallel
    results = await asyncio.gather(
        self.hypothesis_bot.run_async(cleaned),
        self.explain_agent.run_async(cleaned),
        self.summarizer_agent.run_async(cleaned)
    )
    
    return combine(results)
```

---

## Extending the System

### Adding a New Agent

1. **Create agent class** in `backend/app/services/adk_agents.py`:
   ```python
   class MyCustomAgent(Agent):
       def run(self, data, **kwargs):
           # Your logic here
           return {"output": "..."}
   ```

2. **Integrate into workflow** in `InsightOrchestraWorkflow`:
   ```python
   self.my_agent = MyCustomAgent()
   
   def run(self, df):
       # ... existing stages ...
       custom_result = self.my_agent.run(...)
       # ... rest of pipeline ...
   ```

3. **Expose via API** in `backend/app/api/endpoints.py`:
   ```python
   @router.post("/my-custom-endpoint")
   async def my_endpoint(request: MyRequest):
       # Call your agent
   ```

---

## Configuration

### Agent Parameters

```python
# LLM Service configuration
LLM_SERVICE = LLMService(
    provider="ollama",
    model="llama2",
    base_url="http://localhost:11434"
)

# Agent instantiation with LLM
hypothesis_bot = HypothesisBotAgent(
    name="hypothesis-bot",
    llm_service=LLM_SERVICE
)
```

### Timeout & Limits

```python
# In backend/.env
AGENT_EXECUTION_TIMEOUT_SEC=30
MAX_HYPOTHESES=10
MAX_RANKED_HYPOTHESES=5
SANDBOX_MEMORY_LIMIT_MB=512
```

---

## Monitoring & Debugging

### Enable Debug Logging

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Agent Metrics

Each agent tracks:
- Execution time
- Input size
- Output size
- Error rate
- Cache hits (future)

### Testing Individual Agents

```python
# Test Data Janitor
from app.services.adk_agents import DataJanitorAgent
import pandas as pd

df = pd.read_csv('test_data.csv')
agent = DataJanitorAgent()
result = agent.run(df.to_dict(orient='records'))
print(result['report'])
```

---

## References

- [Architecture Overview](ARCHITECTURE.md)
- [API Reference](API_REFERENCE.md)
- [Local Setup Guide](SETUP.md)
