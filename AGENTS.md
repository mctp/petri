# AGENTS.md — Instructions for AI Coding Agents

This repository is a project template that pairs **marimo reactive notebooks**
with the **pi** coding agent via the `marimo-pair` skill. It combines Python
(`uv`, Polars) and R (`renv`, `ggplot2`/`ggpubr`) in a reactive data science environment.

---

## ⚠️ Critical Rule #1: Live Kernel is Source of Truth

When a marimo server or kernel session is running:
- **DO NOT** edit notebook files (`notebooks/*.py`) directly on disk using file tools (`edit`, `write`). The live kernel holds cell state in memory and will overwrite disk on save.
- **DO** execute Python code in the kernel using `bash .pi/skills/marimo-pair/scripts/execute-code.sh`.
- **DO** use `marimo._code_mode` (`cm`) inside the scratchpad to create, edit, re-order, or delete notebook cells.

---

## R Interop Conventions (`r_bridge`)

- **Import `r_bridge`**: Notebook cells must use `from r_bridge import pl_to_r, r_eval, r_set, r_to_pl`.
- **No `pandas`**: Use Polars for Python dataframes. Data transfers to/from R use `pl_to_r` and `r_to_pl` without `pandas` or `pandas2ri`.
- **No in-cell `renv` activation**: Do NOT call `source("renv/activate.R")` or `renv::load()` in notebook cells. `r_bridge` initializes R in `PROJECT_ROOT`, which activates `renv` automatically once at import time.
- **marimo DAG vs R `.GlobalEnv`**: R's global environment is invisible to marimo's dataflow graph. To ensure marimo re-runs an R-dependent cell when Python data changes, reference the Python Polars DataFrame in the cell signature (e.g. `_ = sample_df`).

---

## Package & Dependency Management

- **Python**:
  - Outside a live session: `uv add <pkg>` or `uv add --dev <pkg>`.
  - Inside a live session: use `ctx.packages.add("<pkg>")` via `cm`.
- **R**:
  - `make r-install PKG="pkgname"` (installs into `renv/library` and updates `renv.lock`).
  - `make r-restore` (restores `renv/library` from `renv.lock`).
  - `make r-status` (verifies library vs. lockfile).

---

## File & Artifact Paths

- **Notebooks**: Notebooks live in `notebooks/` (`blank.py`, `py_example.py`, `r_example.py`).
- **Paths**: Use `from paths import DATA_DIR, OUTPUTS_DIR, PROJECT_ROOT` for pure Python paths (no R dependencies).
- **Data**: Data files live in `data/` (`raw/`, `interim/`, `processed/`, `external/`).
- **Outputs**: Plots and figures MUST be saved to `outputs/` (e.g. `OUTPUTS_DIR / "plot.png"`), never `/tmp/`. Display in marimo using `mo.image(plot_path.read_bytes(), width=600)`.
- **Secrets**: Store local credentials in `.env` (gitignored). Document keys in `.env.example`.

---

## Command Reference

| Command | Purpose |
|---|---|
| `make setup` | Install Python (`uv sync`), R packages (`renv::restore`), git hooks |
| `make nb` | Start marimo server editing `notebooks/` (`--no-token`) |
| `make lint` | Run `ruff check .` and `ruff format --check .` |
| `make fmt` | Run `ruff check --fix .` and `ruff format .` |
| `make r-install PKG="..."` | Install R package(s) and update `renv.lock` |
| `make r-status` | Verify R library against `renv.lock` |
