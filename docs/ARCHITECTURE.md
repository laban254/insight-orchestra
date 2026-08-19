# Insight Orchestra — Architecture Overview

## System Architecture

Insight Orchestra is a **multi-agent AI data analysis platform** with a three-layer architecture: a Next.js frontend, a FastAPI backend, and a services layer for agent orchestration and sandboxed code execution. LLM providers are pluggable (OpenAI API or local Ollama).

```
┌─────────────────────────────────────────────────────────────┐
│                   Frontend (Next.js 14)                      │
│  - FileUpload / DatabaseConnect                             │
│  - ChatPanel (Q&A interface)                                │
│  - AgentPipeline (SSE progress visualization)               │
│  - Plotly Charts (ChartRenderer)                            │
└──────────────────────┬──────────────────────────────────────┘
                       │ REST API + SSE
                       ▼
┌─────────────────────────────────────────────────────────────┐
│              FastAPI Backend (Python 3.11+)                   │
│                                                               │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  API Layer                                           │   │
│  │  - Upload Handler  - Database Connectors            │   │
│  │  - Query Router    - Session Management             │   │
│  │  - SSE Streaming   - Export                          │   │
│  └──────────────────────────────────────────────────────┘   │
│                       ▼                                       │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Services Layer (Agent Orchestration)                │   │
│  │  • Data Janitor Agent      → Cleaning & validation  │   │
│  │  • Hypothesis Bot Agent    → LLM insight generation│   │
│  │  • Debate Manager Agent    → LLM scoring & ranking  │   │
│  │  • Viz Whiz Agent          → Plotly chart generation│   │
│  │  • NLQ Agent               → NL → code → execution  │   │
│  │  • LLM Service             → Provider abstraction    │   │
│  │  • Sandbox Executor        → RestrictedPython sandbox│   │
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
    │ • CSVs      │                   │ • Ollama (local) │
    └─────────────┘                   └──────────────────┘
```

---

## Component Breakdown

### 1. Frontend Layer (Next.js 14)

**Location**: `frontend/`

**Responsibilities**:
- User interface for data ingestion (file upload / DB connection)
- Interactive chat panel for Q&A
- Real-time agent progress visualization via SSE
- Plotly chart rendering
- Session state management

**Key Components**:
- [`FileUpload.tsx`](frontend/components/upload/FileUpload.tsx) — CSV file upload with drag-and-drop, demo dataset selector
- [`DatabaseConnect.tsx`](frontend/components/upload/DatabaseConnect.tsx) — Database connection form, then a table picker to select which table to analyze
- [`ChatPanel.tsx`](frontend/components/chat/ChatPanel.tsx) — Main Q&A interface with message history
- [`AgentPipeline.tsx`](frontend/components/agents/AgentPipeline.tsx) — SSE-based real-time agent progress display
- [`MessageBubble.tsx`](frontend/components/chat/MessageBubble.tsx) — Renders messages with code blocks, Plotly charts, reasoning
- [`ChartRenderer.tsx`](frontend/components/viz/ChartRenderer.tsx) — Plotly.js chart rendering
- [`ExportPanel.tsx`](frontend/components/export/ExportPanel.tsx) — Session export controls
- [`ShareButton.tsx`](frontend/components/export/ShareButton.tsx) — Token-based session sharing

**Technologies**: React 18, Next.js 14 (App Router), Tailwind CSS, Plotly.js

---

### 2. Backend API Layer (FastAPI)

**Location**: [`backend/app/api/`](backend/app/api/)

**Responsibilities**:
- HTTP request routing
- File upload management
- Database connector orchestration
- Session lifecycle management
- SSE event streaming for agent progress
- Response formatting

**Key Files**:
- [`endpoints.py`](backend/app/api/endpoints.py) — Main API routes (upload, process, nlq, summarize, explain, report, bigquery, demo, SSE streaming)
- [`connectors.py`](backend/app/api/connectors.py) — Database connection handlers
- [`export.py`](backend/app/api/export.py) — Result export endpoints (HTML, Markdown, CSV)
- [`sessions.py`](backend/app/api/sessions.py) — Session sharing with expiring tokens
- [`main.py`](backend/app/api/main.py) — Legacy v1 endpoints (duplicate, maintained for backward compatibility)

