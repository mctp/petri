"""End-to-end test of the write path.

The contract tests in test_provenance.py cover the kernel-free surface. Writing an
artifact needs a live marimo runtime, so these run the real thing in a subprocess:
the worked example writes `data/shared/` and `data/preserved/`, and `make check`
verifies every manifest.

These require a project that `make init full` has populated, and they exercise the
example's R cells, so they need the renv library too. On a bare clone `notebooks/`
is empty and the whole module skips — that is the shipped state, not a failure.

A notebook run costs a few seconds, and five tests asking for their own runs cost
nine of them — the rest of the suite is under a second, so that was the whole
runtime. The `twice` fixture runs it two times for the module and snapshots the
tree after each, which is all any of these assertions needs; only the fresh-clone
test, whose setup deletes files first, runs it again.

It is safe to run against the repo. Writes are idempotent, so a run that changes
nothing rewrites nothing, and `make check` fails if it does.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from dataclasses import dataclass

import pytest

from petri.paths import PRESERVED_DIR, PROJECT_ROOT, SHARED_DIR

NOTEBOOK = PROJECT_ROOT / "notebooks/full_example.py"

pytestmark = [
    pytest.mark.slow,
    pytest.mark.skipif(
        not NOTEBOOK.exists(),
        reason="needs `make init full` — notebooks/ ships empty",
    ),
]


def _make(target: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["make", target],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=600,
    )


def _run_notebook() -> None:
    """Run the worked example headlessly, and fail the test if it errors.

    PYTHONPATH is what the Makefile exports: running a notebook as a script puts
    notebooks/ on sys.path rather than the repo root, so `import petri` and
    `import scripts` both need the root added back.
    """
    run = subprocess.run(
        ["uv", "run", "python", str(NOTEBOOK)],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=600,
        env={**os.environ, "PYTHONPATH": str(PROJECT_ROOT)},
    )
    assert run.returncode == 0, run.stdout + run.stderr


@dataclass(frozen=True)
class Snapshot:
    """What the tree looked like after one run."""

    shared_mtimes: dict[str, int]
    shared_manifests: dict[str, bytes]
    # Hashes, not mtimes: _write_if_changed leaves an unchanged file alone, so an
    # mtime comparison passes even when a render is unstable.
    preserved_digests: dict[str, str]


def _snapshot() -> Snapshot:
    return Snapshot(
        shared_mtimes={
            p.name: p.stat().st_mtime_ns for p in SHARED_DIR.glob("*") if p.is_file()
        },
        shared_manifests={
            p.name: p.read_bytes() for p in SHARED_DIR.glob("*.manifest.json")
        },
        preserved_digests={
            str(p.relative_to(PRESERVED_DIR)): hashlib.sha256(
                p.read_bytes()
            ).hexdigest()
            for p in sorted(PRESERVED_DIR.rglob("*"))
            if p.is_file() and p.name != "manifest.json"
        },
    )


@pytest.fixture(scope="module")
def twice() -> tuple[Snapshot, Snapshot]:
    """Run the notebook twice, snapshotting after each run."""
    _run_notebook()
    first = _snapshot()
    _run_notebook()
    return first, _snapshot()


def test_notebook_then_check_round_trips(twice):
    check = _make("check")
    assert check.returncode == 0, check.stdout + check.stderr
    assert "no problems" in check.stdout, check.stdout


def test_producer_writes_table_and_manifest_together(twice):
    """A shared table without a manifest is the state the design forbids."""
    tables = sorted(SHARED_DIR.glob("*.csv"))
    assert tables, "the notebook produced no table"
    for table in tables:
        manifest_path = table.with_suffix(".manifest.json")
        assert manifest_path.exists(), f"{table.name} has no manifest"
        manifest = json.loads(manifest_path.read_text())
        assert manifest["inputs"], f"{table.name} declares no inputs"
        assert any(o["filename"] == table.name for o in manifest["outputs"])


def test_second_run_rewrites_nothing(twice):
    """Idempotence: unchanged content must not produce a git diff."""
    first, second = twice
    changed = [
        name
        for name, mtime in first.shared_mtimes.items()
        if second.shared_mtimes.get(name) != mtime
    ]
    assert not changed, f"rewritten on an unchanged run: {changed}"


def test_preserved_outputs_are_byte_stable(twice):
    """A deliverable must render the same bytes twice.

    Only data/shared/ was covered here, and data/preserved/ is the half that git
    tracks wholesale — so an unseeded `sns.stripplot` shipped figures whose jitter
    moved on every run, and every re-run showed a binary diff.
    """
    first, second = twice
    assert first.preserved_digests, "the notebook preserved nothing"
    unstable = [
        name
        for name, digest in first.preserved_digests.items()
        if second.preserved_digests.get(name) != digest
    ]
    assert not unstable, f"re-render changed these bytes: {unstable}"


def test_rebuilding_from_a_clone_rewrites_no_manifest(twice):
    """The state every collaborator starts in: manifests present, tables not.

    Recording an mtime made this rewrite every manifest, because a rebuilt table
    is byte-identical but newly stamped. The committed record has to be a
    function of the content, or it conflicts in git for no reason.

    The only test that needs a third run: its setup deletes the tables first.
    """
    _, before = twice
    assert before.shared_manifests, "no shared manifests to compare"

    for table in SHARED_DIR.glob("*.csv"):
        table.unlink()  # gitignored, so a clone does not have them
    _run_notebook()

    rewritten = [
        name
        for name, data in before.shared_manifests.items()
        if (SHARED_DIR / name).read_bytes() != data
    ]
    assert not rewritten, f"a byte-identical rebuild rewrote: {rewritten}"
