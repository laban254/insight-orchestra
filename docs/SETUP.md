# Local Development Setup

Complete guide to set up Insight Orchestra for development.

---

## Prerequisites

### System Requirements

- **OS**: macOS, Linux, or Windows (WSL2)
- **CPU**: 2+ cores
- **RAM**: 4GB minimum (8GB recommended)
- **Disk**: 2GB free space

### Required Software

1. **Python 3.11+**
   ```bash
   python --version
   # Should output: Python 3.11.x or higher
   ```

2. **Node.js 18+**
   ```bash
   node --version
   # Should output: v18.x or higher
   ```

3. **Git**
   ```bash
   git --version
   ```

4. **Docker & Docker Compose** (optional, for containerized setup)
   ```bash
   docker --version
   docker-compose --version
   ```

---

## Setup Steps

### 1. Clone Repository

```bash
git clone https://github.com/laban254/insight-orchestra.git
cd insight-orchestra
```

### 2. Backend Setup

#### 2.1 Create Virtual Environment

```bash
cd backend
python -m venv venv

# Activate virtual environment
# On Linux/macOS:
source venv/bin/activate

# On Windows:
venv\Scripts\activate
```

#### 2.2 Install Python Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

#### 2.3 Configure Environment Variables

```bash
# Copy example environment file
cp .env.example .env

# Edit .env with your settings
nano .env  # or use your favorite editor
```

**Minimum Configuration** (`.env`):

```bash
# LLM Provider
LLM_PROVIDER=ollama              # or: openai, anthropic
LLM_MODEL=llama2                 # Model name
OLLAMA_BASE_URL=http://localhost:11434

# Optional: For OpenAI
# OPENAI_API_KEY=sk-xxxxx
# OPENAI_MODEL=gpt-4

# File uploads
UPLOAD_DIR=./uploads
MAX_UPLOAD_SIZE_MB=100

# CORS (for frontend during development)
CORS_ORIGINS=["http://localhost:3000"]

# Session storage (MVP uses in-memory, production uses Redis)
# REDIS_URL=redis://localhost:6379
```

#### 2.4 Create Uploads Directory

```bash
mkdir -p uploads
```

#### 2.5 Run Backend Development Server

```bash
cd app
python -m uvicorn main:app --reload --port 8000
```

**Expected Output**:
```
INFO:     Uvicorn running on http://127.0.0.1:8000
INFO:     Application startup complete
```

**Access**:
- API: `http://localhost:8000`
- Swagger Docs: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

---

### 3. Frontend Setup

#### 3.1 Install Node Dependencies

```bash
cd frontend
npm install
```

#### 3.2 Configure Environment Variables

```bash
# Create .env.local for development
cat > .env.local << EOF
NEXT_PUBLIC_API_URL=http://localhost:8000
EOF
```

#### 3.3 Run Development Server

```bash
npm run dev
```

**Expected Output**:
```
> ready - started server on 0.0.0.0:3000, url: http://localhost:3000
```

**Access**: `http://localhost:3000`

---

### 4. Setup Ollama (Optional but Recommended)

For **100% local operation** with no cloud dependencies:

#### 4.1 Install Ollama

```bash
# macOS
brew install ollama

# Linux
curl https://ollama.ai/install.sh | sh

# Windows
# Download from https://ollama.ai
```

#### 4.2 Pull a Model

```bash
# Llama 2 (7B) - ~4GB, good quality
ollama pull llama2

# Or: Mistral (7B) - ~3.8GB, faster
ollama pull mistral

# Or: Neural Chat - ~4GB, instruction-tuned
ollama pull neural-chat
```

#### 4.3 Start Ollama Service

```bash
# Keep this running in a separate terminal
ollama serve
```

**Expected Output**:
```
time=2024-03-04T10:30:00.000Z level=info msg="Listening on 127.0.0.1:11434"
```

#### 4.4 Test Ollama Connection

