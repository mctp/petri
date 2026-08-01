# AGENTS.md — Instructions for AI Coding Agents

This project pairs **marimo notebooks** with the **pi agent** via `marimo-pair`. It uses Python (`uv`, Polars) and R (`renv`, `ggplot2`).

---

## ⚠️ Critical Rule: Live Kernel is Source of Truth

When marimo is running:
- **Do not edit** `notebooks/*.py` files on disk. The kernel overwrites disk files on save.
- **Run code** using `bash .pi/skills/marimo-pair/scripts/execute-code.sh`.
- **Edit cells** using `marimo._code_mode` (`cm`) in the scratchpad.
- **Hide code by default**: When creating cells via `cm` (`marimo._code_mode`), always pass `hide_code=True` (e.g. `ctx.create_cell(code, hide_code=True)`) so the code editor remains collapsed in the UI unless requested otherwise.

---

## Opening a Notebook for Pairing

1. **Start the server** (if not running): `make nb` runs `marimo edit notebooks/ --no-token`.
2. **Open the notebook** in the browser. The server root is `notebooks/`, so file
   URLs are relative to that directory — **omit the `notebooks/` prefix**:
   `open "http://localhost:2718/?file=<name>.py"` (e.g. `?file=coding_patterns.py`,
   NOT `?file=notebooks/coding_patterns.py`).
3. **Find the session id** (one per open notebook):
   `curl -s http://localhost:2718/api/sessions | jq -r 'to_entries[] | "\(.key)  \(.value.filename)"'`.
4. **Connect / run code** against that kernel, passing the session id (not the filename):
   ```bash
   bash .pi/skills/marimo-pair/scripts/execute-code.sh --url http://localhost:2718 --session <id> -c "print('connected')"
   ```

If a single notebook is open you can omit `--session`; the script auto-selects it.

---

## Prevent and Fix Process Hangs

### Rules
1. **Set tool timeout**: Pass `timeout: 30` when calling `execute-code.sh`.
2. **Do not block the kernel**: Do not run `input()`, infinite loops, or interactive prompts.

### Recovery Procedure
If `execute-code.sh` hangs or times out:
1. Stop stuck processes: `pkill -9 -f "marimo edit"`
2. Remove old state files: `rm -f ~/.local/state/marimo/servers/*.json`
3. Restart marimo server: `nohup make nb > marimo.log 2>&1 &`
4. Ask user to open [http://localhost:2718](http://localhost:2718) in the browser.

---

## R Interop (`r_bridge`)

- **Import**: `from r_bridge import pl_to_r, r_eval, r_set, r_to_pl`.
- **Dataframes**: Use Polars only. Do not use `pandas`.
- **renv**: Do not call `renv::load()` or `activate.R` in cells. `r_bridge` activates `renv` automatically.
- **DAG trigger**: Reference Polars DataFrames in cell signatures to trigger marimo updates.

---

## Analysis Workflows

- **Analyst Skill**: Use the `analyst` skill (`.pi/skills/analyst/SKILL.md`) to agree on inputs and methods before running code.
- **Notebook Presentation**: During Phase 2 (Incremental Execution), always present data, plots, summary tables, and statistics directly inside live marimo notebook cells (via `cm`, with `hide_code=True` by default) so the user can interactively review them in the marimo UI. Do not rely solely on text or scratchpad outputs in chat.

---

## Dependency Management

- **Python**: Run `uv add <pkg>` on host, or `ctx.packages.add("<pkg>")` in live session via `cm`.
- **R**: Run `make r-install PKG="pkgname"` or `make r-install PKG="bioc::pkgname"`.
- **Restore R**: Run `make r-restore`.

---

## File Paths & Outputs

- **Notebooks**: `notebooks/`
- **Paths**: Import from `paths`: `DATA_DIR`, `OUTPUTS_DIR`, `PROJECT_ROOT`.
- **Data**: Store in `data/` (`raw/`, `interim/`, `processed/`, `external/`).
- **Outputs**: Save plots to `OUTPUTS_DIR / "name.png"`. Display with `mo.image(path.read_bytes(), width=600)`.
- **Secrets**: Store credentials in `.env`.

---

## Command Reference

| Command | Purpose |
|---|---|
| `make setup` | Install Python dependencies, R packages, git hooks |
| `make nb` | Start marimo server (`--no-token`) |
| `make lint` | Run code quality checks |
| `make fmt` | Auto-format Python code |
| `make r-install PKG="..."` | Install R packages and update `renv.lock` |
| `make r-status` | Check R library status |
