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
make r-restore              # rebuild renv/library from renv.lock
make r-install PKG=ggplot2  # install into the project library, then snapshot
make r-snapshot             # record the current library into renv.lock
make r-status               # check library vs. lockfile
```

Inside an R session started at the project root, `.Rprofile` activates renv
automatically, so `renv::install()` / `renv::snapshot()` work directly.

## No DESCRIPTION file

renv's default snapshot mode ("implicit") scans `.R`/`.Rmd` files for
`library(...)` calls to decide what to record. In this project R code lives
inside Python strings in marimo notebooks, so nothing is discoverable that way,
and the alternative ("explicit") mode requires maintaining a `DESCRIPTION`
package file.

Instead, snapshots record **whatever is installed in the project library** —
the venv-like behaviour:

```bash
Rscript -e 'renv::snapshot(packages = rownames(installed.packages(lib.loc = renv::paths$library())), prompt = FALSE)'
```

That is exactly what `make r-snapshot` runs. Note that plain
`renv::snapshot(type = "all")` is *not* equivalent: it also sweeps in the base
and recommended packages from renv's sandbox (MASS, survival, Matrix, ...),
which you do not want in the lockfile.

## Using the project library from a notebook

marimo runs the kernel with its working directory set to the notebook's
directory (`notebooks/`), not the project root — so R started by `rpy2` does
**not** see the root `.Rprofile` and defaults to your system library.

Activate the project library explicitly in a cell:

```python
import rpy2.robjects as ro

ro.r(f'renv::load("{PROJECT_ROOT}")')
list(ro.r(".libPaths()"))
# ['/…/marimo-pi/renv/library/macos/R-4.5/aarch64-apple-darwin24.6.0',
#  '/…/renv/sandbox/…']
```

This gives full isolation: the project library plus renv's sandbox of base and
recommended packages, with your system site-library excluded. It requires
`renv` to be installed in the system library (`install.packages("renv")`).

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
