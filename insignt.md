# Insight Orchestra — Improvement Roadmap
> From "another CSV chatbot" to the definitive open-source data intelligence platform

---

## Snapshot

| | |
|---|---|
| **Phases** | 4 |
| **Timeline** | 12 Weeks |
| **Key Features** | Multi-DB, Ollama, React UI, Collaboration |
| **Estimated Hours** | ~160 hrs |

---

## What You Have vs. What You Need

```
CURRENT STATE                        TARGET STATE
─────────────────────────────────    ─────────────────────────────────
CSV upload only              →       PostgreSQL, MySQL, SQLite, DuckDB
Cloud LLM only (OpenAI)      →       Ollama local LLM support
Streamlit UI (dev-grade)     →       React/Next.js (production-grade)
Solo usage                   →       Team sharing + export
Hidden BigQuery feature      →       All connectors front and centre
"Julius alternative"         →       The open-source data intelligence OS
```

---

## The Competitor Reality Check

Before diving into the plan, you need to know exactly who you are up against:

| Tool | Strength | Weakness | Your Advantage |
|------|----------|----------|----------------|
| **Julius AI** | Polished UX, broad user base | Expensive ($25+/mo), 15 msg free limit, no privacy | You are free, self-hostable, unlimited |
| **Vanna AI** | Deep SQL/warehouse integration | No multi-agent pipeline, no hypothesis generation | Your 4-agent architecture is unique |
| **Chat2DB** | Schema-aware queries, ERD gen | No hypothesis engine, no debate scoring | Your Debate Manager is genuinely novel |
| **Deepnote** | Collaboration, real-time | Requires cloud, data leaves your machine | Your local-only execution is the moat |
| **PandasAI** | Dev-friendly, Python-native | No UI, no agents, just code gen | You have a full UI and agent pipeline |

**Your actual USP (say this clearly in your README):**
> "The only open-source data analysis tool with a multi-agent hypothesis pipeline, sandbox execution, and full local LLM support — your data never leaves your machine."

---

## Phase Overview

| Phase | What You Build | Why It Matters | Timeline | Hours |
|-------|---------------|----------------|----------|-------|
| **Phase 1** | Database connectors + Ollama | Closes the #1 Julius complaint | Week 1–3 | ~45 hrs |
| **Phase 2** | React/Next.js UI | Looks production-grade, not a prototype | Week 4–6 | ~50 hrs |
| **Phase 3** | Export + Collaboration | Makes it useful inside teams | Week 7–9 | ~35 hrs |
| **Phase 4** | Polish + GitHub growth | Makes it impossible to ignore | Week 10–12 | ~30 hrs |

---

## Phase 1 — Database Connectors + Local LLM
### `Week 1–3 · ~45 hours`

This is your most important phase. Right now Insight Orchestra has the same limitation as Julius AI — users must upload CSVs manually. Adding live database connections is the single change that transforms your positioning from "alternative to Julius" to "actually better than Julius."

---

### 1.1 Multi-Database Support

Add connectors for four databases. Each one is 2–3 days of work and opens a completely new user segment.

**New file structure:**
```
backend/app/
├── connectors/
│   ├── __init__.py
│   ├── base.py           ← Abstract base connector class
│   ├── postgresql.py     ← PostgreSQL + schema introspection
│   ├── mysql.py          ← MySQL / MariaDB
│   ├── sqlite.py         ← SQLite (zero-config, great for demos)
│   └── duckdb.py         ← DuckDB (analytics-optimised, fast)
```

**Base connector interface:**
```python
# backend/app/connectors/base.py

from abc import ABC, abstractmethod
import pandas as pd

class BaseConnector(ABC):

    @abstractmethod
    def connect(self, connection_string: str) -> None:
        """Establish connection to the database"""
        pass

    @abstractmethod
    def get_schema(self) -> dict:
        """Return table names + column names + types"""
        pass

    @abstractmethod
    def execute_query(self, sql: str) -> pd.DataFrame:
        """Execute SQL and return DataFrame"""
        pass

    @abstractmethod
    def test_connection(self) -> bool:
        """Health check — returns True if connected"""
        pass

    @abstractmethod
    def disconnect(self) -> None:
        pass
```

