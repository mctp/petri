# marimo-pi

Template for data science projects that pair a live [marimo](https://marimo.io)
notebook with the [pi](https://github.com/earendil-works/pi-coding-agent) coding
agent (via the `marimo-pair` skill).

## Requirements

- [uv](https://docs.astral.sh/uv/) (manages Python and the virtualenv)
- `git`, `bash`, `curl`, `jq`

## Quickstart

```bash
git clone <this-template> my-project && cd my-project
uv sync                  # creates .venv from uv.lock, installs dev tools
uv run pre-commit install # enable git hooks
uv run marimo edit notebooks/ --no-token   # start a notebook server
```

Everything runs through `uv run`, so activating `.venv` is optional:

```bash
source .venv/bin/activate   # optional
```

## Layout

```
src/marimo_pi/     shared, importable, testable project code
notebooks/         marimo notebooks (.py files, git-friendly)
tests/             pytest suite for src/
data/raw/          immutable inputs        (gitignored)
data/interim/      intermediate artifacts  (gitignored)
data/processed/    analysis-ready datasets (gitignored)
data/external/     third-party sources     (gitignored)
outputs/           figures, reports, exports (gitignored)
```

Keep notebooks thin: reusable loading/cleaning/plotting logic belongs in
`src/marimo_pi/` where it can be imported and tested.

## Common tasks

```bash
make help     # list targets
make lint     # ruff check + format check
make fmt      # ruff fix + format
make test     # pytest
make check    # lint + types + tests
make nb       # marimo edit notebooks/ --no-token
```

## Renaming the package

After cloning, rename `marimo-pi` / `marimo_pi`:

```bash
git mv src/marimo_pi src/my_project
rg -l 'marimo[-_]pi' | xargs sed -i '' 's/marimo-pi/my-project/g; s/marimo_pi/my_project/g'
uv sync
```

## Conventions

- Python is pinned in `.python-version`; dependencies are locked in `uv.lock`
  (both committed).
- Add runtime deps with `uv add <pkg>`, tools with `uv add --dev <pkg>`.
- Notebooks are plain Python files, so they diff and review normally.
- Secrets live in `.env` (gitignored); document new keys in `.env.example`.
