<h1 align="center">Insight Orchestra</h1>

<p align="center"><strong>Your data, analyzed by a team of AI agents.</strong></p>

<p align="center">
  Connect a CSV or database and watch specialized agents clean it, form hypotheses,<br/>
  debate them, and visualize what matters — then ask follow-ups in plain English.
</p>

<p align="center">
  <a href="https://insight-orchestra-io.lovable.app">Website</a> ·
  <a href="docs/">Docs</a> ·
  <a href="https://github.com/laban254/insight-orchestra/issues/new">Report a bug</a>
</p>

<p align="center">
  <a href="https://github.com/laban254/insight-orchestra/actions/workflows/ci.yml"><img src="https://github.com/laban254/insight-orchestra/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://github.com/laban254/insight-orchestra/actions/workflows/codeql.yml"><img src="https://github.com/laban254/insight-orchestra/actions/workflows/codeql.yml/badge.svg" alt="CodeQL"></a>
  <a href="LICENSE"><img src="https://img.shields.io/github/license/laban254/insight-orchestra" alt="License"></a>
  <a href="https://github.com/laban254/insight-orchestra/stargazers"><img src="https://img.shields.io/github/stars/laban254/insight-orchestra?style=social" alt="Stars"></a>
</p>

![Insight Orchestra workspace](docs/assets/workspace.png)

---

## What is Insight Orchestra?

Insight Orchestra is an **open-source, self-hostable alternative to Julius AI** — AI-powered data analysis where your data never leaves your machine. Upload a CSV or connect a database, and a 4-agent pipeline cleans the data, generates evidence-backed hypotheses, scores them in an LLM-refereed debate, and builds interactive Plotly charts. Then keep asking questions in plain English: an NLQ agent writes pandas code and executes it in a locked-down sandbox.

It works with **your choice of LLM** — OpenAI, Anthropic, or DeepSeek in the cloud, or fully local and private with Ollama.

## Quick Start

**Prerequisites:** Docker & Docker Compose v2 · Git · 4 GB RAM (8 GB recommended for local LLMs)

### 1. Clone and configure

```bash
git clone https://github.com/laban254/insight-orchestra.git
cd insight-orchestra
cp backend/.env.example backend/.env
```

Edit `backend/.env` to pick your LLM provider:

```bash
# Local inference with Ollama (default — no API key needed, fully private)
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://ollama:11434
OLLAMA_MODEL=qwen2.5:1.5b
REQUEST_TIMEOUT=600

# Or OpenAI (cloud)
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...

# Or Anthropic (cloud)
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...

# Or DeepSeek (cloud — OpenAI-compatible, cheap & fast)
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=sk-...
DEEPSEEK_MODEL=deepseek-chat
```

### 2. Start services

```bash
# Full local mode (with Ollama)
docker compose up -d --build
docker compose exec ollama ollama pull qwen2.5:1.5b   # once, after first start

# Or API mode (cloud LLM — no Ollama container needed)
docker compose up backend frontend
```

### 3. Open the app

| Service | URL |
|---------|-----|
| Frontend | http://localhost:8501 |
| Backend API | http://localhost:8000 |
| Swagger Docs | http://localhost:8000/docs |

Pick one of the five bundled demo datasets (or upload your own CSV) and the pipeline runs automatically.

## How It Works

The pipeline runs the moment you upload or select a dataset. Results — narrative, ranked insights, charts, suggested follow-ups — appear in the chat as the first message.

| Stage | Agent | Function |
|-------|-------|----------|
| 1 | **Data Janitor** | Removes duplicates; imputes missing values (median for numeric, mode for categorical); flags bias (>30% missing); detects outliers via IQR |
| 2 | **Hypothesis Bot** | Builds descriptive statistics + correlations, then asks the LLM to generate 5–8 specific, directional, evidence-backed insights referencing actual column names and numbers |
| 3 | **Debate Manager** | LLM scores each hypothesis on `confidence` and `business_value` (0–1) using the real data stats as evidence; sorts by combined score; selects consensus winner |
| 4 | **Viz Whiz** | Asks the LLM which columns best illustrate the top insight; falls back to regex extraction then structured heuristics; generates up to 6 Plotly charts |
| 5 | **Insight Summarizer** | LLM writes a 3–5 sentence narrative summarising all findings; generates 4–5 specific follow-up questions using actual column names |

Each stage streams real-time progress to the UI via SSE. See the [Agent Pipeline Guide](docs/AGENTS.md) for the full breakdown.

## Features

- **Natural Language Queries** — the NLQ agent generates pandas code, executes it in the RestrictedPython sandbox, and returns results + optional Plotly charts
- **Four LLM Providers** — OpenAI, Anthropic, DeepSeek, or Ollama (any locally-hosted model); switch provider/model at runtime, no restart needed
- **Multi-Database Support** — PostgreSQL, MySQL, SQLite, DuckDB, BigQuery, and CSV — all read-only with SQL injection protection
- **Sandboxed Code Execution** — no file I/O, no network access, no dangerous imports; configurable timeout
- **Real-Time Agent Progress** — SSE streaming shows each agent's status, output, and duration
- **Workspace, Share & Export** — pin and compare charts, one-click read-only share links (72 h TTL), export as HTML / Markdown / CSV
- **5 Demo Datasets** — try it without bringing your own data

## Documentation

| Document | Purpose |
|----------|---------|
| [Setup Guide](docs/SETUP.md) | Docker and local development setup, troubleshooting |
| [Architecture](docs/ARCHITECTURE.md) | System design, component breakdown, data flow |
| [Agent Pipeline](docs/AGENTS.md) | Deep dive into all 4 agents + NLQ agent |
| [API Reference](docs/API_REFERENCE.md) | All REST endpoints with request/response examples |

## Roadmap

Near-term focus is correctness and hardening: CI builds from a clean cache, rate limiting, input validation, and broader test coverage. Further out: more data formats (Excel, JSON, Parquet), saved dashboards, PDF export, and server-side workspace persistence. Have a request or want to influence priorities? [Open an issue](https://github.com/laban254/insight-orchestra/issues).

## Contributing

Contributions are welcome — the [Contributing Guide](CONTRIBUTING.md) covers the development workflow, code style, and how to add a new agent to the pipeline.

If Insight Orchestra is useful to you, consider **starring the repo** — it helps others find the project.

## License

Apache 2.0 — see [LICENSE](LICENSE).

**Author:** [@laban254](https://github.com/laban254)
