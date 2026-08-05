"""init.py — populate an empty project from `petri/examples/`.

The user's folders ship empty. `notebooks/`, `scripts/` and the four `data/`
directories hold nothing but a `.gitkeep` in a fresh clone, so nothing has to be
deleted before real work starts. This module copies the template's examples into
them on request:

    make init            the three standalone notebooks
    make init minimal    the same, named
    make init full       adds full_example.py, scripts/ and the data it reads

Two rules make the copy safe to run against a project that already has work in
it. Nothing is overwritten unless `--force` is passed, and every file is copied
with `shutil.copy2`, byte for byte.

Byte-exactness is not tidiness. A manifest records the sha256 of every module
the producing cell imported, and `check()` reports a mismatch as an error, not a
warning. Rewriting one line of a module on the way in would make the shipped
manifests fail verification the moment they were installed.

That is also why a set is closed under its own inputs. `full` ships the shared
tables *and* their manifests *and* the preserved bundles, because a preserved
artifact declares the shared table it was built from as an input: a set that
installed the deliverable without that table would not verify.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from .paths import PROJECT_ROOT

EXAMPLES_DIR = Path(__file__).resolve().parent / "examples"

# Each entry is a path relative to EXAMPLES_DIR, and lands at the same path
# relative to PROJECT_ROOT. The layout inside petri/examples/ mirrors the project
# root exactly, so there is no mapping table to keep in sync.
MINIMAL: tuple[str, ...] = (
    "notebooks/blank.py",
    "notebooks/py_example.py",
    "notebooks/r_example.py",
)

FULL_ONLY: tuple[str, ...] = (
    "notebooks/full_example.py",
    "scripts/__init__.py",
    "scripts/measurements.py",
    "data/external/example_measurements.csv",
    "data/shared/batch-stats.csv",
    "data/shared/batch-stats.manifest.json",
    "data/shared/measurements-ranked.csv",
    "data/shared/measurements-ranked.manifest.json",
    "data/preserved/full_example/pattern6_batch_effect/figure-source.csv",
    "data/preserved/full_example/pattern6_batch_effect/figure.pdf",
    "data/preserved/full_example/pattern6_batch_effect/figure.png",
    "data/preserved/full_example/pattern6_batch_effect/manifest.json",
    "data/preserved/full_example/pattern7_batch_table/manifest.json",
    "data/preserved/full_example/pattern7_batch_table/params.json",
    "data/preserved/full_example/pattern7_batch_table/table.csv",
)

SETS: dict[str, tuple[str, ...]] = {
    "minimal": MINIMAL,
    "full": MINIMAL + FULL_ONLY,
}

DEFAULT_SET = "minimal"


def files_for(names: list[str]) -> list[str]:
    """Resolve set names to a de-duplicated file list, order preserved.

    `full` already contains `minimal`, so asking for both is not an error.
    """
    if not names:
        names = [DEFAULT_SET]
    unknown = [n for n in names if n not in SETS]
    if unknown:
        raise SystemExit(
            f"unknown set: {', '.join(unknown)} (choose from {', '.join(sorted(SETS))})"
        )
    seen: dict[str, None] = {}
    for name in names:
        for relpath in SETS[name]:
            seen[relpath] = None
    return list(seen)


def install(
    relpaths: list[str], *, force: bool = False, dry_run: bool = False
) -> tuple[list[str], list[str]]:
    """Copy each file into the project. Returns (written, skipped)."""
    written: list[str] = []
    skipped: list[str] = []

    for relpath in relpaths:
        src = EXAMPLES_DIR / relpath
        dst = PROJECT_ROOT / relpath
        if not src.is_file():
            raise SystemExit(f"missing from petri/examples/: {relpath}")
        if dst.exists() and not force:
            skipped.append(relpath)
            continue
        if not dry_run:
            dst.parent.mkdir(parents=True, exist_ok=True)
            # copy2, not copy: a manifest pins the sha256 of what it imported.
            shutil.copy2(src, dst)
        written.append(relpath)

    return written, skipped


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m petri.init",
        description="Populate notebooks/, scripts/ and data/ from petri/examples/.",
    )
    parser.add_argument(
        "sets",
        nargs="*",
        metavar="SET",
        help=f"one or more of: {', '.join(sorted(SETS))} (default: {DEFAULT_SET})",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="overwrite files that already exist",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="report what would be written without writing it",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="list the available sets and their contents",
    )
    args = parser.parse_args(argv)

    if args.list:
        for name in sorted(SETS):
            print(f"{name}:")
            for relpath in SETS[name]:
                print(f"  {relpath}")
        return 0

    relpaths = files_for(args.sets)
    written, skipped = install(relpaths, force=args.force, dry_run=args.dry_run)

    tag = "would write" if args.dry_run else "wrote"
    summary = "would be written" if args.dry_run else "written"
    for relpath in written:
        print(f"  {tag}  {relpath}")
    for relpath in skipped:
        print(f"  exists  {relpath}")

    print()
    if skipped and not args.force:
        print(
            f"{len(written)} file(s) {summary}, {len(skipped)} left alone. "
            "Pass --force to overwrite."
        )
    else:
        print(f"{len(written)} file(s) {summary}.")

    if written and not args.dry_run:
        print()
        print("next:  make check   # verify the installed provenance")
        print("       make nb      # start marimo on notebooks/")

    return 0


if __name__ == "__main__":
    sys.exit(main())
