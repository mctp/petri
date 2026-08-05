# Architecture & Design Decisions

This document describes the design decisions behind the `petri` project template.

---

## 1. marimo Reactive Notebook Model

Unlike traditional Jupyter notebooks (`.ipynb` JSON files with out-of-order execution), marimo notebooks are **reactive, deterministic Python programs** saved as `.py` files.

- **DAG Dataflow**: marimo parses cell inputs/outputs and constructs a Directed Acyclic Graph (DAG). When a variable changes (e.g. via a slider or parent cell), marimo automatically re-executes dependent cells in topological order.
- **Single Definition Rule**: A public name can only be defined in one cell across the entire notebook. Use private variables (`_name`) for cell-internal temporaries.
- **Git-friendly**: Notebooks are valid Python scripts that diff, review, and format like standard code.

---

## 2. Python <-> R Interop (`petri/r_bridge.py`)

Embedding R inside Python using `rpy2` within a reactive, multi-threaded notebook runtime presents several edge cases. `petri/r_bridge.py` solves them centrally:

1. **Working Directory & `renv` Auto-activation**:
   - `marimo` sets the Python kernel's working directory to `notebooks/`.
   - `petri/r_bridge.py` changes `os.chdir(PROJECT_ROOT)` before `import rpy2.robjects as ro`.
   - When R initializes, it uses `getwd()` (`PROJECT_ROOT`), automatically finding `.Rprofile` and running `.renv/activate.R` once.

2. **CFFI ABI Mode**:
   - `petri/r_bridge.py` sets `os.environ["RPY2_CFFI_MODE"] = "ABI"` before importing `rpy2` to silence stderr CFFI warnings when the installed `rpy2` wheel was compiled against a different R build.

3. **Thread-Safe Conversion Rules (`ContextVar`)**:
   - `rpy2` stores type conversion rules in a Python `contextvars.ContextVar`.
   - Because marimo runs cells in separate execution contexts, calling `rpy2` without context wrapping causes `NotImplementedError: Conversion rules ... appear to be missing`.
   - `petri/r_bridge.py` wraps all R operations (`r_eval`, `r_set`, `pl_to_r`, `r_to_pl`) inside `with _conv.context():`, keeping notebook cell code clean and error-free.

4. **Polars Data Transfers**:
   - Transfers data to/from R directly using `ro.DataFrame`, `ro.StrVector`, and `ro.FloatVector` without a `pandas` dependency or `pandas2ri` overhead.

---

## 3. R Package Management (`renv`)

- **Venv-like Isolation**: R packages install into `.renv/library/` (gitignored), mirroring `.venv/`. `renv.lock` sits at the root beside `uv.lock` and tracks exact versions.
- **Custom Snapshot Filter**: Because R code lives inside Python strings in notebook files, standard `renv` dependency scanning ("implicit" mode) cannot discover imports. `.renv/settings.json` sets `snapshot.type = "custom"`, and `.Rprofile` defines a filter that snapshots whatever packages are present in `.renv/library/`.

---

## 4. AI Agent Pairing (`marimo-pair` skill)

- **Kernel as Source of Truth**: The active marimo kernel namespace holds the live session state. File edits on disk during a session are ignored or overwritten by marimo.
- **Scratchpad Execution**: `execute-code.sh` evaluates Python code in marimo's scratchpad namespace.
- **Code Mode (`cm`)**: To make persistent changes (create, edit, re-run, or delete cells), agents use `marimo._code_mode` inside the scratchpad.

The runtime has four levels: **server → session → kernel → scratchpad**. The
last two decide what an agent's work leaves behind. The scratchpad shares the
kernel namespace, but it is outside the notebook file and outside the dependency
graph.

```mermaid
graph LR
    Agent["pi / Claude Code"] -->|"execute-code.sh, cm"| Kernel["marimo kernel<br/>(source of truth)"]
    User["browser :2718"] --> Kernel
    Kernel --> Ext["data/external/"] --> Proc["scripts/"] --> Shared["data/shared/"] --> Pres["data/preserved/"]
```

