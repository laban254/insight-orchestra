#!/usr/bin/env bash
# Insight Orchestra one-command setup: writes backend/.env, starts the stack,
# and (for Ollama) pulls the model. Re-run any time — `./setup.sh doctor` just
# checks the environment without touching anything.
set -euo pipefail
SECONDS=0

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$ROOT_DIR/backend/.env"
ENV_EXAMPLE="$ROOT_DIR/backend/.env.example"

PROVIDER=""
API_KEY=""
ASSUME_YES=false
SUBCOMMAND=""
BUILD_FROM_SOURCE=false
COMPOSE="docker compose"

# ── output helpers ───────────────────────────────────────────────────────
if [ -t 1 ]; then
  BOLD=$'\033[1m'; DIM=$'\033[2m'; CYAN=$'\033[36m'
  GREEN=$'\033[32m'; YELLOW=$'\033[33m'; RED=$'\033[31m'; RESET=$'\033[0m'
else
  BOLD=""; DIM=""; CYAN=""; GREEN=""; YELLOW=""; RED=""; RESET=""
fi

banner() {
  printf '%s\n' "${BOLD}${CYAN}Insight Orchestra${RESET}"
  printf '%s\n' "${DIM}Your data, analyzed by a team of AI agents.${RESET}"
}
# House style shared with .env.example / .pre-commit-config.yaml section headers.
info() {
  local title="$*" width=64 pad
  pad=$(( width - ${#title} - 4 ))
  [ "$pad" -lt 2 ] && pad=2
  printf '\n%s── %s %s%s\n' "$BOLD" "$title" "$(printf -- '─%.0s' $(seq 1 "$pad"))" "$RESET"
}
ok()    { printf '%s\n' "  ${GREEN}✓${RESET} $*"; }
warn()  { printf '%s\n' "  ${YELLOW}!${RESET} $*"; }
fail()  { printf '%s\n' "  ${RED}✗${RESET} $*"; }
die()   { fail "$*"; exit 1; }

# Reads KEY=value from backend/.env, stripping inline `# comments` and
# whitespace (.env.example ships some, e.g. `LLM_PROVIDER=openai  # openai | ...`).
env_get() {
  grep -E "^$1=" "$ENV_FILE" 2>/dev/null | head -1 | cut -d= -f2- \
    | sed -e 's/[[:space:]]*#.*//' -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//'
}

usage() {
  cat <<EOF
${BOLD}${CYAN}Insight Orchestra${RESET} setup

Usage: ./setup.sh [command] [options]

Commands:
  (none)      Configure backend/.env, start the stack, pull the Ollama model if needed (default)
  doctor      Check the environment without starting or changing anything
  help        Show this message

Options:
  --provider <openai|anthropic|deepseek|ollama>   LLM provider (skips the prompt)
  --api-key <key>                                 API key for a cloud provider (skips the prompt)
  --build                                          Build images from source instead of pulling
  -y, --yes                                        Non-interactive: accept defaults, don't prompt

Examples:
  ./setup.sh                                  # interactive wizard
  ./setup.sh --provider ollama -y             # fully non-interactive, local model
  ./setup.sh --provider openai --api-key sk-... -y
  ./setup.sh --build                          # build locally (for development)
  ./setup.sh doctor                           # just run health checks
EOF
}

# ── arg parsing ──────────────────────────────────────────────────────────
while [ $# -gt 0 ]; do
  case "$1" in
    doctor|help) SUBCOMMAND="$1"; shift ;;
    --provider) PROVIDER="${2:-}"; shift 2 ;;
    --provider=*) PROVIDER="${1#*=}"; shift ;;
    --api-key) API_KEY="${2:-}"; shift 2 ;;
    --api-key=*) API_KEY="${1#*=}"; shift ;;
    --build) BUILD_FROM_SOURCE=true; shift ;;
    -y|--yes) ASSUME_YES=true; shift ;;
    -h|--help) usage; exit 0 ;;
    *) die "Unknown argument: $1 (see --help)" ;;
  esac
done

if [ "$SUBCOMMAND" = "help" ]; then usage; exit 0; fi

# ── doctor checks (used both standalone and as pre-flight) ──────────────
port_in_use() {
  (exec 3<>"/dev/tcp/127.0.0.1/$1") 2>/dev/null && { exec 3<&- 3>&-; return 0; } || return 1
}

check_docker() {
  command -v docker >/dev/null 2>&1 || { fail "Docker is not installed — https://docs.docker.com/get-docker/"; return 1; }
  ok "Docker is installed ($(docker --version | sed 's/,.*//'))"

  # Compose v2 ships either as the `docker compose` CLI plugin or (less
  # commonly) as a standalone `docker-compose` binary — accept either.
  if docker compose version >/dev/null 2>&1; then
    COMPOSE="docker compose"
  elif command -v docker-compose >/dev/null 2>&1 && docker-compose version --short 2>/dev/null | grep -q '^2\.'; then
    COMPOSE="docker-compose"
  else
    fail "Docker Compose v2 is not available (try updating Docker, or install the plugin: https://docs.docker.com/compose/install/linux/)"
    return 1
  fi
  ok "Docker Compose v2 is available (via '$COMPOSE')"

  docker info >/dev/null 2>&1 || { fail "Docker daemon is not running — start Docker Desktop / dockerd"; return 1; }
  ok "Docker daemon is running"
}

