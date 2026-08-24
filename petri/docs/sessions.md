# Starting and stopping marimo sessions

How an agent starts and stops marimo sessions for this project.

| Action | Command / call |
|---|---|
| Start the server | `make nb ARGS=--daemon` (or `make nb` in terminal) |
| Create a session | `make nb-open NB=notebooks/<name>.py` — starts the server if needed and loads the notebook in the browser, which spawns a kernel/session |
| Stop all sessions | `make nb-stop` — stops this project's server and every session it hosts. **Requires explicit user permission.** |
| Stop one session | close its browser tab |

Those four cover every case worth automating. Use `make nb-stop` (with permission)
or the browser tab; do not build anything on top of the endpoint below.

## Which session, and for how long

A session id is not stable on its own. marimo's browser client mints a fresh one
on every page load: it accepts `?session_id=` from the URL only when the value
matches `^s_[\da-z]{6}$`, deletes the parameter from the address bar once read,
and otherwise generates a random id
(`frontend/src/core/kernel/session.ts`). Closing a notebook and opening it again
therefore arrives at the server as a new session.

What keeps the kernel is `EditModeResumeStrategy`: an orphaned session for the
same file is *renamed* to the incoming id
(`marimo/_server/resume_strategies.py`). The browser keeps its variables; anything
holding the old id does not — `/api/kernel/execute` answers `Invalid session id`.

So petri derives the id instead of discovering it. `make nb-open` derives one from the
notebook's name (`petri/server.py`, `session_id()`) and hands it to the browser in
the URL, which sends marimo down its reconnect-by-id path: same kernel, same id,
no resume and no second session. `make nb-session NB=...` prints the same value,
and an agent can derive it without asking anyone.

Two things it does not fix, both harmless if you know them:

- A refresh inside the browser (⌘R) reloads a URL the client has already stripped,
  so it comes back as a new random id and the kernel is resumed under that one.
  Reopening with `make nb-open` returns to the pinned id.
- Opening the same notebook in a second tab takes the session over from the first,
  because the reconnect path calls `disconnect_main_consumer()`.

`execute-code.sh --file notebooks/<name>.py` avoids the question by
resolving the id from `/api/sessions` on every call. Prefer it. Use `--session`
when the user hands you an id, and re-resolve if a call answers `Invalid session
id`.

**On marimo before 0.24 the effect was worse.** `try_resume` matched
sessions with `os.path.abspath(file_key)`, which resolves against the server's
working directory, while `marimo edit notebooks/` serves keys relative to
`notebooks/`. Nothing ever matched, so every reopen started a *second kernel* and
left the first orphaned for good — no TTL applies in edit mode. Upstream
[#10474](https://github.com/marimo-team/marimo/pull/10474) resolves file keys
through the workspace; `pyproject.toml` requires `marimo>=0.24` for that reason.
Two sessions for one file is now a symptom, not the normal state of affairs.

**Never attempt to terminate a session by calling `sys.exit()`, `os._exit()`, or
killing processes from within the scratchpad.**
Abrupt process exit severs the SSE event stream and hangs the tool harness.

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
