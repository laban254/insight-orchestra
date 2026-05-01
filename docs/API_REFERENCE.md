# API Reference

## Overview

Insight Orchestra provides a **RESTful API** built with FastAPI. All endpoints return JSON responses and support CORS for frontend integration.

**Base URL**: `http://localhost:8000`

**Interactive Docs**:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

---

## Authentication

Insight Orchestra runs in **local/internal deployment mode** with no built-in authentication. For network-facing deployments, restrict access via firewall rules or a reverse proxy (see [Setup Guide](SETUP.md#security)).

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

#### `POST /upload`

Upload a CSV file for analysis.

**Request**: `multipart/form-data`
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `file` | File | Yes | CSV file |

**Example**:
```bash
curl -X POST http://localhost:8000/upload \
  -F "file=@data.csv"
```

**Response** `200 OK`:
```json
{
  "file_path": "/tmp/abc123_data.csv"
}
```

**Errors**:
| Status | Detail |
|--------|--------|
| `400` | `File size exceeds 50 MB limit` |
| `500` | `File upload failed.` |

---

### Process Data (Full Pipeline)

#### `POST /process`

Run the complete 4-agent pipeline (Data Janitor → Hypothesis Bot → Debate Manager → Viz Whiz). Emits SSE events to `/agents/stream/{session_id}`.

**Request Body**:
```json
{
  "file_path": "/tmp/abc123_data.csv"
}
```

**Optional query parameter**: `session_id` (for SSE event correlation)

**Example**:
```bash
curl -X POST http://localhost:8000/process \
  -H "Content-Type: application/json" \
  -d '{"file_path": "/tmp/abc123_data.csv"}'
```

**Response** `200 OK`:
```json
{
  "cleaner": {
    "cleaned_data": [...],
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
| `404` | `File not found.` |
| `400` | `Failed to read CSV: ...` |

---

### Natural Language Query

#### `POST /nlq`

Convert a natural language question into pandas code, execute it in the sandbox, and return results. Also emits SSE events to `/agents/stream/{session_id}` (Data Janitor + Viz Whiz stages).

**Request Body**:
```json
{
  "file_path": "/tmp/abc123_data.csv",
  "question": "What's the average salary by department?",
  "session_id": "optional-sse-session-id"
}
```

**Example**:
```bash
curl -X POST http://localhost:8000/nlq \
  -H "Content-Type: application/json" \
  -d '{
    "file_path": "/tmp/abc123_data.csv",
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
| `400` | `Failed to read CSV: ...` |
| `404` | `File not found.` |

---

### Summarize

#### `POST /summarize`

Generate a text summary of workflow results.

**Request Body**:
```json
{
  "workflow_results": {
    "cleaner": {...},
    "hypothesis": {...},
    "debate": {...},
    "viz": {...}
  }
}
```

**Response** `200 OK`:
```json
{
  "summary": "The dataset had 15 columns and 1000 rows. 5 duplicates were removed. 5 hypotheses were generated..."
}
```

---

### Explain

#### `POST /explain`

Generate a plain-English explanation for a Plotly chart (rule-based, not LLM-powered).

**Request Body**:
```json
{
  "plot": {
    "chart_type": "scatter",
    "x_column": "age",
    "y_column": "salary"
  }
}
```

**Response** `200 OK`:
```json
{
  "explanation": "This scatter plot shows the relationship between age and salary."
}
```

---

### Generate Report

#### `POST /report`

Generate an HTML report from workflow results.

**Request Body**:
```json
{
  "workflow_results": {...}
}
```

**Response** `200 OK`:
```json
{
  "report_path": "/tmp/report_abc123.html"
}
```

---

### BigQuery Query

#### `POST /bigquery`

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
  "file_path": "/tmp/bq_abc123.csv",
  "columns": ["id", "name", "created_at"],
  "row_count": 100
}
```

**Errors**:
| Status | Detail |
|--------|--------|
| `400` | Validation error (e.g., empty credentials) |
| `500` | `BigQuery error: ...` |

---

### Database Connection

#### `POST /connectors/connect`

Connect to a database for live querying.

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
  "database": "mydb",
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
| `500` | `Connection failed. Check your credentials.` |

#### `GET /connectors/schema`

List the schema of the currently connected database.

**Response** `200 OK`:
```json
{
  "schema": { "table_name": [{"name": "col", "type": "type"}] }
}
```

---

### Session Management

#### `GET /sessions/{session_id}`

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

#### `DELETE /sessions/{session_id}`

Clear a session's history.

**Response** `200 OK`:
```json
{
  "status": "cleared"
}
```

---

### Session Sharing

#### `POST /sessions/share`

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

#### `GET /sessions/shared/{token}`

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

#### `GET /export/{session_id}/html`

Export session results as an HTML file. Currently returns mock data.

**Response**: `200 OK` — HTML file download.

#### `GET /export/{session_id}/markdown`

Export session results as Markdown. Currently returns mock data.

**Response**: `200 OK` — Markdown text file download.

#### `GET /export/{session_id}/csv`

Export session results as CSV. Currently returns mock data.

**Response**: `200 OK` — CSV file download.

---

### Demo Datasets

#### `GET /demo/list`

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

#### `GET /demo/load`

Load a demo dataset by ID. Disabled when `DEMO_MODE=false`.

**Query parameter**: `dataset_id` (default: `"sales"`)

**Response** `200 OK`:
```json
{
  "file_path": "/tmp/demo_sales_abc123.csv",
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

#### `GET /agents/stream/{session_id}`

Server-Sent Events endpoint that streams real-time agent progress. Used by the frontend [`AgentPipeline`](frontend/components/agents/AgentPipeline.tsx) component.

Events are consumed after calling `/process` or `/nlq` with a matching `session_id`.

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
UPLOAD_RESPONSE=$(curl -s -X POST http://localhost:8000/upload \
  -F "file=@sales_data.csv")

FILE_PATH=$(echo $UPLOAD_RESPONSE | jq -r '.file_path')

# 2. Create a session ID for SSE streaming
SESSION_ID="test-session-1"

# Open SSE stream in another terminal:
# curl -N http://localhost:8000/agents/stream/$SESSION_ID

# 3. Process data through full pipeline
curl -s -X POST "http://localhost:8000/process?session_id=$SESSION_ID" \
  -H "Content-Type: application/json" \
  -d "{\"file_path\": \"$FILE_PATH\"}"

# 4. Ask a question
curl -s -X POST http://localhost:8000/nlq \
  -H "Content-Type: application/json" \
  -d "{
    \"file_path\": \"$FILE_PATH\",
    \"question\": \"Sales by region this quarter?\",
    \"session_id\": \"$SESSION_ID\"
  }"
```

### Database Query

```bash
# Connect to PostgreSQL
curl -X POST http://localhost:8000/connectors/connect \
  -H "Content-Type: application/json" \
  -d '{
    "type": "postgresql",
    "connection_string": "postgresql://user:pass@localhost/db"
  }'

# Get schema
curl http://localhost:8000/connectors/schema
```
