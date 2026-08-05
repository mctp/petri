---
name: analysis
description: Rules for taking data through to deliverables — ingesting and cleaning raw inputs, building shared tables, running statistics, making plots, and preserving figures. Use when analyzing data, making plots, running statistics, harmonizing or cleaning a raw dataset, or producing a new shared table.
---

# Analysis

You are writing a notebook. It is a document, read top to bottom, that has to
stand alone after this session ends.

This skill covers two things: reaching for the petri API instead of the
filesystem, and what to check before you speak. The API reference and the folder
rules are in [AGENTS.md](../../../AGENTS.md); kernel mechanics are in
`marimo-pair`.

## Reach for the Petri API

Each call in the middle column writes your data **and a manifest beside it**: a
small JSON file recording the declared inputs, the output hashes, the cell that
produced it, and the git commit. The manifest is what `check()` verifies and what
lets another notebook trust the file.

The right column writes the same bytes without one. Nothing downstream can then
tell what produced the file, which inputs it came from, or whether it is still
current.

| When you | Call | Not |
|---|---|---|
| need data in an analysis notebook | `load_shared("name")` | `pl.read_csv(...)` |
| need an unowned input, in a producer notebook | `load_external("file.csv")` | reading `data/external/` directly |
| have a table other notebooks need | `save_shared(df, "name", inputs=[...])` | `df.write_csv(SHARED_DIR / ...)` |
| have a figure that ships | `preserve_figure(fig, "<cell name>", source_data=df)` | `fig.savefig(...)` |
| have a table that ships | `preserve_table(df, "<cell name>")` | `df.write_csv(...)` |
| have something already serialized | `preserve_file(src, "<cell name>", filename=...)` | copying the file yourself |
| need a path for `inputs=` | `shared_path(name)`, `external_path(relpath)` | a hand-built string |
| want to know what exists | `list_shared()`, `list_preserved()` | walking the filesystem |
| want to know if artifacts are current | `check()` | assuming they are |

`check()` returns a `CheckReport` with `.ok`, `.errors` and `.warnings`, so call it
from a cell or the scratchpad while you work. `make check` runs the same pass and
exits non-zero, which is the form for the shell and for CI.

## Cells

Cells have kinds, not a fixed order. Several of each is normal.

| Kind | Contains |
|---|---|
| setup | imports, kept together near the top |
| narrative | `mo.md` or `mo.vstack`, no computation; placed before the step it describes |
| input | `load_shared()`, or `load_external()` in a producer notebook |
| step | computes and displays; anything non-trivial calls a function in `scripts/` |

Edit the cell that owns a name; add a cell for a new name.

Any step becomes a deliverable in place: name the cell to match the artifact and
call `preserve_*` inside it. The bundle is `data/preserved/<notebook>/<cell name>/`, so
the cell stays where it is in the document.

## Scratchpad

The scratchpad runs code in the notebook's kernel without adding a cell. Use it to:

- **test** a `scripts/` function before wiring it into a cell
- **debug** a cell that failed
- **inspect** a frame, a schema, or any value the notebook defined
- **one-off** calls such as `check()` or `list_preserved()`
- **fix** a cell with `cm`, then re-run it

Nothing there is saved, and a name you define in the scratchpad is invisible to
cells. When something is worth keeping, write it as a cell. Do not build work up
in the scratchpad and transcribe it later; transcription is where errors enter.

## Read every result back

Whatever you just produced — in the scratchpad, in an unnamed cell, in a named
cell, or preserved — read it back from where it landed before you say anything
about it. Verify it is what you intended, then interpret it.

Read it back as well as the situation allows. The three routes answer different
questions:

- **the raster render**, with the `read` tool — what it looks like. Needs a
  terminal that renders images. Do not assume a filename: `list_preserved()`
  reports each bundle's actual files, and a bundle built with `formats=("svg",)`
  has no PNG at all. For a figure you have not preserved, write one to `data/cache/`
  and read that.
- **the SVG, as text** — what was actually drawn, with no image support needed.
  matplotlib writes the tick values as comments, so you can read the axis ranges
  after autoscale; it names the element groups (`axes_1`, `legend_1`), so you can
  confirm a legend exists and count what was plotted.
- **the data** — whether the numbers are right. Print the frame, or read the
  bundle's source-data file, which `preserve_figure()` always writes.

Then do one of four things:

- **fix** — the result is wrong. Correct it before showing anything.
- **present** — the result is right. Show it with one observation, in numbers.
- **ask** — the result raises a decision that is not yours. Put the question.
- **report the failure** — you cannot make it work. Say what you tried and what
  happened. Never present a broken result as a finished one.
