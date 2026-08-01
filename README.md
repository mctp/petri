# Petri

A project template for data science work done in [marimo](https://marimo.io)
notebooks, paired with the [pi](https://github.com/earendil-works/pi)
coding agent through the
[`marimo-pair`](https://github.com/marimo-team/marimo-pair) skill.

The agent does not edit notebook files. It attaches to the **running marimo
kernel** and makes changes there, so the notebook you see in the browser and the
notebook the agent works on are the same live object.

There is no Python package here — the deliverables are notebooks under
`notebooks/`, plus documentation.

## Requirements

- [uv](https://docs.astral.sh/uv/) — manages Python and the virtualenv
- `git`, `bash`, `curl`, `jq`
- R (optional, for `rpy2`)

## Quickstart

```bash
git clone <this-template> my-project && cd my-project
make setup          # uv sync + pre-commit install
make nb             # start marimo on notebooks/ with --no-token
```

Then, in a second terminal, start `pi` in the project root and ask it to pair on
the notebook. `--no-token` lets the skill auto-discover the running server.

Everything runs through `uv run`, so activating `.venv` is optional.
Run `make help` to see all targets.

## The marimo-pair skill

Upstream [`marimo-pair`](https://github.com/marimo-team/marimo-pair) is vendored
directly into the repo (not a submodule) so it ships self-contained and your
local customizations travel with the repo:

```
.pi/skills/marimo-pair/                   vendored copy of the skill
```

pi discovers skills in `.pi/skills/`, so the skill loads with no extra
configuration. Because it's a plain tracked directory (not a submodule), any
edits you make to `SKILL.md` or the reference files are ordinary versioned
changes — no push rights to the upstream repo are needed, and nothing dangles on
a fresh clone.

> **Why not a submodule?** A parent repo only records a submodule's commit SHA,
> never local edits. Vendoring the files instead keeps your customizations in
> version control and makes the template self-contained.

Update to the latest upstream skill (replaces the copy, then you review):

```bash
make skills-update
# review the diff, then:
git add .pi/skills/marimo-pair
git commit -am "chore: update marimo-pair skill"
```

See [docs/skill-vendoring.md](docs/skill-vendoring.md) for details on how the
copy is kept in sync with upstream.

## Layout

```
notebooks/         marimo notebooks (blank.py, coding_patterns.py, py_example.py, r_example.py)
docs/              project documentation (architecture, renv, rpy2)
paths.py           pure Python project directory paths helper
r_bridge.py        embedded R session & Polars <-> R interop helper
renv/              project-local R library (contents gitignored)
.pi/skills/        skills pi loads for this project (marimo-pair is vendored here)
data/raw/          immutable inputs         (gitignored)
data/interim/      intermediate artifacts   (gitignored)
data/processed/    analysis-ready datasets  (gitignored)
data/external/     third-party sources      (gitignored)
outputs/           figures, reports, exports (gitignored)
```

## Dependencies

Declared in `pyproject.toml`, locked in `uv.lock` (both committed):

- notebook: `marimo[recommended]`
- data: `numpy`, `pandas`, `polars`, `pyarrow`, `duckdb`, `scipy`
- plotting: `matplotlib`, `seaborn`, `plotly`
  (`altair` is not a direct dependency, but arrives with `marimo[recommended]`)
- R interop: `rpy2`

Add or remove with `uv add <pkg>` / `uv remove <pkg>` (dev tools:
`uv add --dev <pkg>`). During a live pairing session, let the agent use the
skill's package API (`ctx.packages.add(...)`) so the kernel stays in sync.

### R environment

R packages are managed with [renv](https://rstudio.github.io/renv/), the R
equivalent of `.venv` + lockfile:

```bash
make r-restore                             # rebuild renv/library from renv.lock
make r-install PKG="ggplot2 bioc::DESeq2"  # CRAN or Bioconductor packages + snapshot
make r-status                              # library vs. lockfile
```

`.Rprofile` and `renv.lock` are committed; `renv/library/` is not. Locked R
packages: `ggplot2`, `ggpubr`, `limma`, `BiocManager` (81 with dependencies).

Notebooks import `r_bridge` (`from r_bridge import pl_to_r, r_eval, r_set, r_to_pl`),
which sets `PROJECT_ROOT` as working directory before `rpy2` imports, automatically
activating `.Rprofile` and `renv/library/` once. See [docs/renv.md](docs/renv.md).

`rpy2` itself requires a local R installation and its behaviour depends on how
that R was built. The template ships no rpy2-specific build settings —
configure R on your machine, then see [docs/rpy2.md](docs/rpy2.md) for
verification steps, API vs. ABI mode, and troubleshooting.

## Conventions

- Python version is pinned in `.python-version`.
- Notebooks are `.py` files: they diff, review, and run as scripts.
- Never hand-edit a notebook file while its kernel is running — the kernel is the
  source of truth and will overwrite it.
- Secrets live in `.env` (gitignored); document new keys in `.env.example`.
- `make lint` / `make fmt` run ruff with notebook-friendly rules.