**API Routes**:
```
POST   /upload                 → Save CSV, return file_path
POST   /process                → Run full agent pipeline (emits SSE events)
POST   /nlq                    → Natural language → code → execution (emits SSE events)
POST   /summarize              → Summarize workflow results
POST   /explain                → Explain a visualization
POST   /report                 → Generate HTML report
POST   /bigquery               → Query Google BigQuery
POST   /connectors/connect     → Establish DB connection, return connection_id + schema
POST   /connectors/load-table  → Materialize a table into a CSV (feeds /process, /nlq)
DELETE /connectors/{id}        → Disconnect a database connection
GET    /connectors/schema       → Not yet implemented (placeholder)
GET    /sessions/{id}          → Get session history
DELETE /sessions/{id}          → Clear session
POST   /sessions/share         → Create share link
GET    /sessions/shared/{token}→ Access shared session
GET    /export/{id}/html|md|csv → Export results
GET    /demo/list              → List demo datasets
GET    /demo/load              → Load demo dataset
GET    /agents/stream/{id}     → SSE stream for agent progress
GET    /health                 → Service status
```

---

### 3. Services Layer (Agent Orchestration)

**Location**: [`backend/app/services/`](backend/app/services/)

This is the **intelligent core** of Insight Orchestra.

#### 3.1 Data Janitor Agent
**File**: [`adk_agents.py`](backend/app/services/adk_agents.py) → `DataJanitorAgent`

**Purpose**: Data preprocessing and validation.

**Workflow**:
```
Input DataFrame
    ↓
Check duplicates → Remove if found
    ↓
Parse object columns that look like dates → real datetime64 dtype
    ↓
Identify missing values per column
    ↓
Flag bias: columns with >30% missing values
    ↓
Impute: numeric → median, categorical/datetime → mode
    ↓
Detect constant columns (single unique value)
    ↓
Output: Cleaned DataFrame + metadata report
```

Date parsing runs before imputation so a `date`-like column becomes a real
`datetime64` dtype instead of being treated as categorical downstream — left
as strings, hypothesis generation would otherwise group by individual date
values (e.g. "'2025-09-20' leads 'date'..."), which is meaningless since a
near-unique value can't meaningfully "lead" a group.

**Output**:
```json
{
  "cleaned_data": [...],
  "report": {
    "initial_shape": [1000, 15],
    "duplicates_removed": 5,
    "missing_values": {"age": 12, "salary": 3},
    "total_missing": 15,
    "bias_flags": ["Column 'age' missing for 15.0% of rows."],
    "missing_values_imputed": true,
    "constant_columns": [],
    "final_shape": [995, 15]
  }
}
```

#### 3.2 Hypothesis Bot Agent
**File**: [`adk_agents.py`](backend/app/services/adk_agents.py) → `HypothesisBotAgent`

**Purpose**: Generate testable hypotheses using an LLM.

**Workflow**:
```
DataFrame schema (via DataFrameSchema helper)
    ↓
Construct schema prompt (columns, types, stats, sample values)
    ↓
Send to LLM via LLMService.complete_json()
    ↓
Parse LLM response → hypothesis list + reasoning
    ↓
Output: List of hypotheses with summary
```

Uses `LLMService` for provider-agnostic LLM calls. Falls back gracefully if the LLM is unavailable.

Receives `bias_flags` from Stage 1 (columns >30% imputed) and folds them into
the stats prompt so the LLM is told which correlations may be artificially
weakened by imputation. The stats summary also excludes near-unique
categorical columns (>90% unique ratio, e.g. raw IDs) from its distribution
section — these would otherwise waste the limited stats budget on
uninformative singleton counts.

#### 3.3 Debate Manager Agent
**File**: [`adk_agents.py`](backend/app/services/adk_agents.py) → `DebateManagerAgent`

**Purpose**: Score and rank hypotheses using an LLM auditor.

**Scoring**: The LLM assigns each hypothesis a `confidence` and `business_value` score (0–1 scale). Hypotheses are sorted by `confidence × business_value` (descending). The top-scoring hypothesis becomes the "consensus."

**Output**:
```json
{
  "scored_hypotheses": [
    {"hypothesis": "...", "confidence": 0.85, "business_value": 0.9, "statistical_argument": "...", "business_argument": "..."}
  ],
  "summary": {
    "num_hypotheses": 5,
    "consensus": {"hypothesis": "...", "confidence": 0.85, "business_value": 0.9},
    "arguments": [{"hypothesis": "...", "statistical": "...", "business": "..."}]
  }
}
```

#### 3.4 Viz Whiz Agent
**File**: [`adk_agents.py`](backend/app/services/adk_agents.py) → `VizWhizAgent`

