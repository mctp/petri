# R environment (renv)

`renv` is to R what `uv`/`.venv` is to Python: a project-local package library
plus a lockfile. This project is initialised as a bare renv project — the
library starts empty, and you add packages as you need them.

| Python                     | R                                   |
| -------------------------- | ----------------------------------- |
| `.venv/`                   | `.renv/library/`                    |
| `uv.lock`                  | `renv.lock`                         |
| `uv sync`                  | `renv::restore()` / `make r-restore`|
| `uv add pkg`               | `renv::install("pkg")` + snapshot   |
| `pyproject.toml`           | *(none — see "no DESCRIPTION")*     |

The layout mirrors the Python side exactly, which is why the table above lines
up: the package library is hidden at `.renv/` next to `.venv/`, and the lockfile
sits at the project root next to `uv.lock`. `uv.lock` cannot be relocated at
all — uv offers no flag or environment variable for it — so keeping `renv.lock`
beside it is the symmetric choice rather than an arbitrary one.

renv looks for its directory at `renv/` by default, so `.Rprofile` sets
`RENV_PATHS_RENV = ".renv"` to point it at the dot-name. The lockfile needs no
variable: the project root is already renv's default. `.Rprofile` has to stay at
the root because R sources it from the startup working directory.

Committed: `.Rprofile`, `renv.lock`, `.renv/activate.R`, `.renv/settings.json`.
Ignored: `.renv/library/`, `.renv/sandbox/`, `.renv/staging/` (renv writes its
own `.renv/.gitignore`).

## Daily use

```bash
make r-restore                       # rebuild .renv/library from renv.lock
make r-install PKG="ggplot2 ggpubr"  # install into the project library + snapshot
make r-snapshot                      # record the current library into the lockfile
make r-status                        # check library vs. lockfile
```

Currently locked: `ggplot2`, `ggpubr`, `limma`, `BiocManager`, and their dependencies (81 packages).

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
`.renv/settings.json` sets `snapshot.type = "custom"` and `.Rprofile` registers
the filter:

```r
options(renv.snapshot.filter = function(project) {
  rownames(installed.packages(lib.loc = renv::paths$library(project = project)))
})
```

This must be set **before** `source(".renv/activate.R")`, because activate.R
checks project sync during startup and errors out if the filter is missing.

Both `renv::snapshot()` and `renv::status()` use the filter, so status reports
a clean project instead of flagging all 77 packages as "recorded but not used".

Note that `renv::snapshot(type = "all")` is *not* equivalent: it walks every
library path, sweeping the base and recommended packages out of renv's sandbox
(MASS, survival, Matrix, ...) into the lockfile.

## Using the project library from a notebook

`petri/r_bridge.py` handles initializing R from the project root automatically when
imported:

```python
from petri.r_bridge import pl_to_r, r_eval, r_png, r_set, r_to_pl
```

When `r_bridge` is imported, it sets the working directory to `PROJECT_ROOT`
before importing `rpy2`. R initializes in `PROJECT_ROOT`, automatically runs
`.Rprofile`, activates `.renv/library/`, and registers the custom snapshot filter
once for the entire session.

Notebook cells call `r_eval()`, `pl_to_r()`, `r_png()`, `r_to_pl()` without any in-cell
R environment setup or conversion boilerplate.

Alternative, if you prefer not to touch notebook code — export the library path
before starting marimo (keeps the system site-library visible, so it isolates
less):

```bash
export R_LIBS_USER="$(Rscript -e 'cat(renv::paths$library())')"
make nb
```

### Do not `source(".renv/activate.R")` from a notebook

It resolves paths relative to the *current working directory*. Called with the
kernel's cwd at `notebooks/`, it silently bootstraps a second renv project in
`notebooks/renv/` and then hangs trying to download renv in a non-interactive
embedded R session. Use `renv::load("<project root>")` instead.

## Installing R packages

`BiocManager` is included in `renv.lock` and available by default in the project library, enabling seamless installation of both CRAN and Bioconductor packages.

```bash
make r-install PKG=ggplot2                 # CRAN package + snapshot
make r-install PKG="bioc::DESeq2"          # Bioconductor package + snapshot
Rscript -e 'renv::install(c("dplyr", "arrow"))' && make r-snapshot
Rscript -e 'renv::install("bioc::limma")'      # Bioconductor via renv
Rscript -e 'BiocManager::install("DESeq2")' && make r-snapshot # Direct BiocManager call
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
- **`lazy loading failed` during restore**, naming a package that the lockfile
  does list — e.g. `gridExtra` dying on `there is no package called 'rlang'`.
  Run `make r-restore` a second time: the first pass leaves the missing
  dependency installed, so the retry succeeds.

  The cause is worth knowing before reaching for a bigger fix. `renv::restore()`
  installs in topological waves, but it computes them over only the packages it
  must download or build; a package already in the renv cache is linked into the
  library up front and left out of the graph. Edges are built with
  `intersect(deps, packages)`, so dropping that node also drops the constraints
  it carried. With `gtable` cached and `rlang` not, `gridExtra` loses its
  inherited dependency on `rlang` and lands in the same wave — and since each
  wave installs in sorted order, `gridExtra` is attempted first, deterministically.
  Building it from source loads `gtable`, which needs `rlang`, which is not
  installed yet.

  This needs a partly-warm cache to trigger, which is why a plain restore is
  fine almost always. If it turns out to bite people regularly, the fix belongs
  upstream in renv — cached packages should stay in the graph as already-satisfied
  nodes — not in a local reimplementation of renv's installer.
