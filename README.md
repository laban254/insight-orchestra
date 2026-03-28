
# Insight Orchestra 🤖

<div align="center">

![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)
![Next.js 14](https://img.shields.io/badge/Next.js-14-black.svg)
![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)

**AI-powered data analyst with pluggable LLM backends (API or local)**

</div>

---


---

## 🚀 What is Insight Orchestra?

Insight Orchestra is a **self-hostable AI data analysis platform** that lets you:

- Ask questions in natural language
- Generate Python/SQL automatically
- Analyze datasets & databases
- Get visualizations instantly

---

## 🧠 LLM Modes (Key Feature)

Insight Orchestra supports **two modes**:

### ⚡ Easy Mode (Recommended)
- Uses APIs like OpenAI or Anthropic
- Works instantly with an API key
- Runs on low-spec machines

### 🔒 Advanced Mode (Local)
- Uses Ollama
- 100% private (no data leaves your machine)
- Requires higher RAM (8GB+)

👉 You choose based on your needs.

---

## ✨ Core Features

- 🧠 Multi-agent pipeline (Data → Insights → Ranking → Visualization)
- 📊 Works with CSV, PostgreSQL, MySQL, SQLite, DuckDB
- 🔐 Sandboxed Python execution (secure)
- ⚡ Natural language → code → results
- 📈 Interactive charts (Plotly)
- 🧩 Pluggable LLM providers (OpenAI, Anthropic, Ollama)

---

## ⚡ Quick Start

### 1. Clone repo

```bash
git clone https://github.com/laban254/insight-orchestra.git
cd insight-orchestra
```

### 2. Setup environment
cp .env.example .env

Edit .env:

LLM_PROVIDER=openai
OPENAI_API_KEY=your-key

### 3. Run (Lightweight Mode)
docker-compose up backend frontend db

### 4. Run (Full Local Mode with Ollama)
docker-compose up -d --build

🌐 Access
Frontend → http://localhost:8501
Backend → http://localhost:8000
API Docs → http://localhost:8000/docs

---

## 🧠 Architecture Overview

User → API → Agent Pipeline → LLM Provider → Results

LLM Provider is pluggable:

- OpenAI
- Anthropic
- Ollama

---

## 🔧 Tech Stack

Frontend: Next.js 14, React
Backend: FastAPI, Python
Data: PostgreSQL, DuckDB
AI: LangChain, ADK, Ollama, OpenAI
Security: RestrictedPython sandbox

---

## 🧭 Philosophy

Flexible (API or Local)
Transparent (code is visible)
Secure (sandboxed execution)
Scalable (modular architecture)

---

## 📝 License

Apache 2.0

---

## ✨ Key Features

- **Multi-Agent Pipeline**: 4 specialized agents (Data Janitor, Hypothesis Bot, Debate Manager, Viz Whiz) collaborate to analyze your data intelligently
- **Multi-Database Support**: PostgreSQL, MySQL, SQLite, DuckDB, and CSV files
- **Local LLM Integration**: Full support for Ollama—run open-source models like Llama 2 locally
- **Sandboxed Execution**: RestrictedPython prevents malicious code execution while allowing full data analysis capabilities
- **Natural Language Queries**: Ask questions in plain English, get Python/SQL code + results
- **Interactive Visualizations**: Auto-selected charts using Plotly with drill-down capabilities
- **Session Management**: Redis-backed session storage (with in-memory fallback)
- **Production-Ready UI**: Next.js 14 frontend with real-time updates and responsive design
- **Hypothesis Scoring**: Automated quality filtering based on statistical confidence and business impact
- **Security Hardened**: CORS protection, SQL injection prevention, credential masking

---

## 💻 System Requirements

**Minimum**:
- CPU: 2+ cores
- RAM: 4GB (8GB recommended for local LLMs)
- Disk: 2GB free space
- Python: 3.11+
- Docker & Docker Compose (for containerized deployment)

**For Local LLM (Ollama)**:
- RAM: 8GB+ recommended (models range from 3.8GB to 13GB)
- GPU support optional but recommended (NVIDIA CUDA or AMD ROCm)

---

## 🚀 Quick Start

### Option 1: Docker Compose (Recommended)

```bash
# Clone the repository
git clone https://github.com/laban254/insight-orchestra.git
cd insight-orchestra

# Copy environment file
cp .env.example .env

# Start all services (Backend, Frontend, Ollama)
docker-compose up -d --build
```

**Access Points**:
- **Frontend**: http://localhost:8501
- **Backend API**: http://localhost:8000
- **Swagger Docs**: http://localhost:8000/docs
- **Ollama**: http://localhost:11434

### Option 2: Local Development

For step-by-step setup instructions, see [Local Development Setup](docs/SETUP.md)





---

## 📚 Documentation Hub

Complete guides for using and developing Insight Orchestra:

| Document | Purpose |
|----------|----------|
| **[SETUP.md](docs/SETUP.md)** | Step-by-step local development setup |
| **[ARCHITECTURE.md](docs/ARCHITECTURE.md)** | System design, components, and data flow |
| **[AGENTS.md](docs/AGENTS.md)** | Deep dive into the 4-agent pipeline |
| **[API_REFERENCE.md](docs/API_REFERENCE.md)** | REST endpoints, examples, and error handling |

**Quick Links**:
- Interactive API Docs: http://localhost:8000/docs (after running backend)
- Environment Setup: [SETUP.md](docs/SETUP.md#-environment-configuration)

---

## 🔧 The Multi-Agent Pipeline

Insight Orchestra uses 4 specialized agents that work together:

1. **🛠️ Data Janitor** - Cleans data, detects issues, flags biases
2. **🔎 Hypothesis Bot** - Generates insights using LLM analysis
3. **🧠 Debate Manager** - Scores and ranks hypotheses by business value
4. **✨ Viz Whiz** - Auto-selects and creates visualizations

**[Learn how they work →](docs/AGENTS.md)**

```mermaid
graph TD;
    A[Upload CSV or Connect DB] --> B[Data Janitor];
    B --> C[Hypothesis Bot];
    C --> D[Debate Manager];
    D --> E[Viz Whiz];
    E --> F[Interactive Q&A Chat];
```

---

## 💬 What You Can Do

- **Ask Questions**: *"What is the average salary by department?"*
- **Get Visualizations**: *"Show me a bar chart of sales by region."*
- **Find Patterns**: *"Find correlations between age and income."*
- **Understand Data**: *"Which columns have missing values, and how should we treat them?"*
- **Connect Databases**: Query PostgreSQL, MySQL, SQLite, or DuckDB in real-time
- **Export Results**: Save findings as CSV, JSON, Parquet, or PDF

---

## ⚙️ Tech Stack

| Layer | Technologies |
|-------|--------------|
| **Frontend** | Next.js 14, React, Tailwind CSS, shadcn/ui, Plotly.js |
| **Backend** | Python 3.11+, FastAPI, Pandas, DuckDB |
| **AI/Agents** | Google ADK, LangChain, Ollama, OpenAI |
| **Security** | RestrictedPython (sandboxed execution), SQL injection protection |
| **Data** | PostgreSQL, MySQL, SQLite, DuckDB, CSV |
| **Sessions** | Redis (with in-memory fallback) |
| **Deployment** | Docker, Docker Compose |

---

## 🤝 Contributing

Contributions are welcome! To help us build the best open-source data analyst:

1. **Read First**: [Contributing Guide](CONTRIBUTING.md)
2. **Understand the System**: [ARCHITECTURE.md](docs/ARCHITECTURE.md)
3. **Set Up Locally**: [SETUP.md](docs/SETUP.md)
4. **Learn the Agents**: [AGENTS.md](docs/AGENTS.md)
5. **Submit PR**: Fork, create a feature branch, and submit with tests

Our CI Pipeline validates all changes automatically.

---

## 📝 License & Contact

**License**: Apache 2.0 License. See [LICENSE](LICENSE) for details.
**Author**: [@laban254](https://github.com/laban254) | labanrotich6544@gmail.com
