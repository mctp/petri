# Petri

A project template for data analysis in [marimo](https://marimo.io) notebooks,
paired with the [pi](https://github.com/earendil-works/pi) coding agent.

The agent does not edit notebook files. It attaches to the running marimo kernel
and changes cells there. The notebook in your browser and the notebook the agent
works on are the same object.

## Requirements

- [uv](https://docs.astral.sh/uv/) — Python and virtualenv
- `git`, `bash`, `curl`, `jq`
- `R`, `renv` (optional, for `rpy2`)

## Quickstart

```bash
git clone <this-template> my-project && cd my-project
make setup          # install dependencies and git hooks
make init full      # copy the examples in (or `make init` for just the notebooks)
make nb             # start marimo on notebooks/ (port derived from this directory)
```

Start `pi` in the project root in a second terminal and ask the agent to pair on the
notebook.

Your folders ship empty, `make init` to jump-start from `petri/examples/`:

| | Installs |
|---|---|
| `make init` | `blank.py`, `py_example.py`, `r_example.py` — standalone, no data needed |
| `make init full` | the above plus `full_example.py`, `scripts/`, and the data it reads |

`full_example.py` runs the whole pipeline in one notebook: it reads `data/external/`,
calls `scripts/`, publishes to `data/shared/`, then consumes that table and writes
deliverables to `data/preserved/`. Nothing is overwritten on a re-run unless you
pass `--force`. `make help` lists all targets.

## Layout

Yours, empty until `make init`:

```
notebooks/     marimo notebooks
scripts/       your transformations: pure functions, no I/O
data/          your data: external/ shared/ preserved/ cache/ (see below)
```

The two language toolchains are supported:

```
                manifest        lockfile     library
Python          pyproject.toml  uv.lock      .venv/
R               (none)          renv.lock    .renv/
```

For renv, see: [petri/docs/renv.md](petri/docs/renv.md).

Petri infrastructure (do not delete):

```
petri/         paths, provenance, R interop — the API your notebooks import
  examples/    what `make init` copies out: notebooks/ scripts/ data/
  tests/       provenance contracts and the write-path test
  docs/        architecture, renv, rpy2
  skills/      marimo-pair, petri-analysis, petri-init — symlinked into .pi/ and .claude/
  init.py      the `make init` sets
  server.py    the per-directory marimo port, behind `make nb`
  r-restore.R  wave-by-wave renv restore, run by `make r-restore`
.python-version (uv)
.Rprofile (R sources it from the startup directory)
.pre-commit-config.yaml
AGENTS.md (agent instructions)
```

## Data flow

```
data/external/  →  scripts/  →  data/shared/  →  notebook  →  data/preserved/
```

Each data layer is named for the function that writes it.

| Directory | Written by | Read by |
|---|---|---|
| `data/external/` | nobody — inputs from outside | the cell that publishes |
| `data/shared/` | `save_shared()` | any notebook |
| `data/preserved/` | `preserve_figure()`, `preserve_table()`, `preserve_file()` | people |

`data/shared/` is the only channel between notebooks. `data/preserved/` holds
deliverables: a figure bundle is a PDF, a PNG, the plotted source data, and a
manifest. Every write records provenance, and `make check` verifies it.

`data/cache/` sits beside the three but is not a layer — petri never writes it and
nothing verifies it. It is scratch space with a stable path, safe to delete.

**Git ignores all of `data/`.** It holds your inputs, your tables and your
deliverables, and none of it is the template's to version. `make check` verifies
provenance where the data is. Commit a manifest deliberately — `git add -f
data/shared/<name>.manifest.json` — if a collaborator needs to verify a table you
cannot send them.

See [petri/docs/architecture.md](petri/docs/architecture.md) for the design and
`petri/provenance.py` for the API.

## Commands

```bash
make init full  # copy the examples into notebooks/, scripts/, data/
make nb         # start marimo, or print the URL if it is already running here
make nb-stop    # stop this project's server, leaving other projects alone
make check      # verify artifacts against their manifests
make test       # contracts and the write path
make lint       # ruff check and format
```

Each project gets its own marimo port, derived from its directory, so several petri
checkouts run side by side and `make nb-stop` never touches another one. `make
nb-url` prints this project's URL rather than assuming marimo's default.

## Dependencies

Declared in `pyproject.toml`, locked in `uv.lock`. Add with `uv add <pkg>`.
During a pairing session let the agent use `ctx.packages.add(...)` so the kernel
stays in sync.

R packages use [renv](https://rstudio.github.io/renv/):

```bash
make r-restore                             # rebuild .renv/library from renv.lock
make r-install PKG="ggplot2 bioc::DESeq2"  # install and snapshot
```

`rpy2` needs a local R installation. See [petri/docs/renv.md](petri/docs/renv.md)
and [petri/docs/rpy2.md](petri/docs/rpy2.md).

## Conventions

- Notebooks are `.py` files. They diff, review, and run as scripts.
- Do not edit a notebook file while its kernel runs. The kernel overwrites it.
- Secrets go in `.env`. Document new keys in `.env.example`.
- marimo's project settings live in `[tool.marimo]` in `pyproject.toml`. marimo
  reads that section and never writes to it, so a key typed into the AI panel
  lands in your own `~/.config/marimo/marimo.toml`, not in a tracked file.
  Personal preferences — theme, font size, keymap — belong there too.
- The `marimo-pair` skill is a fork in `petri/skills/`, owned by this repo. See
  [petri/docs/marimo-pair-fork.md](petri/docs/marimo-pair-fork.md).
- Agent instructions are in [AGENTS.md](AGENTS.md).

## Agents

The repo works with [pi](https://github.com/earendil-works/pi) and with Claude
Code. The skills are template machinery, so they live in `petri/skills/` with
the rest of it, and each agent's entry point is a symlink — one copy, two
readers, and neither tool's directory owns the content:

```
petri/skills/             the skills themselves: marimo-pair, petri-analysis, petri-init
.pi/skills       -> ../petri/skills
.claude/skills   -> ../petri/skills
CLAUDE.md        -> AGENTS.md
.claude/settings.json     permission allowlist for the marimo scripts and make
```

Adding a third agent means one more symlink, not a third copy. On Windows,
symlinks need `git config core.symlinks=true` or Developer Mode.
