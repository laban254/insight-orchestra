# Insight Orchestra — Architecture Overview

## System Architecture

Insight Orchestra is a **multi-agent AI data analysis platform** with a three-layer architecture: a Next.js frontend, a FastAPI backend, and a services layer for agent orchestration, sandboxed code execution, and (optional) auth/access control. LLM providers are pluggable — OpenAI, Anthropic, DeepSeek, or local Ollama.

```
┌─────────────────────────────────────────────────────────────┐
│                   Frontend (Next.js 14)                      │
│  - FileUpload / DatabaseConnect                              │
│  - Workspace (chat + canvas shell) / MessageBubble           │
│  - AgentTimeline / AnalysisProgress (SSE progress)           │
│  - Plotly charts (ChartRenderer), export, admin panel        │
└──────────────────────┬────────────────────────────────────────┘
                       │ REST API + SSE
                       ▼
┌─────────────────────────────────────────────────────────────┐
│         FastAPI Backend (Python 3.11+, single worker)         │
│                                                               │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  API Layer                                            │   │
│  │  - Upload / Process / NLQ   - Auth & Audit            │   │
│  │  - Database Connectors      - Workspaces              │   │
│  │  - SSE Streaming            - Sessions & Export        │   │
│  └──────────────────────────────────────────────────────┘   │
│                       ▼                                       │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Services Layer (Agent Orchestration + Platform)      │   │
│  │  • Data Janitor / Hypothesis Bot / Debate / Viz Whiz  │   │
│  │  • NLQ Agent (CSV)  • Database NLQ Agent (multi-table)│   │
│  │  • Insight Summarizer Agent  • LLM Service            │   │
│  │  • Sandbox Executor  • Auth / OIDC / Audit Log        │   │
│  └──────────────────────────────────────────────────────┘   │
│                       ▼                                       │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Data Layer                                            │   │
│  │  • Dataset registry (files on a mounted volume)        │   │
│  │  • Redis (sessions, workspaces, connections, users) —  │   │
│  │    in-memory fallback if Redis is unavailable           │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
         ▼                                    ▼
    ┌─────────────┐                   ┌──────────────────┐
    │ Local Files │                   │ LLM Providers     │
    │ (Uploads)   │                   │ OpenAI / Anthropic│
    │ CSV/TSV/    │                   │ DeepSeek / Ollama │
    │ Excel/JSON/ │                   └──────────────────┘
    │ Parquet     │
    └─────────────┘
```

---

## Component Breakdown

### 1. Frontend Layer (Next.js 14)

**Location**: `frontend/`

**Responsibilities**:
- User interface for data ingestion (file upload / DB connection)
- Chat + canvas workspace for Q&A, pinned results, and comparison
- Real-time agent progress visualization via SSE
- Plotly chart rendering
- Auth (login page, session-aware routing) and an admin panel when `AUTH_ENABLED=true`

**Key Components**:
- [`FileUpload.tsx`](frontend/components/upload/FileUpload.tsx) — dataset file upload (CSV/TSV/Excel/JSON/Parquet) with drag-and-drop, demo dataset selector
- [`DatabaseConnect.tsx`](frontend/components/upload/DatabaseConnect.tsx) — database connection form, then a table picker (or a direct NL→SQL question) against the connected database
- [`Workspace.tsx`](frontend/components/workspace/Workspace.tsx) — top-level shell coordinating the chat pane and canvas pane for one analysis session
- [`CanvasPane.tsx`](frontend/components/workspace/CanvasPane.tsx) — pinned results, comparisons, and the loading state while a pipeline run is in flight
- [`MessageBubble.tsx`](frontend/components/chat/MessageBubble.tsx) — renders messages with code blocks, Plotly charts, reasoning, markdown tables
- [`AgentTimeline.tsx`](frontend/components/agents/AgentTimeline.tsx) — consumes the SSE stream and tracks per-agent status
- [`AnalysisProgress.tsx`](frontend/components/agents/AnalysisProgress.tsx) — what the canvas shows while a pipeline run is in progress (a loader plus a real, changing status line — not a step tracker)
- [`ChartRenderer.tsx`](frontend/components/viz/ChartRenderer.tsx) — Plotly.js chart rendering
- [`ExportMenu.tsx`](frontend/components/ui/ExportMenu.tsx) — interactive HTML report, PDF (print), Markdown summary, Q&A CSV
- [`admin/`](frontend/components/admin/) — `UsersTab.tsx`, `ApiKeysTab.tsx`, `AuditLogTab.tsx`, shown only to signed-in admins when auth is on
- [`login/page.tsx`](frontend/app/login/page.tsx) — split-layout sign-in page, shown only when `AUTH_ENABLED=true` and no session exists