Definitions, source citations, and the frozen-snapshot rules are in
[`petri/skills/marimo-pair/reference/execution-context.md`](../skills/marimo-pair/reference/execution-context.md),
with the skill that uses them.

---

## 5. Artifacts & Data Layers (`petri/provenance.py`)

A marimo notebook is reproducible by construction: the `.py` file is the
program, and git versions it. That guarantee does not cover what the notebook
writes. `petri/provenance.py` adds identity, provenance, and integrity for the
output.

### Two kinds of artifact

An artifact is any file petri writes with a manifest. There are two kinds,
separated by who reads them.

| Kind | Location | Read by | On mismatch |
|---|---|---|---|
| shared | `data/shared/` | other notebooks | `load_shared()` raises |
| preserved | `data/preserved/<notebook>/<name>/` | people | `make check` reports |

A shared table has downstream consumers. If it is edited by hand or is out of
date, it must fail at read time, before it reaches a figure. A preserved
artifact has no consumers, so its check only reports whether it still matches
the code and inputs recorded for it.

No notebook reads another notebook's preserved artifact. A result that other
code needs is an interface, not a deliverable, and goes to `data/shared/` through
`save_shared()`. There is no `load_preserved()`.

### Naming

Each data directory is named for the function that writes it:
`load_external()` → `data/external/`, `save_shared()` → `data/shared/`,
`preserve_*()` → `data/preserved/`. "Artifact" covers both kinds, so no directory uses that name.

### Boundary

A notebook reads `data/shared/`. A producer notebook also reads `data/external/`.
Petri versions `data/shared/`, so every notebook input is verifiable.

`data/external/` is outside the boundary. Petri does not own those files and does not
preserve them. It records `(path, size, sha256)` and reports a change as a
warning, because the file can be re-supplied from outside without petri.

Petri therefore guarantees reproducibility from `data/shared/` onward. External
inputs are recorded, not guaranteed.

### Identity

A preserved bundle is addressed by `<notebook stem>/<name>`. The runtime context
supplies the notebook. The name is an argument, because the marimo kernel does
not expose a cell's own name at runtime. It exposes the notebook path and an
ephemeral cell id such as `pmun`. Cell names live in the session document.

A rename therefore leaves the bundle under the old name. `check()` reads the
notebook with marimo's `load_app()` and confirms that a cell of that name exists
and that its code hash matches the manifest. Renaming, deleting, or editing a
producing cell is a `check` error.

Cell code is hashed after whitespace at the edges is removed. The kernel reports
`cell.code` with a trailing newline; the on-disk form has none. Hashing the raw
text marks every artifact stale as soon as it is written.

`check()` also walks the other direction, from the files to the manifests. An
artifact is a file plus a manifest, so a file that no manifest records — a table
copied in by hand, a figure left by an interrupted run — is an error. Verifying
manifests alone let such a tree report clean.

### Producer notebooks

A notebook that writes to `data/shared/` is a producer. A numeric filename prefix
marks it: `notebooks/00_ingest.py`, `10_normalize.py`. `make shared` runs
`notebooks/[0-9]*.py` in sorted order, then verifies.

There is no DAG engine. The sort order is the dependency graph. This is
sufficient until producers depend on each other in more than one direction.
Transformations are already plain functions in `scripts/`, so a move to
Snakemake would not require rewriting them.

Producers run headless through the `app.run()` call at the end of each marimo
notebook. `make` exports `PYTHONPATH` for this: `python notebooks/00_x.py` puts
`notebooks/` on `sys.path`, not the repo root, and marimo's
`runtime.pythonpath` applies only to the editor.

Two runtime settings support the same notebooks in the editor.
`auto_instantiate = false` prevents a pipeline run when you open a notebook.
`auto_reload = "lazy"` marks importing cells stale when you edit a module in
`scripts/`, instead of keeping the kernel on the previous version.

### Code dependencies

Transformations live in `scripts/`, not in cells. Functions there are
testable without a kernel, and a thin cell does not re-run an expensive chain
when you edit the transformation. (`on_cell_change` is `autorun`.)