**PostgreSQL connector (most important one):**
```python
# backend/app/connectors/postgresql.py

import psycopg2
import pandas as pd
from .base import BaseConnector

class PostgreSQLConnector(BaseConnector):

    def __init__(self):
        self.connection = None
        self.cursor = None

    def connect(self, connection_string: str) -> None:
        """
        Accepts standard PostgreSQL connection strings:
        postgresql://user:password@host:5432/dbname
        """
        self.connection = psycopg2.connect(connection_string)
        self.cursor = self.connection.cursor()

    def get_schema(self) -> dict:
        """
        Returns schema as dict:
        { "users": ["id", "name", "email"], "orders": [...] }
        """
        query = """
        SELECT table_name, column_name, data_type
        FROM information_schema.columns
        WHERE table_schema = 'public'
        ORDER BY table_name, ordinal_position
        """
        self.cursor.execute(query)
        rows = self.cursor.fetchall()

        schema = {}
        for table, column, dtype in rows:
            if table not in schema:
                schema[table] = []
            schema[table].append({"name": column, "type": dtype})

        return schema

    def execute_query(self, sql: str) -> pd.DataFrame:
        # CRITICAL: read-only safety check
        sql_upper = sql.strip().upper()
        if any(sql_upper.startswith(kw) for kw in ["DROP", "DELETE", "INSERT", "UPDATE", "ALTER", "TRUNCATE"]):
            raise ValueError("Only SELECT queries are permitted")
        return pd.read_sql_query(sql, self.connection)

    def test_connection(self) -> bool:
        try:
            self.cursor.execute("SELECT 1")
            return True
        except Exception:
            return False

    def disconnect(self) -> None:
        if self.cursor:
            self.cursor.close()
        if self.connection:
            self.connection.close()
```

**DuckDB connector (analytics powerhouse — fast on large files):**
```python
# backend/app/connectors/duckdb.py

import duckdb
import pandas as pd
from .base import BaseConnector

class DuckDBConnector(BaseConnector):
    """
    DuckDB is special — it can directly query:
    - Parquet files
    - CSV files (faster than pandas)
    - JSON files
    - Remote S3 files

    This makes it a universal connector for analytical workloads.
    """

    def __init__(self):
        self.connection = None

    def connect(self, path: str = ":memory:") -> None:
        """
        path = ":memory:" for in-memory (fastest)
        path = "/path/to/file.db" for persistent
        """
        self.connection = duckdb.connect(path)

    def load_csv(self, file_path: str, table_name: str = "data") -> None:
        """Load CSV directly — no pandas needed, much faster"""
        self.connection.execute(
            f"CREATE TABLE {table_name} AS SELECT * FROM read_csv_auto('{file_path}')"
        )

    def execute_query(self, sql: str) -> pd.DataFrame:
        return self.connection.execute(sql).df()

    def get_schema(self) -> dict:
        tables = self.connection.execute("SHOW TABLES").fetchall()
        schema = {}
        for (table,) in tables:
            cols = self.connection.execute(f"DESCRIBE {table}").fetchall()
            schema[table] = [{"name": col[0], "type": col[1]} for col in cols]
        return schema
```

**Wire into FastAPI:**
```python
# backend/app/api/connectors.py

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.connectors import PostgreSQLConnector, MySQLConnector, SQLiteConnector, DuckDBConnector

router = APIRouter(prefix="/connectors", tags=["connectors"])

CONNECTOR_MAP = {
    "postgresql": PostgreSQLConnector,
    "mysql":      MySQLConnector,
    "sqlite":     SQLiteConnector,
    "duckdb":     DuckDBConnector,
}

class ConnectRequest(BaseModel):
    type: str               # "postgresql", "mysql", "sqlite", "duckdb"
    connection_string: str  # Standard connection string

@router.post("/connect")
async def connect_database(req: ConnectRequest):
    if req.type not in CONNECTOR_MAP:
        raise HTTPException(400, f"Unsupported connector: {req.type}")

    connector = CONNECTOR_MAP[req.type]()
    connector.connect(req.connection_string)

    if not connector.test_connection():
        raise HTTPException(500, "Connection failed. Check your credentials.")

    schema = connector.get_schema()
    return {"status": "connected", "schema": schema}

@router.get("/schema")
async def get_schema():
    """Returns active connection schema for the agent context"""
    # Return current session's schema
    pass
```

---

### 1.2 Ollama Local LLM Support

This is your privacy moat. Every cloud-only competitor loses on this. Your headline should be: **"zero data leaves your machine."**

