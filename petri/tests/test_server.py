"""Contract tests for petri.server.

One machine runs many petri projects. These pin the two properties that keeps
them from interfering: a port belongs to a directory, and a stop signal reaches
only the server for the current project.

The bug these prevent: `make nb` used marimo's default port for every project, and
the documented recovery was `pkill -f "marimo edit"`, which stopped every marimo on
the machine. An agent working in one project killed the server another was using.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from petri import server as S
from petri.paths import PROJECT_ROOT

# --- ports belong to directories ---------------------------------------------


def test_port_is_stable_for_a_directory():
    """Restarting must land on the same port, or a bookmarked URL breaks."""
    assert S.preferred_port(PROJECT_ROOT) == S.preferred_port(PROJECT_ROOT)


def test_port_does_not_depend_on_how_the_path_is_spelled():
    assert S.preferred_port(PROJECT_ROOT) == S.preferred_port(
        PROJECT_ROOT / "petri" / ".."
    )


def test_different_directories_get_different_ports():
    """Deterministic, so this asserts the real spread rather than a probability.

    A collision is handled — free_port() moves on — but it costs the project its
    preferred port, so the span is wide enough to make one rare. Twenty paths in a
    span of 1000 collide about 2% of the time by birthday odds; these twenty do not
    collide at all, and if a change to the hash makes them, that is worth seeing.
    """
    ports = {S.preferred_port(Path(f"/tmp/project-{i}")) for i in range(20)}
    assert len(ports) == 20, f"collisions among 20 paths: {sorted(ports)}"


def test_port_stays_in_the_declared_range():
    for i in range(200):
        port = S.preferred_port(Path(f"/tmp/p{i}"))
        assert S.PORT_BASE <= port < S.PORT_BASE + S.PORT_SPAN


# --- identity is the working directory ---------------------------------------


def _fake_registry(monkeypatch, tmp_path, entries):
    """Point petri.server at a registry we control, and stub liveness."""
    directory = tmp_path / "servers"
    directory.mkdir()
    import json

    cwds = {}
    for pid, port, cwd in entries:
        (directory / f"127.0.0.1_{port}.json").write_text(
            json.dumps({"pid": pid, "host": "127.0.0.1", "port": port})
        )
        cwds[pid] = Path(cwd)
    monkeypatch.setattr(S, "servers_dir", lambda: directory)
    monkeypatch.setattr(S, "_alive", lambda pid: True)
    monkeypatch.setattr(S, "_healthy", lambda port, timeout=2.0: True)
    monkeypatch.setattr(S, "_process_cwd", lambda pid: cwds.get(pid))


def test_server_here_ignores_another_project(monkeypatch, tmp_path):
    """The whole point: a server in another directory is not ours."""
    _fake_registry(
        monkeypatch,
        tmp_path,
        [(111, 2718, "/other/project"), (222, 2754, str(PROJECT_ROOT))],
    )
    found = S.server_here(PROJECT_ROOT)
    assert found is not None
    assert found.pid == 222, "picked the other project's server"


def test_server_here_is_none_when_only_others_run(monkeypatch, tmp_path):
    """`make nb` must start a server rather than adopt someone else's."""
    _fake_registry(monkeypatch, tmp_path, [(111, 2718, "/other/project")])
    assert S.server_here(PROJECT_ROOT) is None


def test_stop_here_signals_nothing_when_only_others_run(monkeypatch, tmp_path):
    """`pkill -f "marimo edit"` is what this replaces."""
    _fake_registry(monkeypatch, tmp_path, [(111, 2718, "/other/project")])
    signalled = []
    monkeypatch.setattr(S.os, "kill", lambda pid, sig: signalled.append((pid, sig)))
    assert S.stop_here(PROJECT_ROOT) is None
    assert signalled == [], f"signalled another project: {signalled}"


def test_stop_here_signals_only_our_pid(monkeypatch, tmp_path):
    _fake_registry(
        monkeypatch,
        tmp_path,
        [(111, 2718, "/other/project"), (222, 2754, str(PROJECT_ROOT))],
    )
    signalled = []
    monkeypatch.setattr(S.os, "kill", lambda pid, sig: signalled.append((pid, sig)))
    monkeypatch.setattr(S, "_port_free", lambda port: True)
    # Alive for discovery, gone once signalled — patching it False outright would
    # hide the server from discovery and pass for the wrong reason.
    monkeypatch.setattr(S, "_alive", lambda pid: not signalled)
    stopped = S.stop_here(PROJECT_ROOT)
    assert stopped is not None and stopped.pid == 222
    assert {pid for pid, _ in signalled} == {222}


