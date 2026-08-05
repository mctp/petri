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
