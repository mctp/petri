.DEFAULT_GOAL := help
.PHONY: help setup nb lint fmt clean

help: ## Show available targets
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
		| awk -F':.*?## ' '{printf "  \033[36m%-8s\033[0m %s\n", $$1, $$2}'

setup: ## Create .venv from uv.lock and install git hooks
	uv sync
	uv run pre-commit install

nb: ## Start marimo on notebooks/ (discoverable by the marimo-pair skill)
	uv run marimo edit notebooks/ --no-token

lint: ## Lint notebooks and verify formatting
	uv run ruff check .
	uv run ruff format --check .

fmt: ## Auto-fix lint issues and format
	uv run ruff check --fix .
	uv run ruff format .

clean: ## Remove caches and marimo artifacts
	rm -rf .ruff_cache
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
	find notebooks -name __marimo__ -type d -prune -exec rm -rf {} +
