# Installing rpy2 correctly

`rpy2` embeds a real R interpreter in the Python process. It is listed as a
normal dependency, so `uv sync` installs it — but whether it works *well*
depends on your machine's R installation. This project deliberately ships **no
rpy2 workarounds**: no pinned build mode, no environment overrides. Configure R
once on your machine, the way you want it.

## 1. Install R first

```bash
# macOS
brew install r
# or the official build: https://cran.r-project.org/bin/macosx/

# Debian/Ubuntu
sudo apt install r-base r-base-dev

# conda/mamba
mamba install -c conda-forge r-base
```

Verify that R is on `PATH` and that rpy2 will find it:

```bash
R --version
R RHOME          # what rpy2 uses when R_HOME is unset
```

If R is installed somewhere unusual, export `R_HOME`:

```bash
export R_HOME=$(R RHOME)
```

## 2. Check what rpy2 sees

```bash
uv run python -m rpy2.situation
```

Two lines matter:

- `Loaded: CFFI_MODE.API` — rpy2's C extension is linked against R. Fastest,
  most featureful.
- `Loaded: CFFI_MODE.ABI` — rpy2 loads `libR` dynamically via `cffi`'s ABI
  interface. Works fine, marginally slower, and some callbacks behave
  differently.

Smoke test:

```bash
uv run python -c "import rpy2.robjects as ro; print(ro.r('R.version.string')[0])"
```

## 3. Wheels vs. source build

The published `rpy2-rinterface` wheels (rpy2 3.6+ splits into `rpy2`,
`rpy2-rinterface`, `rpy2-robjects`) are linked against the R the maintainers
built with — on macOS, framework R under `/Library/Frameworks/R.framework/`.
If your R lives elsewhere (e.g. Homebrew), the API extension fails to `dlopen`
and rpy2 falls back to ABI mode after printing a loud `Error importing in API
mode: ImportError(...)` on import.

Three ways to deal with it, in increasing order of effort:

**a. Accept ABI mode, silence the message**

```bash
export RPY2_CFFI_MODE=ABI      # e.g. in your shell profile, or .env
```

**b. Install framework R** so the wheel's expected path exists (macOS, CRAN
build).

**c. Build rpy2 against your own R.** The compiled extension is in
`rpy2-rinterface`, so that is the package to build from source:

```bash
uv pip install --no-binary rpy2-rinterface --reinstall-package rpy2-rinterface rpy2
```

To make this permanent for your clone (a local choice — keep it out of shared
commits), put it in `.venv`-adjacent local config rather than `pyproject.toml`,
or add to your own fork:

```toml
[tool.uv]
no-binary-package = ["rpy2-rinterface"]
```

## 4. Troubleshooting source builds

### `ld: library 'emutls_w' not found` (macOS + Homebrew R)

rpy2's build takes its link flags from `R CMD config --ldflags`, which comes
from `$(R RHOME)/etc/Makeconf`. Homebrew's R bottle hardcodes the gcc version
directory it was built with, e.g.

```
-L/opt/homebrew/opt/gcc/lib/gcc/current/gcc/aarch64-apple-darwin24/15 -lemutls_w -lheapt_w ...
```

After `brew upgrade gcc`, that directory no longer exists and the link fails.
A `~/.R/Makevars` `FLIBS` override does *not* help: `--ldflags` is generated
from `Makeconf`, which `Makevars` cannot override.

Check the mismatch:

```bash
R CMD config --ldflags | tr ' ' '\n' | grep darwin
ls -d /opt/homebrew/opt/gcc/lib/gcc/current/gcc/*/
```

Fix by pointing `Makeconf` at the gcc you actually have (adjust versions):

```bash
MK="$(R RHOME)/etc/Makeconf"
sudo cp "$MK" "$MK.bak"
sudo sed -i '' 's|darwin24/15|darwin24/16|g' "$MK"   # GNU sed: drop the ''
```

This is machine state, not project state: it is reverted by `brew upgrade r`
and re-broken by `brew upgrade gcc`. If you maintain a dotfiles installer, put
the rewrite there. Otherwise prefer option (a) or (b) above.

### `R_HOME` not found / wrong R picked up

rpy2 resolves R via `R_HOME`, then `R` on `PATH`. With multiple R installs
(Homebrew, CRAN framework, conda), set `R_HOME` explicitly before starting
marimo, since the notebook kernel inherits the environment of the process that
launched it.

### R packages are missing inside notebooks

rpy2 uses your user/site R libraries. Install R packages with R itself:

```bash
Rscript -e 'install.packages("ggplot2", repos="https://cloud.r-project.org")'
```

## 5. Using rpy2 in a marimo notebook via `petri/r_bridge.py`