**Technologies**: React 18, Next.js 14 (App Router), Tailwind CSS, Plotly.js. UI primitives (`components/ui/`) are hand-built, not a shadcn/ui install.

---

### 2. Backend API Layer (FastAPI)

**Location**: [`backend/app/api/`](backend/app/api/)

**Responsibilities**:
- HTTP request routing
- File upload management
- Database connector orchestration
- Session/workspace lifecycle management
- SSE event streaming for agent progress
- Auth, RBAC enforcement, and audit logging (all a no-op while `AUTH_ENABLED=false`)

**Key Files**:
- [`endpoints.py`](backend/app/api/endpoints.py) — core routes: upload, process, nlq, config, datasets, demo, SSE streaming, BigQuery
- [`connectors.py`](backend/app/api/connectors.py) — database connection handlers, including the multi-table NL→SQL endpoint
- [`workspaces.py`](backend/app/api/workspaces.py) — save/list/load/delete named workspaces
- [`export.py`](backend/app/api/export.py) — result export endpoints (HTML, Markdown, CSV)
- [`sessions.py`](backend/app/api/sessions.py) — session sharing with expiring tokens
- [`auth.py`](backend/app/api/auth.py) — login/logout, `/me`, OIDC, API keys, user management
- [`audit.py`](backend/app/api/audit.py) — audit log read/export (admin-only)

**API Routes** (all under `/api/v1` except `/health`; see [API Reference](API_REFERENCE.md) for full request/response bodies and the auth/role required for each):
```
POST   /upload                        → Upload + parse a dataset file, return a dataset_id
POST   /process                       → Run the full 4-agent pipeline (emits SSE events)
POST   /nlq                           → Natural language → pandas code → execution (emits SSE events)
GET    /config   POST /config         → Current/switch LLM provider & model at runtime (admin)
GET    /datasets/{id}                 → Whether a dataset is still usable, shape + preview
GET    /datasets/{id}/rows            → Paged rows, for browsing past the fixed preview
POST   /datasets/{id}/transform       → Deterministic column transform (normalize/scale/encode) → new dataset
DELETE /datasets/{id}                 → Forget a dataset and delete its file
POST   /bigquery                      → Query Google BigQuery (experimental, optional dep, 501 by default)
GET    /connectors/local-files        → SQLite/DuckDB files visible under the uploads mount (admin)
POST   /connectors/connect            → Establish a DB connection, return connection_id + schema (admin)
POST   /connectors/load-table         → Materialize a table into a CSV (feeds /process, /nlq) (admin)
POST   /connectors/query              → Multi-table NL→SQL directly against a connected database (member+)
DELETE /connectors/{id}               → Disconnect a database connection (admin)
GET    /connectors/schema             → Not yet implemented (placeholder)
GET    /sessions/{id}   DELETE        → Get / clear chat history for a session
POST   /sessions/share                → Create a read-only share link (72 h TTL)
GET    /sessions/shared/{token}       → Access a shared session (always public)
GET    /export/{id}/html|markdown|csv → Export session results
GET    /workspaces   POST/PUT/DELETE  → Save/list/load/delete named workspaces
GET    /demo/list   GET /demo/load    → List / load a bundled demo dataset
GET    /agents/stream/{id}            → SSE stream of agent progress
GET    /auth/login   POST   /auth/logout   GET /auth/me   → Session-cookie auth
GET    /auth/oidc/login   GET /auth/oidc/callback         → SSO
GET/POST/DELETE /auth/api-keys        → Self-service API keys
GET/POST/PATCH/DELETE /auth/users     → User management (admin)
GET    /audit/log   GET /audit/export → Audit log (admin)
GET    /health                        → Service status (unversioned, no /api/v1 prefix)
```

---

### 3. Services Layer (Agent Orchestration)

**Location**: [`backend/app/services/`](backend/app/services/)

This is the **intelligent core** of Insight Orchestra. `InsightOrchestraWorkflow` in [`adk_agents.py`](backend/app/services/adk_agents.py) chains the first four sequentially; `/process` then hands the combined result to `InsightSummarizerAgent` for the narrative.