**Update LLM service to support Ollama:**
```python
# backend/app/services/llm_service.py

from enum import Enum
import openai
import httpx

class LLMProvider(str, Enum):
    OPENAI    = "openai"
    ANTHROPIC = "anthropic"
    OLLAMA    = "ollama"   # NEW

class LLMService:

    def __init__(self, provider: LLMProvider, model: str, base_url: str = None):
        self.provider = provider
        self.model = model
        self.base_url = base_url or self._default_url(provider)

    def _default_url(self, provider: LLMProvider) -> str:
        return {
            LLMProvider.OPENAI:    "https://api.openai.com/v1",
            LLMProvider.ANTHROPIC: "https://api.anthropic.com",
            LLMProvider.OLLAMA:    "http://localhost:11434",  # local
        }[provider]

    async def complete(self, prompt: str, system: str = "") -> str:
        if self.provider == LLMProvider.OLLAMA:
            return await self._ollama_complete(prompt, system)
        elif self.provider == LLMProvider.OPENAI:
            return await self._openai_complete(prompt, system)
        elif self.provider == LLMProvider.ANTHROPIC:
            return await self._anthropic_complete(prompt, system)

    async def _ollama_complete(self, prompt: str, system: str) -> str:
        """
        Calls local Ollama instance.
        Recommended models for data analysis:
        - llama3.1:8b (fast, good for code gen)
        - codestral:22b (best for Python/SQL generation)
        - qwen2.5-coder:7b (excellent code generation)
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user",   "content": prompt},
                    ],
                    "stream": False,
                },
                timeout=120.0,
            )
            return response.json()["message"]["content"]
```

**Update `.env.example`:**
```bash
# .env.example

# ── Choose your LLM provider ──────────────────────────────────
LLM_PROVIDER=openai          # openai | anthropic | ollama

# ── OpenAI (cloud) ────────────────────────────────────────────
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini

# ── Anthropic (cloud) ─────────────────────────────────────────
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-3-5-haiku-20241022

# ── Ollama (local — zero data leaves your machine) ────────────
# Install: https://ollama.ai
# Pull model: ollama pull llama3.1:8b
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1:8b
```

**Add to docker-compose for full local stack:**
```yaml
# docker-compose.yml additions

  ollama:
    image: ollama/ollama:latest
    ports:
      - "11434:11434"
    volumes:
      - ollama_data:/root/.ollama
    # For GPU acceleration (optional):
    # deploy:
    #   resources:
    #     reservations:
    #       devices:
    #         - driver: nvidia
    #           count: 1
    #           capabilities: [gpu]

volumes:
  ollama_data:    # persists downloaded models between restarts
```

---

### 1.3 Demo Dataset (small but critical)

Every user who clones the repo should see it working immediately — no hunting for a CSV.

```python
# backend/app/utils/demo_data.py

import pandas as pd
import numpy as np

def get_demo_dataset() -> pd.DataFrame:
    """
    Sales dataset — realistic enough to produce
    interesting analysis without being boring.
    ~1000 rows, covers all common analysis patterns.
    """
    np.random.seed(42)
    n = 1000

    return pd.DataFrame({
        "date":       pd.date_range("2023-01-01", periods=n, freq="D"),
        "region":     np.random.choice(["North", "South", "East", "West"], n),
        "product":    np.random.choice(["Widget A", "Widget B", "Gadget X", "Gadget Y"], n),
        "sales_rep":  np.random.choice([f"Rep_{i}" for i in range(1, 21)], n),
        "quantity":   np.random.randint(1, 50, n),
        "unit_price": np.random.uniform(10, 500, n).round(2),
        "revenue":    lambda df: (df["quantity"] * df["unit_price"]).round(2),
        "cost":       lambda df: (df["revenue"] * np.random.uniform(0.4, 0.7, n)).round(2),
        "customer_satisfaction": np.random.choice([1, 2, 3, 4, 5], n,
                                  p=[0.05, 0.10, 0.20, 0.40, 0.25]),
    })
```

**Add to README:**
```bash
# Try the demo dataset immediately — no CSV needed
curl http://localhost:8000/api/demo/load
# Then ask: "Which region has the highest profit margin?"
```

---

### Phase 1 Task Breakdown

