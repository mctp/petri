# R environment (renv)

`renv` is to R what `uv`/`.venv` is to Python: a project-local package library
plus a lockfile. This project is initialised as a bare renv project — the
library starts empty, and you add packages as you need them.

| Python                     | R                                   |
| -------------------------- | ----------------------------------- |
| `.venv/`                   | `renv/library/`                     |
| `uv.lock`                  | `renv.lock`                         |
| `uv sync`                  | `renv::restore()` / `make r-restore`|
| `uv add pkg`               | `renv::install("pkg")` + snapshot   |
| `pyproject.toml`           | *(none — see "no DESCRIPTION")*     |

Committed: `.Rprofile`, `renv.lock`, `renv/activate.R`, `renv/settings.json`.
Ignored: `renv/library/`, `renv/sandbox/`, `renv/staging/` (renv writes its own
`renv/.gitignore`).

## Daily use

```bash
make r-restore                       # rebuild renv/library from renv.lock
make r-install PKG="ggplot2 ggpubr"  # install into the project library + snapshot
make r-snapshot                      # record the current library into renv.lock
make r-status                        # check library vs. lockfile
```

Currently locked: `ggplot2`, `ggpubr` and their dependencies (77 packages).

Inside an R session started at the project root, `.Rprofile` activates renv
automatically, so `renv::install()` / `renv::snapshot()` work directly.

## No DESCRIPTION file

renv's default snapshot mode ("implicit") scans `.R`/`.Rmd` files for
`library(...)` calls to decide what to record. In this project R code lives
inside Python strings in marimo notebooks, so nothing is discoverable that way,
and the alternative ("explicit") mode requires maintaining a `DESCRIPTION`
package file.

Instead the project uses renv's **custom** snapshot type: the dependency list
*is* the project library, the way `.venv` is the source of truth for Python.
`renv/settings.json` sets `snapshot.type = "custom"` and `.Rprofile` registers
the filter:

```r
options(renv.snapshot.filter = function(project) {
  rownames(installed.packages(lib.loc = renv::paths$library(project = project)))
})
```

This must be set **before** `source("renv/activate.R")`, because activate.R
checks project sync during startup and errors out if the filter is missing.

Both `renv::snapshot()` and `renv::status()` use the filter, so status reports
a clean project instead of flagging all 77 packages as "recorded but not used".

Note that `renv::snapshot(type = "all")` is *not* equivalent: it walks every
library path, sweeping the base and recommended packages out of renv's sandbox
(MASS, survival, Matrix, ...) into the lockfile.

## Using the project library from a notebook

`r_bridge.py` handles initializing R from the project root automatically when
imported:

```python
from r_bridge import pl_to_r, r_eval, r_set, r_to_pl
```

When `r_bridge` is imported, it sets the working directory to `PROJECT_ROOT`
before importing `rpy2`. R initializes in `PROJECT_ROOT`, automatically runs
`.Rprofile`, activates `renv/library/`, and registers the custom snapshot filter
once for the entire session.

Notebook cells call `r_eval()`, `pl_to_r()`, `r_to_pl()` without any in-cell
R environment setup or conversion boilerplate.

Alternative, if you prefer not to touch notebook code — export the library path
before starting marimo (keeps the system site-library visible, so it isolates
less):

```bash
export R_LIBS_USER="$(Rscript -e 'cat(renv::paths$library())')"
make nb
```

### Do not `source("renv/activate.R")` from a notebook

It resolves paths relative to the *current working directory*. Called with the
kernel's cwd at `notebooks/`, it silently bootstraps a second renv project in
`notebooks/renv/` and then hangs trying to download renv in a non-interactive
embedded R session. Use `renv::load("<project root>")` instead.

## Installing R packages

```bash
make r-install PKG=ggplot2                 # single package + snapshot
Rscript -e 'renv::install(c("dplyr", "arrow"))' && make r-snapshot
Rscript -e 'renv::install("tidyverse/dplyr")'   # GitHub
```

Reproduce the environment elsewhere:

```bash
git clone <repo> && cd <repo>
make r-restore
```

## Troubleshooting

- **`renv` not found**: `Rscript -e 'install.packages("renv", repos="https://cloud.r-project.org")'`
- **Package installed but not visible in a notebook**: the kernel loaded R
  before `renv::load()`, or the cell never ran. Re-run the activation cell and
  check `ro.r(".libPaths()")`.
- **Compilation failures on macOS**: see [rpy2.md](rpy2.md) — the same
  gcc/gfortran toolchain issues affect R source packages.
- **Lockfile churn**: `make r-snapshot` records the library exactly; if a
  teammate's diff removes packages, they had a smaller library, not a bug —
  run `make r-restore` before snapshotting.