check_ports() {
  local busy=0
  for p in 8000 8501; do
    if port_in_use "$p"; then
      warn "Port $p is already in use — that service may fail to start"
      busy=1
    else
      ok "Port $p is free"
    fi
  done
  return $busy
}

check_env_file() {
  if [ -f "$ENV_FILE" ]; then
    ok "backend/.env exists"
    local configured_provider
    configured_provider="$(env_get LLM_PROVIDER)"
    [ -n "$configured_provider" ] && ok "LLM_PROVIDER=$configured_provider"
  else
    warn "backend/.env not found — run ./setup.sh to create it"
  fi
}

check_backend_health() {
  local port
  port="$(env_get BACKEND_PORT)"
  port="${port:-8000}"
  if curl -fsS "http://localhost:${port}/health" >/dev/null 2>&1; then
    ok "Backend is responding at http://localhost:${port}/health"
  else
    warn "Backend is not responding at http://localhost:${port}/health (is it running? try: $COMPOSE up -d)"
  fi
}

check_ollama_model() {
  [ -f "$ENV_FILE" ] || return 0
  [ "$(env_get LLM_PROVIDER)" = "ollama" ] || return 0
  local model
  model="$(env_get OLLAMA_MODEL)"
  model="${model:-qwen2.5:1.5b}"
  if $COMPOSE exec -T ollama ollama list 2>/dev/null | grep -q "$model"; then
    ok "Ollama model '$model' is pulled"
  else
    warn "Ollama model '$model' not found — run: $COMPOSE exec ollama ollama pull $model"
  fi
}

run_doctor() {
  banner
  info "Checking environment"
  check_docker || true
  info "Checking ports"
  check_ports || true
  info "Checking configuration"
  check_env_file
  info "Checking running services"
  check_backend_health
  check_ollama_model
  echo
}

if [ "$SUBCOMMAND" = "doctor" ]; then
  run_doctor
  exit 0
fi

# ── setup flow ────────────────────────────────────────────────────────────
banner
info "Checking prerequisites"
check_docker || die "Fix the issues above and re-run ./setup.sh"

info "Configuring backend/.env"
if [ -f "$ENV_FILE" ]; then
  warn "backend/.env already exists"
  if [ "$ASSUME_YES" = true ]; then
    PROVIDER="$(env_get LLM_PROVIDER)"
    ok "Keeping existing backend/.env (LLM_PROVIDER=$PROVIDER)"
  else
    read -r -p "  Overwrite it? [y/N] " reply
    case "$reply" in
      [yY]*) rm -f "$ENV_FILE" ;;
      *) PROVIDER="$(env_get LLM_PROVIDER)"
         ok "Keeping existing backend/.env (LLM_PROVIDER=$PROVIDER)" ;;
    esac
  fi
fi

if [ ! -f "$ENV_FILE" ]; then
  if [ -z "$PROVIDER" ]; then
    if [ "$ASSUME_YES" = true ]; then
      PROVIDER="ollama"
    else
      echo
      printf '  %sWhich LLM provider?%s\n' "$BOLD" "$RESET"
      echo "  1) Ollama    — local, private, no API key needed (default)"
      echo "  2) OpenAI    — cloud"
      echo "  3) Anthropic — cloud"
      echo "  4) DeepSeek  — cloud"
      read -r -p "  Pick 1-4 [1]: " choice
      case "${choice:-1}" in
        1) PROVIDER="ollama" ;;
        2) PROVIDER="openai" ;;
        3) PROVIDER="anthropic" ;;
        4) PROVIDER="deepseek" ;;
        *) die "Invalid choice: $choice" ;;
      esac
    fi
  fi

  case "$PROVIDER" in
    ollama|openai|anthropic|deepseek) ;;
    *) die "Unknown provider '$PROVIDER' (expected openai, anthropic, deepseek, or ollama)" ;;
  esac
  ok "Provider: $PROVIDER"

  cp "$ENV_EXAMPLE" "$ENV_FILE"
  # sed -i portable across GNU/BSD sed
  sedi() { if sed --version >/dev/null 2>&1; then sed -i "$@"; else sed -i '' "$@"; fi; }

  sedi "s/^LLM_PROVIDER=.*/LLM_PROVIDER=${PROVIDER}/" "$ENV_FILE"

  if [ "$PROVIDER" != "ollama" ]; then
    if [ -z "$API_KEY" ] && [ "$ASSUME_YES" = false ]; then
      read -r -s -p "  Enter your ${PROVIDER} API key (leave blank to fill in backend/.env later): " API_KEY
      echo
    fi
    if [ -n "$API_KEY" ]; then
      case "$PROVIDER" in
        openai)    sedi "s|^OPENAI_API_KEY=.*|OPENAI_API_KEY=${API_KEY}|" "$ENV_FILE" ;;
        anthropic) sedi "s|^ANTHROPIC_API_KEY=.*|ANTHROPIC_API_KEY=${API_KEY}|" "$ENV_FILE" ;;
        deepseek)  sedi "s|^DEEPSEEK_API_KEY=.*|DEEPSEEK_API_KEY=${API_KEY}|" "$ENV_FILE" ;;
      esac
      ok "API key written to backend/.env"
    else
      warn "No API key set — add it to backend/.env before using the app"
    fi
  else
    # Docker-internal hostname; localhost won't resolve to the ollama container.
    sedi "s|^OLLAMA_BASE_URL=.*|OLLAMA_BASE_URL=http://ollama:11434|" "$ENV_FILE"
  fi

  ok "Wrote backend/.env"