| Week | Task | Details | Hrs |
|------|------|---------|-----|
| Week 1 | Create `connectors/base.py` | Abstract interface, error handling | 4h |
| Week 1 | PostgreSQL connector | Connect, schema, execute, safety | 8h |
| Week 1 | SQLite connector | Simplest connector, great for demos | 4h |
| Week 2 | MySQL connector | Similar to PostgreSQL, minor diffs | 5h |
| Week 2 | DuckDB connector | CSV acceleration + Parquet support | 6h |
| Week 2 | Wire connectors into FastAPI | New `/connectors` API endpoints | 4h |
| Week 3 | Ollama LLM integration | LLMService update + docker-compose | 6h |
| Week 3 | Demo dataset | Sales data, `/api/demo/load` endpoint | 3h |
| Week 3 | Tests for all connectors | Unit + mock DB integration tests | 5h |

---

## Phase 2 — React/Next.js Frontend
### `Week 4–6 · ~50 hours`

This is the hardest phase but the highest visual impact. Streamlit works — but it signals "developer tool" to non-technical users. Julius AI's main audience is analysts and business users who expect a polished product. If you want that audience, you need to look like a product.

---

### 2.1 Tech Stack Decision

```
RECOMMENDED STACK:
- Next.js 14 (App Router)     — framework
- TypeScript                  — type safety
- Tailwind CSS                — styling
- shadcn/ui                   — component library (beautiful defaults)
- Recharts or Plotly.js       — charts (Plotly matches your backend)
- React Query (TanStack)      — API state management
- Monaco Editor               — code display (VS Code's editor, same as Julius)

WHY THIS STACK:
- shadcn/ui gives you a polished look with minimal effort
- Monaco Editor is what Julius uses for showing code — matching it
  removes the "Julius is more professional" perception instantly
- Next.js 14 App Router has excellent streaming support —
  critical for showing agent progress in real-time
```

---

### 2.2 New Project Structure

```
frontend/
├── app/                          # Next.js App Router
│   ├── layout.tsx                # Root layout, fonts, theme
│   ├── page.tsx                  # Landing / home
│   ├── dashboard/
│   │   └── page.tsx              # Main analysis dashboard
│   └── api/                      # Next.js API routes (proxy to FastAPI)
├── components/
│   ├── ui/                       # shadcn/ui components
│   ├── upload/
│   │   ├── FileUpload.tsx        # Drag-and-drop CSV
│   │   └── DatabaseConnect.tsx  # DB connection form
│   ├── chat/
│   │   ├── ChatPanel.tsx         # Main Q&A interface
│   │   ├── MessageBubble.tsx     # User/AI messages
│   │   └── CodeBlock.tsx         # Monaco-based code display
│   ├── agents/
│   │   ├── AgentPipeline.tsx     # Visual pipeline progress
│   │   └── AgentCard.tsx         # Individual agent status
│   ├── viz/
│   │   ├── ChartRenderer.tsx     # Dynamic Plotly chart renderer
│   │   └── DataTable.tsx         # Results table
│   └── export/
│       └── ExportPanel.tsx       # Export controls
├── lib/
│   ├── api.ts                    # API client
│   └── types.ts                  # TypeScript types
├── package.json
└── next.config.js
```

---

### 2.3 Key Component: Agent Pipeline Visualiser

This is your most unique UI feature — show users the 4 agents working in real-time. No competitor does this visually.

