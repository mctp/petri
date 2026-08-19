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

.PHONY: help setup init $(INIT_SETS) nb nb-url nb-status nb-stop run export test lint fmt check clean r-restore r-snapshot r-status r-install

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
#
# petri.server picks a port from this directory and execs marimo, so two projects
# on one machine never share a port and never stop each other's server. Running
# this when a server is already up here prints its URL and does nothing else.
nb: ## Start marimo on notebooks/, or print the URL if it is already running
	set -a; [ -f .env ] && . ./.env; set +a; PYTHONPATH="$(CURDIR)" uv run python -m petri.server $(ARGS)

nb-url: ## Print this project's marimo URL
	@uv run python -m petri.server --url

nb-status: ## Report whether marimo is running for this project
	@uv run python -m petri.server --status || true

nb-stop: ## Stop this project's marimo server, leaving other projects alone
	@uv run python -m petri.server --stop

# Loads .env the same way `nb` does. marimo's `runtime.dotenv` reaches the editor
# kernel but not a script run, so without this a notebook that reads a key works
# in the browser and fails here — the one place it is meant to be verified.
run: ## Run a notebook headlessly as a script: make run NB=notebooks/full_example.py
	@test -n "$(NB)" || (echo 'usage: make run NB=notebooks/<name>.py'; exit 1)
	@test -f "$(NB)" || (echo "no such notebook: $(NB)"; exit 1)
	set -a; [ -f .env ] && . ./.env; set +a; uv run python $(NB)

export: ## Export notebook to self-contained HTML: make export NB=notebooks/<name>.py [OUT=<name>.html]
	@test -n "$(NB)" || (echo 'usage: make export NB=notebooks/<name>.py [OUT=<name>.html]'; exit 1)
	@test -f "$(NB)" || (echo "no such notebook: $(NB)"; exit 1)
	@set -a; [ -f .env ] && . ./.env; set +a; \
	OUT=$${OUT:-$$(echo "$(NB)" | sed 's/\.py$$/\.html/')}; \
	LOG=$$(mktemp); \
	if PYTHONPATH="$(CURDIR)" uv run marimo export html "$(NB)" -o "$$OUT" > "$$LOG" 2>&1; then \
	  rm -f "$$LOG"; echo "Exported HTML to $$OUT"; \
	else \
	  cat "$$LOG"; rm -f "$$LOG"; \
	  echo "export failed: $(NB)"; exit 1; \
	fi

lint: ## Lint everything or single target: make lint [NB=notebooks/<name>.py]
	@TARGET=$${TARGET:-$${NB:-.}}; \
	uv run ruff check --output-format=concise "$$TARGET" && \
	(echo "$$TARGET" | grep -q '^notebooks/' || uv run ruff format --check "$$TARGET")

test: ## Run the test suite (contracts plus the notebook write path)
	uv run pytest petri/tests/ -q

check: ## Verify artifact and shared-table provenance (exits non-zero on errors)
	@uv run python -c "import sys, petri; r = petri.check(); print(r); sys.exit(0 if r.ok else 1)"

# Both commands write files, so both skip notebooks/. `ruff format` reads its
# exclusion from [tool.ruff.format]; `ruff check --fix` does not, and needs it
# here. Fix a notebook through the live kernel with `cm`, never on disk.
fmt: ## Auto-fix lint issues and format, leaving notebooks/ to marimo
	uv run ruff check --fix --extend-exclude "notebooks/**" .
	uv run ruff format .

r-restore: ## Install R packages from renv.lock into .renv/library
	Rscript -e 'renv::restore(prompt = FALSE)'

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