**Purpose**: Auto-select visualization types and generate Plotly charts.

**Logic**: Parses the consensus hypothesis for variable names via regex. Determines data types (numeric vs. categorical vs. object) and selects appropriate chart types:

| Variable Combination | Chart Types |
|---------------------|-------------|
| Numeric × Numeric | Scatter plot, density heatmap |
| Categorical × Numeric | Box plot, violin plot |
| Numeric × Categorical | Box plot (swapped), violin plot |
| Single Numeric | Histogram |
| Single Categorical | Bar chart |

Falls back through all hypotheses, then all column pairs, if the consensus hypothesis yields no valid charts.

Scatter plots reduce marker opacity (to 0.3) above 5,000 rows so dense point clouds stay legible instead of overplotting into a solid blob.

#### 3.5 NLQ Agent (Natural Language Query)
**File**: [`nlq_agent.py`](backend/app/services/nlq_agent.py) → `NaturalLanguageQueryAgent`

**Purpose**: Convert natural language to executable Python code and return results.

**Process**:
```
User question + DataFrame schema
    ↓
Construct prompt with schema description and examples
    ↓
LLM generates pandas code
    ↓
Ensure result variable assignment
    ↓
Execute via SandboxExecutor with retry logic
    ↓
Return: answer + code + reasoning + optional plot_json
```

Includes retry logic: if execution fails, the error is fed back to the LLM for code regeneration (up to 2 retries). Supports clarification requests when the question is ambiguous.

#### 3.6 LLM Service
**File**: [`llm_service.py`](backend/app/services/llm_service.py) → `LLMService`

**Purpose**: Unified interface to multiple LLM providers.

**Supported Providers**:
| Provider | Type | Configuration |
|----------|------|---------------|
| **OpenAI** | Cloud API | `LLM_PROVIDER=openai`, `OPENAI_API_KEY`, `OPENAI_MODEL` |
| **DeepSeek** | Cloud API (OpenAI-compatible) | `LLM_PROVIDER=deepseek`, `DEEPSEEK_API_KEY`, `DEEPSEEK_MODEL`, `DEEPSEEK_BASE_URL` |
| **Anthropic** | Cloud API | `LLM_PROVIDER=anthropic`, `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL` |
| **Ollama** | Local | `LLM_PROVIDER=ollama`, `OLLAMA_BASE_URL`, `OLLAMA_MODEL` |

**Public Methods**:
```python
complete(system_prompt, user_prompt, use_fallback=False) → LLMResponse
complete_json(system_prompt, user_prompt, use_fallback=False) → dict
get_cost_summary() → dict
```

**Features**:
- Exponential backoff retry (configurable via `MAX_RETRIES` and `REQUEST_TIMEOUT` env vars)
- Token cost tracking (OpenAI only; Ollama is free)
- JSON-format enforcement for structured outputs
- Fallback model support for OpenAI (`OPENAI_MODEL_FALLBACK`)

#### 3.7 Sandbox Executor
**File**: [`sandbox_executor.py`](backend/app/services/sandbox_executor.py) → `SandboxExecutor`

**Purpose**: Safely execute generated code without security risks.

**Safety Mechanisms**:
- **RestrictedPython**: Compiles code with restricted bytecode — removes dangerous builtins
- **Safety check**: Pre-execution AST scan for blocked imports (`os`, `subprocess`, `socket`, ...), blocked builtins (`eval`, `exec`, `open`, ...), dangerous dunder attribute access (`__globals__`, `__subclasses__`, ...), and blocked pandas I/O/eval-alike methods regardless of receiver (`.eval()`, `.query()`, `pd.read_pickle()`, `.to_sql()`, `.to_csv()`, etc.) — generated code only ever needs to transform the pre-loaded `df`, so file/network I/O and a second `eval()` have no legitimate use case
- **Timeout**: Configurable (default 30 s), enforced via `ThreadPoolExecutor.result(timeout=...)` — not `SIGALRM`, which only fires on the main thread and silently no-ops in a worker thread
- **Output isolation**: stdout/stderr captured via `io.StringIO`

**Allowed in sandbox**:
```python
# pandas, plotly.express, numpy pre-imported
df.groupby(...).agg(...)
pd.merge(...)
df['col'].mean()
px.scatter(df, x='a', y='b')
```