#### 3.1 Data Janitor Agent
**File**: [`adk_agents.py`](backend/app/services/adk_agents.py) → `DataJanitorAgent`

**Purpose**: Data preprocessing and validation. Runs at the start of both `/process` and `/nlq` (a follow-up question reuses the cached cleaned frame rather than re-cleaning).

**Workflow**:
```
Input DataFrame
    ↓
Check duplicates → remove if found
    ↓
Parse object columns that look like dates → real datetime64 dtype
    ↓
Identify missing values per column
    ↓
Flag bias: columns with >30% missing values
    ↓
Impute: numeric → median, datetime → median timestamp, categorical → mode (or "MISSING")
    ↓
Flag outliers via IQR (flagged, not removed)
    ↓
Detect constant columns (single unique value)
    ↓
Output: {"cleaned_df": DataFrame, "report": {...}}
```

Date parsing runs before imputation so a `date`-like column becomes a real
`datetime64` dtype instead of being treated as categorical downstream — left
as strings, hypothesis generation would otherwise group by individual date
values (e.g. "'2025-09-20' leads 'date'..."), which is meaningless since a
near-unique value can't meaningfully "lead" a group.

#### 3.2 Hypothesis Bot Agent
**File**: [`adk_agents.py`](backend/app/services/adk_agents.py) → `HypothesisBotAgent`

**Purpose**: Generate 5–8 specific, directional, evidence-backed hypotheses using an LLM grounded in actual statistics (descriptive stats, correlations with |r| > 0.3, top category distributions) — not just column names. Falls back to a heuristic group-mean/correlation pass if the LLM is unavailable or fails.

Receives `bias_flags` from Stage 1 (columns >30% imputed) and folds them into
the stats prompt so the LLM is told which correlations may be artificially
weakened by imputation. The stats summary also excludes near-unique
categorical columns (>90% unique ratio, e.g. raw IDs) from its distribution
section — these would otherwise waste the limited stats budget on
uninformative singleton counts.

#### 3.3 Debate Manager Agent
**File**: [`adk_agents.py`](backend/app/services/adk_agents.py) → `DebateManagerAgent`

**Purpose**: Score and rank hypotheses using an LLM that receives the same statistics summary as evidence, not just the hypothesis text.

**Scoring**: The LLM assigns each hypothesis a `confidence` and `business_value` score (0–1 scale), plus a `statistical_argument` and `business_argument`. Hypotheses are sorted by `confidence × business_value` (descending); the top scorer becomes the **consensus**. On LLM failure, a positional fallback (0.85 → 0.60 descending) is used instead.

#### 3.4 Viz Whiz Agent
**File**: [`adk_agents.py`](backend/app/services/adk_agents.py) → `VizWhizAgent`

**Purpose**: Auto-select visualization types and generate up to 6 Plotly charts, using LLM-based column selection grounded in the consensus hypothesis.

**Logic**: Asks the LLM which 1–2 columns best illustrate the consensus insight, then picks a chart type by data type (numeric×numeric → scatter + trendline or density heatmap; categorical×numeric → bar + box plot; single numeric → histogram; single categorical → bar chart). Falls back through regex extraction from the hypothesis text, then the other hypotheses, then schema heuristics, then single-column histograms, if the primary path yields nothing.

Scatter plots reduce marker opacity (to 0.3) above 5,000 rows so dense point clouds stay legible instead of overplotting into a solid blob.

#### 3.5 NLQ Agent (Natural Language Query)
**File**: [`nlq_agent.py`](backend/app/services/nlq_agent.py) → `NaturalLanguageQueryAgent`

**Purpose**: Convert a natural-language question about the current (CSV/uploaded/demo/DB-table) dataset into pandas code and return the result.

**Process**:
```
User question + DataFrame schema
    ↓
LLM generates pandas code, assigned to a `result` variable
    ↓
SandboxExecutor.execute_with_retry() (up to 2 retries)
    ↓
On failure: feed the error back to the LLM for code regeneration
    ↓
Return: answer + code + reasoning + optional plot_json
```

Supports clarification requests when the LLM finds the question ambiguous. Identical queries against the same dataset are served from a short-lived query cache (`query_cache.py`) rather than re-calling the LLM.

#### 3.6 Database NLQ Agent (multi-table)
**File**: [`db_nlq_agent.py`](backend/app/services/db_nlq_agent.py) → `DatabaseNLQAgent`

