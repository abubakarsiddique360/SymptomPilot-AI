.PHONY: help install test lint format eval run ingest clean docker-build docker-run

ifeq ($(OS),Windows_NT)
BOOTSTRAP ?= python
PY := .venv/Scripts/python.exe
else
BOOTSTRAP ?= python3
PY := .venv/bin/python
endif

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

install: ## Create the virtual environment and install dev dependencies
	$(BOOTSTRAP) -m venv .venv
	$(PY) -m pip install --upgrade pip
	$(PY) -m pip install -e ".[dev]"

test: ## Run the test suite
	$(PY) -m pytest

lint: ## Check style and formatting
	$(PY) -m ruff check .
	$(PY) -m ruff format --check .

format: ## Auto-fix lint issues and format code
	$(PY) -m ruff check . --fix
	$(PY) -m ruff format .

eval: ## Run the offline evaluation suite
	$(PY) -m symptompilot eval

run: ## Start the web app on http://127.0.0.1:8000
	$(PY) -m symptompilot serve

ingest: ## Rebuild the SQLite index from knowledge/
	$(PY) -m symptompilot ingest

clean: ## Remove caches and local runtime data
	rm -rf .pytest_cache .ruff_cache htmlcov .coverage var
	find . -name __pycache__ -type d -prune -exec rm -rf {} +

docker-build: ## Build the container image
	docker build -t symptompilot:local .

docker-run: ## Run the container on port 8000
	docker run --rm -p 8000:8000 symptompilot:local