The cell hash cannot see those functions. Rewrite one, re-run, and no recorded
value changes. Each manifest therefore also carries `code_deps`: the hash of
every project-local module the cell imports, resolved through `sys.modules` at
write time. Editing `scripts/measurements.py` marks the artifacts that import
it stale and leaves the rest unchanged.

`code_deps` covers modules under `PROJECT_ROOT`, except `petri/`, `.venv/`, and
site-packages. Hashing the template would mark every artifact stale on a
template update. Dependency versions belong in `tool` and the lockfiles.

Resolution takes both readings of `from pkg import name`, since the name may be
a submodule rather than an attribute, and it hashes each ancestor package as
well, because a package `__init__` runs when a submodule is imported. What it
does not cover is a module imported by another module: `code_deps` records what
the cell imports, not the whole transitive closure.

### Manifests

Each artifact has one JSON manifest: `data/shared/<name>.manifest.json`, or
`manifest.json` inside a preserved bundle. `manifest_version` is checked on
read; a manifest from a newer petri is an error, not a silent misread. Git ignores the bytes and tracks the
manifests, so `git log` on a manifest gives the artifact's version history. A
preserved bundle is tracked in full, because the source data it carries holds the
plotted rows, not the source matrix.

Manifests record inputs by path and replace a previous entry for the same path.
An input's fingerprint changes with its content, so a dedup by equality would
leave two entries for one file and a claim of provenance from a version that no
longer exists.

Every field a manifest records about a file comes from that file's content: a
size and a SHA-256, for outputs and for inputs alike. Nothing records an mtime.
An earlier version did, as a fast path that let verification skip the hash, and
because `data/shared/` ships its manifests without its tables, every collaborator's
first `make shared` rewrote every manifest with a new mtime and identical hashes.
A record that changes when its subject does not is not a record.

An input under `data/shared/` is pinned to the version its manifest published, not to
the bytes on disk; that table's own manifest is what verifies those. An input
under `data/external/` is hashed like any other, but a change there is a warning
rather than an error, because those files are unowned and can be re-supplied
without petri.

### Writes

Writes are idempotent. Petri does not rewrite unchanged content. A preserved
cell re-runs whenever its dependencies change, and rewriting identical bytes
would produce a git diff on every iteration.

matplotlib stamps a timestamp into every format, so petri strips it: `Software`
for PNG, `CreationDate` for PDF, `Date` for SVG. A format with no known key is
rejected, because it would write new bytes on every run and never verify twice.
Passing a `Path` instead of a figure copies that file byte for byte, so an
external renderer's timestamp survives — R's `pdf()` writes a `CreationDate` and
a `ModDate` — and each run rewrites the file. Prefer PNG or SVG from R.

Names are validated on the way in. A shared table name becomes a filename, so it
must be one flat name. A preserved bundle name must be a Python identifier,
because `check()` looks it up among the notebook's cell names and a name that is
not an identifier could never match. A filename inside a bundle must be flat too,
since only the basename is recorded.

Payloads are serialized, then identity and inputs resolve, then petri writes.
Order carries weight here: opening a bundle empties it when the cell's code has
changed, so a payload rejected after that point would destroy the deliverable it
was about to replace.

Verification is size, then hash, on every file. There is no fast path to skip.

### CSV

`data/shared/` and `preserve_table()` write CSV, which agents and people can read
with `grep`. CSV carries no dtypes, so petri records the Polars schema in the
manifest and applies it through `schema_overrides` on read.

That record holds a dtype by name, so `save_shared()` accepts only columns whose
dtype is fully described by its name. A time zone, a time unit other than the
default, a decimal precision and an enum's categories are all lost, and nested
data does not fit in CSV at all. Such a column is rejected at publication, not in
the notebook that reads it back.

Floats use the Polars defaults. `float_precision` writes `1e-300` as
`0.000000000000`, which destroys p-values. Petri pins only the ambiguous
settings: line terminator, BOM, header, and ISO-8601 dates.
