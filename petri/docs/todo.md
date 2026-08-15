# TODO

Two open questions, unrelated to each other except that both are about things
that are currently held together by configuration rather than by code.

---

# 1. Import resolution without `PYTHONPATH`

## Background

Running a notebook from the CLI (`python notebooks/<name>.py`) puts
`notebooks/` on `sys.path[0]`, not the repo root, so both of these fail:

```python
import petri  # petri/ is at the root
from scripts.measurements import rank_by_significance  # scripts/ is too
```

Three separate settings paper over it today, each for one entry point:

1. `export PYTHONPATH := $(CURDIR)` in the `Makefile` — covers `make run` and `make test`
2. `[tool.marimo.runtime] pythonpath = ["."]` — covers the editor kernel
3. `[tool.pytest.ini_options] pythonpath = ["."]` — covers a bare `uv run pytest`

Nothing covers a bare `uv run python notebooks/<name>.py`, an IDE test runner, or
a debugger launch. That is the gap.

**Both imports have to keep working.** `petri/examples/notebooks/full_example.py`
imports from `scripts/` in three cells, and that is the template's own worked
example — an option that fixes `import petri` alone fixes half the problem and
leaves the more surprising half.

## Option A: editable install via a build backend

Make `petri` an installed package that `uv` keeps in sync.

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["petri"]
```

…then drop `package = false` from `[tool.uv]` and `uv sync`.

- **Pros**: the standard mechanism; `uv` installs and re-syncs it with no help
  from us.
- **Cons**: **does not solve `scripts/`.** `scripts/` is a sibling of `petri/` at
  the root, not a subpackage, and it cannot be added to `packages = [...]`: it
  ships empty and gitignored, so there is nothing to build, and its contents are
  the user's rather than the template's. `import petri` would resolve everywhere
  and `from scripts... import ...` would still need the root on `sys.path` —
  leaving the same three settings in place for the one import they still cover.

## Option B: a `.pth` file in `.venv`, written by `make setup`

```makefile
setup: ## Create .venv and R library, install git hooks
	uv sync
	uv run python -c "import site, pathlib; (pathlib.Path(site.getsitepackages()[0]) / 'petri.pth').write_text('$(CURDIR)\n')"
	uv run pre-commit install
	$(MAKE) r-restore
```

`site` reads every `.pth` in `site-packages` at startup and appends the paths it
finds to `sys.path`.

- **Pros**: puts the **repo root** on the path, so `petri`, `scripts` and
  anything else added at the root all resolve, from any interpreter that uses
  this `.venv` — including a debugger and an IDE test runner. Keeps
  `package = false` and needs no build backend. This is the option that actually
  closes the gap.
- **Cons**: it is a generated file, so a `.venv` rebuilt by a bare `uv sync`
  loses it until `make setup` runs again — and nothing announces that, the
  imports simply start failing the old way. Worth having `make setup` be
  idempotent and cheap so re-running it is the obvious first move.

**Leaning: B**, on the strength of `scripts/`. If A is taken anyway for the
packaging benefits, it is an addition to the `PYTHONPATH` settings rather than a
replacement for them, and the todo should say so.

---

# 2. Formatting-invariant code hashes for manifests

## Background

`petri.provenance._code_hash(code)` is a SHA-256 over `code.strip()`. The write
side hashes what the kernel holds (`ctx.graph.cells[cell_id].code`); `check()`
hashes what it reads back from the saved `.py`. Anything that rewrites a cell's
text on disk without re-running the cell therefore turns every manifest that cell
produced into a `cell 'x' changed since this was written` error.

**How live this is, as of now:** not very, and deliberately so.

- marimo does not reformat on save — `format_on_save = false`.
- ruff is excluded from `notebooks/` for writes: `[tool.ruff.format] exclude` and
  the `--extend-exclude` on `make fmt`'s `ruff check --fix`. That exclusion is
  there for this reason and because the kernel owns those files.

So the drift source is currently fenced off rather than absent. The fence is two
config lines, and this section is what to do if it ever comes down — or if a
future marimo starts normalising cell text on save.

## Option C: hash a canonical AST

```python
def _code_hash(code: str) -> str:
    """Hash a canonical AST representation of cell code, invariant to formatting."""
    try:
        canonical = ast.unparse(ast.parse(code.strip()))
    except SyntaxError:
        canonical = code.strip()
    return _sha256_bytes(canonical.encode("utf-8"))
```

- **Pros**: invariant to whitespace, blank lines, trailing commas and line
  wrapping, while staying sensitive to every real change.
- **Cons, and they are not nothing:**
  - **`ast.unparse` discards comments.** Editing only a comment would stop
    invalidating the manifest. That may well be the behaviour you want — a
    comment does not change the output — but it narrows what the manifest
    asserts, from "this text produced it" to "this code produced it". Decide it
    on purpose rather than inherit it.
  - **`ast.unparse` output is not stable across CPython releases.** Its
    formatting has changed repeatedly (parenthesisation, f-string
    reconstruction after PEP 701). A manifest hashed under 3.13 can fail under
    3.14 on byte-identical source. For a tool whose promise is that a year-old
    artifact still verifies, that swaps a formatting-drift failure for an
    interpreter-upgrade failure — and the second is worse, because it fires on
    every artifact in the project at once rather than on the cell someone
    touched.

  If C is taken, record `code_hash_scheme` and the Python version in the
  manifest, and have `check()` **warn** rather than error when either differs
  from what it is running. Otherwise the first `uv python upgrade` reports the
  whole project as drifted.

## Option D: normalise with the formatter that causes the drift

Run the same normaliser on both sides — `ruff format` over the snippet at write
time and in `check()`. ruff is already a pinned dependency, and the drift being
defended against is ruff's own.

- **Pros**: targets the actual mechanism; no AST semantics change; comments
  survive; the pin in `uv.lock` is what makes it reproducible, and it is a
  version this project already controls.
- **Cons**: a subprocess per hash unless something in-process is used; and it
  moves the reproducibility question onto the ruff pin, which at least is
  explicit and already reviewed.

**Leaning: neither, while the fence holds.** If it stops holding, D is the
narrower change.
