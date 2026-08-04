.DEFAULT_GOAL := help

# Running a notebook headlessly (`python notebooks/00_ingest.py`) puts
# notebooks/ on sys.path, not the repo root, so `import petri` fails. marimo's
# own `runtime.pythonpath = ["."]` covers the editor but not script execution.
export PYTHONPATH := $(CURDIR)

# Producer notebooks rebuild shared/. The numeric prefix declares run order —
# there is no DAG engine, so the sort IS the dependency graph. Everything else
# under notebooks/ is an analysis notebook and is not run by `make shared`.
PRODUCERS := $(sort $(wildcard notebooks/[0-9]*.py))

.PHONY: help setup nb shared test lint fmt check clean r-restore r-snapshot r-status r-install

help: ## Show available targets
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
		| awk -F':.*?## ' '{printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

setup: ## Create .venv and R library, install git hooks
	uv sync
	uv run pre-commit install
	$(MAKE) r-restore

# .env reaches the notebook kernel through marimo's own `runtime.dotenv`, but not
# the server process, which is what resolves the AI provider key. Load it here so
# GEMINI_API_KEY works from .env instead of being typed into tracked config.
nb: ## Start marimo on notebooks/ (discoverable by the marimo-pair skill)
	set -a; [ -f .env ] && . ./.env; set +a; PYTHONPATH="$(CURDIR)" uv run marimo edit notebooks/ --no-token

lint: ## Lint notebooks and verify formatting
	uv run ruff check .
	uv run ruff format --check .

shared: ## Rebuild shared/ by running producer notebooks (notebooks/NN_*.py) in order, then verify
	@if [ -z "$(PRODUCERS)" ]; then \
		echo "No producer notebooks found (expected notebooks/NN_name.py)."; \
		echo "The numeric prefix declares run order; see docs/architecture.md."; \
	else \
		for nb in $(PRODUCERS); do \
			echo "==> $$nb"; \
			uv run python "$$nb" || exit 1; \
		done; \
	fi
	@$(MAKE) --no-print-directory check

test: ## Run the test suite (contracts plus the make shared/check write path)
	uv run pytest tests/ -q

# Needs the tables present, so run `make shared` first on a fresh clone:
# shared/ ships its manifests, not its CSVs.
check: ## Verify artifact and shared-table provenance (exits non-zero on errors)
	@uv run python -c "import sys, petri; r = petri.check(); print(r); sys.exit(0 if r.ok else 1)"

fmt: ## Auto-fix lint issues and format
	uv run ruff check --fix .
	uv run ruff format .

# Wave by wave, not one renv::restore(). A plain restore can start building a
# package before a transitive dependency is installed; scripts/r-restore.R has
# the mechanism and the error it produces.
r-restore: ## Install R packages from renv.lock into renv/library, in dependency order
	Rscript scripts/r-restore.R renv.lock

r-install: ## Install R package(s) into the project library: make r-install PKG="ggplot2 bioc::DESeq2"
	@test -n "$(PKG)" || (echo 'usage: make r-install PKG="<package>..." (e.g. PKG="ggplot2" or PKG="bioc::DESeq2")'; exit 1)
	Rscript -e 'renv::install(commandArgs(TRUE))' $(PKG)
	$(MAKE) r-snapshot

r-snapshot: ## Record the project library into renv.lock
	Rscript -e 'renv::snapshot(prompt = FALSE)'

r-status: ## Show renv project status
	Rscript -e 'renv::status()'

clean: ## Remove tool caches and marimo session state (not preserved/ or shared/)
	rm -rf .ruff_cache
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
	find notebooks -name __marimo__ -type d -prune -exec rm -rf {} +
