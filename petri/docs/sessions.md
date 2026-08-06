# Starting and stopping marimo sessions

How an agent starts and stops marimo sessions for this project, and the
server-token mechanism that gates the per-session shutdown endpoint. This is
reference for anyone who needs to manage sessions below the `make` targets.

## What an agent can do with the normal tooling

| Action | Command / call |
|---|---|
| Start the server | `make nb` (or `nohup make nb > marimo.log 2>&1 &`) |
| Create a session | `open "<url>?file=<name>.py"` — loads the notebook in the browser, which spawns a kernel/session |
| Stop all sessions | `make nb-stop` — stops this project's server and every session it hosts |
| Stop one session | not available through the normal tooling (see below) |

## Stopping a single session

marimo has an endpoint to shut down one session:

```
POST /api/home/shutdown_session
{"sessionId": "<id>"}     # field is camelCase, not session_id
```

It returns 200 and the remaining sessions. But it is gated by a middleware that
requires the server's **skew-protection token** in the `Marimo-Server-Token`
header.

### The token model

marimo has two separate tokens (see `marimo/_server/token_manager.py`):

- **auth token** — `--no-token` sets this to empty (no auth). `execute-code.sh`
  connects because `/api/kernel/execute` is exempt from the middleware anyway.
- **skew-protection token** — `SkewProtectionToken.random()` = `secrets.token_urlsafe(16)`,
  generated inside the marimo process at startup in edit mode. Not written to
  disk, not printed unless MCP is enabled.

The skew token is delivered to the client on first connection (over the
websocket). The middleware requires it on every POST **except** `/api/kernel/execute`,
`/ws`, and `/auth/login`. So `POST /api/home/shutdown_session` returns
`401 Missing server token` if the header is absent.

### Recovering the token

Because it is random per startup and not persisted, there is no clean way to
know it in advance. It can, however, be recovered on demand: the middleware
logs the expected value whenever a POST fails the check:

```
[W ... middleware:162] Received request with invalid server token (skew
protection token). ... Expected: <token>, got: <anything>
```

So the sequence is:

```bash
# 1. Trigger a failure to leak the expected token into marimo.log
curl -X POST "$URL/api/home/shutdown_session" \
  -H "Content-Type: application/json" \
  -H "Marimo-Server-Token: bogus" \
  -d '{"sessionId":"<id>"}'

# 2. Read the expected token
grep "invalid server token" marimo.log | tail -1 | grep -oE "Expected: [^,]+"

# 3. Resend with the real header
curl -X POST "$URL/api/home/shutdown_session" \
  -H "Content-Type: application/json" \
  -H "Marimo-Server-Token: <token>" \
  -d '{"sessionId":"<id>"}'
```

This is a workaround, not an API: it relies on the middleware logging the
expected value, and it treats `marimo.log` as the log file the server was
started with. Prefer `make nb-stop` (all sessions) or closing the browser tab
(one session) when either is acceptable.
