#!/usr/bin/env bash
# One-line installer: clones Insight Orchestra and hands off to ./setup.sh.
#
#   curl -fsSL https://raw.githubusercontent.com/laban254/insight-orchestra/main/install.sh | bash
#   curl -fsSL .../install.sh | bash -s -- --provider ollama -y
#
# Anything after `--` (or any arg, when run locally as ./install.sh) is
# forwarded to setup.sh verbatim — see `./setup.sh --help` for options.
set -euo pipefail

REPO_URL="https://github.com/laban254/insight-orchestra.git"
INSTALL_DIR="${INSTALL_DIR:-insight-orchestra}"

if [ -t 1 ]; then
  BOLD=$'\033[1m'; CYAN=$'\033[36m'; GREEN=$'\033[32m'; RED=$'\033[31m'; RESET=$'\033[0m'
else
  BOLD=""; CYAN=""; GREEN=""; RED=""; RESET=""
fi
ok()   { printf '%s\n' "  ${GREEN}✓${RESET} $*"; }
die()  { printf '%s\n' "  ${RED}✗${RESET} $*" >&2; exit 1; }

printf '%s\n' "${BOLD}${CYAN}Insight Orchestra${RESET} installer"

command -v git >/dev/null 2>&1 || die "git is required but not found. Install git and re-run."
command -v docker >/dev/null 2>&1 || die "Docker is required but not found. Install Docker and re-run."

# Compose v2 ships either as the `docker compose` CLI plugin or (less commonly)
# as a standalone `docker-compose` binary — accept either. setup.sh re-detects
# this itself, so we only need a fast fail here.
if ! docker compose version >/dev/null 2>&1; then
  if ! { command -v docker-compose >/dev/null 2>&1 && docker-compose version --short 2>/dev/null | grep -q '^2\.'; }; then
    die "Docker Compose v2 is required (docker compose version failed). Install the compose plugin: https://docs.docker.com/compose/install/linux/"
  fi
fi

if [ -d "$INSTALL_DIR" ]; then
  if [ -d "$INSTALL_DIR/.git" ] && git -C "$INSTALL_DIR" remote get-url origin 2>/dev/null | grep -q "laban254/insight-orchestra"; then
    ok "Found an existing clone at ./$INSTALL_DIR — reusing it (re-running setup.sh is safe)."
  else
    die "./$INSTALL_DIR already exists and isn't an Insight Orchestra clone. Set INSTALL_DIR=<other-path> and re-run, or remove it first."
  fi
else
  ok "Cloning into ./$INSTALL_DIR"
  git clone --depth 1 "$REPO_URL" "$INSTALL_DIR"
fi

cd "$INSTALL_DIR"
chmod +x setup.sh
exec ./setup.sh "$@"
