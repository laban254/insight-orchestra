.DEFAULT_GOAL := help

PYTHON := backend/venv/bin/python
COMPOSE := docker compose

.PHONY: help install dev up down logs test lint format frontend-build clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-16s\033[0m %s\n", $$1, $$2}'

install: ## Set up backend/venv (Python 3.11, matching CI) and install frontend deps
	python3.11 -m venv backend/venv
	$(PYTHON) -m pip install -r backend/requirements.txt
	$(PYTHON) -m pip install ruff mypy pytest pytest-asyncio pytest-cov
	cd frontend && npm install

dev: ## Start the full stack, building images from local source (for active development)
	$(COMPOSE) -f docker-compose.yml -f docker-compose.dev.yml up -d --build

up: ## Start the full stack using the published GHCR images
	$(COMPOSE) up -d

down: ## Stop the stack
	$(COMPOSE) down

logs: ## Tail logs from all services
	$(COMPOSE) logs -f

test: ## Run the backend test suite (run `make install` first)
	$(PYTHON) -m pytest tests/ -v

lint: ## Run every linter/type-checker CI runs
	$(PYTHON) -m ruff check .
	$(PYTHON) -m ruff format --check .
	$(PYTHON) -m mypy backend/app/ --ignore-missing-imports
	cd frontend && npm run lint && npx tsc --noEmit

format: ## Auto-format Python with Ruff
	$(PYTHON) -m ruff format .

frontend-build: ## Production build of the frontend
	cd frontend && npm run build

clean: ## Remove the backend venv and lint/test caches
	rm -rf backend/venv .pytest_cache .ruff_cache .mypy_cache
	find . -path ./frontend/node_modules -prune -o -name '__pycache__' -exec rm -rf {} +
