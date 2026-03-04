# API Reference

## Overview

Insight Orchestra provides a **RESTful API** built with FastAPI. All endpoints return JSON responses and support CORS for front-end integration.

**Base URL**: `http://localhost:8000`

**Interactive Docs**:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

---

## Authentication

Insight Orchestra currently runs in **local/internal deployment mode** with session-based access through the frontend. For multi-user or cloud deployments, see [Security & Authentication](SETUP.md#-security--authentication) in the setup guide.

---

## Core Endpoints

### Health Check

#### `GET /health`

Check if the backend is running.

**Response**:
```json
{
  "status": "ok"
}
```

**Status Code**: `200 OK`

---

### File Upload

#### `POST /upload`

Upload a CSV file for analysis.

**Request**:
```
Content-Type: multipart/form-data

Parameters:
- file: File (required) - CSV file
```

**Example**:
```bash
curl -X POST http://localhost:8000/upload \
  -F "file=@data.csv"
```

**Response**:
```json
{
  "file_path": "/home/kibe/pro/engineeringhub/insight-orchestra/backend/uploads/abc123_data.csv",
  "file_size_kb": 156,
  "rows": 1000,
  "columns": 15
}
```

**Status Code**: `200 OK`

**Error Responses**:
```json
{
  "detail": "File size exceeds 100 MB limit"
}
```

Status Code: `400 Bad Request`

---

### Process Data (Full Pipeline)

#### `POST /process`

Run the complete Insight Orchestra agent pipeline on a file.

**Request Body**:
```json
{
  "file_path": "/path/to/uploaded/file.csv"
}
```

**Example**:
```bash
curl -X POST http://localhost:8000/process \
  -H "Content-Type: application/json" \
  -d '{
    "file_path": "/home/kibe/pro/engineeringhub/insight-orchestra/backend/uploads/abc123_data.csv"
  }'
```

**Response**:
```json
{
  "cleaned_data_summary": {
    "shape": [1000, 15],
    "duplicates_removed": 5,
    "missing_values_imputed": true,
    "bias_flags": []
  },
  "hypotheses": [
    "Age and salary correlate positively",
    "Department type affects performance",
    "Geographic location impacts retention"
  ],
  "top_insight": {
    "hypothesis": "Age and salary correlate positively",
    "confidence": 0.89,
    "visualization_html": "<div>...</div>"
  },
  "session_id": "sess_xyz123"
}
```

**Status Code**: `200 OK`

**Error Responses**:
```json
{
  "detail": "File not found"
}
```

Status Code: `404 Not Found`

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

**Supported Types**:
- `postgresql`
- `mysql`
- `sqlite`
- `duckdb`

**Example**:
```bash
curl -X POST http://localhost:8000/connectors/connect \
  -H "Content-Type: application/json" \
  -d '{
    "type": "postgresql",
    "connection_string": "postgresql://user:pass@localhost:5432/analytics"
  }'
```

**Response**:
```json
{
  "status": "connected",
  "database": "analytics",
  "schema": {
    "users": [
      {"name": "id", "type": "integer"},
      {"name": "email", "type": "varchar"},
      {"name": "created_at", "type": "timestamp"}
    ],
    "orders": [
      {"name": "id", "type": "integer"},
      {"name": "user_id", "type": "integer"},
      {"name": "total", "type": "decimal"}
    ]
  }
}
```

**Status Code**: `200 OK`

**Error Responses**:
```json
{
  "detail": "Connection failed. Check your credentials."
}
```

Status Code: `500 Internal Server Error`

---

### Natural Language Query

#### `POST /nlq`

Convert a natural language question into code and execute it.

**Request Body**:
```json
{
  "file_path": "/path/to/file.csv",
  "question": "What's the average salary by department?"
}
```

**Optional Fields**:
```json
{
  "session_id": "sess_xyz123"
}
```

**Example**:
```bash
curl -X POST http://localhost:8000/nlq \
  -H "Content-Type: application/json" \
  -d '{
    "file_path": "/home/kibe/pro/engineeringhub/insight-orchestra/backend/uploads/abc123_data.csv",
    "question": "Show me top 5 departments by average salary"
  }'
```

**Response**:
```json
{
  "question": "Show me top 5 departments by average salary",
  "generated_code": "df.groupby('department')['salary'].mean().nlargest(5)",
  "results": {
    "Engineering": 145000,
    "Data Science": 138000,
    "Product": 132000,
    "Sales": 98000,
    "HR": 75000
  },
  "visualization_html": "<div>...</div>",
  "execution_time_ms": 245
}
```

**Status Code**: `200 OK`

**Error Responses**:
```json
{
  "detail": "Code execution failed: invalid column name"
}
```

Status Code: `400 Bad Request`

---

### Export Results

#### `POST /export`

Export analysis results in various formats.

**Request Body**:
```json
{
  "session_id": "sess_xyz123",
  "format": "csv"
}
```

**Supported Formats**:
- `csv` - Comma-separated values
- `json` - JSON format
- `parquet` - Apache Parquet (for large datasets)
- `pdf` - PDF report (includes visualizations)

**Example**:
```bash
curl -X POST http://localhost:8000/export \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "sess_xyz123",
    "format": "csv"
  }' \
  --output results.csv
```

**Response**: File download (binary content)

**Status Code**: `200 OK`

---

### Get Session Data

#### `GET /sessions/{session_id}`

Retrieve details from a previous session.

**Example**:
```bash
curl http://localhost:8000/sessions/sess_xyz123
```

**Response**:
```json
{
  "session_id": "sess_xyz123",
  "file_path": "/path/to/file.csv",
  "created_at": "2024-03-04T10:30:00Z",
  "chat_history": [
    {
      "role": "user",
      "content": "What's the average salary?"
    },
    {
      "role": "assistant",
      "content": "...",
      "code": "df['salary'].mean()"
    }
  ],
  "insights": [...]
}
```

**Status Code**: `200 OK`

---

## Request/Response Format

### Headers

All requests should include:
```
Content-Type: application/json
```

### Status Codes

| Code | Meaning |
|------|---------|
| `200` | Success |
| `400` | Bad Request (client error) |
| `404` | Not Found |
| `500` | Server Error |

### Error Format

```json
{
  "detail": "Human-readable error message"
}
```

---

## Rate Limiting

**Current**: Unlimited (designed for local/internal deployment)

**Production Rate Limits** (coming soon):
- Per IP: 100 requests/minute
- Per session: 10 requests/second
- Execution timeout: 30 seconds

---

## Examples

### Complete Workflow

```bash
# 1. Upload CSV
UPLOAD_RESPONSE=$(curl -s -X POST http://localhost:8000/upload \
  -F "file=@sales_data.csv")

FILE_PATH=$(echo $UPLOAD_RESPONSE | jq -r '.file_path')

# 2. Process data through full pipeline
curl -s -X POST http://localhost:8000/process \
  -H "Content-Type: application/json" \
  -d "{\"file_path\": \"$FILE_PATH\"}"

# 3. Ask a question
curl -s -X POST http://localhost:8000/nlq \
  -H "Content-Type: application/json" \
  -d "{
    \"file_path\": \"$FILE_PATH\",
    \"question\": \"Sales by region this quarter?\"
  }"

# 4. Export results
SESSION_ID="..."
curl -s -X POST http://localhost:8000/export \
  -H "Content-Type: application/json" \
  -d "{
    \"session_id\": \"$SESSION_ID\",
    \"format\": \"csv\"
  }" \
  --output results.csv
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

# Query connected database
curl -X POST http://localhost:8000/nlq \
  -H "Content-Type: application/json" \
  -d '{
    "file_path": "db://connected_db",
    "question": "Revenue by customer segment?"
  }'
```

---

## WebSocket Endpoints (Coming Soon)

Real-time streaming responses:
- `WS /analyze/stream` - Stream agent pipeline execution with live agent updates
- `WS /chat/stream` - Real-time chat responses as they're generated

---

## SDK/Client Libraries (Coming Soon)

Official client libraries for easier integration:
- **Python**: `pip install insight-orchestra-python`
- **JavaScript**: `npm install insight-orchestra-js`
- **Go**: `go get github.com/laban254/insight-orchestra-go`

---

## Changelog

### v1.0.0 (Current)
- Initial API release
- Core endpoints: upload, process, nlq, export
- Single file / session management

### v1.1.0 (Planned)
- Database connectors
- Batch processing
- WebSocket streaming
- Export formats (PDF, Excel)
