"""End-to-end test of the write path.

The contract tests in test_provenance.py cover the kernel-free surface. Writing an
artifact needs a live marimo runtime, so this test runs the real entry points in
a subprocess: `make shared` executes the producer notebooks, `make check`
verifies every manifest.

It is safe to run against the repo. Writes are idempotent, so a run that changes
nothing rewrites nothing, and `make check` fails if it does.
"""

from __future__ import annotations

import json
import subprocess

import pytest

from petri.paths import PROJECT_ROOT, SHARED_DIR


def _make(target: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["make", target],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=600,
    )


@pytest.mark.slow
def test_make_shared_then_check_round_trips():
    shared = _make("shared")
    assert shared.returncode == 0, shared.stdout + shared.stderr
    assert "no problems" in shared.stdout, shared.stdout

    check = _make("check")
    assert check.returncode == 0, check.stdout + check.stderr


@pytest.mark.slow
def test_producer_writes_table_and_manifest_together():
    """A shared table without a manifest is the state the design forbids."""
    assert _make("shared").returncode == 0
    tables = sorted(SHARED_DIR.glob("*.csv"))
    assert tables, "make shared produced no table"
    for table in tables:
        manifest_path = table.with_suffix(".manifest.json")
        assert manifest_path.exists(), f"{table.name} has no manifest"
        manifest = json.loads(manifest_path.read_text())
        assert manifest["inputs"], f"{table.name} declares no inputs"
        assert any(o["filename"] == table.name for o in manifest["outputs"])


@pytest.mark.slow
def test_second_run_rewrites_nothing():
    """Idempotence: unchanged content must not produce a git diff."""
    assert _make("shared").returncode == 0
    before = {p: p.stat().st_mtime_ns for p in SHARED_DIR.glob("*") if p.is_file()}
    assert _make("shared").returncode == 0
    after = {p: p.stat().st_mtime_ns for p in SHARED_DIR.glob("*") if p.is_file()}
    changed = [str(p) for p in before if before[p] != after.get(p)]
    assert not changed, f"rewritten on an unchanged run: {changed}"


@pytest.mark.slow
def test_rebuilding_from_a_clone_rewrites_no_manifest():
    """The state every collaborator starts in: manifests committed, tables not.

    Recording an mtime made this rewrite every manifest, because a rebuilt table
    is byte-identical but newly stamped. The committed record has to be a
    function of the content, or it conflicts in git for no reason.
    """
    assert _make("shared").returncode == 0
    manifests = {p: p.read_bytes() for p in SHARED_DIR.glob("*.manifest.json")}
    assert manifests, "no shared manifests to compare"

    for table in SHARED_DIR.glob("*.csv"):
        table.unlink()  # gitignored, so a clone does not have them
    assert _make("shared").returncode == 0

    rewritten = [p.name for p, before in manifests.items() if p.read_bytes() != before]
    assert not rewritten, f"a byte-identical rebuild rewrote: {rewritten}"