def test_a_server_with_an_unreadable_cwd_is_not_claimed(monkeypatch, tmp_path):
    """Windows, or a process owned by another user. Unknown is not ours."""
    _fake_registry(monkeypatch, tmp_path, [(111, 2718, "/other")])
    monkeypatch.setattr(S, "_process_cwd", lambda pid: None)
    assert S.server_here(PROJECT_ROOT) is None


def test_dead_entries_are_skipped_and_left_in_place(monkeypatch, tmp_path):
    """Deleting another project's stale file is the shared-state edit to avoid."""
    _fake_registry(monkeypatch, tmp_path, [(111, 2718, str(PROJECT_ROOT))])
    monkeypatch.setattr(S, "_alive", lambda pid: False)
    assert S.running_servers() == []
    assert list((tmp_path / "servers").glob("*.json")), "removed a registry file"


def test_a_corrupt_registry_entry_is_skipped(monkeypatch, tmp_path):
    directory = tmp_path / "servers"
    directory.mkdir()
    (directory / "bad.json").write_text("{not json")
    monkeypatch.setattr(S, "servers_dir", lambda: directory)
    assert S.running_servers() == []


# --- free_port ---------------------------------------------------------------


def test_free_port_prefers_the_projects_own_port(monkeypatch):
    monkeypatch.setattr(S, "_port_free", lambda port: True)
    assert S.free_port(PROJECT_ROOT) == S.preferred_port(PROJECT_ROOT)


def test_free_port_moves_on_when_the_preferred_one_is_taken(monkeypatch):
    """A hash collision with another project must not block startup."""
    taken = S.preferred_port(PROJECT_ROOT)
    monkeypatch.setattr(S, "_port_free", lambda port: port != taken)
    assert S.free_port(PROJECT_ROOT) == taken + 1


def test_free_port_raises_rather_than_looping_forever(monkeypatch):
    monkeypatch.setattr(S, "_port_free", lambda port: False)
    with pytest.raises(SystemExit, match="no free port"):
        S.free_port(PROJECT_ROOT)


# --- daemon mode -------------------------------------------------------------
#
# `--daemon` is what an agent runs, because a foreground `make nb` blocks a
# synchronous tool call until it times out. It therefore has to be honest about
# failure: a wrong exit code sends the caller into a restart loop against a
# server that is fine, or leaves it talking to one that is not its own.

DAEMON_PID = 12345


class FakePopen:
    """A child that stays up. `exit_code` makes it die on the first poll."""

    pid = DAEMON_PID

    def __init__(self, exit_code: int | None = None):
        self.returncode = exit_code

    def poll(self):
        return self.returncode


