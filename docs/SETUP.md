# Local Development Setup

Complete guide to set up Insight Orchestra for development using Docker.

---

## Prerequisites

### System Requirements

- **OS**: macOS, Linux, or Windows (WSL2)
- **CPU**: 2+ cores
- **RAM**: 4 GB minimum (8 GB recommended for local LLMs)
- **Disk**: 2 GB free space

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

```bash
# Create .env from example
cp .env.example .env
```

The backend reads environment variables from `.env` in the project root (mounted into the Docker container). Edit the file to set your LLM provider.

### 3. Choose Your LLM Mode

#### API Mode (OpenAI)

Edit your `.env` file:

```bash
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-your-key-here
```

Start backend and frontend (no Ollama required):

```bash
docker compose up backend frontend
```

**What this starts:**
| Service | URL |
|---------|-----|
| Backend (FastAPI) | `http://localhost:8000` |
| Frontend (Next.js) | `http://localhost:3000` |
| API Docs (Swagger) | `http://localhost:8000/docs` |

#### Local Mode (Ollama)

Edit your `.env` file:

```bash
LLM_PROVIDER=ollama
OLLAMA_MODEL=qwen2.5:0.5b  # lightweight model for testing
```

Start all services (including Ollama):

```bash
docker compose up backend frontend ollama
```

After starting, pull the model:

```bash
docker compose exec ollama ollama pull qwen2.5:0.5b
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
open http://localhost:3000
```

---

## Environment Variables Reference

### LLM Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_PROVIDER` | `openai` | LLM provider: `openai` or `ollama` |
| `OPENAI_API_KEY` | — | API key for OpenAI (required if using `openai`) |
| `OPENAI_MODEL` | `gpt-4o-mini` | OpenAI model to use |
| `OPENAI_MODEL_FALLBACK` | `gpt-4o` | Fallback model for OpenAI |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama service URL |
| `OLLAMA_MODEL` | `llama3.1:8b` | Ollama model to use |
| `MAX_RETRIES` | `3` | Max retries for LLM requests |
| `REQUEST_TIMEOUT` | `300` | LLM request timeout (seconds) |

### Application Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `BACKEND_HOST` | `0.0.0.0` | Backend bind address |
| `BACKEND_PORT` | `8000` | Backend port |
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
| `CORS_ORIGIN` | `http://localhost:3000` | Primary allowed CORS origin |
| `CORS_ORIGIN_ALT` | `http://localhost:3000` | Secondary CORS origin |

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

1. **Firewall**: Restrict ports 8000 and 3000 to trusted IPs
   ```bash
   sudo ufw allow from 127.0.0.1 to any port 8000
   sudo ufw allow from 192.168.1.0/24 to any port 8000
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
   ```

2. Verify `OLLAMA_BASE_URL` in `.env` is set to `http://ollama:11434` (Docker internal networking).

### LLM read timeout

If you see `Read timed out` errors from Ollama, the model is too large for your machine.

**Solutions:**
1. Use a smaller model: `OLLAMA_MODEL=qwen2.5:0.5b` (1.5 GB instead of 4+ GB)
2. Increase timeout: set `REQUEST_TIMEOUT=600` in `.env`

### Frontend connection refused

- Ensure the backend is running: `docker compose ps`
- Check CORS origin matches your frontend URL: `CORS_ORIGIN=http://localhost:3000`
- Verify network: `curl -v http://localhost:8000/health`

---

## Performance Tips

- **Faster LLM**: Use `qwen2.5:0.5b` or `mistral` instead of `llama2` for quicker responses
- **Faster frontend builds**: Use `npm ci` instead of `npm install`
- **Incremental testing**: `pytest tests/test_file.py -v` to avoid running full suite during development
- **GPU acceleration**: Set `OLLAMA_NUM_GPU=1` in environment if NVIDIA GPU is available

---

## Next Steps

- [Architecture Overview](ARCHITECTURE.md)
- [Agent Pipeline Guide](AGENTS.md)
- [API Reference](API_REFERENCE.md)
- [Contributing Guide](../CONTRIBUTING.md)
