# This project has no .R scripts and no DESCRIPTION: R code lives inside Python
# strings in marimo notebooks, so renv cannot discover dependencies by scanning.
# Treat the project library itself as the dependency list, the way `.venv` is
# the source of truth for Python. Used by both renv::snapshot() and
# renv::status() (renv/settings.json sets snapshot.type = "custom").
#
# Must be set before renv/activate.R, which checks project sync on startup.
options(renv.snapshot.filter = function(project) {
  lib <- file.path(project, "renv", "library")
  if (!dir.exists(lib)) {
    return(character())
  }
  rownames(installed.packages(lib.loc = renv::paths$library(project = project)))
})

source("renv/activate.R")