def _fast_daemon(monkeypatch, tmp_path):
    """Shrink the wait, and keep marimo.log out of the real project root."""
    monkeypatch.setattr(S, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(S, "DAEMON_INTERVAL", 0.001)
    monkeypatch.setattr(S, "DAEMON_TIMEOUT", 0.01)
    monkeypatch.setattr(S, "_port_free", lambda port: True)


def _spawns(monkeypatch, proc):
    """Record the Popen call so the test can assert on what was launched."""
    calls: list[tuple[tuple, dict]] = []

    def fake_popen(*args, **kwargs):
        calls.append((args, kwargs))
        return proc

    monkeypatch.setattr(S.subprocess, "Popen", fake_popen)
    return calls


def _server_appears(monkeypatch, later):
    """None on the first call, `later` on every call after.

    main() asks server_here() once to decide whether to start anything at all,
    and start_daemon() asks again to confirm what it started. A fixture that
    answers the first question with a live server never reaches the daemon path.
    """
    calls = {"n": 0}

    def fake(root=PROJECT_ROOT):
        calls["n"] += 1
        return None if calls["n"] == 1 else later

    monkeypatch.setattr(S, "server_here", fake)


def test_daemon_does_not_start_a_second_server(monkeypatch, capsys):
    """Already running here: report it and start nothing."""
    running = S.Server(999, 2718, PROJECT_ROOT, True)
    monkeypatch.setattr(S, "server_here", lambda root=PROJECT_ROOT: running)
    monkeypatch.setattr(
        S.subprocess,
        "Popen",
        lambda *a, **k: pytest.fail("started a second server"),
    )

    assert S.main(["--daemon"]) == 0
    assert "marimo is already running" in capsys.readouterr().out


def test_daemon_launches_marimo_detached_in_this_project(monkeypatch, tmp_path):
    """The command, the directory and the detachment are the contract.

    Without this, a lost --no-token or a wrong --port passes every other test:
    the old version asserted only on stdout.
    """
    _fast_daemon(monkeypatch, tmp_path)
    proc = FakePopen()
    calls = _spawns(monkeypatch, proc)
    monkeypatch.setattr(S, "_healthy", lambda port, timeout=2.0: True)
    _server_appears(monkeypatch, S.Server(proc.pid, 2718, tmp_path, True))

    assert S.main(["--daemon"]) == 0

    (argv,), kwargs = calls[0]
    assert argv == S.marimo_argv(S.free_port())
    assert "--no-token" in argv
    assert kwargs["cwd"] == str(tmp_path)
    # Without a new session the server dies with the shell that spawned it.
    assert kwargs["start_new_session"] is True


def test_daemon_reports_the_url_of_the_server_it_started(monkeypatch, tmp_path, capsys):
    _fast_daemon(monkeypatch, tmp_path)
    proc = FakePopen()
    _spawns(monkeypatch, proc)
    monkeypatch.setattr(S, "_healthy", lambda port, timeout=2.0: True)
    _server_appears(monkeypatch, S.Server(proc.pid, 2718, tmp_path, True))

    assert S.main(["--daemon"]) == 0
    out = capsys.readouterr().out
    assert "started marimo" in out
    assert str(DAEMON_PID) in out


def test_daemon_fails_when_the_child_exits(monkeypatch, tmp_path, capsys):
    """A dead child must not read as a running server."""
    _fast_daemon(monkeypatch, tmp_path)
    _spawns(monkeypatch, FakePopen(exit_code=1))
    monkeypatch.setattr(S, "_healthy", lambda port, timeout=2.0: True)
    _server_appears(monkeypatch, None)

    assert S.main(["--daemon"]) == 1
    assert "exited immediately" in capsys.readouterr().out


def test_daemon_does_not_claim_a_server_it_does_not_own(monkeypatch, tmp_path, capsys):
    """Health on the port is not proof of ownership.

    free_port() releases its probe socket before the child binds, so another
    project can take the port in between. Identifying a server by its port is the
    confusion this whole module exists to avoid, so a foreign pid answering
    /health must time out rather than report success.
    """
    _fast_daemon(monkeypatch, tmp_path)
    _spawns(monkeypatch, FakePopen())
    monkeypatch.setattr(S, "_healthy", lambda port, timeout=2.0: True)
    _server_appears(monkeypatch, S.Server(777, 2718, tmp_path, True))

    assert S.main(["--daemon"]) == 1
    assert "timed out" in capsys.readouterr().out


def test_daemon_times_out_when_the_server_never_answers(monkeypatch, tmp_path, capsys):
    _fast_daemon(monkeypatch, tmp_path)
    _spawns(monkeypatch, FakePopen())
    monkeypatch.setattr(S, "_healthy", lambda port, timeout=2.0: False)
    _server_appears(monkeypatch, None)

    assert S.main(["--daemon"]) == 1
    assert "timed out" in capsys.readouterr().out


def test_daemon_explains_a_missing_marimo(monkeypatch, tmp_path, capsys):
    """No .venv: a sentence, not a FileNotFoundError traceback."""
    _fast_daemon(monkeypatch, tmp_path)
    _server_appears(monkeypatch, None)

    def missing(*args, **kwargs):
        raise FileNotFoundError(2, "No such file or directory: 'marimo'")

    monkeypatch.setattr(S.subprocess, "Popen", missing)

    assert S.main(["--daemon"]) == 1
    assert "make setup" in capsys.readouterr().out


def test_both_start_paths_use_one_command(monkeypatch):
    """marimo_argv is the single definition the exec path and --daemon share."""
    argv = S.marimo_argv(4242)
    assert argv[:3] == ["marimo", "edit", "notebooks/"]
    assert argv[argv.index("--port") + 1] == "4242"
    assert argv[argv.index("--host") + 1] == S.HOST
