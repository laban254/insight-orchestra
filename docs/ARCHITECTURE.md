# Insight Orchestra - Architecture Overview

## System Architecture


Insight Orchestra is built on a **multi-agent collaborative pipeline** with emphasis on flexibility, privacy, transparency, and pluggable LLM backends (API or local execution).

```
┌─────────────────────────────────────────────────────────────┐
│                   Frontend (Next.js 14)                      │
│  - FileUpload / DatabaseConnect                             │
│  - ChatPanel (Q&A interface)                                │
│  - Plotly Visualizations                                    │
└──────────────────────┬──────────────────────────────────────┘
                       │ REST API (JSON)
                       ▼
┌─────────────────────────────────────────────────────────────┐
│              FastAPI Backend (Python)                        │
│                                                               │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  API Layer                                           │   │
│  │  - Upload Handler  - Database Connectors            │   │
│  │  - Query Router    - Session Management             │   │
│  └──────────────────────────────────────────────────────┘   │
│                       ▼                                       │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Services Layer (Agent Orchestration)                │   │
│  │  • Data Janitor Agent      → Cleaning & validation  │   │
│  │  • Hypothesis Bot Agent    → Insight generation    │   │
│  │  • Debate Manager Agent    → Quality filtering      │   │
│  │  • Viz Whiz Agent          → Visualization         │   │
│  │  • NLQ Agent               → Natural language Q&A   │   │
│  │  • LLM Service             → Model interface        │   │
│  │  • Sandbox Executor        → Safe code execution    │   │
│  └──────────────────────────────────────────────────────┘   │
│                       ▼                                       │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Data Layer                                          │   │
│  │  • CSV Storage     • Database Connectors            │   │
│  │  • Session Cache   • Result Export                  │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
         ▼                                    ▼
    ┌─────────────┐                   ┌──────────────────┐
    │ Local Files │                   │ LLM Providers    │
    │ (Uploads)   │                   │ • OpenAI (API)   │
    │ • CSVs      │                   │ • Anthropic (API)|
    │             │                   │ • Ollama (local) │
    └─────────────┘                   └──────────────────┘
```

---

## Component Breakdown

### 1. Frontend Layer (Next.js 14)

**Location**: `frontend/`

**Responsibilities**:
- User interface for data ingestion (file upload / DB connection)
- Interactive chat panel for Q&A
- Real-time visualization rendering
- Session state management
- Code review before execution

**Key Components**:
- `FileUpload.tsx` - CSV file selection and upload
- `DatabaseConnect.tsx` - DB connection form
- `ChatPanel.tsx` - Main analysis interface
- `Plotly Charts` - Interactive visualizations

**Technologies**:
- React 18+ with hooks
- Next.js 14 (App Router)
- Tailwind CSS + shadcn/ui
- Monaco Editor (code display)
- Plotly.js (charts)

---

### 2. Backend API Layer (FastAPI)

**Location**: `backend/app/api/`

**Responsibilities**:
- HTTP request routing
- File upload management
- Database connector orchestration
- Session lifecycle management
- Response formatting

**Key Files**:
- `endpoints.py` - Main API routes
- `connectors.py` - Database connection handlers
- `export.py` - Result export endpoints
- `sessions.py` - Session storage

**API Routes**:
```
POST   /upload                 → Save CSV, return file_path
POST   /connectors/connect     → Establish DB connection
POST   /process                → Run agent pipeline
POST   /nlq                    → Process natural language query
GET    /health                 → Service status
```

---

### 3. Services Layer (Agent Orchestration)

**Location**: `backend/app/services/`

This is the **intelligent core** of Insight Orchestra.

#### 3.1 Data Janitor Agent
**File**: `adk_agents.py` → `DataJanitorAgent`

**Purpose**: Data preprocessing and validation

**Workflow**:
```
Input DataFrame
    ↓
Check duplicates → Remove if found
    ↓
Identify missing values → Impute (mean/mode)
    ↓
Flag data quality issues
    ↓
Detect constant columns
    ↓
Output: Cleaned DataFrame + metadata report
```

**Output Structure**:
```json
{
  "cleaned_data": [...],
  "report": {
    "initial_shape": [1000, 15],
    "duplicates_removed": 5,
    "missing_values": {"age": 12, "salary": 3},
    "bias_flags": ["Column 'age' missing 15% of values"],
    "final_shape": [995, 15]
  }
}
```

#### 3.2 Hypothesis Bot Agent
**File**: `adk_agents.py` → `HypothesisBotAgent`

