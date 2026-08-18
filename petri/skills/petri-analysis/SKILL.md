---
name: petri-analysis
description: Rules for taking data through to deliverables — ingesting and cleaning raw inputs, building shared tables, running statistics, making plots, and preserving figures. Use when analyzing data, making plots, running statistics, harmonizing or cleaning a raw dataset, or producing a new shared table.
---

# petri-analysis

You are writing a notebook. It is a document, read top to bottom, that has to
stand alone after this session ends.

This skill covers two things: reaching for the petri API instead of the
filesystem, and what to check before you speak. The API reference and the folder
rules are in [AGENTS.md](../../../AGENTS.md); kernel mechanics are in
`marimo-pair`.

If `notebooks/` is empty, suggest `make init`. A fresh clone ships it that way.

## Reach for the Petri API

Each call in the middle column writes your data **and a manifest beside it**: a
small JSON file recording the declared inputs, the output hashes and the cell
that produced it. The manifest is what `check()` verifies and what lets another
notebook trust the file.

The right column writes the same bytes without one. Nothing downstream can then
tell what produced the file, which inputs it came from, or whether it is still
current.

| When you | Call | Not |
|---|---|---|
| need data in an analysis notebook | `load_shared("name")` | `pl.read_csv(...)` |
| need an unowned input, in a publishing cell | `load_external("file.csv")` | reading `data/external/` directly |
| have a table other notebooks need | `save_shared(df, "name", inputs=[...])` | `df.write_csv(SHARED_DIR / ...)` |
| have a figure that ships | `preserve_figure(fig, "<cell name>", source_data=df)` | `fig.savefig(...)` |
| have a table that ships | `preserve_table(df, "<cell name>")` | `df.write_csv(...)` |
| have something already serialized | `preserve_file(src, "<cell name>", filename=...)` | copying the file yourself |
| need a path for `inputs=` | `shared_path(name)`, `external_path(relpath)` | a hand-built string |
| want to know what exists | `list_shared()`, `list_preserved()` | walking the filesystem |
| want to know if artifacts are current | `check()` | assuming they are |

`check()` returns a `CheckReport` with `.ok`, `.errors` and `.warnings`. Two forms,
and the difference is cost:

- **`check()` from the scratchpad** is the interactive one. It runs in the kernel
  you already have, so call it whenever you want to know where things stand.
- **`make check`** runs the same pass in a new interpreter, re-importing
  everything, and exits non-zero. That is the form for the shell and for CI.
  Keep it for a finished deliverable, a handoff or a commit — **not for every
  analysis step or chat turn**, where the startup cost buys nothing `check()`
  would not have told you sooner.

`save_shared()` refuses a column it could not give back, because `data/shared/` is
CSV and the manifest records a dtype by name. A time zone, a time unit other than
microseconds, a decimal precision, an enum's categories and anything nested are
all lost, so they are rejected at publication instead of silently dropped on read.
Cleaning raw timestamps is where this shows up: cast to a naive `Datetime` and keep
the zone in its own column, or store the value as a string.

Keep `save_shared()` and `preserve_*()` outside any `mo.persistent_cache` block.
On a cache hit marimo skips the block and its side effects, so the write never
happens and nothing reports it.

Cache is disposable, and the notebook has to prove it. With every cache cleared —
`rm -rf data/cache/*` and `make clean`, which removes the `notebooks/__marimo__/`
one that `mo.persistent_cache` uses by default — `make run NB=...` must still
succeed from raw inputs. Never read a cache file the notebook did not write
itself; a file some other process left there has no provenance, and building a
deliverable on it means nothing in the notebook produces that deliverable.

## Cells

Cells have kinds, not a fixed order. Several of each is normal.

| Kind | Contains |
|---|---|
| setup | imports, kept together near the top |
| narrative | `mo.md` or `mo.vstack`, no computation; placed before the step it describes |
| input | `load_shared()`, or `load_external()` in a publishing cell |
| step | computes and displays; anything non-trivial calls a function in `scripts/` |

Edit the cell that owns a name; add a cell for a new name.

Any step becomes a deliverable in place: name the cell to match the artifact and
call `preserve_*` inside it. The bundle is `data/preserved/<notebook>/<cell name>/`, so
the cell stays where it is in the document.

### Passing a table between cells

marimo registers a dependency only through a cell argument. `save_shared()` and
`load_shared()` are file I/O and invisible to the graph, so a reader can run
before its writer. Return the path `save_shared()` gives you, and take it as an
argument wherever you read that table back.

### Seed before you preserve

A deliverable has to render the same bytes twice. Seed every generator in play, in
the cell: `np.random.seed()`, `random.seed()`, `set.seed()` in R. `seaborn` has no
seed of its own; its jitter draws from numpy's.

### Raw strings for math and plot text

Write narrative cells, Markdown equations and matplotlib labels as raw strings —
`r"""..."""`, or `rf"""..."""` when interpolating. `"\text{x}"` is a tab followed
by `ext{x}`, `"$\times$"` renders as `$<tab>imes$`, and `"\nu"` is a newline and a
`u`. Python warns about an unknown escape, but the ones it does interpret pass
silently and reach the figure.

### The cell draws what it preserves

Embed the plotting code in the cell and preserve the figure that cell draws.
Pointing `mo.image(...)` or `preserve_file(...)` at a PNG some other process
wrote leaves a deliverable no cell produces, which is the one thing the manifest
is meant to rule out. Keep what a cell displays under 5 MB — marimo rejects
larger payloads, so plot natively rather than `imshow`-ing a multi-megapixel
raster.

## Scratchpad

The scratchpad runs code in the notebook's kernel without adding a cell. Use it to:

- **test** a `scripts/` function before wiring it into a cell
- **debug** a cell that failed
- **inspect** a frame, a schema, or any value the notebook defined
- **one-off** calls such as `check()` or `list_preserved()`
- **fix** a cell with `cm`, then re-run it

Nothing there is saved, and a name you define in the scratchpad is invisible to
cells. `save_shared()` and `preserve_*()` raise there: an artifact is anchored to
the named cell that wrote it, and the scratchpad is not one. When something is
worth keeping, write it as a cell. Do not build work up
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
- **present** — the result is right. Put it in a cell if it is not in one yet,
  then say one thing about it in chat, in numbers. The cell carries the result;
  chat carries the sentence that tells the user where to look.
- **ask** — the result raises a decision that is not yours. Put the question.
- **report the failure** — you cannot make it work. Say what you tried and what
  happened. Never present a broken result as a finished one.
