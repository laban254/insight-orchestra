# Contributing to Insight Orchestra

This guide outlines the development workflow, code style, and pull request process.

---

## Quick Start

### 1. Fork and Clone

```bash
git clone https://github.com/YOUR_USERNAME/insight-orchestra.git
cd insight-orchestra
```

### 2. Run the App

```bash
./setup.sh --build
```

This is the same Docker-first setup used in the [README](README.md#quick-start) and [Setup Guide](docs/SETUP.md) — it writes `backend/.env`, starts the containers, and pulls the Ollama model if you pick that provider. Use this to run the app end-to-end while you work.

`--build` is the part that matters for development: without it, setup pulls the
released images from GHCR and you'd be running published code rather than your
own. It's shorthand for layering in the dev override:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build
```

Rebuild the same way after changing backend or frontend source.

### 3. Set Up Local Tooling (for linting, type-checking, and tests)

CI runs lint/type-check/tests outside Docker, so match that locally:

```bash
# Backend
cd backend
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows
pip install -r requirements.txt
pip install ruff mypy pytest pytest-asyncio pytest-cov

# Pre-commit hooks (ruff, ruff-format, eslint, gitleaks, etc. — see .pre-commit-config.yaml)
# Installs both the pre-commit hooks and the commit-msg hook that enforces Conventional Commits.
pip install pre-commit
pre-commit install
pre-commit install --hook-type commit-msg

# Frontend (new terminal)
cd frontend
npm install
```

### 4. Run Tests

```bash
# From project root, with the venv from step 3 activated
pytest tests/ -v
```

> **Use the venv, and use Python 3.11** (what CI runs). Running `pytest` against a system
> Python with unrelated global packages installed typically fails during *collection* with a
> wall of `ImportError`/`AttributeError` messages that look like real breakage but are just
> version skew. If you see collection errors before a single test runs, check your interpreter
> first. As an alternative, run the suite inside the backend container, which already has the
> pinned dependencies:
>
> ```bash
> docker compose exec backend pip install -q pytest pytest-asyncio
> docker compose cp ../tests backend:/app/tests && docker compose exec -w /app backend pytest tests/ -q
> ```

### 5. Run Linting

```bash
ruff check .
ruff format --check .
mypy backend/app/ --ignore-missing-imports
cd frontend && npm run lint && npx tsc --noEmit
```

---

## Code Style Guidelines

### Python

- Follow [PEP 8](https://peps.python.org/pep-0008/)
- Use type hints on all function signatures
- Format with [Ruff](https://docs.astral.sh/ruff/): `ruff format .`
- Lint with [Ruff](https://docs.astral.sh/ruff/): `ruff check .`

### TypeScript / React

- Use functional components with hooks
- Follow Next.js 14 App Router conventions
- Use Tailwind CSS for styling

### Commits

Use [Conventional Commits](https://www.conventionalcommits.org/) — this is enforced by a commit-msg hook (`pre-commit install --hook-type commit-msg`, see above) and drives automated versioning (see [Releases](#releases) below), not just a style preference:

```
feat: add Excel file upload support
fix: handle empty DataFrame in Data Janitor
docs: update API reference for /process endpoint
refactor: extract schema prompt builder
test: add Hypothesis Bot unit tests
```

A breaking change adds a `!` after the type or a `BREAKING CHANGE:` footer, e.g. `feat!: drop support for CSV files without headers`.

### Tests

- Write tests for new features
- Use pytest fixtures for shared setup
- Mock LLM calls to avoid external dependencies in unit tests

---

## Releases

Versioning and changelogs are automated by [release-please](https://github.com/googleapis/release-please) (`.github/workflows/release-please.yml`), driven entirely by Conventional Commits on `main`:

- `fix:` commits → patch release, `feat:` → minor release, `feat!:`/`BREAKING CHANGE:` → major release.
- release-please keeps a standing "Release PR" up to date with the next version bump and changelog as commits land on `main`.
- Merging that PR is what actually cuts the release: it tags the commit, publishes a GitHub Release, and updates the version in `pyproject.toml` and `frontend/package.json` together (config: `release-please-config.json`, current version tracked in `.release-please-manifest.json`).

Nothing is published to a package registry or container registry as part of this — it's tags, changelog, and GitHub Releases only.

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
