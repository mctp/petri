"""server.py — start, find and stop this project's marimo server.

One machine runs many petri projects, and marimo defaults every server to port
2718. Two projects therefore compete for one port, and the agent that finds a
server there cannot tell whose it is: marimo's registry under
`~/.local/state/marimo/servers/` records a pid, host and port, and no working
directory. `/api/status` reports absolute notebook paths, but only once a notebook
is open, so it cannot identify an idle server either.

That gap is what let one project's agent kill another's server. `pkill -f "marimo
edit"` matches every marimo on the machine.

So a server is identified here by the working directory of its process, which is
always available and cannot be confused between projects:

    running here      a live pid whose cwd is PROJECT_ROOT, answering /health
    hung here         a live pid whose cwd is PROJECT_ROOT, not answering
    somewhere else    a live pid with a different cwd — never touched

The port is derived from PROJECT_ROOT, so one project keeps one port across
restarts and two projects do not collide. It is a starting point, not an identity:
if something else holds it, the next free port is used and discovery still works,
because discovery matches on the directory.

    python -m petri.server            ensure a server, then exec marimo
    python -m petri.server --status   report; exit 0 if one is running here
    python -m petri.server --url      print the base URL and nothing else
    python -m petri.server --stop     stop this project's server, no other
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, NamedTuple
from urllib.error import URLError
from urllib.request import urlopen

from .paths import PROJECT_ROOT

HOST = "127.0.0.1"

# marimo's own default is 2718. Starting there keeps the range recognisable, and
# 1000 ports is wide enough that two projects rarely want the same one: ten
# concurrent projects collide 4% of the time, against 37% in a span of 100. A
# collision costs only the preferred port, since an occupied port is skipped and
# a server is found by its directory either way.
PORT_BASE = 2718
PORT_SPAN = 1000


def servers_dir() -> Path:
    """Where marimo records its running servers."""
    if platform.system() == "Windows":
        return Path.home() / ".marimo" / "servers"
    state = os.environ.get("XDG_STATE_HOME") or str(Path.home() / ".local" / "state")
    return Path(state) / "marimo" / "servers"


def preferred_port(root: Path = PROJECT_ROOT) -> int:
    """The port this project prefers. Same directory, same port, every time.

    A hash of the path rather than a counter: nothing has to be written down, and
    two projects only ever collide by chance, which the caller resolves by moving
    to the next free port.
    """
    digest = hashlib.sha256(str(root.resolve()).encode()).digest()
    return PORT_BASE + int.from_bytes(digest[:4], "big") % PORT_SPAN


def _process_cwd(pid: int) -> Path | None:
    """Working directory of a running process, or None if it cannot be read."""
    proc = Path(f"/proc/{pid}/cwd")
    if proc.exists():  # Linux
        try:
            return Path(os.readlink(proc)).resolve()
        except OSError:
            return None
    if not shutil.which("lsof"):  # macOS without lsof, or Windows
        return None
    try:
        out = subprocess.run(
            ["lsof", "-a", "-p", str(pid), "-d", "cwd", "-Fn"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    for line in out.stdout.splitlines():
        if line.startswith("n"):
            return Path(line[1:]).resolve()
    return None


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:  # someone else's process, but it exists
        return True
    return True


def _healthy(port: int, timeout: float = 2.0) -> bool:
    try:
        with urlopen(f"http://{HOST}:{port}/health", timeout=timeout) as response:
            return response.status == 200
    except (URLError, OSError, ValueError):
        return False


class Server(NamedTuple):
    pid: int
    port: int
    cwd: Path | None
    healthy: bool

    @property
    def url(self) -> str:
        return f"http://{HOST}:{self.port}"


def running_servers() -> list[Server]:
    """Every live marimo server this user is running, with its directory.

    Dead entries are left alone. Removing another project's stale file is the kind
    of shared-state edit that caused the original problem, and marimo cleans up
    after itself.
    """
    found: list[Server] = []
    directory = servers_dir()
    if not directory.is_dir():
        return found
    for path in sorted(directory.glob("*.json")):
        try:
            record: dict[str, Any] = json.loads(path.read_text())
            pid, port = int(record["pid"]), int(record["port"])
        except (OSError, ValueError, KeyError):
            continue
        if not _alive(pid):
            continue
        found.append(
            Server(pid=pid, port=port, cwd=_process_cwd(pid), healthy=_healthy(port))
        )
    return found


def server_here(root: Path = PROJECT_ROOT) -> Server | None:
    """The server serving this project, if there is one."""
    root = root.resolve()
    for server in running_servers():
        if server.cwd == root:
            return server
    return None


def _port_free(port: int) -> bool:
    with socket.socket() as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((HOST, port))
        except OSError:
            return False
    return True


def free_port(root: Path = PROJECT_ROOT) -> int:
    """This project's preferred port, or the next free one after it."""
    start = preferred_port(root)
    for offset in range(PORT_SPAN):
        port = PORT_BASE + (start - PORT_BASE + offset) % PORT_SPAN
        if _port_free(port):
            return port
    raise SystemExit(
        f"no free port in {PORT_BASE}-{PORT_BASE + PORT_SPAN - 1}. "
        "Stop a marimo server you are not using."
    )


