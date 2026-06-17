# Local Development Setup

Complete guide to set up Insight Orchestra for development using Docker.

---

## Prerequisites

### System Requirements

- **OS**: macOS, Linux, or Windows (WSL2)
- **CPU**: 4+ cores recommended (2 minimum)
- **RAM**: 4 GB minimum (8 GB recommended for local LLMs)
- **Disk**: 5 GB free space (model download ~2 GB)

### Required Software

1. **Docker & Docker Compose**
   ```bash
   docker --version
   docker compose version
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

The backend reads its environment from `backend/.env`. Copy the example and edit it:

```bash
cp backend/.env.example backend/.env
```

> **Note**: The backend Docker container reads `backend/.env` — not the root `.env`. Keep both in sync if you maintain both.

### 3. Choose Your LLM Mode

#### API Mode (OpenAI)

Edit `backend/.env`:

```bash
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-your-key-here
OPENAI_MODEL=gpt-4o-mini
```

Start backend and frontend (no Ollama required):

```bash
docker compose up backend frontend
```

#### API Mode (DeepSeek) — cheap & fast cloud alternative

DeepSeek exposes an OpenAI-compatible API, so it runs through the same code path
as OpenAI. Get a key at https://platform.deepseek.com, then edit `backend/.env`:

```bash
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=sk-your-key-here
DEEPSEEK_MODEL=deepseek-chat     # or deepseek-reasoner
DEEPSEEK_BASE_URL=https://api.deepseek.com
```

No Ollama required. Far faster than CPU-local models and a fraction of the cost
of GPT-4o (~$0.27 / 1M input tokens).

**What this starts:**
| Service | URL |
|---------|-----|
| Backend (FastAPI) | `http://localhost:8000` |
| Frontend (Next.js) | `http://localhost:8501` |
| API Docs (Swagger) | `http://localhost:8000/docs` |

#### Local Mode (Ollama) — Recommended

Edit `backend/.env`:

```bash
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://ollama:11434   # Docker internal URL — do not use localhost
OLLAMA_MODEL=qwen2.5:1.5b             # Good speed/quality balance on CPU
REQUEST_TIMEOUT=600                   # 10 min — needed for first-run model loading
```

Start all services:

```bash
docker compose up -d backend frontend ollama
```

Pull the model (run once after first start):

```bash
docker compose exec ollama ollama pull qwen2.5:1.5b
```

Verify the model loaded:

```bash
docker compose exec ollama ollama list
# Should show: qwen2.5:1.5b   ...   ~1 GB
```

---

### 4. Monitoring & Logs

```bash
# View aggregated logs for all services
docker compose logs -f

# View logs for a specific service
docker compose logs -f backend
docker compose logs -f ollama
```

---

### 5. Health Checks

```bash
# Backend health
curl http://localhost:8000/health
# Response: {"status":"ok"}

# Frontend
open http://localhost:8501
```

---

## Environment Variables Reference

### LLM Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_PROVIDER` | `ollama` | LLM provider: `openai`, `anthropic`, `deepseek`, or `ollama` |
| `OPENAI_API_KEY` | — | API key for OpenAI (required if using `openai`) |
| `OPENAI_MODEL` | `gpt-4o-mini` | OpenAI model to use |
| `OPENAI_MODEL_FALLBACK` | `gpt-4o` | Fallback model for OpenAI |
| `OLLAMA_BASE_URL` | `http://ollama:11434` | Ollama service URL (use `ollama` hostname inside Docker) |
| `OLLAMA_MODEL` | `qwen2.5:1.5b` | Ollama model — `qwen2.5:1.5b` balances speed/quality on CPU |
| `MAX_RETRIES` | `1` | Max retries for LLM requests |
| `REQUEST_TIMEOUT` | `600` | LLM request timeout (seconds) |

### Application Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `BACKEND_HOST` | `0.0.0.0` | Backend bind address |
| `BACKEND_PORT` | `8000` | Backend port |
| `FRONTEND_PORT` | `8501` | Frontend port |
| `ENVIRONMENT` | `development` | `development` or `production` |
| `DEMO_MODE` | `true` | Enable demo endpoints (disable in production) |
| `LOG_LEVEL` | `INFO` | Logging level: `DEBUG`, `INFO`, `WARNING`, `ERROR` |

### Redis Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `REDIS_URL` | `redis://localhost:6379` | Redis connection URL |
| `USE_REDIS` | `true` | Enable Redis; set `false` for in-memory fallback |
| `SESSION_TTL_SECONDS` | `3600` | Session expiration time (1 hour) |

