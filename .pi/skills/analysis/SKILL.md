---
name: analysis
description: Rules for taking data through to deliverables — ingesting and cleaning raw inputs, building shared tables, running statistics, making plots, and preserving figures. Use when analyzing data, making plots, running statistics, harmonizing or cleaning a raw delivery, or producing a new shared table.
---

# Analysis

```
external/  ->  processing/  ->  shared/  ->  analysis  ->  preserved/
```

[AGENTS.md](../../../AGENTS.md) has the data layer rules and the artifact API.
This skill covers what to decide, what to repeat, and where to stop.

## Scale the process to the request

Answer a one-step request in one step. If the user asks for a plot from a table
that already exists in `shared/`, make it, read it, and show it. A plan for a
single computation is friction.

Plan first when the work is multi-step, needs a new `shared/` table, or changes
what other notebooks read.

## Decisions the user owns

| Decision | Ask before |
|---|---|
| what enters `shared/` | writing a new shared table |
| what ships to `preserved/` | preserving anything |
| whether the result answers the question | closing the work |

The first is a hard stop. `shared/` is the contract between notebooks, so the
user decides what enters it, and you do not improvise one mid-analysis. Name the
table and say what it holds.

The other two are places to stop and show, not to wait for permission to
continue.

## The loop

```
pick the next step  ->  run it  ->  read what you wrote  ->  report  ->  stop
```

Run one step at a time. Do not run unrequested follow-up analyses or secondary
plots in the same turn. Stop after you present a result and wait for feedback.

Producing a shared table is a step in this loop, not a separate phase: write the
transformation in `processing/`, call it from a producer notebook
(`notebooks/NN_name.py`), publish with `save_shared()`, then run `make shared`.

## Every iteration

- **Read what you wrote** before presenting it. Print a table. Use the `read`
  tool on a figure's PNG. Report one observation with numbers.
- **Report every row dropped** by a filter, join, or NaN handling, with counts
  before and after. A silent drop reads as full coverage.
- **Keep exploratory plots in the cell.** Preserve only what the user says
  ships.
- **Put `save_shared()` outside any `mo.persistent_cache` block.** On a cache hit
  marimo skips the block and its writes.
- **Name a cell when you create it** if it will preserve an artifact.

## Closing

Run the analysis end-to-end. Preserve the agreed deliverables. Run `make check`
and report it. Then read each preserved file from disk — this is the first look
at the bytes that ship, since `preserve_figure()` writes a PDF and a PNG that no
cell has displayed. Report one observation per deliverable.

Summarize like a methods section: the result, the caveat, the next step. No
emoji. Name the property, not a judgment: write "higher-resolution", not
"better".

## What the code already catches

You do not need to be careful about these. They fail and tell you.

| Where | What |
|---|---|
| signature | `inputs=` and `source_data` are required |
| raises | scratchpad has no identity; unverified shared table; unknown figure format; `str` src without `filename`; manifest from a newer petri |
| `make check` | renamed or edited cell; edited `processing/` module; artifact pinned to a superseded shared table; changed output hash |