def stop_here(root: Path = PROJECT_ROOT) -> Server | None:
    """Stop this project's server. Never signals another project's.

    Waits for the port to be released as well as the process to exit. A killed
    server can still hold its listening socket for a moment, and choosing a port
    in that window moved the project to the next one on every recovery.
    """
    server = server_here(root)
    if server is None:
        return None
    os.kill(server.pid, 15)
    for _ in range(50):  # up to 5s for a clean exit
        if not _alive(server.pid):
            break
        time.sleep(0.1)
    else:
        os.kill(server.pid, 9)
    for _ in range(30):  # then up to 3s for the socket
        if _port_free(server.port):
            break
        time.sleep(0.1)
    return server


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m petri.server",
        description="Start, find or stop the marimo server for this project.",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--status", action="store_true", help="report, change nothing")
    mode.add_argument("--url", action="store_true", help="print the base URL only")
    mode.add_argument("--stop", action="store_true", help="stop this project's server")
    args = parser.parse_args(argv)

    here = server_here()

    if args.url:
        print((here or Server(0, preferred_port(), None, False)).url)
        return 0

    if args.status:
        if here is None:
            print(f"no marimo server for {PROJECT_ROOT}")
            print(f"  `make nb` would start one on port {free_port()}")
            others = [s for s in running_servers() if s.cwd != PROJECT_ROOT.resolve()]
            for other in others:
                print(f"  (port {other.port} belongs to {other.cwd or 'unknown'})")
            return 1
        state = "running" if here.healthy else "NOT RESPONDING"
        print(f"{state}: {here.url}  (pid {here.pid}, {PROJECT_ROOT})")
        return 0

    if args.stop:
        stopped = stop_here()
        if stopped is None:
            print(f"no marimo server for {PROJECT_ROOT}; nothing to stop")
        else:
            print(f"stopped pid {stopped.pid} on port {stopped.port}")
        return 0

    # Default: make the server exist, then hand off to marimo.
    if here is not None and here.healthy:
        print(f"marimo is already running for this project: {here.url}")
        print(f"  pid {here.pid}. Open it, or `make nb-stop` to stop it.")
        return 0

    if here is not None:
        print(
            f"marimo for this project (pid {here.pid}, port {here.port}) is not "
            "responding on /health. Stopping it and starting a new one."
        )
        stop_here()

    port = free_port()
    if port != preferred_port():
        print(f"port {preferred_port()} is taken; using {port}")
    print(f"starting marimo for {PROJECT_ROOT} on http://{HOST}:{port}")
    # execvp replaces this process image, so anything still sitting in Python's
    # stdout buffer is discarded rather than written. Every message above was
    # lost when stdout was a file rather than a terminal.
    sys.stdout.flush()
    os.execvp(
        "marimo",
        [
            "marimo",
            "edit",
            "notebooks/",
            "--no-token",
            "--host",
            HOST,
            "--port",
            str(port),
        ],
    )


if __name__ == "__main__":
    sys.exit(main())
