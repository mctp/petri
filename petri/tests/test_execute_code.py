"""Contract tests for how execute-code.sh picks a session.

The script is what an agent runs on every turn, and `--file` is the targeting
mode that survives a browser reopen: marimo renames a session when it resumes
one, so a pinned `--session` can go stale between turns while the kernel lives
on. The rules below are worth pinning because getting them wrong is silent — the
call lands on a kernel, just not the one the user is looking at.

These run against a stub of marimo's HTTP API rather than a live server, so they
cost nothing and cannot disturb an open notebook.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from petri.paths import PROJECT_ROOT

SCRIPT = (
    PROJECT_ROOT / "petri" / "skills" / "marimo-pair" / "scripts" / "execute-code.sh"
)

pytestmark = pytest.mark.skipif(
    not (shutil.which("jq") and shutil.which("curl")),
    reason="execute-code.sh talks to the API with curl and jq",
)


def _handler(sessions: dict[str, str]):
    """A stand-in for GET /api/sessions and POST /api/kernel/execute.

    The execute response echoes the session id the script chose, which is the
    thing under test: the caller reads it back as ordinary stdout.
    """

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):  # keep pytest output clean
            del args

        def do_GET(self):
            body = json.dumps(
                {
                    session_id: {"filename": path, "path": path}
                    for session_id, path in sessions.items()
                }
            ).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            chose = self.headers.get("Marimo-Session-Id", "")
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            self.wfile.write(
                f"event: stdout\ndata: {json.dumps({'data': chose})}\n\n"
                'event: done\ndata: {"success": true, "output": '
                '{"mimetype": "text/plain", "data": ""}}\n\n'.encode()
            )
            self.wfile.flush()

    return Handler


@pytest.fixture
def marimo_api():
    """Serve a session map; yields a function returning the script's stdout."""
    state: dict[str, dict[str, str]] = {"sessions": {}}
    server = ThreadingHTTPServer(("127.0.0.1", 0), _handler(state["sessions"]))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_address[1]}"

    def run(sessions: dict[str, str], *args: str) -> subprocess.CompletedProcess:
        state["sessions"].clear()
        state["sessions"].update(sessions)
        return subprocess.run(
            ["bash", str(SCRIPT), "--url", url, *args, "-c", "print(1)"],
            capture_output=True,
            text=True,
            timeout=30,
        )

    yield run
    server.shutdown()


ONE = {"s_aaaaaa": "/proj/notebooks/one.py"}
TWO = {"s_aaaaaa": "/proj/notebooks/one.py", "s_bbbbbb": "/proj/notebooks/two.py"}


@pytest.mark.parametrize(
    "spelling",
    ["notebooks/two.py", "two.py", "/proj/notebooks/two.py", "./notebooks/two.py"],
)
def test_file_finds_the_session_however_the_path_is_spelled(marimo_api, spelling):
    """marimo reports absolute paths; the agent types whatever it has."""
    done = marimo_api(TWO, "--file", spelling)
    assert done.returncode == 0, done.stderr
    assert done.stdout.strip() == "s_bbbbbb", "targeted the wrong session"


def test_an_explicit_session_wins_over_the_file(marimo_api):
    """`--session` is the escape hatch for a case the file cannot name."""
    done = marimo_api(TWO, "--session", "s_aaaaaa", "--file", "notebooks/two.py")
    assert done.stdout.strip() == "s_aaaaaa"


def test_a_notebook_with_no_session_says_how_to_open_it(marimo_api):
    """The common miss: the notebook is not open in a browser yet."""
    done = marimo_api(TWO, "--file", "notebooks/absent.py")
    assert done.returncode == 1
    assert "make nb-open NB=notebooks/absent.py" in done.stderr
    assert "s_aaaaaa" in done.stderr, "did not list what is running"


def test_two_sessions_for_one_notebook_refuse_to_guess(marimo_api):
    """Should not happen on marimo >= 0.24, and must never be resolved by guess:
    only one of the two kernels is the one writing the file."""
    duplicated = {
        "s_aaaaaa": "/proj/notebooks/one.py",
        "s_cccccc": "/proj/notebooks/one.py",
    }
    done = marimo_api(duplicated, "--file", "notebooks/one.py")
    assert done.returncode == 1
    assert "--session" in done.stderr
    assert "s_aaaaaa" in done.stderr and "s_cccccc" in done.stderr


def test_one_session_still_needs_no_targeting(marimo_api):
    """The single-notebook case keeps working without --file."""
    done = marimo_api(ONE)
    assert done.returncode == 0, done.stderr
    assert done.stdout.strip() == "s_aaaaaa"


def test_several_sessions_and_no_target_names_both_ways_out(marimo_api):
    done = marimo_api(TWO)
    assert done.returncode == 1
    assert "--file" in done.stderr and "--session" in done.stderr
