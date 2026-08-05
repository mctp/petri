"""Pure transformations. One stage of the pipeline.

    data/external/  ->  scripts/  ->  data/shared/

This package holds your code. `petri/` holds the template's code. Keeping them
apart means a template update does not touch your work.

Rules:

- Pure functions only. Data in, data out. No file I/O, no writes, no path
  constants, no marimo imports, no calls into `petri.provenance`. Side effects
  belong in cells, where they are visible and named.
- Cells stay thin. The producer notebook orchestrates; this package computes.
  A thin cell also means an edit here does not re-run an expensive chain.
- Functions here run without a kernel, so you can test them.

An edit here marks the artifacts built from it stale in `make check`. See
petri/docs/architecture.md section 5.
"""