```tsx
// components/agents/AgentPipeline.tsx

"use client";

import { useState, useEffect } from "react";

type AgentStatus = "waiting" | "running" | "done" | "error";

interface Agent {
  id: string;
  name: string;
  emoji: string;
  description: string;
  status: AgentStatus;
  output?: string;
  duration?: number;
}

const AGENTS: Agent[] = [
  { id: "janitor",  name: "Data Janitor",    emoji: "🧹",
    description: "Cleaning duplicates, imputing missing values" },
  { id: "hypothesis", name: "Hypothesis Bot", emoji: "🔬",
    description: "Generating testable hypotheses from your data" },
  { id: "debate",   name: "Debate Manager",  emoji: "⚖️",
    description: "Scoring hypotheses by confidence & business value" },
  { id: "viz",      name: "Viz Whiz",        emoji: "📊",
    description: "Auto-generating Plotly charts" },
].map(a => ({ ...a, status: "waiting" }));

export function AgentPipeline({ sessionId }: { sessionId: string }) {
  const [agents, setAgents] = useState<Agent[]>(AGENTS);

  // Poll for agent status updates via SSE or polling
  useEffect(() => {
    const source = new EventSource(`/api/agents/stream/${sessionId}`);
    source.onmessage = (e) => {
      const update = JSON.parse(e.data);
      setAgents(prev => prev.map(a =>
        a.id === update.agent_id ? { ...a, ...update } : a
      ));
    };
    return () => source.close();
  }, [sessionId]);

  return (
    <div className="flex flex-col gap-3 p-4">
      {agents.map((agent, i) => (
        <div key={agent.id} className="flex items-start gap-3">
          {/* Connector line between agents */}
          {i > 0 && (
            <div className="absolute left-[27px] -mt-3 w-0.5 h-3 bg-gray-200" />
          )}

          {/* Status icon */}
          <div className={`
            w-10 h-10 rounded-full flex items-center justify-center text-lg
            flex-shrink-0 border-2 transition-all duration-300
            ${agent.status === "running" ? "border-blue-500 bg-blue-50 animate-pulse" : ""}
            ${agent.status === "done"    ? "border-green-500 bg-green-50" : ""}
            ${agent.status === "error"   ? "border-red-500 bg-red-50" : ""}
            ${agent.status === "waiting" ? "border-gray-200 bg-gray-50" : ""}
          `}>
            {agent.emoji}
          </div>

          {/* Agent info */}
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <span className="font-semibold text-sm">{agent.name}</span>
              {agent.status === "running" && (
                <span className="text-xs text-blue-600 animate-pulse">
                  Processing...
                </span>
              )}
              {agent.status === "done" && agent.duration && (
                <span className="text-xs text-gray-400">
                  {agent.duration}ms
                </span>
              )}
            </div>
            <p className="text-xs text-gray-500 mt-0.5">{agent.description}</p>
            {agent.output && agent.status === "done" && (
              <div className="mt-2 text-xs bg-gray-50 rounded p-2 border">
                {agent.output}
              </div>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
```

---

### 2.4 Key Component: Code Block with Monaco

Show generated Python code exactly like Julius does — syntax highlighted, copyable, runnable.

```tsx
// components/chat/CodeBlock.tsx

"use client";

import Editor from "@monaco-editor/react";
import { useState } from "react";
import { Copy, Play, Check } from "lucide-react";

interface CodeBlockProps {
  code: string;
  language?: string;
  onRunAgain?: () => void;
}

export function CodeBlock({ code, language = "python", onRunAgain }: CodeBlockProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="rounded-lg border border-gray-200 overflow-hidden">
      {/* Toolbar */}
      <div className="flex items-center justify-between px-4 py-2 bg-gray-900">
        <span className="text-xs text-gray-400 font-mono">
          Generated Python
        </span>
        <div className="flex gap-2">
          <button
            onClick={handleCopy}
            className="flex items-center gap-1 text-xs text-gray-400
                       hover:text-white transition-colors"
          >
            {copied ? <Check size={12} /> : <Copy size={12} />}
            {copied ? "Copied" : "Copy"}
          </button>
          {onRunAgain && (
            <button
              onClick={onRunAgain}
              className="flex items-center gap-1 text-xs text-blue-400
                         hover:text-blue-300 transition-colors"
            >
              <Play size={12} />
              Run again
            </button>
          )}
        </div>
      </div>

      {/* Monaco Editor (read-only display) */}
      <Editor
        height="auto"
        language={language}
        value={code}
        theme="vs-dark"
        options={{
          readOnly: true,
          minimap: { enabled: false },
          scrollBeyondLastLine: false,
          fontSize: 13,
          lineNumbers: "on",
          wordWrap: "on",
          automaticLayout: true,
        }}
      />
    </div>
  );
}
```

---

### Phase 2 Task Breakdown

| Week | Task | Details | Hrs |
|------|------|---------|-----|
| Week 4 | Next.js project setup | TypeScript, Tailwind, shadcn/ui, routing | 6h |
| Week 4 | API client (`lib/api.ts`) | Typed wrappers for all FastAPI endpoints | 5h |
| Week 4 | FileUpload + DB connect forms | Drag-and-drop, connection string UI | 6h |
| Week 5 | ChatPanel + MessageBubble | Main Q&A interface with streaming | 8h |
| Week 5 | CodeBlock with Monaco | Syntax highlighting, copy button | 4h |
| Week 5 | ChartRenderer (Plotly.js) | Dynamic chart rendering from JSON spec | 5h |
| Week 6 | AgentPipeline visualiser | Real-time SSE updates per agent | 8h |
| Week 6 | DataTable component | Sortable, paginated results table | 4h |
| Week 6 | Responsive layout + polish | Mobile-friendly, dark mode option | 4h |

