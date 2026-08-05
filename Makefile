.DEFAULT_GOAL := help

# Running a notebook headlessly (`python notebooks/full_example.py`) puts
# notebooks/ on sys.path, not the repo root, so `import petri` fails. marimo's
# own `runtime.pythonpath = ["."]` covers the editor but not script execution.
export PYTHONPATH := $(CURDIR)

# `make init full` — the set names are goals, not targets, because make takes no
# positional arguments. The no-op rule below absorbs them so make does not report
# "No rule to make target 'full'".
INIT_SETS := minimal full
INIT_ARGS := $(filter $(INIT_SETS),$(MAKECMDGOALS))

.PHONY: help setup init $(INIT_SETS) nb test lint fmt check clean r-restore r-snapshot r-status r-install

help: ## Show available targets
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
		| awk -F':.*?## ' '{printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

setup: ## Create .venv and R library, install git hooks
	uv sync
	uv run pre-commit install
	$(MAKE) r-restore

# The user's folders ship empty; this fills them from petri/examples/. Existing
# files are left alone unless --force, so it is safe to re-run. Flags go through
# ARGS, because make claims a bare `--force` for itself:
#   make init full ARGS=--force
#   make init full ARGS=--dry-run
init: ## Copy template examples into notebooks/, scripts/, data/: make init [minimal|full] [ARGS=--force]
	uv run python -m petri.init $(INIT_ARGS) $(ARGS)

# Absorbs `minimal`/`full` when they appear as goals alongside `init`.
$(INIT_SETS):
	@:

# .env reaches the notebook kernel through marimo's own `runtime.dotenv`, but not
# the server process, which is what resolves the AI provider key. Load it here so
# GEMINI_API_KEY works from .env instead of being typed into tracked config.
nb: ## Start marimo on notebooks/ (discoverable by the marimo-pair skill)
	set -a; [ -f .env ] && . ./.env; set +a; PYTHONPATH="$(CURDIR)" uv run marimo edit notebooks/ --no-token

lint: ## Lint notebooks and verify formatting
	uv run ruff check .
	uv run ruff format --check .

test: ## Run the test suite (contracts plus the notebook write path)
	uv run pytest petri/tests/ -q

check: ## Verify artifact and shared-table provenance (exits non-zero on errors)
	@uv run python -c "import sys, petri; r = petri.check(); print(r); sys.exit(0 if r.ok else 1)"

fmt: ## Auto-fix lint issues and format
	uv run ruff check --fix .
	uv run ruff format .

# Wave by wave, not one renv::restore(). A plain restore can start building a
# package before a transitive dependency is installed; petri/r-restore.R has
# the mechanism and the error it produces.
r-restore: ## Install R packages from renv.lock into .renv/library, in dependency order
	Rscript petri/r-restore.R renv.lock

r-install: ## Install R package(s) into the project library: make r-install PKG="ggplot2 bioc::DESeq2"
	@test -n "$(PKG)" || (echo 'usage: make r-install PKG="<package>..." (e.g. PKG="ggplot2" or PKG="bioc::DESeq2")'; exit 1)
	Rscript -e 'renv::install(commandArgs(TRUE))' $(PKG)
	$(MAKE) r-snapshot

r-snapshot: ## Record the project library into renv.lock
	Rscript -e 'renv::snapshot(prompt = FALSE)'

r-status: ## Show renv project status
	Rscript -e 'renv::status()'

clean: ## Remove tool caches and marimo session state (not data/)
	rm -rf .ruff_cache .pytest_cache
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
	find notebooks -name __marimo__ -type d -prune -exec rm -rf {} +