**Blocked**:
```python
os.remove('file.txt')         # File I/O
requests.get('http://...')   # Network
exec('malicious_code')       # Code injection
__import__('subprocess')     # Dynamic imports
pd.read_pickle('/etc/passwd') # Arbitrary file read + deserialization
df.to_sql('x', engine)        # Arbitrary DB write
df.eval('...')                # Secondary eval
```

**Known limitation**: this is a hand-maintained AST blocklist, not process-level
isolation — code still runs `exec()`'d in the same OS process as the backend,
via a worker thread. A blocklist can be exhaustive against `os`/`subprocess`
but can never be provably exhaustive against a library as large as pandas;
the method-name list above closes the specific escape vectors identified in
review (deserialization via `read_pickle`, arbitrary file write via
`to_csv`/`to_sql`/etc., secondary `eval`/`query`), but it is defense-in-depth,
not a hard security boundary. For untrusted multi-tenant deployments, running
the sandbox in a separate container or process (e.g. gVisor, `--network none`,
read-only filesystem) is the stronger guarantee and is not yet implemented.

**Note**: Memory limiting is declared (`max_memory_mb`) but not actively enforced at runtime.

#### 3.8 Supporting Agents

- **ExplainabilityAgent** ([`explain_agent.py`](backend/app/services/explain_agent.py)) — Hardcoded rule-based explanation generator for Plotly charts (not LLM-powered).
- **InsightSummarizerAgent** ([`summarizer_agent.py`](backend/app/services/summarizer_agent.py)) — Simple string concatenation to summarize workflow results.
- **ReportGeneratorAgent** ([`report_agent.py`](backend/app/services/report_agent.py)) — Generates basic HTML reports from workflow results.

---

### 4. Data Connectors

**Location**: [`backend/app/connectors/`](backend/app/connectors/)

All connectors implement the [`BaseConnector`](backend/app/connectors/base.py) abstract interface:

```python
class BaseConnector(ABC):
    @abstractmethod
    def connect(self, connection_string: str) -> None
    @abstractmethod
    def get_schema(self) -> dict
    @abstractmethod
    def execute_query(self, sql: str) -> pd.DataFrame
    @abstractmethod
    def test_connection(self) -> bool
```

| Connector | File | Dependencies |
|-----------|------|--------------|
| PostgreSQL | [`postgresql.py`](backend/app/connectors/postgresql.py) | `psycopg2` |
| MySQL | [`mysql.py`](backend/app/connectors/mysql.py) | `pymysql` |
| SQLite | [`sqlite.py`](backend/app/connectors/sqlite.py) | `sqlite3` (stdlib) |
| DuckDB | [`duckdb.py`](backend/app/connectors/duckdb.py) | `duckdb` |
| BigQuery | [`bigquery_utils.py`](backend/app/utils/bigquery_utils.py) | `google.cloud.bigquery` (via API) |

**Safety**: All connectors enforce read-only queries (SELECT only). SQL injection is mitigated via blocked keyword patterns.

**Connection Persistence**: [`connection_store.py`](backend/app/services/connection_store.py)

The backend runs multiple uvicorn workers (`--workers 2`), so a live connector
instance (open socket + cursor) held in one worker's memory is invisible to
requests handled by another. Connections are therefore never held open across
requests: `/connectors/connect` opens just long enough to validate
credentials and read the schema, then disconnects. Only the connection
metadata (type, connection string, cached schema) is persisted — Redis-backed
with an in-memory fallback, same pattern as `session_manager.py` and
`workspace_store.py` — keyed by a `connection_id` with a sliding TTL
(`DB_CONNECTION_TTL_SECONDS`, default 10 min). `/connectors/load-table`
reconnects fresh from that metadata each time it's called, runs `SELECT *
FROM <table> LIMIT n`, and writes the result to a CSV under `/tmp` so it can
flow through `/process`/`/nlq` exactly like an uploaded file.

---

### 5. Session Management

**Location**: [`session_manager.py`](backend/app/services/session_manager.py), [`sessions.py`](backend/app/api/sessions.py)

**Storage Backends**:
| Backend | When Used | Characteristics |
|---------|-----------|-----------------|
| In-memory dict | No Redis available | Single-process, ephemeral |
| Redis | `REDIS_URL` configured | Distributed, persistent, TTL-based expiry |

**Session Data**: Each session stores a list of interaction dictionaries (`{question, answer, code}`) appended during NLQ requests.

**Session Sharing**: Token-based share links created via `POST /sessions/share` with 72-hour TTL.

---

### 6. Real-Time Agent Progress (SSE)

**File**: [`agent_progress.py`](backend/app/agent_progress.py)

Agent progress is streamed to the frontend via Server-Sent Events (SSE). The mechanism:

1. [`get_queue(session_id)`](backend/app/agent_progress.py:27) — Creates/retrieves an `asyncio.Queue` per session
2. [`push_event()`](backend/app/agent_progress.py:39) — Producers (endpoints) push `{agent_id, status, output, duration}` dicts
3. [`push_sentinel()`](backend/app/agent_progress.py:81) — Signals end-of-stream with `None`
4. [`GET /agents/stream/{session_id}`](backend/app/api/endpoints.py:334) — SSE endpoint drains the queue; 60-second inactivity timeout

The frontend [`AgentPipeline`](frontend/components/agents/AgentPipeline.tsx) component consumes these events and updates agent status cards in real time.

---

## Data Flow: End-to-End

### Scenario: User uploads CSV and asks a question

```
[1] User uploads file
    ↓
    POST /upload  (multipart/form-data)
    ↓
    File saved to backend/uploads/{uuid}_{filename}.csv
    ↓
    Return {"file_path": "/tmp/...csv"}