---

## Phase 3 — Export + Collaboration
### `Week 7–9 · ~35 hours`

This is what makes Insight Orchestra useful inside teams, not just for solo use. Currently analysis lives and dies in a session. Phase 3 makes it shareable and persistent.

---

### 3.1 Export to HTML Report

The most valuable export format — a self-contained HTML file that anyone can open in a browser with no software needed. Include charts, code, results, and agent outputs all in one file.

```python
# backend/app/services/export_service.py

from jinja2 import Environment, BaseLoader
import json

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>{{ title }} — Insight Orchestra Report</title>
  <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
  <style>
    body { font-family: -apple-system, sans-serif; max-width: 960px;
           margin: 0 auto; padding: 40px 20px; color: #1a1a1a; }
    h1   { color: #0f3460; border-bottom: 2px solid #e0e0e0; padding-bottom: 12px; }
    h2   { color: #16213e; margin-top: 32px; }
    pre  { background: #1e1e1e; color: #d4d4d4; padding: 16px;
           border-radius: 8px; overflow-x: auto; font-size: 13px; }
    .agent-block { background: #f8f9fa; border-left: 4px solid #0f3460;
                   padding: 16px; margin: 16px 0; border-radius: 0 8px 8px 0; }
    .timestamp   { color: #888; font-size: 12px; }
    .chart       { margin: 24px 0; }
  </style>
</head>
<body>
  <h1>{{ title }}</h1>
  <p class="timestamp">Generated {{ timestamp }} · Insight Orchestra</p>

  <h2>Agent Analysis</h2>
  {% for agent in agents %}
  <div class="agent-block">
    <strong>{{ agent.emoji }} {{ agent.name }}</strong>
    <p>{{ agent.output }}</p>
  </div>
  {% endfor %}

  <h2>Conversation</h2>
  {% for msg in messages %}
    {% if msg.role == "user" %}
      <p><strong>Q:</strong> {{ msg.content }}</p>
    {% else %}
      <p>{{ msg.content }}</p>
      {% if msg.code %}
      <pre>{{ msg.code }}</pre>
      {% endif %}
    {% endif %}
  {% endfor %}

  <h2>Visualisations</h2>
  {% for chart in charts %}
  <div class="chart" id="chart-{{ loop.index }}"></div>
  <script>
    Plotly.newPlot('chart-{{ loop.index }}',
      {{ chart.data | tojson }},
      {{ chart.layout | tojson }}
    );
  </script>
  {% endfor %}

</body>
</html>
"""

class ExportService:

    def to_html(self, session_data: dict) -> str:
        """Generate self-contained HTML report"""
        env = Environment(loader=BaseLoader())
        template = env.from_string(HTML_TEMPLATE)
        return template.render(**session_data)

    def to_markdown(self, session_data: dict) -> str:
        """Generate markdown report for Git storage"""
        lines = [f"# {session_data['title']}\n"]
        lines.append(f"*Generated {session_data['timestamp']} · Insight Orchestra*\n")

        lines.append("## Agent Analysis\n")
        for agent in session_data["agents"]:
            lines.append(f"### {agent['emoji']} {agent['name']}\n{agent['output']}\n")

        lines.append("## Conversation\n")
        for msg in session_data["messages"]:
            if msg["role"] == "user":
                lines.append(f"**Q:** {msg['content']}\n")
            else:
                lines.append(f"{msg['content']}\n")
                if msg.get("code"):
                    lines.append(f"```python\n{msg['code']}\n```\n")

        return "\n".join(lines)
```

**FastAPI export endpoints:**
```python
# backend/app/api/export.py

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, PlainTextResponse, FileResponse

router = APIRouter(prefix="/export", tags=["export"])

@router.get("/{session_id}/html")
async def export_html(session_id: str):
    session = await get_session(session_id)
    html = export_service.to_html(session)
    return HTMLResponse(content=html, headers={
        "Content-Disposition": f"attachment; filename=analysis-{session_id}.html"
    })

@router.get("/{session_id}/markdown")
async def export_markdown(session_id: str):
    session = await get_session(session_id)
    md = export_service.to_markdown(session)
    return PlainTextResponse(content=md, headers={
        "Content-Disposition": f"attachment; filename=analysis-{session_id}.md"
    })

@router.get("/{session_id}/csv")
async def export_results_csv(session_id: str):
    """Export last query result as CSV"""
    result = await get_last_result(session_id)
    return FileResponse(result.csv_path, filename="results.csv")
```

