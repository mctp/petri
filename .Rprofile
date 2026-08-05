# R reads this file from the startup working directory, so it is one of the few
# things that cannot leave the project root.
#
# The R side mirrors the Python side: `.renv/` is the package library, hidden
# beside `.venv/`, and `renv.lock` sits at the root beside `uv.lock`. renv looks
# for its directory at `renv/` by default, so RENV_PATHS_RENV is what points it
# at the dot-name; it is read by .renv/activate.R and resolved relative to the
# project. The lockfile needs no variable — root is already renv's default.
Sys.setenv(RENV_PATHS_RENV = ".renv")

# This project has no .R scripts and no DESCRIPTION: R code lives inside Python
# strings in marimo notebooks, so renv cannot discover dependencies by scanning.
# Treat the project library itself as the dependency list, the way `.venv` is
# the source of truth for Python. Used by both renv::snapshot() and
# renv::status() (.renv/settings.json sets snapshot.type = "custom").
#
# Must be set before activate.R, which checks project sync on startup.
options(renv.snapshot.filter = function(project) {
  if (!dir.exists(renv::paths$library(project = project))) {
    return(character())
  }
  rownames(installed.packages(lib.loc = renv::paths$library(project = project)))
})

source(".renv/activate.R")
