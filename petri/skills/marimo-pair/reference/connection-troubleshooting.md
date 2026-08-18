# Connection Troubleshooting

Use this reference when `execute-code.sh` or MCP cannot reach the intended
marimo session, cannot select a session, or fails because code was passed
incorrectly.

## Targeting

Use explicit targets when possible.

- `--url` connects to a known marimo server or notebook URL.
- `--port` selects a local marimo server from the registry.
- `--session` selects one notebook session on a server.

If multiple servers or sessions are available, do not guess. Ask for the URL or
session, or inspect local context.

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
- **No active sessions on the server** - open the notebook in the browser or
  provide `--session`.
- **Multiple sessions on server** - rerun with `--session`.
- **Failed to connect** - check the URL, token, and whether the server is still
  running.
- **SyntaxError** - the submitted Python was malformed; use a heredoc or file.
- **ImportError** - diagnose in the notebook kernel. Install packages through
  `cm` when needed.

## Starting marimo

Discover first. If no server is running and the user wants a notebook, use
[finding-marimo.md](finding-marimo.md).

## Starting and stopping sessions

- **Start** - `make nb ARGS=--daemon` starts the server in the background and
  returns once it answers as this project's; `open "<url>?file=<name>.py"` opens
  a notebook and creates its session/kernel. Bare `make nb` runs in the
  foreground, so it blocks a synchronous tool call until that call times out.
- **Stop all** - `make nb-stop` stops this project's server and every session.
  **Requires explicit user permission**: it drops live state in every open kernel,
  including notebooks the user is working in. Report the hang and let them decide;
  never restart to clear one of your own errors.
- **Stop one** - close its browser tab. There is no clean programmatic way;
  [`petri/docs/sessions.md`](../../../docs/sessions.md) says why.
