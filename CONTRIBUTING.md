# Contributing to Insight Orchestra

Thank you for your interest in contributing! This guide will help you get started.

## 🚀 Quick Start for Contributors

### 1. Fork and Clone

```bash
git clone https://github.com/YOUR_USERNAME/insight-orchestra.git
cd insight-orchestra
```

### 2. Set Up Development Environment

```bash
# Backend
cd backend
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows
pip install -r requirements.txt

# Frontend (new terminal)
cd frontend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Run Tests

```bash
# From project root
pytest tests/ -v
```

### 4. Run Linting

```bash
ruff check .
black --check .
mypy backend/app/
```

---

## 📋 Ways to Contribute

| Type | Description |
|------|-------------|
| 🐛 Bug Fixes | Fix issues in the codebase |
| ✨ New Features | Add new agents or functionality |
| 📚 Documentation | Improve docs, add examples |
| 🎨 UX/UI | Enhance the Streamlit frontend |
| 🧪 Tests | Add unit tests or integration tests |

---

## 🏗️ Architecture Overview

### Backend (FastAPI)

```
backend/app/
├── api/
│   └── endpoints.py      # REST API endpoints
├── services/
│   ├── adk_agents.py     # 4 core ADK agents
│   ├── nlq_agent.py      # Natural language query agent
│   ├── llm_service.py    # OpenAI wrapper with retry
│   └── sandbox_executor.py # Safe code execution
└── utils/
    ├── file_utils.py     # File upload handling
    └── bigquery_utils.py # BigQuery integration
```

### Frontend (Streamlit)

```
frontend/
└── app.py               # Main Streamlit application
```

---

## ➕ Adding a New Agent

### Step 1: Create Agent Class

Create a new file in `backend/app/services/`:

```python
# backend/app/services/my_agent.py
from google.adk import Agent

class MyNewAgent(Agent):
    def run(self, data, **kwargs):
        # Your agent logic here
        return {"result": "success"}
```

### Step 2: Add Endpoint

Add an endpoint in `backend/app/api/endpoints.py`:

```python
@router.post("/my-agent")
async def my_agent_endpoint(payload: dict = Body(...)):
    agent = MyNewAgent()
    return agent.run(payload)
```

### Step 3: Add Tests

Add tests in `tests/services/`:

```python
# tests/services/test_my_agent.py
def test_my_agent():
    agent = MyNewAgent()
    result = agent.run({"input": "test"})
    assert result["result"] == "success"
```

### Step 4: Update Documentation

- Update `README.md` with new features
- Update `AGENTS.md` with agent documentation

---

## 📐 Code Style Guidelines

### Python

- Follow PEP 8
- Use type hints
- Run `black` for formatting
- Run `ruff` for linting

### Commits

- Use conventional commits: `feat:`, `fix:`, `docs:`, `refactor:`
- Write clear commit messages

### Tests

- Write tests for new features
- Aim for 80% coverage on new code
- Use pytest fixtures

---

## 🐛 Reporting Bugs

Use GitHub Issues with the bug template:

```markdown
## Bug Description
Describe the bug...

## Steps to Reproduce
1. Go to...
2. Click on...
3. See error...

## Expected Behavior
What should happen...

## Screenshots
Add screenshots if applicable...

## Environment
- OS: [e.g., macOS 14]
- Python: [e.g., 3.11]
- Browser: [e.g., Chrome 120]
```

---

## 💡 Suggesting Features

Use GitHub Issues with the feature template:

```markdown
## Feature Description
Describe the feature...

## Motivation
Why is this useful? What problem does it solve?

## Proposed Solution
Describe your proposed implementation...

## Alternatives
What alternatives did you consider?

## Additional Context
Add any other context or screenshots...
```

---

## 📜 Code of Conduct

This project follows our [Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code.

---

## ❓ Questions?

- Check existing [Issues](../../issues)
- Start a [Discussion](../../discussions)
- Email: labanrotich6544@gmail.com

---

Thank you for contributing! 🎻