**Purpose**: Answer a question directly against a *connected* database — JOIN-capable across every table in the connection's schema — instead of requiring a table to be materialized first. Reached via `POST /connectors/query`; a separate code path from the CSV-pipeline NLQ agent above, which stays scoped to one already-materialized table. Generates read-only SQL (not pandas code) and executes it through the live connector.

#### 3.7 Insight Summarizer Agent
**File**: [`summarizer_agent.py`](backend/app/services/summarizer_agent.py) → `InsightSummarizerAgent`

**Purpose**: LLM-powered agent that writes a 3–5 sentence narrative summary of the full `/process` pipeline result and generates 4–5 follow-up questions referencing real column names. Falls back to a template built from the actual column names if the LLM call fails. Shown to the user as the first chat message after a pipeline run completes.

#### 3.8 LLM Service
**File**: [`llm_service.py`](backend/app/services/llm_service.py) → `LLMService`

**Purpose**: Unified interface to multiple LLM providers.

**Supported Providers**:
| Provider | Type | Configuration |
|----------|------|---------------|
| **OpenAI** | Cloud API | `LLM_PROVIDER=openai`, `OPENAI_API_KEY`, `OPENAI_MODEL` |
| **Anthropic** | Cloud API | `LLM_PROVIDER=anthropic`, `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL` |
| **DeepSeek** | Cloud API (OpenAI-compatible) | `LLM_PROVIDER=deepseek`, `DEEPSEEK_API_KEY`, `DEEPSEEK_MODEL`, `DEEPSEEK_BASE_URL` |
| **Ollama** | Local | `LLM_PROVIDER=ollama`, `OLLAMA_BASE_URL`, `OLLAMA_MODEL` |

**Public Methods**:
```python
complete(system_prompt, user_prompt, use_fallback=False) → LLMResponse
complete_json(system_prompt, user_prompt, use_fallback=False) → dict
get_cost_summary() → dict
```

**Features**:
- Retry with backoff (configurable via `MAX_RETRIES` and `REQUEST_TIMEOUT` env vars)
- Token cost tracking (cloud providers; Ollama is free)
- JSON-format enforcement for structured outputs
- Fallback model support for OpenAI (`OPENAI_MODEL_FALLBACK`)
- Provider/model can be switched at runtime via `POST /config` (admin-only with auth on) — no restart needed

#### 3.9 Sandbox Executor
**File**: [`sandbox_executor.py`](backend/app/services/sandbox_executor.py) → `SandboxExecutor`

**Purpose**: Safely execute LLM-generated pandas/plotly code.

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

**Note**: Memory limiting is declared (`SANDBOX_MEMORY_LIMIT`) but not actively enforced at runtime.

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
| BigQuery *(experimental)* | [`bigquery_utils.py`](backend/app/utils/bigquery_utils.py) | `google.cloud.bigquery` — optional, not installed by default |

**Safety**: All connectors enforce read-only queries (SELECT only). SQL injection is mitigated via blocked keyword patterns.

**Connection Persistence**: [`connection_store.py`](backend/app/services/connection_store.py)

