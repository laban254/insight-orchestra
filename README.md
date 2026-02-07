# Insight Orchestra 🎻

<div align="center">

![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)
![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)
![GitHub Stars](https://img.shields.io/github/stars/laban254/insight-orchestra)
![CI](https://github.com/laban254/insight-orchestra/actions/workflows/ci.yml/badge.svg)

**The Open-Source Julius AI Alternative**

*Self-hostable, transparent code, unlimited local usage*

</div>

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| **Multi-Agent Orchestration** | 4 AI agents: Data Janitor, Hypothesis Bot, Debate Manager, Viz Whiz |
| **Natural Language Q&A** | Ask questions in plain English, get Python code + results |
| **Transparent Code** | Every analysis shows the generated Python code |
| **Safe Execution** | Sandbox execution prevents harmful code |
| **Auto Visualizations** | Plotly charts auto-generated from your data |
| **Session Memory** | Chat context across follow-up questions |
| **Self-Hosted** | Run locally with your own API keys |

---

## 🚀 Quick Start

### Option 1: Docker Compose (Recommended)

```bash
# Clone the repository
git clone https://github.com/laban254/insight-orchestra.git
cd insight-orchestra

# Copy environment file
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY

# Start all services
docker-compose up --build
```

- Frontend: http://localhost:8501
- Backend: http://localhost:8000

### Option 2: Local Development

```bash
# Backend
cd backend
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows
pip install -r requirements.txt
uvicorn app.main:app --reload

# Frontend (new terminal)
cd frontend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

---

## 📊 How It Works

```
1. Upload CSV or connect to BigQuery
         ↓
2. Run Analysis (4 agents work in sequence)
   - Data Janitor: Clean duplicates, impute missing
   - Hypothesis Bot: Generate testable hypotheses
   - Debate Manager: Score with confidence & value
   - Viz Whiz: Auto-generate Plotly charts
         ↓
3. Ask Questions in Natural Language
         ↓
4. Get Results + Code + Visualizations
```

---

## 🔍 Example Queries

```python
# Try asking:
"What's the average salary by department?"
"Show me a bar chart of sales by region"
"Find correlations between age and income"
"Which columns have missing values?"
```

---

## 📁 Project Structure

```
insight-orchestra/
├── backend/
│   ├── app/
│   │   ├── api/          # FastAPI endpoints
│   │   ├── services/      # Agent logic
│   │   │   ├── adk_agents.py      # 4 ADK agents
│   │   │   ├── nlq_agent.py       # Natural language query
│   │   │   ├── llm_service.py      # OpenAI wrapper
│   │   │   └── sandbox_executor.py # Safe code execution
│   │   └── utils/         # File handling, BigQuery
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── app.py            # Streamlit UI
│   ├── Dockerfile
│   └── requirements.txt
├── tests/                # Unit tests
├── docker-compose.yml
├── pyproject.toml
└── README.md
```

---

## 🛡️ Security

- **API Keys**: Stored in `.env`, never committed
- **Sandbox**: RestrictedPython prevents harmful code execution
- **Local Only**: Your data never leaves your machine

---

## 📝 License

Apache 2.0 License. See [LICENSE](LICENSE) for details.

---

## 🤝 Contributing

Contributions are welcome! See [CONTRIBUTING.md](CONTRIBUTING.md).

---

## 📧 Contact

- GitHub: [@laban254](https://github.com/laban254)
- Email: labanrotich6544@gmail.com

---

<div align="center">

*Made with ♥ by the Insight Orchestra team*

</div>
