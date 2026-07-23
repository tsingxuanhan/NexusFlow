# ============================================================
# NexusFlow Makefile
# ============================================================
# Common development and deployment commands
# ============================================================

.PHONY: help install install-dev test test-cov lint format serve demo doctor clean docker-build docker-up docker-down

# Default target
help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ---------- Installation ----------

install:  ## Install runtime dependencies
	pip install -e .

install-dev:  ## Install with development dependencies
	pip install -e ".[dev]"
	pre-commit install 2>/dev/null || true

# ---------- Testing ----------

test:  ## Run unit tests
	python -m pytest tests/ -v --tb=short --timeout=30

test-cov:  ## Run tests with coverage report
	python -m pytest tests/ -v --tb=short --timeout=30 --cov=nexusflow --cov-report=term-missing

test-quick:  ## Run tests (skip slow/integration)
	python -m pytest tests/ -v --tb=short --timeout=30 -m "not slow"

# ---------- Code Quality ----------

lint:  ## Run linter and show issues
	ruff check nexusflow/ tests/

lint-fix:  ## Run linter and auto-fix
	ruff check nexusflow/ tests/ --fix

format:  ## Format code
	ruff format nexusflow/ tests/ examples/

check:  ## Run all checks (lint + format check + test)
	ruff check nexusflow/ tests/
	ruff format --check nexusflow/ tests/
	python -m pytest tests/ -v --tb=short --timeout=30

# ---------- Run ----------

serve:  ## Start Dashboard server
	nexusflow serve

demo:  ## Run end-to-end demo
	nexusflow demo

doctor:  ## Check environment and dependencies
	nexusflow doctor

# ---------- Docker ----------

docker-build:  ## Build Docker image
	docker build -t nexusflow:latest .

docker-up:  ## Start with docker compose
	docker compose up -d

docker-up-local:  ## Start with local Ollama
	docker compose --profile local up -d

docker-down:  ## Stop docker compose
	docker compose down

docker-logs:  ## Follow docker logs
	docker compose logs -f

# ---------- Utilities ----------

clean:  ## Clean build artifacts
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf .pytest_cache dist/ build/ *.egg-info .coverage htmlcov/
	@echo "Cleaned."

version:  ## Show current version
	@python -c "from nexusflow import __version__; print(__version__)"
