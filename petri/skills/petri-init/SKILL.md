---
name: petri-init
description: >-
  Populate an empty petri project with the template examples — standalone
  notebooks, and optionally the full worked example with its transformations and
  data. Use when starting a new project, when notebooks/ or data/ are empty, when
  the user asks for example notebooks, or when an import from scripts/ fails
  because the folder holds nothing.
allowed-tools: Bash(make init*), Bash(uv run python -m petri.init*), Read
---

# petri-init

A fresh petri project ships with empty folders. `notebooks/`, `scripts/` and the
four `data/` directories hold nothing but a `.gitkeep`, so the user starts with
their own work rather than deleting someone else's. The examples live in
`petri/examples/` and are copied out on request.

## Which set

| Set | Installs | Reach for it when |
|---|---|---|
| `minimal` | `blank.py`, `py_example.py`, `r_example.py` | the user wants a starting point, or a plotting reference |
| `full` | the above, plus `full_example.py`, `scripts/`, and the data it reads | the user wants the provenance API demonstrated end to end |

`minimal` is the default and installs nothing under `data/` or `scripts/` — the
three notebooks synthesize their own data. Choose it unless the user asks about
the artifact API, `save_shared`, `preserve_*`, or wants a worked pipeline to
copy from.

`full` is a superset. Running it after `minimal` adds only the missing files.

```bash
make init            # minimal
make init minimal
make init full
```

## Before you run it

**Check whether the folders already hold work.** `make init` never overwrites —
it prints `exists` and moves on — so a re-run is safe, but a project that already
has notebooks probably does not want examples dropped beside them. Look first,
and if there is existing work, say what you would add and let the user decide.

**Do not pass `--force` on your own initiative.** It overwrites the user's files
with template copies. Only use it when the user asks to reset an example they
have edited, and name the files it will replace before you run it.

`--dry-run` and `--list` answer "what would this do" without writing anything.

## After you run it

Run `make check`. On `full` this verifies the four installed artifacts against
their manifests and should report no problems; on `minimal` there is nothing to
verify and it reports zero artifacts, which is also correct.

The installed files are byte-exact copies, and that matters: each manifest pins
the sha256 of the modules its producing cell imported, so a single edited line in
an installed `scripts/` module makes `check()` report an error, not a warning.
If `check` fails right after an install, suspect the copy, not the notebook.

Then hand off:

- **`make nb ARGS=--daemon`** starts marimo in the background, and the `marimo-pair` skill covers driving it.
- The **`petri-analysis`** skill covers the actual data work.

## What not to do

Do not copy files out of `petri/examples/` by hand, and do not edit them in place
to change what a user gets. `petri/examples/` is the template's own payload;
`petri/init.py` holds the set definitions, and the sets are closed under their
inputs on purpose — `full` ships the shared tables *and* their manifests *and*
the preserved bundles, because a preserved artifact declares the shared table it
was built from as an input. Installing half of that would not verify.
