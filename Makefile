.DEFAULT_GOAL := help
.PHONY: help setup fmt lint types test check nb clean

help: ## Show available targets
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
		| awk -F':.*?## ' '{printf "  \033[36m%-8s\033[0m %s\n", $$1, $$2}'

setup: ## Create .venv from uv.lock and install git hooks
	uv sync
	uv run pre-commit install

fmt: ## Auto-fix lint issues and format
	uv run ruff check --fix .
	uv run ruff format .

lint: ## Lint and verify formatting
	uv run ruff check .
	uv run ruff format --check .

types: ## Type-check src/ and tests/
	uv run mypy

test: ## Run the test suite
	uv run pytest

check: lint types test ## Run all checks

nb: ## Start a marimo notebook server (discoverable by the marimo-pair skill)
	uv run marimo edit notebooks/ --no-token

clean: ## Remove caches and build artifacts
	rm -rf .pytest_cache .ruff_cache .mypy_cache htmlcov .coverage build dist
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