```bash
# From another terminal
curl http://localhost:11434/api/tags

# Should return something like:
# {"models":[{"name":"llama2:latest",...}]}
```

---

### 5. Verify Full Stack is Running

#### 5.1 Terminal 1: Backend

```bash
cd backend/app
python -m uvicorn main:app --reload --port 8000
```

#### 5.2 Terminal 2: Frontend

```bash
cd frontend
npm run dev
```

#### 5.3 Terminal 3: Ollama (Optional)

```bash
ollama serve
```

#### 5.4 Health Checks

```bash
# Backend health
curl http://localhost:8000/health
# Response: {"status":"ok"}

# Frontend
open http://localhost:3000
```

---

## Development Workflow

### Adding a New Feature

1. **Create a feature branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make changes** in your editor

3. **Test changes**
   - Backend: Tests auto-reload with `--reload`
   - Frontend: HMR (Hot Module Reload) enabled by default

4. **Commit changes**
   ```bash
   git add .
   git commit -m "feat: description of your change"
   ```

5. **Push and create PR**
   ```bash
   git push origin feature/your-feature-name
   ```

### Running Tests

#### Backend Tests

```bash
cd backend
pytest tests/ -v

# Or with coverage
pytest tests/ --cov=app
```

#### Frontend Tests

```bash
cd frontend
npm test

# Or with coverage
npm test -- --coverage
```

### Code Quality

#### Backend

```bash
cd backend

# Format code
black app/

# Lint
flake8 app/

# Type checking
mypy app/
```

#### Frontend

```bash
cd frontend

# Format code
npm run format

# Lint
npm run lint

# Type checking
npm run type-check
```

---

## Troubleshooting

### Issue: "Port 8000 already in use"

```bash
# Kill process on port 8000
lsof -ti:8000 | xargs kill -9

# Or use a different port
python -m uvicorn main:app --reload --port 8001
```

### Issue: "Port 3000 already in use"

```bash
# Kill process on port 3000
lsof -ti:3000 | xargs kill -9

# Or use a different port
npm run dev -- -p 3001
```

### Issue: "Ollama not found"

Ensure Ollama is installed and running:
```bash
which ollama
ollama serve  # In a separate terminal
```

### Issue: "Connection to backend failed"

1. Verify backend is running: `curl http://localhost:8000/health`
2. Check `.env` and `CORS_ORIGINS` setting
3. Check frontend `.env.local` has correct `NEXT_PUBLIC_API_URL`

### Issue: "LLM not responding"

1. Check LLM provider in `.env`
2. For Ollama: Verify it's running and model is pulled
   ```bash
   ollama pull llama2
   ```
3. For OpenAI: Verify `OPENAI_API_KEY` is set correctly

### Issue: "FileNotFoundError: uploads directory"

```bash
# Create uploads directory
mkdir -p backend/uploads
```

---

## Using Docker (Alternative)

For a one-command setup:

```bash
docker-compose up -d --build
```

This starts:
- Backend (FastAPI) on port 8000
- Frontend (Next.js) on port 8501
- Ollama on port 11434

Access:
- Frontend: `http://localhost:8501`
- Backend API: `http://localhost:8000`
- Swagger: `http://localhost:8000/docs`

---

## Environment Variables Reference

