# Contributing to Insight Orchestra

This guide outlines the development workflow, code style, and pull request process.

---

## Quick Start

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
npm install
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

## Code Style Guidelines

### Python

- Follow [PEP 8](https://peps.python.org/pep-0008/)
- Use type hints on all function signatures
- Format with [Black](https://black.readthedocs.io/): `black .`
- Lint with [Ruff](https://docs.astral.sh/ruff/): `ruff check .`

### TypeScript / React

- Use functional components with hooks
- Follow Next.js 14 App Router conventions
- Use Tailwind CSS for styling

### Commits

Use [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add Excel file upload support
fix: handle empty DataFrame in Data Janitor
docs: update API reference for /process endpoint
refactor: extract schema prompt builder
test: add Hypothesis Bot unit tests
```

### Tests

- Write tests for new features
- Use pytest fixtures for shared setup
- Mock LLM calls to avoid external dependencies in unit tests

---

## Project Structure

```
insight-orchestra/
├── backend/
│   └── app/
│       ├── api/            # FastAPI route handlers
│       │   ├── endpoints.py    # Main API routes
│       │   ├── connectors.py   # DB connection endpoints
│       │   ├── sessions.py     # Session sharing
│       │   └── export.py       # Export endpoints
│       ├── services/        # Business logic & agents
│       │   ├── adk_agents.py       # 4-agent pipeline
│       │   ├── nlq_agent.py        # NL → code agent
│       │   ├── llm_service.py      # LLM provider abstraction
│       │   ├── sandbox_executor.py # RestrictedPython sandbox
│       │   ├── session_manager.py  # Redis/in-memory sessions
│       │   └── ...                 # explain, summarizer, report
│       ├── connectors/       # Database connectors
│       └── utils/            # file_utils, demo_data, bigquery
├── frontend/
│   ├── app/                 # Next.js App Router pages
│   └── components/          # React components
│       ├── agents/          # AgentPipeline SSE visualization
│       ├── chat/            # ChatPanel, MessageBubble, CodeBlock
│       ├── upload/          # FileUpload, DatabaseConnect
│       ├── viz/             # ChartRenderer, DataTable
│       └── export/          # ExportPanel, ShareButton
├── docs/                    # Documentation
└── tests/                   # Unit & integration tests
```

---

## Adding a New Agent

### Step 1: Create Agent Class

Add to [`backend/app/services/adk_agents.py`](backend/app/services/adk_agents.py):

```python
from google.adk import Agent

class MyNewAgent(Agent):
    def run(self, data, **kwargs):
        # Your agent logic here
        return {"result": "success"}
```

### Step 2: Integrate into Workflow

Add to [`InsightOrchestraWorkflow`](backend/app/services/adk_agents.py:226):

```python
self.my_agent = MyNewAgent()

def run(self, data):
    # ... existing stages ...
    my_result = self.my_agent.run(...)
```

### Step 3: Add Endpoint (if needed)

Add to [`backend/app/api/endpoints.py`](backend/app/api/endpoints.py):

```python
@router.post("/my-agent")
async def my_agent_endpoint(payload: dict):
    agent = MyNewAgent()
    return agent.run(payload)
```

### Step 4: Add Tests

Create [`tests/services/test_my_agent.py`](tests/services/):

```python
def test_my_agent():
    agent = MyNewAgent()
    result = agent.run({"input": "test"})
    assert result["result"] == "success"
```

### Step 5: Update Documentation

- Add agent description to [`docs/AGENTS.md`](docs/AGENTS.md)
- Add new API route to [`docs/API_REFERENCE.md`](docs/API_REFERENCE.md)

---

## Reporting Bugs

Use GitHub Issues with the following information:

```markdown
## Description
Clear description of the bug.

## Steps to Reproduce
1. Upload file...
2. Run query...
3. See error...

## Expected Behavior
What should happen instead.

## Environment
- OS: [e.g., Ubuntu 22.04]
- Python: [e.g., 3.11]
- Browser: [e.g., Chrome 120]
- LLM Provider: [e.g., Ollama with qwen2.5:0.5b]
```

---

## Feature Requests

Use GitHub Issues with:

```markdown
## Feature Description
What the feature does.

## Motivation
What problem it solves.

## Proposed Implementation
Technical approach, if known.
```

---

## Code of Conduct

This project follows a standard [Contributor Covenant](https://www.contributor-covenant.org/) code of conduct. Be respectful, constructive, and professional in all interactions.