This template provides `petri/r_bridge.py` to simplify `rpy2` usage in marimo notebooks:

```python
import polars as pl
from petri.r_bridge import (
    np_to_r,
    pl_to_r,
    py_to_r,
    r_eval,
    r_png,
    r_to_np,
    r_to_pl,
    r_to_py,
)

# Python -> R (Polars to R data.frame without pandas)
pl_to_r(df, "r_df")

# Python -> R (native dict/list to R list)
py_to_r({"name": "alice", "scores": [90.5, 85.0], "meta": {"id": 7}}, "config")

# Python -> R (NumPy array to R matrix)
np_to_r(np.arange(6.0).reshape(2, 3), "mat")

# Evaluate R code in the permanent R session
r_eval("""
suppressPackageStartupMessages(library(ggpubr))
p <- ggboxplot(r_df, x = "group", y = "value")
ggsave("data/cache/plot.png", p)
""")

# R graphics -> PNG bytes, with no file on disk
mo.image(r_png("print(p)", width=500, height=400), width=500)

# R -> Python (R data.frame to Polars)
summary_df = r_to_pl("summary_df")

# R -> Python (R matrix or vector to NumPy ndarray)
mat_scaled = r_to_np("mat")

# R -> Python (R named list to native dict; recursion handles nesting)
r_eval("cfg <- list(name = 'bob', scores = c(1.5, 2.5))")
cfg = r_to_py("cfg")
```

### The six converters

Three pairs, each one the other's inverse. Which function you call is decided by
the object's shape, so every call's return type is predictable:

| Python | push | pull | R |
|---|---|---|---|
| `dict` / `list` / scalar | `py_to_r(obj, name)` | `r_to_py(name)` | named list, vector, scalar |
| NumPy `ndarray` | `np_to_r(arr, name)` | `r_to_np(name)` | matrix, array, vector |
| Polars `DataFrame` | `pl_to_r(df, name)` | `r_to_pl(name)` | `data.frame` |

Pass an object to the wrong one and it raises, naming the right one — nothing
reshapes itself silently. Missing values cross in both directions: `None`
becomes the typed R `NA`, and `NA` comes back as `None`.

The docstrings in `petri/r_bridge.py` are the contract, down to the corner
cases: which dtypes `pl_to_r` carries, what a partly named R list becomes, why an
`int` sometimes lands in R as a double.

Key features of `petri/r_bridge.py`:
- Sets working directory to `PROJECT_ROOT` before importing `rpy2`, so `.Rprofile` and `.renv/library/` load once automatically at startup.
- Wraps all R operations in `_conv.context()` so `rpy2` conversion rules work across marimo's multi-threaded cell execution contexts.
- Transfers data directly between Polars and R without `pandas` or `pandas2ri`.

Reach for `r_png()` rather than importing `rpy2.robjects.lib.grdevices` in a cell.
That import calls `importr("grDevices")` as a side effect, so it needs the
conversion rules to be in scope and fails with
`NotImplementedError: Conversion rules ... appear to be missing` when a cell runs
it directly. Rendering through `ggsave()` inside `r_eval()` and reading the file
back is still fine — that path never touches rpy2's converters.

Notes for notebook use:

- `r_to_pl(name)`, `r_to_np(name)`, and `r_to_py(name)` take the NAME of an R
  variable in the global environment, not an expression —
  `r_to_pl("as.data.frame(mat)")` raises `KeyError`. Assign the object a name
  in R first.
- Two R shapes have no Python counterpart and raise rather than arrive wrong: a
  date-time (`POSIXct`, `difftime`) carries a zone or unit the bridge will not
  invent, and `NA` in an integer, logical or character array has no NumPy
  equivalent. Convert in R first — `format()`, `as.numeric()` — or pull the
  object with `r_to_py`.
- `r_set(name, value)` is a legacy alias for `py_to_r` with the arguments the
  other way round. It stays because notebooks call it; prefer `py_to_r`.
- Import rpy2 in one cell and let other cells reference its names; R is a single
  global interpreter, so treat it as shared mutable state.
- Each marimo session's kernel is its own Python process, and rpy2 initializes
  R exactly once per process — so each session has one embedded R. R state
  (globals, loaded packages) does **not** cross sessions, and it resets on a
  kernel restart.
- R's global environment is *not* part of marimo's dataflow graph. If a cell
  mutates `ro.globalenv`, dependent cells will not re-run automatically. Keep R
  work inside one cell, or pass values back into Python names.
- Long-running R calls block the kernel; the notebook UI will show the cell as
  running.
- If rpy2 prints the API-mode import error inside a notebook, start marimo with
  `RPY2_CFFI_MODE=ABI` exported (see option (a)).
