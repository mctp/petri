# Execution Context

How a running marimo notebook is structured, what the scratchpad shares with it,
and what comes back over the wire. Read this before interpreting scratchpad
output, or when notebook state looks stale.

Every claim below is checkable against the installed `marimo` package; source
paths are given so this file can be re-verified after an upgrade.

## Four nested levels

| Level | What it is | Scope | Source |
|---|---|---|---|
| **Server** | one `marimo edit <dir>` process | hosts many sessions | `_server/` |
| **Session** | "A client session. Each session has its own Python kernel, for editing and running the app, and its own websocket." | one open notebook | `_session/session.py` |
| **Kernel** | "Kernel that manages the dependency graph and its execution." | one Python process per session | `_runtime/runtime.py` |
| **Scratchpad** | "a temporary execution environment that has access to all variables defined in the notebook but does not affect the notebook's cells or dependency graph." | one throwaway cell per call | `_server/scratchpad.py` |

`scratchpad` is marimo's own term, not this skill's — it appears in the runtime
(`ExecuteScratchpadCommand`, `session.scratchpad_lock`), the HTTP API
(`POST /api/kernel/execute`, `POST /api/scratchpad/run`), marimo's own MCP
server (`_mcp/code_server/main.py`), and the editor UI.

**A session is identified by a session id, never a filename.** Discover with
`GET /api/sessions`, which returns a map keyed by session id whose values carry
`filename`. Pass the key to `--session`, not the filename. One notebook opened
twice is two sessions over one kernel each.

## What the scratchpad shares, and what it does not

The scratch cell is a real cell in the session view under the reserved id
`__scratch__` (`_runtime/scratch.py`). It runs inside the session's kernel, so
it sees every name the notebook defines. It is nonetheless outside the notebook
in three ways that matter:

- **Not in the `.py` file.** Nothing run there is saved. It vanishes with the
  session.
- **Not in the dependency graph.** Defining a name in the scratchpad creates no
  edges, triggers no dependents, and does not collide with the single-definition
  rule. Cells cannot reference it.
- **Not visible to the user's notebook view.** Its output goes back over the
  wire to the caller, not into a notebook cell.

### Assignment is discarded, mutation is not

`execute-code` evaluates in a temporary namespace holding a **shallow copy** of
the kernel globals. Two consequences that do not match each other:

- A new top-level binding or rebinding is **discarded** when the call ends. A
  later call raises `NameError` for it.
- An **in-place mutation of a notebook-owned object persists**, because the
  scratchpad's name still points at the kernel's object.

Verified against a live kernel. With a cell owning `probe_state = {"a": 1}`:

```
call 1   probe_state["b"] = 2            scratch_only = "x"
call 2   probe_state -> {'a': 1, 'b': 2}  scratch_only -> NameError
a cell   probe_state -> {'a': 1, 'b': 2}
```

So the scratchpad can change notebook state, silently and outside the dependency
graph: no dependent cell re-runs and the `.py` file is unchanged. Mutate a
notebook-owned frame, dict or array there only when you intend exactly that.

The reverse direction is asymmetric too: `ctx.globals` records that mutations via
`run_cell` update the kernel globals but not the scratchpad's copy.

Use the scratchpad for inspection and to drive `cm`. Put anything the user must
see, re-run, or keep into a cell.

Scratchpad executions against one session **serialize** — each acquires
`session.scratchpad_lock`, so concurrent calls queue rather than interleave.

## Frozen snapshots (the main trap)

At scratchpad start, `snapshot_for_scratchpad()` freezes the notebook document
and every cell's outputs. Cells that `cm` creates and runs *during* the same
call do not refresh that snapshot:

- `ctx.cells[...].output` and `.console_outputs` are "**Frozen snapshot** —
  taken at scratchpad-start, not refreshed when `ctx.run_cell` produces new
  outputs in the same batch. Re-enter `cm.get_context()` to see fresh outputs."
- `ctx.globals` — "Mutations via `run_cell` update the kernel globals but *not*
  the scratchpad's copy. Read values through this property (`ctx.globals["x"]`)
  rather than bare variable names."

So after `ctx.run_cell(...)`, a bare variable name in the same scratchpad call is
stale. Read through `ctx.globals["x"]`, or re-enter `cm.get_context()` to pick up
new outputs. Source: `_code_mode/_context.py`.

## What comes back over the wire

`POST /api/kernel/execute` streams SSE events, then one terminal event:

1. `stdout` / `stderr` — `{"data": "..."}`, streamed as the cell runs. The
   listener also captures console output from *other* cells that execute while
   the scratchpad runs, i.e. cells run by `cm`.
2. `done` — `{"success": bool, "output": {"mimetype": str, "data": str}}`.

Two results follow from `build_done_event`:

- **Error detail comes before `done`, on `stderr`.** On failure `done` carries
  the success bit and an empty output. `success` is false if the scratch cell
  failed, or if any downstream cell the listener captured failed. A `cm`-driven
  cell failure therefore fails the whole call.
- **Rich output becomes text.** A mimebundle is reduced to its `text/plain`
  entry, then `text/html`, then `str(data)`. `execute-code.sh` prints
  `.output.data` and drops the mimetype.

No rendered image or widget returns through this path. To see a plot, save it to
a file and read that file in a separate tool call. To give the user a plot or an
interactive element, put it in a cell with `mo.image(...)`, `mo.ui.*`, or an
anywidget. See [rich-representations.md](rich-representations.md).

## Print economy

Everything the scratchpad prints becomes a tool result in the agent's
conversation and stays there. Print only what decides the next step: an
aggregate, a count, a shape, an `assert`. Write more than 10 lines to a file, or
to a cell where the user can read it.

## See also

- [connection-troubleshooting.md](connection-troubleshooting.md) — targeting,
  auth, quoting, and script errors
- [finding-marimo.md](finding-marimo.md) — choosing the right marimo invocation
- [gotchas.md](gotchas.md) — name redefinition and notebook traps