### CORS

| Variable | Default | Description |
|----------|---------|-------------|
| `CORS_ORIGIN` | `http://localhost:8501` | Primary allowed CORS origin |
| `CORS_ORIGIN_ALT` | `http://localhost:8501` | Secondary CORS origin |

### File Upload

| Variable | Default | Description |
|----------|---------|-------------|
| `MAX_FILE_SIZE` | `52428800` | Maximum file size in bytes (50 MB) |
| `UPLOAD_DIR` | `backend/uploads` | Upload directory |

### Sandbox

| Variable | Default | Description |
|----------|---------|-------------|
| `SANDBOX_ENABLED` | `true` | Enable sandboxed code execution |
| `SANDBOX_TIMEOUT` | `30` | Maximum execution time in seconds |
| `SANDBOX_MEMORY_LIMIT` | `256` | Maximum memory in MB (tracked, not enforced) |

---

## Security

### Current Architecture

Insight Orchestra is designed as a **local-first, privacy-by-default** system:

| Measure | Implementation |
|---------|---------------|
| **Network isolation** | Runs on local machine or private network |
| **No external data leakage** | LLM credentials stay in `.env` (never committed) |
| **Sandboxed execution** | All generated code runs in RestrictedPython |
| **Read-only database queries** | All connectors enforce SELECT-only |
| **SQL injection prevention** | Blocked keywords on query strings |
| **Path traversal protection** | Validates file paths against allowed directories |
| **CORS** | Configurable allowed origins |
| **Session isolation** | Per-user session storage via Redis or in-memory |

### Recommended Deployment Practices

1. **Firewall**: Restrict ports 8000 and 8501 to trusted IPs
   ```bash
   sudo ufw allow from 127.0.0.1 to any port 8000
   sudo ufw allow from 192.168.1.0/24 to any port 8000
   sudo ufw allow from 192.168.1.0/24 to any port 8501
   ```

2. **Environment variables**: Store all secrets in `.env`; never commit to version control

3. **CORS**: Set explicit origins in production (not wildcard `*`)

4. **Demo mode**: Set `DEMO_MODE=false` in production to disable demo endpoints

---

## Troubleshooting

### Port 8000 already in use

```bash
# Kill process on port 8000
lsof -ti:8000 | xargs kill -9
```

### Ollama not responding

1. Check if the model is pulled:
   ```bash
   docker compose exec ollama ollama list
   # Should show qwen2.5:1.5b with ~1 GB size
   ```

2. If not listed, pull it:
   ```bash
   docker compose exec ollama ollama pull qwen2.5:1.5b
   ```

3. Verify `OLLAMA_BASE_URL` in `backend/.env` is set to `http://ollama:11434` — this is the Docker internal hostname. Using `http://localhost:11434` inside a container won't work.

### LLM read timeout

If you see `Read timed out` errors, the model is taking too long for your hardware.

**Solutions:**
1. Set `REQUEST_TIMEOUT=600` in `backend/.env` (already the recommended default)
2. For very low-spec machines (CPU-only, < 8 GB RAM): drop to `OLLAMA_MODEL=qwen2.5:0.5b` (~500 MB) — quality is noticeably lower but responses are faster

### Wrong model loaded

If the backend is using the wrong model after you change `OLLAMA_MODEL`:
```bash
# Rebuild the backend container to pick up the new env value
docker compose build --no-cache backend
docker compose up -d backend
```

### Frontend connection refused

- Ensure the backend is running: `docker compose ps`
- Check CORS origin matches your frontend URL: `CORS_ORIGIN=http://localhost:8501`
- Verify network: `curl -v http://localhost:8000/health`
- Frontend runs on port **8501** by default (not 3000).

---

## Performance Tips

- **Recommended model**: `qwen2.5:1.5b` (~1 GB) — good balance of quality and speed on CPU-only machines. For higher quality on faster machines, `qwen2.5:3b` (~1.9 GB) also works.
- **Faster responses**: Increase `OLLAMA_NUM_GPU=1` in environment if an NVIDIA GPU is available
- **Faster frontend builds**: Use `npm ci` instead of `npm install`
- **Incremental testing**: `pytest tests/test_file.py -v` to avoid running full suite during development

---

## Next Steps

- [Architecture Overview](ARCHITECTURE.md)
- [Agent Pipeline Guide](AGENTS.md)
- [API Reference](API_REFERENCE.md)
- [Contributing Guide](../CONTRIBUTING.md)
