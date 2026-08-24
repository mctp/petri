# Connection Troubleshooting

Use this reference when `execute-code.sh` or MCP cannot reach the intended
marimo session, cannot select a session, or fails because code was passed
incorrectly.

## Targeting

Use explicit targets when possible.

- `--url` connects to a known marimo server or notebook URL.
- `--port` selects a local marimo server from the registry.
- `--file` names the notebook and resolves its session on every call.
- `--session` pins one session id, overriding `--file`.

Prefer `--file`: marimo renames a session when it resumes one, so an id captured
earlier in a conversation can stop resolving while the kernel behind it is still
running. See [execution-context.md](execution-context.md) for why.

If multiple servers are available, do not guess. Ask for the URL, or inspect
local context.

## Auth

For token-authenticated servers, prefer `MARIMO_TOKEN`.

```bash
MARIMO_TOKEN=... bash scripts/execute-code.sh --url http://localhost:2718 -c "1 + 1"
```

`--token` also works, but may expose the token in process listings. If both are
present, `--token` overrides `MARIMO_TOKEN`. The script sends the token as
`Authorization: Bearer ...` on session discovery and code execution requests.

## Quoting

Use `-c` only for short one-liners. Use a single-quoted heredoc or file input
for multiline code or shell-sensitive characters.

```bash
bash scripts/execute-code.sh --url http://localhost:2718 <<'PY'
print(df.head())
PY
```

```bash
bash scripts/execute-code.sh --url http://localhost:2718 /tmp/code.py
```

## Common Script Errors

- **No running marimo instances found** - use an explicit `--url`, or start
  marimo with the project's normal tooling.
- **Multiple instances found** - rerun with `--port` or `--url`.
- **No active sessions on the server** - open the notebook in the browser
  (`make nb-open NB=notebooks/<name>.py`).
- **No session for <path>** - that notebook is not open; the message lists what
  is. Check the path before opening a second copy of something already running.
- **Multiple sessions on server** - rerun with `--file` or `--session`.
- **Multiple sessions match <path>** - two kernels for one notebook, only one of
  which writes to disk. Ask the user which; do not pick.
- **Invalid session id** - the id moved (a reopen renames a resumed session).
  Re-resolve with `--file`, or ask for the current id.
- **Failed to connect** - check the URL, token, and whether the server is still
  running.
- **SyntaxError** - the submitted Python was malformed; use a heredoc or file.
- **ImportError** - diagnose in the notebook kernel. Install packages through
  `cm` when needed.

## Starting marimo

Discover first. If no server is running and the user wants a notebook, use
[finding-marimo.md](finding-marimo.md).

## Starting and stopping sessions

- **Start** - `make nb-open NB=notebooks/<name>.py` starts the server if needed
  and opens that notebook, creating its session/kernel on an id derived from the
  notebook's name. `make nb ARGS=--daemon` starts the server alone and returns
  once it answers as this project's. Bare `make nb` runs in the foreground, so it
  blocks a synchronous tool call until that call times out.
- **Stop all** - `make nb-stop` stops this project's server and every session.
  **Requires explicit user permission**: it drops live state in every open kernel,
  including notebooks the user is working in. Report the hang and let them decide;
  never restart to clear one of your own errors.
- **Stop one** - close its browser tab. There is no clean programmatic way;
  [`petri/docs/sessions.md`](../../../docs/sessions.md) says why.