fi

info "Checking ports"
PORTS_FREE=true
check_ports || { PORTS_FREE=false; warn "Continuing anyway — free the ports above if a service fails to start"; }

info "Starting services"
SERVICES="backend frontend"
[ "$PROVIDER" = "ollama" ] && SERVICES="backend frontend ollama"

# Default path pulls the released images from GHCR (seconds). --build layers in
# docker-compose.dev.yml to compile from source instead — several minutes, since
# the backend builds pandas/statsmodels.
COMPOSE_FILES=(-f docker-compose.yml)
UP_ARGS=(up -d)
if [ "$BUILD_FROM_SOURCE" = true ]; then
  COMPOSE_FILES+=(-f docker-compose.dev.yml)
  UP_ARGS+=(--build)
  printf '%s\n' "  ${DIM}Building from source — this takes a few minutes on a first run.${RESET}"
else
  printf '%s\n' "  ${DIM}Pulling prebuilt images (use --build to compile from source instead).${RESET}"
fi

if ! (cd "$ROOT_DIR" && $COMPOSE "${COMPOSE_FILES[@]}" "${UP_ARGS[@]}" $SERVICES); then
  if [ "$PORTS_FREE" = false ]; then
    die "Failed to start containers — a port above was already in use; free it (or stop the conflicting service) and re-run ./setup.sh"
  elif [ "$BUILD_FROM_SOURCE" = true ]; then
    die "Failed to start containers — see the build output above for the cause. A failed package download mid-build is usually just a transient network hiccup; re-running ./setup.sh often fixes it."
  else
    die "Failed to start containers — see the output above. If the image pull failed, check your network and that ghcr.io is reachable; you can also build locally instead with ./setup.sh --build"
  fi
fi
ok "Containers started ($SERVICES)"

if [ "$PROVIDER" = "ollama" ]; then
  MODEL="$(env_get OLLAMA_MODEL)"
  MODEL="${MODEL:-qwen2.5:1.5b}"
  info "Pulling Ollama model '$MODEL' (first run only, can take a few minutes)"
  if (cd "$ROOT_DIR" && $COMPOSE exec -T ollama ollama pull "$MODEL"); then
    ok "Model '$MODEL' ready"
  else
    warn "Model pull failed — retry later with: $COMPOSE exec ollama ollama pull $MODEL"
  fi
fi

info "Waiting for backend to become healthy"
PORT="$(env_get BACKEND_PORT)"
PORT="${PORT:-8000}"

# uvicorn binds the port long before it can serve: each worker still has to
# import pandas, statsmodels and the agent SDK, which on a cold page cache is
# most of a minute. A measured cold start was 64s, so the old 60s budget
# reported a healthy stack as broken. Wait well past that, and show elapsed
# time so the wait reads as progress rather than a hang.
HEALTH_TIMEOUT=240
healthy=false
waited=0
while [ "$waited" -lt "$HEALTH_TIMEOUT" ]; do
  if curl -fsS "http://localhost:${PORT}/health" >/dev/null 2>&1; then
    healthy=true
    break
  fi
  if [ -t 1 ]; then
    printf '\r  starting the backend — first run loads a lot, this is normal (%ss)   ' "$waited"
  fi
  sleep 2
  waited=$((waited + 2))
done
[ -t 1 ] && printf '\r\033[K'
if [ "$healthy" = true ]; then
  ok "Backend healthy at http://localhost:${PORT}/health (${waited}s)"
else
  warn "Backend still not responding after ${HEALTH_TIMEOUT}s — check: $COMPOSE logs -f backend"
fi

info "Done in ${SECONDS}s"
cat <<SUMMARY
  Frontend      http://localhost:8501
  Backend API   http://localhost:${PORT}
  Swagger docs  http://localhost:${PORT}/docs

  Logs:    $COMPOSE logs -f
  Health:  ./setup.sh doctor

  Pick one of the five demo datasets (or upload your own CSV) — the pipeline runs automatically.
SUMMARY
