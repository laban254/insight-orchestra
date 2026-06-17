
# Insight Orchestra

<div align="center">

![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)
![Next.js 14](https://img.shields.io/badge/Next.js-14-black.svg)
![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)

**Self-hostable AI data analysis platform with a multi-agent pipeline and pluggable LLM backends**

</div>

---

## Overview

Insight Orchestra is a production-ready, self-hostable AI data analysis platform. It accepts CSV files or database connections, runs data through a **4-agent pipeline** (cleaning → hypothesis generation → scoring → visualization), and answers natural-language questions via LLM-powered code generation.

**Key capabilities:**
- Upload a CSV or connect to PostgreSQL, MySQL, SQLite, or DuckDB
- Run the full agent pipeline: automated cleaning, insight generation, ranking, and charting
- Ask arbitrary natural-language questions — the system generates and sandbox-executes Python code
- Choose between cloud LLMs (OpenAI) or local models (Ollama) — no vendor lock-in
- Stream real-time agent progress to the frontend via SSE

---

## Architecture

```
User → Frontend (Next.js 14) → FastAPI Backend → Agent Pipeline → LLM Provider → Results
                                                        ↓
                                              Sandbox Executor
                                          (RestrictedPython)
```

The system has three layers:

1. **Frontend** — Next.js 14 with React, Tailwind CSS, Plotly.js charts
2. **Backend API** — FastAPI (Python 3.11+) with REST endpoints, SSE streaming, session management
3. **Services** — 4-agent pipeline + NLQ agent + sandboxed code execution

LLM providers are pluggable via environment variable:
- **OpenAI** (GPT-4o-mini, GPT-4o) — cloud API
- **Ollama** (Llama, Mistral, Qwen) — local, private

See [Architecture Overview](docs/ARCHITECTURE.md) for the complete breakdown.

---

## Quick Start

### Prerequisites

- Docker & Docker Compose
- Git
- 4 GB RAM (8 GB recommended for local LLMs)

### 1. Clone and configure

```bash
git clone https://github.com/laban254/insight-orchestra.git
cd insight-orchestra
cp .env.example .env
```

Edit `backend/.env` to set your LLM provider:

```bash
# For OpenAI (cloud)
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...

# For DeepSeek (cloud — OpenAI-compatible, cheap & fast)
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=sk-...
DEEPSEEK_MODEL=deepseek-chat

# For local inference with Ollama (default — no API key needed)
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://ollama:11434
OLLAMA_MODEL=qwen2.5:1.5b    # pull with: docker compose exec ollama ollama pull qwen2.5:1.5b
REQUEST_TIMEOUT=600
```

### 2. Start services

```bash
# API mode (OpenAI, no Ollama needed)
docker-compose up backend frontend

# Full local mode (with Ollama)
docker-compose up -d --build
```

### 3. Access

| Service | URL |
|---------|-----|
| Frontend | http://localhost:8501 |
| Backend API | http://localhost:8000 |
| Swagger Docs | http://localhost:8000/docs |
| Ollama | http://localhost:11435 |

---

## The Multi-Agent Pipeline

The pipeline runs **automatically** the moment you upload or select a dataset. Results (narrative, charts, suggested follow-up questions) appear in the chat as the first message.

| Stage | Agent | Function |
|-------|-------|----------|
| 1 | **Data Janitor** | Removes duplicates; imputes missing values (median for numeric, mode for categorical); flags bias (>30% missing); detects outliers via IQR |
| 2 | **Hypothesis Bot** | Builds descriptive statistics + correlations, then asks the LLM to generate 5–8 specific, directional, evidence-backed insights referencing actual column names and numbers |
| 3 | **Debate Manager** | LLM scores each hypothesis on `confidence` and `business_value` (0–1) using the real data stats as evidence; sorts by combined score; selects consensus winner |
| 4 | **Viz Whiz** | Asks the LLM which columns best illustrate the top insight; falls back to regex extraction then structured heuristics; generates up to 6 Plotly charts |
| 5 | **Insight Summarizer** | LLM writes a 3–5 sentence narrative summarising all findings; generates 4–5 specific follow-up questions using actual column names |

Each stage emits real-time progress events via SSE, shown in the UI as a collapsible pipeline pill.

See [Agent Pipeline Guide](docs/AGENTS.md) for detailed workflow and examples.

---

## Features

- **Natural Language Queries** — Ask questions in plain English; the NLQ agent generates pandas code, executes it in the RestrictedPython sandbox, and returns results + optional Plotly charts
- **Multi-Database Support** — PostgreSQL, MySQL, SQLite, DuckDB, and CSV — all read-only with SQL injection protection
- **Pluggable LLM Providers** — OpenAI (GPT-4o-mini, GPT-4o) or Ollama (any locally-hosted model). Configured entirely through environment variables
- **Sandboxed Code Execution** — All generated Python runs through RestrictedPython: no file I/O, no network access, no dangerous imports. Configurable timeout (default 30 s)
- **Real-Time Agent Progress** — SSE-based streaming shows each agent's status, output, and duration in the UI
- **Session Management** — Redis-backed (with in-memory fallback) for stateless API usage
- **5 Demo Datasets** — Pre-configured: Sales, Employees, Customers, Weather, Movies — loadable via `/demo/load` endpoint
- **Session Sharing** — Token-based share links with 72-hour TTL
- **Export** — Session results as HTML, Markdown, or CSV (via `/export/{session_id}/{format}`)
- **BigQuery Integration** — Query Google BigQuery datasets via service account credentials

---

## Tech Stack

| Layer | Technologies |
|-------|--------------|
| **Frontend** | Next.js 14, React, Tailwind CSS, Plotly.js |
| **Backend** | Python 3.11+, FastAPI, Pandas, DuckDB |
| **AI/Agents** | Google ADK, OpenAI SDK, Ollama |
| **Security** | RestrictedPython sandbox, SQL injection protection, credential masking |
| **Data** | PostgreSQL, MySQL, SQLite, DuckDB, CSV, BigQuery |
| **Sessions** | Redis (with in-memory fallback) |
| **Deployment** | Docker, Docker Compose |

---

## Documentation

| Document | Purpose |
|----------|---------|
| [Architecture](docs/ARCHITECTURE.md) | System design, component breakdown, data flow |
| [Agent Pipeline](docs/AGENTS.md) | Deep dive into all 4 agents + NLQ agent |
| [Setup Guide](docs/SETUP.md) | Docker and local development setup |
| [API Reference](docs/API_REFERENCE.md) | All REST endpoints with request/response examples |
| [Frontend Testing](docs/FRONTEND_TESTING.md) | Manual test scenarios for the UI |
| [Contributing](CONTRIBUTING.md) | Code style, PR process, and development workflow |

---

## System Requirements

| Resource | Minimum | Recommended (local LLM) |
|----------|---------|------------------------|
| CPU | 2 cores | 4+ cores |
| RAM | 4 GB | 8 GB |
| Disk | 2 GB | 10 GB |
| Docker | Compose v2 | Compose v2 |
| Python | 3.11 | 3.12 |

---

## License

Apache 2.0 — see [LICENSE](LICENSE).

**Author:** [@laban254](https://github.com/laban254)
