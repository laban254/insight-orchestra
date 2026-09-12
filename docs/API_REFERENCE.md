# API Reference

## Overview

Insight Orchestra provides a **RESTful API** built with FastAPI. All endpoints return JSON responses and support CORS for frontend integration.

**Base URL**: `http://localhost:8000/api/v1` — every endpoint below except Health Check lives under this prefix.

**Interactive Docs** (unversioned, outside the `/api/v1` prefix):
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

---

## Authentication

Auth is **off by default** (`AUTH_ENABLED=false`) — Insight Orchestra runs in local/internal
deployment mode with no login, exactly as before. For network-facing deployments, either
restrict access via firewall rules / a reverse proxy (see [Setup Guide](SETUP.md#security)),
or turn on the built-in auth layer described below.

When `AUTH_ENABLED=true`, every endpoint that isn't explicitly public (see below) requires
a signed-in identity: either the `io_session` httponly cookie set by `/auth/login` or
`/auth/oidc/callback`, or an API key as `Authorization: Bearer <key>`. Three roles:

| Role | Can do |
|------|--------|
| `admin` | Everything — config/provider switching, connector connect/disconnect, user management, audit log |
| `member` | Upload, analyze (`/process`, `/nlq`), query connected databases, export, save workspaces |
| `viewer` | Read-only — view datasets, sessions, workspaces, exports; cannot upload, analyze, or change anything |

`GET /api/v1/sessions/shared/{token}` is always public, auth on or off — the share token
itself is the access control there, by design.

### `POST /api/v1/auth/login`
```json
{"email": "admin@example.com", "password": "..."}
```
Sets the `io_session` cookie. `401` on a wrong password or an SSO-only account.

### `POST /api/v1/auth/logout`
Revokes the session and clears the cookie.

### `GET /api/v1/auth/me`
```json
{"auth_enabled": true, "oidc_configured": false, "user": {"id": "...", "email": "...", "role": "admin", "...": "..."}}
```
Safe to call with auth off — `user` is just `null`.

### `GET /api/v1/auth/oidc/login` / `GET /api/v1/auth/oidc/callback`
SSO via OIDC (Authorization Code flow, discovery + JWKS-verified — see `OIDC_ISSUER` /
`OIDC_CLIENT_ID` / `OIDC_CLIENT_SECRET` / `OIDC_REDIRECT_URI` in the [Setup Guide](SETUP.md)).
The first person ever to sign in via SSO becomes `admin`; everyone after starts as `member`.
SAML is not supported.

### API keys — `POST` / `GET` / `DELETE /api/v1/auth/api-keys`
Self-service, for headless callers. `POST` returns the raw key exactly once
(`{"key": "iok_...", ...}`) — it's never shown or stored again, only its hash and a short
display prefix.

### User management (admin-only) — `GET`/`POST /api/v1/auth/users`, `PATCH`/`DELETE /api/v1/auth/users/{id}`
Create/list/update-role/deactivate/delete accounts.

### Audit log (admin-only)
`GET /api/v1/audit/log` (recent entries) and `GET /api/v1/audit/export` (full history as
JSON Lines, for a SIEM) — covers login/logout, config changes, connector connect/disconnect,
dataset deletes, and user/API-key management.

---

## Core Endpoints

### Health Check

#### `GET /health`

Check if the backend is running.

**Response** `200 OK`:
```json
{
  "status": "ok"
}
```

---

### File Upload

#### `POST /api/v1/upload`

Upload a dataset file for analysis — CSV, TSV, Excel (`.xlsx`), JSON, or Parquet.

**Request**: `multipart/form-data`
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `file` | File | Yes | `.csv`, `.tsv`, `.xlsx`, `.json`, or `.parquet` |

**Example**:
```bash
curl -X POST http://localhost:8000/api/v1/upload \
  -F "file=@data.csv"
```

**Response** `200 OK`:
```json
{
  "dataset_id": "8f14e45fceea167a5a36dedd4bea2543",
  "name": "data.csv",
  "rows": 995,
  "columns": 15,
  "column_names": ["date", "region", "revenue"],
  "dtypes": {"date": "datetime64[ns]", "region": "str", "revenue": "float64"},
  "null_counts": {"date": 0, "region": 2, "revenue": 0},
  "preview": [{"date": "2024-01-01T00:00:00", "region": "North", "revenue": 100.0}],
  "assumptions": {
    "encoding": "utf-8",
    "delimiter": ",",
    "datetime_columns": ["date"]
  }
}
```

The file is parsed during upload, so a file that cannot be read fails here
rather than later during analysis. `assumptions` reports what had to be
detected for CSV/TSV — a non-comma delimiter, a non-UTF-8 encoding, or
columns parsed as dates — so the client can tell the user what was inferred.
Excel/JSON/Parquet have no delimiter or encoding to detect, so both fields
come back as empty strings for those formats.

The client receives an opaque `dataset_id`, never a server path.

**Errors**:
| Status | Detail |
|--------|--------|
| `400` | `Only CSV, TSV, Excel (.xlsx), JSON, or Parquet files are allowed.` |
| `400` | `File too large. Maximum is 50 MB.` |
| `400` | `This looks like a spreadsheet or archive rather than a CSV...` (wrong content for a `.csv`/`.tsv` extension) |
| `400` | `This doesn't look like a valid .xlsx file.` / `...valid Parquet file.` / `...valid JSON text.` (wrong content for the claimed extension) |
| `500` | `File upload failed.` |

---

### Process Data (Full Pipeline)

#### `POST /api/v1/process`

Run the complete 4-agent pipeline (Data Janitor → Hypothesis Bot → Debate Manager → Viz Whiz). Emits SSE events to `/api/v1/agents/stream/{session_id}`.

**Request Body**:
```json
{
  "dataset_id": "8f14e45fceea167a5a36dedd4bea2543"
}
```

**Optional query parameter**: `session_id` (for SSE event correlation)

**Example**:
```bash
curl -X POST http://localhost:8000/api/v1/process \
  -H "Content-Type: application/json" \
  -d '{"dataset_id": "8f14e45fceea167a5a36dedd4bea2543"}'
```

**Response** `200 OK`:
```json
{
  "cleaner": {
    "report": {
      "initial_shape": [1000, 15],
      "duplicates_removed": 5,
      "missing_values": {"age": 12},
      "total_missing": 15,
      "bias_flags": ["Column 'age' missing for 15.0% of rows."],
      "missing_values_imputed": true,
      "constant_columns": [],
      "final_shape": [995, 15]
    }
  },
  "hypothesis": {
    "hypotheses": ["Age and salary correlate strongly", "..."],
    "summary": {"num_hypotheses": 5, "reasoning": "..."},
    "revised_hypotheses": ["..."],
    "revised": true
  },
  "debate": {
    "scored_hypotheses": [
      {"hypothesis": "...", "confidence": 0.85, "business_value": 0.9, "statistical_argument": "...", "business_argument": "..."}
    ],
    "summary": {
      "num_hypotheses": 5,
      "consensus": {"hypothesis": "...", "confidence": 0.85, "business_value": 0.9},
      "arguments": [{"hypothesis": "...", "statistical": "...", "business": "..."}]
    }
  },
  "viz": {
    "chart_info": {
      "success": true,
      "plots": [{"type": "scatter", "title": "Scatter plot of age vs salary", "plotly_json": "{...}"}]
    }
  },
  "audit_table": "| Feature | Pass/Fail | Evidence |..."
}
```

**Errors**:
| Status | Detail |
|--------|--------|
| `404` | `That dataset is no longer available. Upload it again to continue.` |
| `400` | `Could not read the file: ...` |

---

### Natural Language Query

#### `POST /api/v1/nlq`

Convert a natural language question into pandas code, execute it in the sandbox, and return results. Also emits SSE events to `/api/v1/agents/stream/{session_id}` (Data Janitor + Viz Whiz stages).

**Request Body**:
```json
{
  "dataset_id": "8f14e45fceea167a5a36dedd4bea2543",
  "question": "What's the average salary by department?",
  "session_id": "optional-sse-session-id"
}
```

**Example**:
```bash
curl -X POST http://localhost:8000/api/v1/nlq \
  -H "Content-Type: application/json" \
  -d '{
    "dataset_id": "8f14e45fceea167a5a36dedd4bea2543",
    "question": "Show me top 5 departments by average salary"
  }'
```

**Response** `200 OK`:
```json
{
  "answer": "The top 5 departments by average salary are Engineering ($145,000), Data Science ($138,000)...",
  "code": "df.groupby('department')['salary'].mean().nlargest(5)",
  "reasoning": "Grouped by department, computed mean salary, selected top 5.",
  "plot_json": null,
  "needs_clarification": false,
  "clarification_question": null,
  "execution_success": true,
  "error": null,
  "session_id": "optional-session-id"
}
```

**Errors**:
| Status | Detail |
|--------|--------|
| `400` | `Could not read the file: ...` |
| `404` | `That dataset is no longer available. Upload it again to continue.` |

---

### Datasets

Every ingestion path (`/api/v1/upload`, `/api/v1/demo/load`, `/api/v1/connectors/load-table`,
`/api/v1/bigquery`) registers the data it materializes and returns an opaque
`dataset_id`. The client never receives or sends a filesystem path, so
`/api/v1/process` and `/api/v1/nlq` have no caller-supplied path to validate. Files live
on the mounted uploads volume, so they survive a container recreate.

#### `GET /api/v1/datasets/{dataset_id}`

Whether a dataset is still usable, plus its shape and a preview. The UI
calls this when reopening a saved analysis so it can report missing data up
front instead of failing on the next question.

**Response** `200 OK`: same body as `/api/v1/upload`, plus the `source` it came
from (`upload`, `demo:<id>`, `database`, `bigquery`).

Demo datasets are regenerated on demand if their file has been removed, so
an old workspace built on demo data reopens normally.

**Errors**:
| Status | Detail |
|--------|--------|
| `404` | `That dataset is no longer available. Upload it again to continue.` |

#### `DELETE /api/v1/datasets/{dataset_id}`

Forget a dataset and delete its file.

---

### Runtime Config

#### `GET /api/v1/config`

Current LLM provider/model, and which providers are actually ready to serve a request right now (API key configured, or Ollama reachable). Admin-only.

**Response** `200 OK`:
```json
{
  "provider": "deepseek",
  "model": "deepseek-chat",
  "available": ["openai", "anthropic", "deepseek", "ollama"],
  "ready": {"openai": false, "anthropic": false, "deepseek": true, "ollama": false}
}
```

#### `POST /api/v1/config`

Switch the LLM provider and/or model at runtime — no restart needed. Admin-only.

**Request Body**:
```json
{"provider": "openai", "model": "gpt-4o-mini"}
```

**Errors**:
| Status | Detail |
|--------|--------|
| `400` | `Unknown provider '...'.` |
| `400` | `Ollama is not reachable at ...` / `No API key configured for '...' on the server.` |

---

### Dataset Rows & Transform

#### `GET /api/v1/datasets/{dataset_id}/rows`

A page of rows from the dataset, for browsing past the fixed 20-row preview returned by `/upload` and `GET /datasets/{id}`.

**Query parameters**: `offset` (default `0`), `limit` (default `50`, max `500`)

**Response** `200 OK`:
```json
{
  "columns": ["date", "region", "revenue"],
  "rows": [{"date": "2024-01-01T00:00:00", "region": "North", "revenue": 100.0}],
  "total_rows": 995,
  "offset": 0,
  "limit": 50,
  "has_more": true
}
```

#### `POST /api/v1/datasets/{dataset_id}/transform`

Apply a deterministic column transform — `normalize` (min-max to 0–1), `scale` (z-score), or `encode` (integer-code each distinct value) — without needing the LLM to write pandas code for a fixed, well-known operation. Non-destructive: writes the result as a new dataset rather than mutating the original. Member+.

**Request Body**:
```json
{"column": "salary", "operation": "normalize", "new_column": "salary_normalized"}
```
`new_column` is optional, defaulting to `{column}_{operation}`.

**Response** `200 OK`: a new `dataset_id` plus the same shape/preview body as `/upload`.

**Errors**:
| Status | Detail |
|--------|--------|
| `400` | `Column '...' not found.` |
| `400` | `'normalize'/'scale' needs a numeric column; '...' is ...` |

---

### BigQuery Query

#### `POST /api/v1/bigquery`

> **Experimental — not enabled by default.** `google-cloud-bigquery` is an
> optional dependency and is *not* installed in the published images, so this
> endpoint returns `501` until an operator runs
> `pip install google-cloud-bigquery` in the backend environment. There is no
> UI for it; it is reachable over the API only.

Run a SQL query against Google BigQuery using service account credentials.

**Request Body**:
```json
{
  "credentials_json": "{...service account JSON...}",
  "query": "SELECT * FROM `project.dataset.table` LIMIT 100"
}
```

**Response** `200 OK`:
```json
{
  "dataset_id": "8f14e45fceea167a5a36dedd4bea2543",
  "columns": ["id", "name", "created_at"],
  "row_count": 100
}
```

**Errors**:
| Status | Detail |
|--------|--------|
| `400` | Validation error (e.g., empty credentials) |
| `500` | `BigQuery error: ...` |
| `501` | Dependency not installed (the default state) |

---

### Database Connection

Connecting a database is a three-step flow: connect (get a schema + a
`connection_id`), load a table (materializes it as a CSV), then run it
through the normal analysis pipeline (`/api/v1/process`, `/api/v1/nlq`) exactly like an
uploaded file.

The live connection itself is never held open between requests, regardless — `/connect`
opens the connection just long enough to validate credentials and read the
schema, then closes it; only the connection metadata (type, connection
string, cached schema) is persisted (in Redis, with a sliding TTL — see
`DB_CONNECTION_TTL_SECONDS` in the [Setup Guide](SETUP.md)). `/load-table` and `/query`
reconnect fresh each time they're called.

> With auth on, connecting/disconnecting/listing local DB files is **admin-only** — running
> a query against an already-connected database (`POST /connectors/query`) is `member`+.

#### `GET /api/v1/connectors/local-files`

SQLite/DuckDB files the backend can actually reach — the uploads directory is
bind-mounted into the container, so it's the one place a user can drop a
database file and have a path resolve. Admin-only.

**Response** `200 OK`:
```json
{
  "host_directory": "./backend/uploads",
  "files": [{"name": "sample.duckdb", "path": "/app/uploads/sample.duckdb"}]
}
```

#### `POST /api/v1/connectors/connect`

**Request Body**:
```json
{
  "type": "postgresql",
  "connection_string": "postgresql://user:password@localhost:5432/mydb"
}
```

**Supported Types**: `postgresql`, `mysql`, `sqlite`, `duckdb`

**Response** `200 OK`:
```json
{
  "status": "connected",
  "connection_id": "5518441615654de8b110d090db78de1f",
  "schema": {
    "users": [
      {"name": "id", "type": "integer"},
      {"name": "email", "type": "varchar"}
    ]
  }
}
```

**Errors**:
| Status | Detail |
|--------|--------|
| `400` | `Connection string cannot be empty.` |
| `400` | `Invalid connection string. Expected format: postgresql://user:password@host:5432/dbname` — malformed string caught before it reaches the driver |
| `400` | `Failed to connect: ...` — the driver's own error (wrong host, refused connection, bad auth) |
| `500` | `Connection failed. Check your credentials.` |

> Connecting from inside Docker to a database on your host machine? `localhost`
> means the container itself, not your host. See
> [Connecting to a database on your host machine](SETUP.md#connecting-to-a-database-on-your-host-machine).

#### `POST /api/v1/connectors/load-table`

Materialize a table from a connected database into a CSV, using the
`connection_id` returned by `/connect`.

**Request Body**:
```json
{
  "connection_id": "5518441615654de8b110d090db78de1f",
  "table_name": "users",
  "row_limit": 50000
}
```
`row_limit` is optional (default `50000`, capped at `500000`).

**Response** `200 OK`:
```json
{
  "dataset_id": "8f14e45fceea167a5a36dedd4bea2543",
  "table_name": "users",
  "row_count": 1000,
  "column_count": 6,
  "columns": ["id", "email", "..."]
}
```
Pass `dataset_id` to `/api/v1/process` or `/api/v1/nlq` just like an uploaded file's id.

**Errors**:
| Status | Detail |
|--------|--------|
| `404` | `Connection not found or expired. Please reconnect to the database.` |
| `400` | `Unknown table: ...` — table isn't in the connection's schema |
| `400` | `Failed to load table: ...` — query failed against the live database |

#### `POST /api/v1/connectors/query`

Multi-table NL→SQL: answer a question directly against the connected
database — JOIN-capable across every table in scope — instead of
materializing a single table first like `/load-table` + `/nlq` do. Member+.

**Request Body**:
```json
{
  "connection_id": "5518441615654de8b110d090db78de1f",
  "question": "How many orders did each customer place last month?"
}
```

**Response** `200 OK`:
```json
{
  "answer": "Customer 'Acme Corp' placed the most orders (14) last month...",
  "sql": "SELECT c.name, COUNT(*) FROM orders o JOIN customers c ON ... GROUP BY c.name",
  "reasoning": "Joined orders to customers and grouped by customer.",
  "plot_json": null,
  "tables_used": ["orders", "customers"],
  "needs_clarification": false,
  "clarification_question": null,
  "execution_success": true,
  "error": null
}
```

**Errors**:
| Status | Detail |
|--------|--------|
| `404` | `Connection not found or expired. Please reconnect to the database.` |
| `400` | `Failed to connect: ...` |

#### `DELETE /api/v1/connectors/{connection_id}`

Disconnect and forget a connection before its TTL expires.

**Response** `200 OK`: `{"status": "disconnected"}`
**Errors**: `404` — `Connection not found or already expired.`

#### `GET /api/v1/connectors/schema`

Placeholder — not yet implemented (always returns `{"status": "not_implemented"}`).
Use the `schema` field returned by `/api/v1/connectors/connect` instead.

---

### Workspaces

A saved snapshot of the frontend's UI state (pinned results, chat history, dataset
reference) — lets a user close the tab and reopen the same analysis later, from any
browser. With auth on, reads require any signed-in role and writes require `member`+;
with auth off, unauthenticated, same as everything else.

#### `GET /api/v1/workspaces`

List saved workspaces (metadata only), most recently updated first.

**Response** `200 OK`:
```json
{"workspaces": [{"id": "ws_abc", "datasetName": "sales.csv", "datasetId": "...", "createdAt": 1730000000000, "updatedAt": 1730000500000}]}
```

#### `GET /api/v1/workspaces/{workspace_id}`

Fetch a full workspace record (metadata + saved UI state). `404` if not found.

#### `PUT /api/v1/workspaces/{workspace_id}`

Create or update a workspace — the saved state replaces any previous one. Member+.

**Request Body**:
```json
{"datasetName": "sales.csv", "datasetId": "8f14e45fceea167a5a36dedd4bea2543", "state": {"...": "..."}}
```

**Errors**: `400` — `Invalid workspace id.` (must match `^[A-Za-z0-9_-]{1,64}$`)

#### `DELETE /api/v1/workspaces/{workspace_id}`

Delete a saved workspace. Member+.

---

### Session Management

#### `GET /api/v1/sessions/{session_id}`

Retrieve chat history for a session.

**Response** `200 OK`:
```json
{
  "session_id": "sess_abc123",
  "history": [
    {
      "question": "What's the average salary?",
      "answer": "The average salary is $85,000",
      "code": "df['salary'].mean()"
    }
  ]
}
```

#### `DELETE /api/v1/sessions/{session_id}`

Clear a session's history.

**Response** `200 OK`:
```json
{
  "status": "cleared"
}
```

---

### Session Sharing

#### `POST /api/v1/sessions/share`

Create a share link for a session. Links expire after 72 hours.

**Request Body**:
```json
{
  "session_id": "sess_abc123"
}
```

**Response** `200 OK`:
```json
{
  "token": "share_xyz789",
  "expires_at": "2026-05-04T19:00:00Z"
}
```

#### `GET /api/v1/sessions/shared/{token}`

Access a shared session.

**Response** `200 OK`:
```json
{
  "session_id": "sess_abc123",
  "history": [...]
}
```

---

### Export

Built from the real session history stored server-side (`session_manager`) —
narrative, hypotheses, charts, and Q&A pairs for that `session_id`. Returns
`404` if the session doesn't exist or has expired.

#### `GET /api/v1/export/{session_id}/html`

Export session results as an HTML file, with charts embedded as interactive Plotly figures.

**Response**: `200 OK` — HTML file download.

#### `GET /api/v1/export/{session_id}/markdown`

Export session results as Markdown (narrative, top insights, chart titles, Q&A transcript).

**Response**: `200 OK` — Markdown text file download.

#### `GET /api/v1/export/{session_id}/csv`

Export the session's question/answer/code history as CSV. Returns `404` if no questions have been asked yet.

**Response**: `200 OK` — CSV file download.

> The frontend's "Interactive report" export button uses a separate,
> client-side HTML generator ([`exportReport.ts`](../frontend/lib/exportReport.ts))
> instead of this endpoint, since it already has the live Plotly figures in
> memory. The "Summary" and "Q&A history" export options call these endpoints
> directly.

---

### Demo Datasets

#### `GET /api/v1/demo/list`

List available demo datasets. Disabled when `DEMO_MODE=false`.

**Response** `200 OK`:
```json
{
  "datasets": {
    "sales": {
      "id": "sales",
      "name": "Sales Dataset",
      "description": "Product sales by region and quarter",
      "rows": 500,
      "columns": 8,
      "use_cases": ["aggregation", "trend analysis"]
    },
    "employees": { "...": "..." },
    "customers": { "...": "..." },
    "weather": { "...": "..." },
    "movies": { "...": "..." }
  }
}
```

#### `GET /api/v1/demo/load`

Load a demo dataset by ID. Disabled when `DEMO_MODE=false`.

**Query parameter**: `dataset_id` (default: `"sales"`)

**Response** `200 OK`:
```json
{
  "dataset_id": "8f14e45fceea167a5a36dedd4bea2543",
  "dataset_id": "sales",
  "dataset_name": "Sales Dataset",
  "columns": ["product", "region", "sales", "quarter"],
  "row_count": 500,
  "column_count": 8,
  "description": "Product sales by region and quarter",
  "use_cases": ["aggregation", "trend analysis"]
}
```

---

### Real-Time Agent Streaming (SSE)

#### `GET /api/v1/agents/stream/{session_id}`

Server-Sent Events endpoint that streams real-time agent progress. Used by the frontend [`AgentTimeline`](frontend/components/agents/AgentTimeline.tsx) component.

Events are consumed after calling `/api/v1/process` or `/api/v1/nlq` with a matching `session_id`.

**Event format** (SSE `data:` field):
```json
{
  "agent_id": "janitor",
  "status": "running",
  "output": null,
  "duration": null
}
```

```json
{
  "agent_id": "janitor",
  "status": "done",
  "output": "Removed 5 dupes, imputed 15 missing values.",
  "duration": 1234
}
```

The stream ends when a sentinel (`None`) is received, or after 60 seconds of inactivity.

---

## Request/Response Format

### Headers

All API requests with JSON bodies should include:
```
Content-Type: application/json
```

### Status Codes

| Code | Meaning |
|------|---------|
| `200` | Success |
| `400` | Bad Request (client error) |
| `404` | Not Found |
| `403` | Forbidden (path traversal blocked) |
| `500` | Server Error |

### Error Format

```json
{
  "detail": "Human-readable error message"
}
```

---

## Examples

### Complete Workflow

```bash
# 1. Upload CSV
UPLOAD_RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/upload \
  -F "file=@sales_data.csv")

DATASET_ID=$(echo $UPLOAD_RESPONSE | jq -r '.dataset_id')

# 2. Create a session ID for SSE streaming
SESSION_ID="test-session-1"

# Open SSE stream in another terminal:
# curl -N http://localhost:8000/api/v1/agents/stream/$SESSION_ID

# 3. Process data through full pipeline
curl -s -X POST "http://localhost:8000/api/v1/process?session_id=$SESSION_ID" \
  -H "Content-Type: application/json" \
  -d "{\"dataset_id\": \"$DATASET_ID\"}"

# 4. Ask a question
curl -s -X POST http://localhost:8000/api/v1/nlq \
  -H "Content-Type: application/json" \
  -d "{
    \"dataset_id\": \"$DATASET_ID\",
    \"question\": \"Sales by region this quarter?\",
    \"session_id\": \"$SESSION_ID\"
  }"
```

### Database Query

```bash
# 1. Connect — returns a connection_id and the DB's schema
CONNECTION_ID=$(curl -s -X POST http://localhost:8000/api/v1/connectors/connect \
  -H "Content-Type: application/json" \
  -d '{
    "type": "postgresql",
    "connection_string": "postgresql://user:pass@localhost:5432/db"
  }' | jq -r '.connection_id')

# 2. Load a table — materializes it as a CSV
DATASET_ID=$(curl -s -X POST http://localhost:8000/api/v1/connectors/load-table \
  -H "Content-Type: application/json" \
  -d "{\"connection_id\": \"$CONNECTION_ID\", \"table_name\": \"users\"}" \
  | jq -r '.dataset_id')

# 3. Run it through the normal pipeline
curl -s -X POST http://localhost:8000/api/v1/process \
  -H "Content-Type: application/json" \
  -d "{\"dataset_id\": \"$DATASET_ID\"}"

# Optional: disconnect early instead of waiting for the TTL
curl -X DELETE http://localhost:8000/api/v1/connectors/$CONNECTION_ID
```
