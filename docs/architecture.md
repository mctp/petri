# Architecture & Design Decisions

This document describes the design decisions behind the `petri` project template.

---

## 1. marimo Reactive Notebook Model

Unlike traditional Jupyter notebooks (`.ipynb` JSON files with out-of-order execution), marimo notebooks are **reactive, deterministic Python programs** saved as `.py` files.

- **DAG Dataflow**: marimo parses cell inputs/outputs and constructs a Directed Acyclic Graph (DAG). When a variable changes (e.g. via a slider or parent cell), marimo automatically re-executes dependent cells in topological order.
- **Single Definition Rule**: A public name can only be defined in one cell across the entire notebook. Use private variables (`_name`) for cell-internal temporaries.
- **Git-friendly**: Notebooks are valid Python scripts that diff, review, and format like standard code.

---

## 2. Python <-> R Interop (`r_bridge.py`)

Embedding R inside Python using `rpy2` within a reactive, multi-threaded notebook runtime presents several edge cases. `r_bridge.py` solves them centrally:

1. **Working Directory & `renv` Auto-activation**:
   - `marimo` sets the Python kernel's working directory to `notebooks/`.
   - `r_bridge.py` changes `os.chdir(PROJECT_ROOT)` before `import rpy2.robjects as ro`.
   - When R initializes, it uses `getwd()` (`PROJECT_ROOT`), automatically finding `.Rprofile` and running `renv/activate.R` once.

2. **CFFI ABI Mode**:
   - `r_bridge.py` sets `os.environ["RPY2_CFFI_MODE"] = "ABI"` before importing `rpy2` to silence stderr CFFI warnings when the installed `rpy2` wheel was compiled against a different R build.

3. **Thread-Safe Conversion Rules (`ContextVar`)**:
   - `rpy2` stores type conversion rules in a Python `contextvars.ContextVar`.
   - Because marimo runs cells in separate execution contexts, calling `rpy2` without context wrapping causes `NotImplementedError: Conversion rules ... appear to be missing`.
   - `r_bridge.py` wraps all R operations (`r_eval`, `r_set`, `pl_to_r`, `r_to_pl`) inside `with _conv.context():`, keeping notebook cell code clean and error-free.

4. **Polars Data Transfers**:
   - Transfers data to/from R directly using `ro.DataFrame`, `ro.StrVector`, and `ro.FloatVector` without a `pandas` dependency or `pandas2ri` overhead.

---

## 3. R Package Management (`renv`)

- **Venv-like Isolation**: R packages install into `renv/library/` (gitignored). `renv.lock` tracks exact versions.
- **Custom Snapshot Filter**: Because R code lives inside Python strings in notebook files, standard `renv` dependency scanning ("implicit" mode) cannot discover imports. `renv/settings.json` sets `snapshot.type = "custom"`, and `.Rprofile` defines a filter that snapshots whatever packages are present in `renv/library/`.

---

## 4. AI Agent Pairing (`marimo-pair` skill)

- **Kernel as Source of Truth**: The active marimo kernel namespace holds the live session state. File edits on disk during a session are ignored or overwritten by marimo.
- **Scratchpad Execution**: `execute-code.sh` evaluates Python code in marimo's scratchpad namespace.
- **Code Mode (`cm`)**: To make persistent changes (create, edit, re-run, or delete cells), agents use `marimo._code_mode` inside the scratchpad.