**Purpose**: Generate testable hypotheses using LLM

**Workflow**:
```
DataFrame schema
    ↓
Construct schema prompt (columns, types, stats)
    ↓
Send to LLM with system prompt
    ↓
Parse LLM response (JSON format enforced)
    ↓
Output: List of hypotheses + reasoning
```

**Example Output**:
```json
{
  "hypotheses": [
    "Age and salary show positive correlation",
    "Department type affects sales performance",
    "Geographic region impacts customer retention"
  ],
  "reasoning": "Analyzed numeric distributions and categorical patterns"
}
```

#### 3.3 Debate Manager Agent
**File**: `adk_agents.py` → `DebateManagerAgent`

**Purpose**: Score and rank hypotheses by quality

**Scoring Criteria**:
- Statistical confidence (0-1 scale)
- Business impact (0-1 scale)
- Testability (0-1 scale)
- Novelty (0-1 scale)

**Output**: Top 3-5 hypotheses ranked

#### 3.4 Viz Whiz Agent
**File**: `adk_agents.py` → `VizWhizAgent`

**Purpose**: Auto-select visualization and generate Plotly code

**Logic**:
```
Hypothesis + Data Schema
    ↓
Determine variable types (numeric vs categorical)
    ↓
Select chart type:
  - Numeric vs Numeric    → Scatter plot
  - Categorical vs Numeric → Box plot / Bar chart
  - Time series           → Line chart
  - Distribution          → Histogram / KDE
    ↓
Generate Plotly code
    ↓
Output: HTML + interactive chart
```

#### 3.5 NLQ Agent (Natural Language Query)
**File**: `nlq_agent.py` → `NaturalLanguageQueryAgent`

**Purpose**: Convert natural language to executable code

**Process**:
```
User question + DataFrame schema
    ↓
Prompt LLM to generate pandas/SQL
    ↓
Extract code from response
    ↓
Pass to Sandbox Executor
    ↓
Return results + visualization
```

**Example**:
```
Input: "Show me average salary by department"
Output Code: df.groupby('department')['salary'].mean()
```

#### 3.6 LLM Service
**File**: `llm_service.py` → `LLMService`

**Purpose**: Unified interface to multiple LLM providers

**Supported Providers**:
- **OpenAI** (GPT-3.5, GPT-4) - Cloud-based
- **Ollama** (Llama 2, Mistral, etc.) - Local execution
- **Anthropic** (Claude) - Cloud-based

**Methods**:
```python
complete_text(system_prompt, user_prompt) → str
complete_json(system_prompt, user_prompt) → dict
```

**Configuration**:
- Provider selected via `LLM_PROVIDER` env var
- Model name via `LLM_MODEL`
- Ollama endpoint via `OLLAMA_BASE_URL`

#### 3.7 Sandbox Executor
**File**: `sandbox_executor.py` → `SandboxExecutor`

**Purpose**: Safely execute generated code without security risks

**Safety Features**:
- Uses **RestrictedPython** (removes dangerous builtins)
- Blocks file I/O (`open()`, `os.system()`)
- Blocks network calls (`requests`, `urllib`)
- Blocks code injection (`exec()`, `compile()`)
- Prevents infinite loops (execution timeout)
- Limits memory usage

**Allowed Operations**:
```python
# ✅ ALLOWED
df.groupby(...).agg(...)
pd.merge(...)
np.mean(...)
df[df['col'] > 5]

# ❌ BLOCKED
os.remove('file.txt')
requests.get('http://...')
open('file.txt', 'w')
exec('malicious_code')
__import__('subprocess')
```

**Execution Flow**:
```
Generated code string
    ↓
Compile with RestrictedPython
    ↓
Execute in restricted environment (timeout: 30s)
    ↓
Capture output + errors
    ↓
Return results
```

---

### 4. Data Connectors

**Location**: `backend/app/connectors/`

**Supported Data Sources**:
- **CSV** - File-based, auto-detection
- **PostgreSQL** - Enterprise SQL databases
- **MySQL/MariaDB** - Open-source SQL
- **SQLite** - Embedded, zero-config
- **DuckDB** - Analytical queries, fast

**Base Interface** (`base.py`):
```python
class BaseConnector(ABC):
    @abstractmethod
    def connect(self, connection_string: str) → None
    
    @abstractmethod
    def get_schema(self) → dict
    
    @abstractmethod
    def execute_query(self, sql: str) → pd.DataFrame
    
    @abstractmethod
    def test_connection(self) → bool
```

