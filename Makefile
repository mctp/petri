.DEFAULT_GOAL := help
.PHONY: help setup skills skills-update nb lint fmt clean r-restore r-snapshot r-status r-install

help: ## Show available targets
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
		| awk -F':.*?## ' '{printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

setup: skills ## Fetch skills, create .venv and R library, install git hooks
	uv sync
	uv run pre-commit install
	$(MAKE) r-restore

skills: ## Fetch/refresh the vendored marimo-pair skill (git submodule)
	git submodule update --init --recursive

skills-update: ## Update the vendored skill to upstream main
	git submodule update --remote --merge vendor/marimo-pair
	@git -C vendor/marimo-pair log --oneline -1

nb: ## Start marimo on notebooks/ (discoverable by the marimo-pair skill)
	uv run marimo edit notebooks/ --no-token

lint: ## Lint notebooks and verify formatting
	uv run ruff check .
	uv run ruff format --check .

fmt: ## Auto-fix lint issues and format
	uv run ruff check --fix .
	uv run ruff format .

r-restore: ## Install R packages from renv.lock into renv/library
	Rscript -e 'renv::restore(prompt = FALSE)'

r-install: ## Install R package(s) into the project library: make r-install PKG="ggplot2 bioc::DESeq2"
	@test -n "$(PKG)" || (echo 'usage: make r-install PKG="<package>..." (e.g. PKG="ggplot2" or PKG="bioc::DESeq2")'; exit 1)
	Rscript -e 'renv::install(commandArgs(TRUE))' $(PKG)
	$(MAKE) r-snapshot

r-snapshot: ## Record the project library into renv.lock
	Rscript -e 'renv::snapshot(prompt = FALSE)'

r-status: ## Show renv project status
	Rscript -e 'renv::status()'

clean: ## Remove caches and marimo artifacts
	rm -rf .ruff_cache
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
	find notebooks -name __marimo__ -type d -prune -exec rm -rf {} +
