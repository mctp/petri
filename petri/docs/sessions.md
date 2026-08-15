# Starting and stopping marimo sessions

How an agent starts and stops marimo sessions for this project.

| Action | Command / call |
|---|---|
| Start the server | `make nb ARGS=--daemon` (or `make nb` in terminal) |
| Create a session | `open "<url>?file=<name>.py"` — loads the notebook in the browser, which spawns a kernel/session |
| Stop all sessions | `make nb-stop` — stops this project's server and every session it hosts |
| Stop one session | close its browser tab |

Those four cover every case worth automating. Use `make nb-stop` or the browser
tab; do not build anything on top of the endpoint below.

## Why there is no third way to stop one session

marimo does have a per-session endpoint — `POST /api/home/shutdown_session` with
`{"sessionId": "<id>"}`, camelCase, returning 200 and the remaining sessions. It
is gated by `SkewProtectionMiddleware`, which requires the server's
skew-protection token in a `Marimo-Server-Token` header and 401s without it. The
token is `secrets.token_urlsafe(16)`, generated inside the marimo process at
startup, never written to disk, and delivered to browser clients over the
websocket. `/api/kernel/execute` is exempt from that middleware, which is why
`execute-code.sh` needs no token.

So an agent cannot know the token in advance. It can be *recovered* — the
middleware logs the expected value whenever a POST arrives with a wrong one, so
one bogus request plus a `grep` of `marimo.log` yields it. That is a log-scraping
trick against an internal, not an API: it depends on marimo's log wording, on
that logging surviving upgrades, and on the server having been started with a log
file to read. Reach for it only while debugging by hand, and never wire it into a
script.