---

### 3.2 Shareable Session Links

Sessions should be shareable via URL. Critical for team use.

```python
# backend/app/api/sessions.py additions

@router.post("/{session_id}/share")
async def create_share_link(session_id: str):
    """
    Creates a read-only share token for a session.
    Share link: https://your-instance.com/shared/{token}
    """
    token = secrets.token_urlsafe(16)
    await db.save_share_token(session_id, token, expires_hours=72)
    return {"share_url": f"/shared/{token}", "expires_in": "72 hours"}

@router.get("/shared/{token}")
async def view_shared_session(token: str):
    """Read-only view of a shared session"""
    session_id = await db.get_session_by_token(token)
    if not session_id:
        raise HTTPException(404, "Share link expired or invalid")
    return await get_session_readonly(session_id)
```

---

### Phase 3 Task Breakdown

| Week | Task | Details | Hrs |
|------|------|---------|-----|
| Week 7 | HTML export service | Jinja2 template, Plotly embed | 8h |
| Week 7 | Markdown export | Clean format for Git storage | 4h |
| Week 7 | CSV results export | Last query result as CSV download | 2h |
| Week 8 | Export API endpoints | `/export/{id}/html`, `/md`, `/csv` | 4h |
| Week 8 | Export buttons in React UI | Download panel with format options | 4h |
| Week 9 | Session sharing | Share token, read-only view endpoint | 8h |
| Week 9 | Share UI | Copy link button, expiry display | 3h |
| Week 9 | Session persistence | Save/load sessions from SQLite | 8h (stretch)|

---

## Phase 4 — Polish & GitHub Growth
### `Week 10–12 · ~30 hours`

Everything so far is about what the tool does. Phase 4 is about making sure the right people find it and trust it.

---

### 4.1 README Rewrite

The current README is functional but doesn't sell. Rewrite it in this order:

```markdown
# Insight Orchestra 🎻

**The open-source data analysis agent — self-hosted, private, unlimited.**

[30-second demo GIF here]

Ask questions about your data in plain English.
Get Python code, charts, and insights — with zero data leaving your machine.

## Why Insight Orchestra?

| | Julius AI | Insight Orchestra |
|-|-----------|-------------------|
| **Cost** | $25+/month | Free forever |
| **Privacy** | Your data goes to cloud | Runs 100% locally |
| **LLM** | OpenAI only | OpenAI, Anthropic, or Ollama |
| **Data sources** | CSV upload | CSV, PostgreSQL, MySQL, SQLite, DuckDB |
| **Agent pipeline** | Single model | 4 specialised agents |
| **Self-hostable** | ❌ | ✅ |

## Quick Start (60 seconds)
[docker-compose command]

## Ask questions like:
- "Which region has the highest profit margin?"
- "Show me a bar chart of sales by month"
- "Are there any outliers in the revenue column?"
- "What's the correlation between price and quantity sold?"
```

---

### 4.2 GitHub Community Files

```
.github/
├── ISSUE_TEMPLATE/
│   ├── bug_report.md        ← structured bug reports
│   └── feature_request.md   ← structured feature requests
├── PULL_REQUEST_TEMPLATE.md ← PR checklist
└── workflows/
    ├── test.yml             ← run tests on every PR
    └── docker-build.yml     ← verify Docker build works
```

**Label new issues clearly:**
- `good first issue` — for contributors
- `bug` / `enhancement` / `documentation`
- `connector:postgresql` / `connector:mysql` etc.

---

### 4.3 Blog Posts to Write

One post per phase, one platform per post:

| After | Post Title | Target Platform |
|-------|-----------|-----------------|
| Phase 1 | "How I added PostgreSQL support to an AI data analysis tool in a weekend" | Dev.to |
| Phase 2 | "Replacing Streamlit with Next.js: before and after" | Hashnode |
| Phase 3 | "Building self-contained HTML reports from AI analysis sessions" | Medium |
| Phase 4 | "Why I built an open-source Julius AI alternative" | Hacker News |