### Backend (`backend/.env`)

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_PROVIDER` | `ollama` | LLM provider: openai, anthropic, or ollama |
| `LLM_MODEL` | `llama2` | Model name/identifier |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama service URL |
| `OPENAI_API_KEY` | - | OpenAI API key (if using OpenAI) |
| `OPENAI_MODEL` | `gpt-4` | OpenAI model (if using OpenAI) |
| `UPLOAD_DIR` | `./uploads` | Directory for uploaded files |
| `MAX_UPLOAD_SIZE_MB` | `100` | Max file size in MB |
| `CORS_ORIGINS` | `["*"]` | Allowed CORS origins |
| `REDIS_URL` | - | Redis connection (for production) |

### Frontend (`frontend/.env.local`)

| Variable | Default | Description |
|----------|---------|-------------|
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Backend API URL |

---

## 🔐 Security & Authentication

### Current Architecture

Insight Orchestra is designed as a **local-first, privacy-by-default** system:

- **Local Deployment**: Runs entirely on your machine (or internal network)
- **Session-Based Frontend**: Next.js frontend manages session state
- **No External API Keys Stored**: LLM credentials stay in your `.env` only
- **Sandboxed Execution**: All generated code runs in RestrictedPython sandbox

### For Local/Internal Use

No additional authentication required. Secure your deployment by:

1. **Network Isolation**: Run on private network only
2. **Firewall Rules**: Restrict port 8000 access to trusted IPs
3. **Environment Variables**: Store all secrets in `.env` (never commit)

**Example firewall rule** (Linux):
```bash
# Allow only localhost and internal network
sudo ufw allow from 127.0.0.1 to any port 8000
sudo ufw allow from 192.168.1.0/24 to any port 8000
```

### For Production/Multi-User Deployment

When deploying to multiple users or cloud environments, tasks to be done:

- [ ] **API Key Authentication**
```python
# backend/app/api/security.py (future)
from fastapi.security import APIKeyHeader

API_KEY_HEADER = APIKeyHeader(name="X-API-Key")

async def verify_api_key(api_key: str = Depends(API_KEY_HEADER)):
    if api_key not in authorized_keys:
        raise HTTPException(status_code=403, detail="Invalid API key")
    return api_key
```

- [ ] **JWT Token Authentication**

```python
# For stateless authentication across multiple instances
from jose import JWTError, jwt

SECRET_KEY = "your-secret-key-here"

async def verify_token(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        user_id: str = payload.get("sub")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    return user_id
```

- [ ] **OAuth 2.0 Integration**
```python
# For enterprise deployments (Okta, Azure AD, Google, etc.)
from authlib.integrations.fastapi_client import OAuth2App

oauth = OAuth2App(
    client_id="...",
    client_secret="...",
    authorize_url="...",
    token_url="...",
)
```

### Deployment Checklist

- [ ] Store secrets in environment variables, NOT code
- [ ] Use HTTPS/TLS for all network communication
- [ ] Enable CORS only for trusted frontendd domains
- [ ] Set `MAX_UPLOAD_SIZE_MB` appropriately
- [ ] Configure firewall rules
- [ ] Use strong database credentials (for PostgreSQL, MySQL)
- [ ] Enable audit logging for sensitive operations
- [ ] Rotate API keys regularly
- [ ] Run behind reverse proxy (Nginx, HAProxy)

### Planned Security Features

| Feature | Status | Timeline |
|---------|--------|----------|
| API Key authentication | Planned | Coming soon |
| JWT tokens | Planned | Coming soon |
| OAuth 2.0 integration | Planned | Coming soon |
| Audit logging | Planned | Coming soon |
| Rate limiting | Planned | Coming soon |
| Database encryption | Planned | Coming soon |

---

1. **Read the Architecture**: [ARCHITECTURE.md](ARCHITECTURE.md)
2. **Learn the Agents**: [AGENTS.md](AGENTS.md)
3. **Review API Docs**: [API_REFERENCE.md](API_REFERENCE.md)
4. **Start Contributing**: See [../CONTRIBUTING.md](../CONTRIBUTING.md)

---

## Performance Tips

### Speed up LLM responses
- Use faster model: `ollama pull mistral` instead of llama2
- Increase Ollama memory: `OLLAMA_NUM_GPU=1` (if GPU available)

### Speed up frontend builds
- Use `npm ci` instead of `npm install` (faster, more reliable)
- Next.js caching: Already enabled with `--reload`

### Speed up backend development
- Use incremental testing: `pytest tests/test_file.py -v`
- Skip full suite during development
