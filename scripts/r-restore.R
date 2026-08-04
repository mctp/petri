#!/usr/bin/env Rscript

# Restore renv.lock one dependency wave at a time.
#
# `renv::restore()` on its own is not safe here. It starts installing a package
# as soon as that package's *direct* lockfile dependencies are ready, and it
# counts a dependency linked from the renv cache as ready before the install
# loop even begins. Those two rules combine badly. When a direct dependency
# comes from the cache but something *it* needs still has to be built, the
# dependent's build can start first — and building from source loads the direct
# dependency's namespace, which needs the whole transitive closure. The build
# then dies on a package renv is still installing in another worker:
#
#   ** byte-compile and prepare package for lazy loading
#   Error in loadNamespace(i, ...) : there is no package called 'rlang'
#   ERROR: lazy loading failed for package 'gridExtra'
#
# (gridExtra imports gtable, gtable imports rlang. With gtable cached and rlang
# not, gridExtra is built before rlang is installed. Its dependents — ggpubr,
# progeny — are then reported as failed without ever being attempted.)
#
# Restoring in topological waves removes the ordering entirely: every package in
# a wave has its full transitive closure installed before the wave starts. renv
# still parallelizes downloads and builds within each wave.

lockfile <- commandArgs(TRUE)[[1]]
records <- renv::lockfile_read(lockfile)$Packages

base <- rownames(installed.packages(priority = "base"))

# A lockfile written by renv carries `Requirements`; one written by hand or by
# another tool carries the DESCRIPTION fields instead. Read both, drop version
# constraints ("rlang (>= 1.1.7)"), and keep only edges inside the lockfile.
requirements <- function(record) {
  fields <- c("Requirements", "Depends", "Imports", "LinkingTo")
  declared <- lapply(fields, function(field) record[[field]])
  # A leaf like BH declares none of the four, which unlists to NULL.
  declared <- as.character(unlist(declared, use.names = FALSE))
  if (length(declared) == 0L) {
    return(character())
  }
  named <- trimws(sub("\\(.*", "", unlist(strsplit(declared, ",", fixed = TRUE))))
  setdiff(intersect(unique(named), names(records)), c(base, record$Package))
}

deps <- lapply(records, requirements)
pending <- names(records)
wave <- 0L

while (length(pending) > 0L) {
  ready <- pending[!vapply(deps[pending], function(d) any(d %in% pending), logical(1))]

  # A dependency cycle leaves nothing orderable. Hand the rest to renv in one
  # call and let it do what it can, rather than looping forever.
  if (length(ready) == 0L) {
    warning("dependency cycle among: ", paste(sort(pending), collapse = ", "))
    ready <- pending
  }

  wave <- wave + 1L
  cat(sprintf("\n== wave %d: %s\n", wave, paste(sort(ready), collapse = " ")))
  renv::restore(packages = ready, prompt = FALSE)
  pending <- setdiff(pending, ready)
}