**Safety**: All connectors enforce read-only queries (SELECT only).

---

### 5. Session Management

**Location**: `backend/app/api/sessions.py`

**Purpose**: Maintain user state across requests

**Data Stored Per Session**:
- File path / DB connection ID
- Cleaned DataFrame (in-memory)
- Agent output history
- User chat messages
- Generated visualizations

**Storage Options**:
- **MVP**: In-memory dict (single-process)
- **Production**: Redis (distributed, persistent)

---

## Data Flow: End-to-End

### Scenario: User uploads CSV and asks a question

```
[1] User uploads file
    ↓
    POST /upload
    ↓
    File saved to backend/uploads/{uuid}_{filename}.csv
    ↓
    Return file_path to frontend

[2] Frontend triggers processing
    ↓
    POST /process with file_path
    ↓
    API loads DataFrame from file
    ↓
    InsightOrchestraWorkflow.run()
    ├─ Data Janitor Agent: Clean data
    ├─ Hypothesis Bot Agent: Generate hypotheses
    ├─ Debate Manager Agent: Score & rank
    └─ Viz Whiz Agent: Create visualization
    ↓
    Return: cleaned_summary + top_insights + viz_html
    ↓
    Frontend displays results

[3] User asks question in chat
    ↓
    POST /nlq with {file_path, question}
    ↓
    NLQAgent.run()
    ├─ Generate pandas/SQL code
    ├─ SandboxExecutor.execute(code)
    └─ Create visualization
    ↓
    Return: code + results + chart
    ↓
    Frontend shows both code and results
```

---

## Key Design Patterns

### 1. Agent Pattern
Each agent is an independent, focused worker:
- **Single Responsibility**: One job per agent
- **Composition**: Chain agents for complex workflows
- **Async-Ready**: Can be parallelized with proper context

### 2. Sandbox Pattern
Untrusted code execution with safety guarantees:
- **Restricted Environment**: Limited builtins
- **Timeout Protection**: Prevent infinite loops
- **Failure Isolation**: Bad code doesn't crash system

### 3. Provider Abstraction
LLM agnostic design:
- **Interface Segregation**: Services use `LLMService` interface
- **Factory Pattern**: Provider instantiation centralized
- **Configuration-Driven**: Providers chosen via env vars

### 4. Session Isolation
User data never mixed:
- **Per-User Sessions**: Unique session IDs
- **Ephemeral by Default**: Sessions expire after inactivity
- **Explicit Export**: Users must export to persist

---

## Performance Considerations

### Bottlenecks & Optimizations

| Component | Bottleneck | Solution |
|-----------|-----------|----------|
| LLM Inference | Network latency (cloud) | Use Ollama locally |
| Data Loading | Large CSV parsing | Use DuckDB/ Parquet |
| Agent Pipeline | Sequential execution | Parallelize independent agents |
| Session Storage | In-memory limit | Migrate to Redis |

### Scaling Strategy

**MVP → Production**:
1. In-memory sessions → Redis
2. Single FastAPI process → Gunicorn + load balancer
3. Local Ollama → Ollama cluster or LLM API
4. File uploads to disk → Object storage (S3/GCS)

---

## Security Model

### Threat Model & Mitigations

| Threat | Mitigation |
|--------|-----------|
| Malicious SQL injection | Parameterized queries, read-only mode |
| Code execution exploits | RestrictedPython sandbox |
| Data exfiltration | No network access from sandbox |
| Resource exhaustion | Execution timeout + memory limits |
| Session hijacking | Secure session tokens, HTTPS |

---

## Technology Choices

### Why These Tools?

| Tool | Reason |
|------|--------|
| **FastAPI** | Type-safe, async-ready, auto-docs |
| **Pandas** | Data manipulation gold standard |
| **RestrictedPython** | Safe dynamic code execution |
| **Google ADK** | Structured agent orchestration |
| **Ollama** | Local LLMs without GPU hassle |
| **Next.js** | Full-stack React with SSR |
| **Docker** | Reproducible deployments |

---

## Future Architecture Improvements

- **Event-Driven Pipeline**: Kafka for async agent execution
- **Distributed Agents**: Multi-machine agent scaling
- **Query Caching**: Memoize expensive LLM calls
- **Real-Time Collaboration**: WebSocket for multi-user sessions
- **ML Pipeline Tracking**: Version hypotheses and results
