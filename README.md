# Petri

A project template for data analysis in [marimo](https://marimo.io) notebooks,
paired with the [pi](https://github.com/earendil-works/pi) coding agent.

The agent does not edit notebook files. It attaches to the running marimo kernel
and changes cells there. The notebook in your browser and the notebook the agent
works on are the same object.

## Requirements

- [uv](https://docs.astral.sh/uv/) — Python and virtualenv
- `git`, `bash`, `curl`, `jq`
- R (optional, for `rpy2`)

## Quickstart

```bash
git clone <this-template> my-project && cd my-project
make setup          # install dependencies and git hooks
make nb             # start marimo on notebooks/
```

Start `pi` in the project root in a second terminal and ask it to pair on the
notebook.

Run `make shared` once to write the example tables, then open
`notebooks/coding_patterns.py` for worked examples of every pattern below.
`make help` lists all targets.

## Layout

```
notebooks/     marimo notebooks. NN_*.py are producers, run by `make shared`
               00_prepare_measurements.py  producer: external -> processing -> shared
               coding_patterns.py          worked examples of every pattern
processing/    your transformations: pure functions, no I/O
petri/         template library: paths, artifact provenance, R interop
tests/         artifact-layer contracts and the write-path test
docs/          architecture, renv, rpy2
```

## Data flow

```
external/  →  processing/  →  shared/  →  notebook  →  preserved/
```

Each data directory is named for the function that writes it.

| Directory | Written by | Read by | Git |
|---|---|---|---|
| `external/` | nobody — inputs from outside | producer notebooks | ignored |
| `shared/` | `save_shared()` | any notebook | manifests only |
| `preserved/` | `preserve_figure()`, `preserve_table()`, `preserve_file()` | people | tracked |
| `cache/` | you | the kernel | ignored |

`shared/` is the only channel between notebooks. `preserved/` holds
deliverables: a figure bundle is a PDF, a PNG, the plotted source data, and a
manifest. Every write records provenance, and `make check` verifies it.

See [docs/architecture.md](docs/architecture.md) for the design and
`petri/artifacts.py` for the API.

## Commands

```bash
make shared     # run producer notebooks, then verify
make check      # verify artifacts against their manifests
make test       # contracts and the write path
make lint       # ruff check and format
```

## Dependencies

Declared in `pyproject.toml`, locked in `uv.lock`. Add with `uv add <pkg>`.
During a pairing session let the agent use `ctx.packages.add(...)` so the kernel
stays in sync.

R packages use [renv](https://rstudio.github.io/renv/):

```bash
make r-restore                             # rebuild renv/library from renv.lock
make r-install PKG="ggplot2 bioc::DESeq2"  # install and snapshot
```

`rpy2` needs a local R installation. See [docs/renv.md](docs/renv.md) and
[docs/rpy2.md](docs/rpy2.md).

## Conventions

- Notebooks are `.py` files. They diff, review, and run as scripts.
- Do not edit a notebook file while its kernel runs. The kernel overwrites it.
- Secrets go in `.env`. Document new keys in `.env.example`.
- The `marimo-pair` skill is vendored in `.pi/skills/`, not a submodule. See
  [docs/skill-vendoring.md](docs/skill-vendoring.md).
- Agent instructions are in [AGENTS.md](AGENTS.md).

## Agents

The repo works with [pi](https://github.com/earendil-works/pi) and with Claude
Code. `.pi/` is canonical; the Claude Code entry points are symlinks, so nothing
is duplicated:

```
CLAUDE.md        -> AGENTS.md
.claude/skills   -> ../.pi/skills
.claude/settings.json     permission allowlist for the marimo scripts and make
```

On Windows, symlinks need `git config core.symlinks=true` or Developer Mode.