[2] Frontend displays upload confirmation
    ↓
    User types question in chat
    ↓
    Frontend opens SSE connection to /agents/stream/{session_id}
    ↓
    POST /nlq with {file_path, question, session_id}
    ↓
    API loads DataFrame from file
    ↓
    Data Janitor Agent runs (SSE: janitor → done)
    ↓
    NLQ Agent generates pandas code
    ↓
    SandboxExecutor executes code
    ↓
    Viz Whiz generates chart (SSE: viz → done, if plot produced)
    ↓
    SSE stream ends (sentinel)
    ↓
    Return: {answer, code, reasoning, plot_json, ...}

[3] Frontend displays:
    - Answer text
    - Code block (syntax-highlighted)
    - Plotly chart (if generated)
    - Reasoning (if provided)
```

---

## Key Design Patterns

### 1. Agent Pattern
Each agent is an independent worker with a single responsibility. Agents are chained sequentially in `InsightOrchestraWorkflow.run()`.

### 2. Provider Abstraction
`LLMService` provides a unified interface (`complete()`, `complete_json()`) that abstracts over OpenAI, DeepSeek, Anthropic, and Ollama. Providers are selected via the `LLM_PROVIDER` environment variable. DeepSeek reuses the OpenAI client path via its OpenAI-compatible API.

### 3. Sandbox Pattern
Generated code is isolated via RestrictedPython with pre-execution safety checks, execution timeout, and output capture. This prevents malicious or buggy code from affecting the host system.

### 4. Session Isolation
User sessions are keyed by ID and stored in Redis (or in-memory). The `/sessions/share` endpoint provides expiring, token-based access for collaboration.

---

## Security Model

| Threat | Mitigation |
|--------|-----------|
| Malicious SQL injection | Blocked keywords (`DROP`, `DELETE`, `INSERT`, etc.) on query strings |
| Code execution exploits | RestrictedPython sandbox + pre-execution AST safety scans (see [3.7](#37-sandbox-executor)) — a blocklist, not process isolation; see that section's "Known limitation" |
| Data exfiltration via sandbox | Blocked network imports (`requests`, `urllib`, `socket`) + blocked pandas I/O methods (`read_*`/`to_*`/`eval`/`query`) |
| Resource exhaustion | Execution timeout (30 s default) |
| Path traversal | File path validation — only `/tmp/` and `uploads/` allowed |
| Credential exposure | Environment variables only; `.env` excluded from version control |
| CORS | Configurable allowed origins (`CORS_ORIGIN` env var) |

**Note**: Rate limiting, HTTPS enforcement, and user authentication are not implemented. The system is designed for local/internal network deployment.

---

## Technology Choices

| Tool | Rationale |
|------|-----------|
| **FastAPI** | Type-safe, auto-docs (Swagger/ReDoc), async-ready |
| **Pandas** | Standard for in-memory data manipulation |
| **RestrictedPython** | Lightweight sandbox for generated code; no container overhead |
| **Google ADK** | Structured agent base class with named agents |
| **Ollama** | Local LLM inference without GPU requirement |
| **Next.js 14** | Full-stack React with App Router, server components |
| **Docker Compose** | Multi-service orchestration with single command |
| **Redis** | Optional distributed session storage |
