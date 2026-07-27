# marimo-pi

A project template for data science work done in [marimo](https://marimo.io)
notebooks, paired with the [pi](https://github.com/earendil-works/pi-coding-agent)
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

## Layout

```
notebooks/         marimo notebooks (plain .py files, reviewable diffs)
docs/              project documentation (setup notes, decisions)
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
- plotting: `matplotlib`, `seaborn`, `altair`, `plotly`
- R interop: `rpy2`

Add or remove with `uv add <pkg>` / `uv remove <pkg>` (dev tools:
`uv add --dev <pkg>`). During a live pairing session, let the agent use the
skill's package API (`ctx.packages.add(...)`) so the kernel stays in sync.

### R interop

`rpy2` requires a local R installation and its behaviour depends on how that R
was built. The template ships no rpy2-specific build settings — configure R on
your machine, then see [docs/rpy2.md](docs/rpy2.md) for verification steps,
API vs. ABI mode, and troubleshooting.

## Conventions

- Python version is pinned in `.python-version`.
- Notebooks are `.py` files: they diff, review, and run as scripts.
- Never hand-edit a notebook file while its kernel is running — the kernel is the
  source of truth and will overwrite it.
- Secrets live in `.env` (gitignored); document new keys in `.env.example`.
- `make lint` / `make fmt` run ruff with notebook-friendly rules.
