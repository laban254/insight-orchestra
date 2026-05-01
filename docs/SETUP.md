# Local Development Setup (Docker)

Complete guide to set up Insight Orchestra for development using Docker.

---

## Prerequisites

### System Requirements

- **OS**: macOS, Linux, or Windows (WSL2)
- **CPU**: 2+ cores
- **RAM**: 4GB minimum (8GB recommended)
- **Disk**: 2GB free space

### Required Software

1. **Docker & Docker Compose**
   ```bash
   docker --version
   docker-compose --version
   ```

2. **Git**
   ```bash
   git --version
   ```

---

## Setup Steps

### 1. Clone Repository

```bash
git clone https://github.com/laban254/insight-orchestra.git
cd insight-orchestra
```

### 2. Configure Environment Variables

```bash
# Create .env from example
cp .env.example .env

# The backend reads from .env automatically in Docker
# For local development, create backend/.env:
cp backend/.env.example backend/.env

# Frontend environment is configured in docker-compose.yml
# API_BASE_URL=http://backend:8000 (for Docker internal networking)
```


### 3. Choose Your LLM Mode

#### ⚡ API Mode (Recommended for most users)

Edit your `.env` file:

```
LLM_PROVIDER=openai  # or anthropic
OPENAI_API_KEY=your-key
```

Start backend and frontend (no Ollama required):

```bash
docker-compose up backend frontend
```

**What this starts:**
- **Backend**: FastAPI on `http://localhost:8000`
- **Frontend**: Next.js on `http://localhost:8501`

#### 🔒 Local Mode (Ollama, for privacy/offline)

Edit your `.env` file:

```
LLM_PROVIDER=ollama
OLLAMA_MODEL=qwen2.5:0.5b  # or your preferred model
```

Start all services (including Ollama):

```bash
docker-compose up backend frontend ollama
```

**What this starts:**
- **Backend**: FastAPI on `http://localhost:8000`
- **Frontend**: Next.js on `http://localhost:8501`
- **Ollama**: Local LLM service on `http://localhost:11434` (Internal)


---

### 4. Monitoring & Logs

To see what's happening inside the containers:

```bash
# View aggregated logs for all services
docker-compose logs -f

# View logs for a specific service (backend, frontend, or ollama)
docker-compose logs -f backend
```

---

## Health Checks

```bash
# Backend health
curl http://localhost:8000/health
# Response: {"status":"ok"}

# Frontend
open http://localhost:8501
```

---

## Troubleshooting

### Issue: "Port 8000 already in use"

```bash
# Kill process on port 8000
lsof -ti:8000 | xargs kill -9
```

### Issue: "Ollama not responding"

1. Check if the model is pulled in the container:
   ```bash
   docker-compose exec ollama ollama pull llama2
   ```
2. Verify `OLLAMA_BASE_URL` in `backend/.env` is set to `http://ollama:11434` for Docker internal networking.

### Issue: "Error calling LLM: Read timed out"

If you see logs like `Error calling LLM... Read timed out. (read timeout=300)` and `500` errors from Ollama, it means your machine is struggling to run the LLM within the allowed time (often due to running on CPU only).

**Solutions:**
1. **Use a smaller, faster model**:
   Switch from `llama2` to a lightweight model like `qwen2.5:0.5b` or `qwen2.5:1.5b`. Update your `backend/.env` file (`LLM_MODEL=qwen2.5:0.5b`) and ensure you pull it inside the container:
   ```bash
   docker-compose exec ollama ollama pull qwen2.5:0.5b
   ```
2. **Increase the timeout**:
   If you must use a larger model and are willing to wait, look for LLM client configurations in the backend code and increase the request timeout beyond 300 seconds.

---

## Environment Variables Reference



### Backend (`backend/.env`)

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_PROVIDER` | `openai` | LLM provider: openai, anthropic, or ollama (**required**) |
| `OPENAI_API_KEY` | - | API key for OpenAI (required if using openai) |
| `OPENAI_MODEL` | `gpt-4o-mini` | OpenAI model to use |
| `ANTHROPIC_API_KEY` | - | API key for Anthropic (required if using anthropic) |
| `OLLAMA_BASE_URL` | `http://ollama:11434` | Ollama service URL (Docker) |
| `OLLAMA_MODEL` | `qwen2.5:0.5b` | Ollama model to use |
| `LLM_FALLBACK_ENABLED` | `true` | Fallback to another provider if primary fails |
| `LLM_TIMEOUT` | `30` | LLM request timeout (seconds) |
| `LLM_MAX_RETRIES` | `3` | Max retries for LLM requests |
| `ENABLE_OLLAMA` | `false` | Enable Ollama provider |
| `ENABLE_OPENAI` | `true` | Enable OpenAI provider |
| `ENABLE_ANTHROPIC` | `false` | Enable Anthropic provider |
| `UPLOAD_DIR` | `backend/uploads` | Directory for uploaded files |
| `DEMO_MODE` | `true` | Enable demo endpoints (disable in production) |
| `CORS_ORIGIN` | `http://localhost:8501` | Allowed CORS origin |
| `REDIS_URL` | `redis://localhost:6379` | Redis URL for sessions |
| `USE_REDIS` | `true` | Enable Redis (set to false for in-memory) |
| `SESSION_TTL_SECONDS` | `3600` | Session expiration time (1 hour) |

---

## 🔐 Security & Authentication

### Current Architecture

Insight Orchestra is designed as a **local-first, privacy-by-default** system:

- **Local Deployment**: Runs entirely on your machine (or internal network)
- **Session-Based Frontend**: Next.js frontend manages session state
- **No External API Keys Stored**: LLM credentials stay in your `.env` only
- **Sandboxed Execution**: All generated code runs in RestrictedPython sandbox
- **Redis Sessions**: Optional Redis-backed session storage for production
- **CORS Protection**: Configurable allowed origins
- **SQL Injection Protection**: Blocked keywords in database queries

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

- [x] Store secrets in environment variables, NOT code
- [ ] Use HTTPS/TLS for all network communication
- [x] Enable CORS only for trusted frontend domains
- [x] Set `MAX_UPLOAD_SIZE_MB` appropriately
- [x] Configure firewall rules
- [x] Use strong database credentials (for PostgreSQL, MySQL)
- [ ] Enable audit logging for sensitive operations
- [ ] Rotate API keys regularly
- [ ] Run behind reverse proxy (Nginx, HAProxy)
- [x] Redis session storage configured

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