The backend runs as a **single uvicorn worker** (`backend/Dockerfile`, `--workers 1` — the in-process SSE progress queue in `agent_progress.py` wouldn't be visible across worker processes, so the whole backend is deliberately kept to one). Live database connectors are still never held open across requests, though: `/connectors/connect` opens just long enough to validate credentials and read the schema, then disconnects; only the connection metadata (type, connection string, cached schema) is persisted — Redis-backed with an in-memory fallback, the same pattern as `session_manager.py` and `workspace_store.py` — keyed by a `connection_id` with a sliding TTL (`DB_CONNECTION_TTL_SECONDS`, default 10 min). `/connectors/load-table` and `/connectors/query` reconnect fresh from that metadata each time they're called.

---

### 5. Session Management

**Location**: [`session_manager.py`](backend/app/services/session_manager.py), [`sessions.py`](backend/app/api/sessions.py)

**Storage Backends**:
| Backend | When Used | Characteristics |
|---------|-----------|-----------------|
| In-memory dict | No Redis available (`USE_REDIS=false` or Redis unreachable) | Single-process, ephemeral |
| Redis | `REDIS_URL` configured, `USE_REDIS=true` (default) | Persistent across restarts, TTL-based expiry |

**Session Data**: Each session stores a list of interaction dictionaries (`{question, answer, code, plot_json?}`) appended during NLQ requests.

**Session Sharing**: Token-based share links created via `POST /sessions/share`, 72-hour TTL. `GET /sessions/shared/{token}` is always public, auth on or off — the token itself is the access control.

---

### 5b. Workspaces

**Location**: [`workspace_store.py`](backend/app/services/workspace_store.py), [`workspaces.py`](backend/app/api/workspaces.py)

A workspace is a named, saved snapshot of the frontend's UI state (pinned results, chat history, dataset reference) — what lets a user close the tab and reopen the same analysis later, from any browser. Stored the same way as sessions (Redis, in-memory fallback), keyed by a client-chosen id. With auth on, reads require any signed-in role and writes require `member`+; with auth off (the default), every workspace is readable/writable by anyone, unchanged from before auth existed.

---

### 5c. Dataset Registry & Retention

**Location**: [`dataset_registry.py`](backend/app/services/dataset_registry.py), [`retention.py`](backend/app/services/retention.py)

Every ingestion path (`/upload`, `/demo/load`, `/connectors/load-table`,
`/bigquery`) registers the file it writes and hands the client an opaque
`dataset_id` — never a filesystem path. `/process` and `/nlq` resolve that id
through the registry, so there is no caller-supplied path for those
endpoints to validate. Records live in Redis (in-memory fallback), same
pattern as sessions, workspaces and DB connections; the files themselves
live under `backend/uploads/` on the mounted volume, not `/tmp`, so
they survive a container recreate. A demo dataset additionally records which
demo it came from and is regenerated on demand if its file is ever lost.

A background sweep (started from `app/main.py`'s lifespan, run on
`RETENTION_SWEEP_INTERVAL_SECONDS`) does two things every pass: reaps
datasets idle past `DATASET_TTL_SECONDS` (sliding — resolving a dataset
resets its clock, so a workspace someone keeps reopening is never reaped),
and deletes any dataset file in the uploads directory
that no registry record points at and that has sat unreferenced for over an
hour (long enough to never touch a file mid-upload or mid-registration).

---

### 6. Real-Time Agent Progress (SSE)

**File**: [`agent_progress.py`](backend/app/agent_progress.py)

Agent progress is streamed to the frontend via Server-Sent Events. The mechanism:

1. `get_queue(session_id)` — creates/retrieves an `asyncio.Queue` per session (in-process; this is why the backend runs a single uvicorn worker — see §4)
2. `push_event()` — producers (the `/process`, `/nlq`, `/connectors/query` handlers) push `{agent_id, status, output, duration}` dicts
3. `push_sentinel()` — signals end-of-stream with `None`
4. `GET /agents/stream/{session_id}` — SSE endpoint drains the queue; 60-second inactivity timeout

The frontend's [`AgentTimeline`](frontend/components/agents/AgentTimeline.tsx) component consumes these events and tracks per-agent status; [`AnalysisProgress`](frontend/components/agents/AnalysisProgress.tsx) uses that same state to drive the loading UI shown in the canvas while a run is in flight.

---

## Data Flow: End-to-End

### Scenario: User uploads a CSV and asks a question

```
[1] User uploads file
    ↓
    POST /upload  (multipart/form-data)
    ↓
    File parsed, registered in the dataset registry
    ↓
    Return {"dataset_id": "...", "rows": ..., "columns": ..., "preview": [...], "assumptions": {...}}

[2] Frontend displays upload confirmation (real shape, not "Unknown rows")
    ↓
    User types a question in chat
    ↓
    Frontend opens an SSE connection to /agents/stream/{session_id}
    ↓
    POST /nlq with {dataset_id, question, session_id}
    ↓
    API resolves dataset_id to a path via the dataset registry, loads the
    DataFrame (or reuses it from the cleaned-frame cache if unchanged)
    ↓
    Data Janitor Agent runs (SSE: janitor → done)
    ↓
    NLQ Agent generates pandas code and runs it via SandboxExecutor
    (SSE: nlq → done, or → error on failure/timeout)
    ↓
    If the code produced a chart (SSE: viz → done)
    ↓
    SSE stream ends (sentinel)
    ↓
    Return: {answer, code, reasoning, plot_json, ...}

[3] Frontend displays:
    - Answer text (rendered as markdown, including tables)
    - Code block (syntax-highlighted)
    - Plotly chart (if generated)
    - Reasoning (if provided)
```

`POST /process` follows the same SSE pattern but runs the full four-stage pipeline (janitor → hypothesis → debate → viz) followed by the Insight Summarizer, rather than a single NLQ turn.

---

## Key Design Patterns

### 1. Agent Pattern
Each agent is an independent worker with a single responsibility. The four pipeline agents are chained sequentially in `InsightOrchestraWorkflow.run()`; NLQ and the Database NLQ agent are invoked directly by their respective endpoints.

### 2. Provider Abstraction
`LLMService` provides a unified interface (`complete()`, `complete_json()`) that abstracts over OpenAI, Anthropic, DeepSeek, and Ollama. Providers are selected via the `LLM_PROVIDER` environment variable, or switched at runtime via `POST /config`. DeepSeek reuses the OpenAI client path via its OpenAI-compatible API.

### 3. Sandbox Pattern
Generated code is isolated via RestrictedPython with pre-execution safety checks, execution timeout, and output capture. This prevents malicious or buggy code from affecting the host system.

### 4. Opaque Identifiers
Datasets, connections, sessions, and workspaces are all addressed by a server-minted opaque id — the client never supplies or needs a filesystem path or a raw DB handle.

### 5. Redis-Backed, Single-Process State
Sessions, workspaces, dataset records, and DB-connection metadata all live in Redis (with an in-memory fallback), even though the backend itself runs a single uvicorn worker — this is what lets that state survive a container restart, not multi-worker coordination.

---

## Authentication & Access Control

**Off by default** (`AUTH_ENABLED=false`) — Insight Orchestra runs single-tenant, no-login, exactly as it always has. Turning it on (`AUTH_ENABLED=true`) adds:

- **Sessions**: email/password login (`POST /auth/login`) sets an httponly `io_session` cookie; alternatively, an `Authorization: Bearer <key>` API key for headless callers.
- **Roles**: three tiers — `admin` (everything, including config/provider switching, connector management, user management, audit log), `member` (upload, analyze, query, export, save workspaces), `viewer` (read-only).
- **SSO**: OIDC (Authorization Code flow, discovery + JWKS-verified). The first person to ever sign in via SSO becomes `admin`; everyone after starts as `member`. SAML is not supported.
- **API keys**: self-service, created/listed/revoked via `/auth/api-keys`; the raw key is shown exactly once.
- **Audit log**: every login/logout, config change, connector connect/disconnect, dataset delete, and user/API-key management action is recorded (`audit_log.py`), readable via `/audit/log` and exportable as JSON Lines via `/audit/export` for a SIEM.
- **Admin panel**: a frontend-only surface (`components/admin/`) for managing users, API keys, and viewing the audit log — visible only to a signed-in `admin`.

See [API Reference § Authentication](API_REFERENCE.md#authentication) for the full endpoint list and [Setup Guide § Authentication & Access Control](SETUP.md#authentication--access-control) for the environment variables.

---

## Security Model

| Threat | Mitigation |
|--------|-----------|
| Malicious SQL injection | Blocked keywords (`DROP`, `DELETE`, `INSERT`, etc.) on query strings; read-only connectors |
| Code execution exploits | RestrictedPython sandbox + pre-execution AST safety scans (see [3.9](#39-sandbox-executor)) — a blocklist, not process isolation; see that section's "Known limitation" |
| Data exfiltration via sandbox | Blocked network imports (`requests`, `urllib`, `socket`) + blocked pandas I/O methods (`read_*`/`to_*`/`eval`/`query`) |
| Resource exhaustion | Execution timeout (30 s default), rate limiting (`RATE_LIMIT_ENABLED`, per-route limits) |
| Path traversal / arbitrary file read | Datasets, connections, sessions, and workspaces are all addressed by opaque server-minted ids — the client never supplies a filesystem path |
| Credential exposure | Environment variables only; `.env` excluded from version control; DB connection strings live in Redis with a TTL, not on disk |
| CORS | Configurable allowed origins (`ALLOWED_ORIGINS`) |
| Unauthorized access (network-facing deployments) | Optional `AUTH_ENABLED=true` — see [Authentication & Access Control](#authentication--access-control) above |

**Note**: HTTPS termination is left to the deployer (a reverse proxy in front of the containers) — the app itself serves plain HTTP.

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
| **Redis** | Durable, restart-surviving storage for sessions, workspaces, datasets, connections, and (with auth on) users/API keys — with an in-memory fallback when Redis isn't configured |