The Hacker News post (Phase 4) is your biggest traffic driver. Write it as a genuine story — why Julius frustrated you, what you built, what you learned. HN responds well to honest builder stories.

---

### 4.4 Demo Deployment

Deploy a live demo so people can try without installing:

```bash
# Cheapest reliable options:

# Option 1: Railway ($5/month, simplest)
railway up

# Option 2: Render (free tier available)
# Connect GitHub repo → auto-deploy on push

# Option 3: Hugging Face Spaces (free, good for ML tools)
# Deploy Streamlit version here while React is in progress
```

Add to README:
```markdown
## Try it now (no install)
👉 [Live Demo](https://demo.insightorchestra.dev) — uses sample sales dataset
```

---

### Phase 4 Task Breakdown

| Week | Task | Details | Hrs |
|------|------|---------|-----|
| Week 10 | Rewrite README | Problem/solution, comparison table, GIF | 5h |
| Week 10 | Record demo GIF | Upload CSV → agent pipeline → chart → Q&A | 3h |
| Week 10 | GitHub community files | Issue templates, PR template, CI workflow | 4h |
| Week 11 | Deploy live demo | Railway or Render, use demo dataset | 4h |
| Week 11 | Write Post 1 (Dev.to) | PostgreSQL connector story | 4h |
| Week 12 | Write Post 2 (HN) | "Why I built a Julius alternative" | 5h |
| Week 12 | Final cleanup | Lint, type hints, test coverage >70% | 5h |

---

## Master Checklist

### Phase 1 — Connectors + Ollama
- [ ] `connectors/base.py` abstract interface created
- [ ] PostgreSQL connector working with schema introspection
- [ ] SQLite connector working
- [ ] MySQL connector working
- [ ] DuckDB connector working (with CSV acceleration)
- [ ] All connectors wired into FastAPI `/connectors` endpoints
- [ ] Ollama support added to `LLMService`
- [ ] Ollama added to `docker-compose.yml`
- [ ] Demo sales dataset available at `/api/demo/load`
- [ ] All connector unit tests passing

### Phase 2 — React UI
- [ ] Next.js 14 project created with TypeScript + Tailwind
- [ ] `lib/api.ts` typed API client complete
- [ ] FileUpload component with drag-and-drop working
- [ ] DatabaseConnect form for all 4 connectors
- [ ] ChatPanel with streaming message display
- [ ] CodeBlock with Monaco editor (syntax highlighting, copy)
- [ ] ChartRenderer with Plotly.js working
- [ ] AgentPipeline visualiser with real-time SSE updates
- [ ] DataTable with sorting + pagination
- [ ] Docker build for React frontend working

### Phase 3 — Export + Collaboration
- [ ] HTML export generates self-contained report with charts
- [ ] Markdown export working
- [ ] CSV results export working
- [ ] All export endpoints in FastAPI
- [ ] Export buttons in React UI
- [ ] Session share tokens working (72-hour expiry)
- [ ] Read-only shared session view working
- [ ] Share link copy button in UI

### Phase 4 — Polish + Growth
- [ ] README completely rewritten with comparison table
- [ ] Demo GIF recorded and embedded
- [ ] GitHub issue templates created
- [ ] CI workflow running tests on every PR
- [ ] Live demo deployed and linked from README
- [ ] At least one blog post published
- [ ] Test coverage above 70%

---

## The Positioning Statement (use this everywhere)

> **Insight Orchestra is the open-source, self-hosted alternative to Julius AI.**
> Upload a CSV or connect to your database. Four specialised AI agents clean your data,
> generate hypotheses, debate them, and visualise the results.
> Ask follow-up questions in plain English.
> Every analysis shows the generated Python code.
> Your data never leaves your machine.

---

## Final Thought

The gap between Insight Orchestra today and a genuinely competitive open-source tool is not large. The core is already working. What it needs is:

1. **Phase 1** — connectors that make it actually better than Julius (not just a free version of it)
2. **Phase 2** — a UI that signals "production tool" not "developer prototype"
3. **Phase 3** — shareability that makes it useful inside teams
4. **Phase 4** — visibility so the right people find it

Execute phases in order. Each one is shippable independently. Each one makes the project meaningfully better.

---

*Insight Orchestra Improvement Plan · February 2026*
