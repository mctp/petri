"""What a notebook contains, without reading the notebook.

A marimo notebook is a Python file, so the obvious way to see what is in one is
to read it. That is the most expensive call an agent can make in this project:
notebooks here run to hundreds of kilobytes, and a single read of the largest
costs tens of thousands of tokens that stay in the session for the rest of it.

The document is a list of cells, and what a reader needs first is that list —
each cell's name, its size, whether it writes an artifact, and the one line that
says what it does. That is two orders of magnitude smaller than the file, and it
is enough to choose which cell to look at. Pull that one body from the live
kernel with `ctx.cells["<name>"].code`.

The cells come from marimo's own loader, the same call check() uses to read cell
names, and each cell body is then parsed with `ast` to describe it. Both read the
file without executing it, so this needs no kernel and no running server, and it
is safe on a notebook someone is editing.

    make nb-outline NB=notebooks/<name>.py
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

from .paths import PROJECT_ROOT
from .provenance import UNNAMED_CELL, _notebook_cells

# What marks a cell as the anchor of an artifact. A bundle is named for its cell,
# so these are the cells a reader looks for first: they are where the deliverables
# and the shared tables come from.
_WRITERS = {
    "preserve_figure": "figure",
    "preserve_table": "table",
    "preserve_file": "file",
    "save_shared": "shared",
}


def _markdown_gist(stmt: ast.stmt) -> str:
    """The first heading or line of a narrative cell's markdown.

    A narrative cell's one useful line is inside the string, not in the call
    around it: the mo.md line itself says nothing, while `## PARS ubiquitylation`
    says what section this is. That makes the outline a table of contents.
    """
    for node in ast.walk(stmt):
        if isinstance(node, ast.Call) and getattr(node.func, "attr", None) == "md":
            for arg in node.args:
                if not (isinstance(arg, ast.Constant) and isinstance(arg.value, str)):
                    continue
                lines = [ln.strip() for ln in arg.value.splitlines() if ln.strip()]
                # A heading names the section. Failing that, the first line with
                # a word in it — markdown often opens on a `---` rule.
                for line in lines:
                    if line.startswith("#"):
                        return line
                for line in lines:
                    if any(char.isalnum() for char in line):
                        return line
    return ""


def _describe(code: str, width: int = 46) -> tuple[str, str]:
    """Return (what the cell writes, the one line that says what it does).

    Both come from one parse of the cell. A substring test for the writers would
    count one named in a comment or a docstring, and reading "the first line" as
    text picks up the continuation of a multi-line import.
    """
    try:
        tree = ast.parse(code)
    except SyntaxError:
        # A cell mid-edit does not parse. Say nothing rather than guess.
        return "", ""

    written: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
        if name in _WRITERS and _WRITERS[name] not in written:
            written.append(_WRITERS[name])

    # A cell of nothing but imports has no statement to summarise, and that is
    # worth saying: it is the setup cell.
    summary = "(imports)" if tree.body else ""
    for stmt in tree.body:
        if isinstance(stmt, (ast.Import, ast.ImportFrom)):
            continue
        # A docstring, not the statement that matters.
        if (
            isinstance(stmt, ast.Expr)
            and isinstance(stmt.value, ast.Constant)
            and isinstance(stmt.value.value, str)
        ):
            continue
        source = _markdown_gist(stmt) or (ast.get_source_segment(code, stmt) or "")
        candidate = source.splitlines()[0].strip() if source else ""
        if candidate:
            summary = candidate
            break
    if len(summary) > width:
        summary = summary[: width - 1] + "…"
    return ",".join(written), summary


def _display(path: Path) -> str:
    """The shortest honest name for the file.

    A path under the project reads better relative to it. One outside — a notebook
    somewhere else, a temporary file — has no relative form, and asking for one
    raises rather than degrading, so ask carefully.
    """
    try:
        return str(path.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def outline(path: Path) -> str:
    """One line per cell: position, name, length, what it writes, what it does."""
    cells = _notebook_cells(path)
    if not cells:
        raise ValueError(f"no cells found in {path} — is it a marimo notebook?")

    total = len(path.read_text().splitlines())
    header = f"{_display(path)} — {len(cells)} cells, {total} lines"
    rows = [header]
    for position, (name, code) in enumerate(cells, start=1):
        writes, summary = _describe(code)
        # marimo writes an unnamed cell as UNNAMED_CELL. It cannot anchor an
        # artifact and cannot be addressed by name, so say so rather than print
        # the underscore.
        label = "(unnamed)" if not name or name == UNNAMED_CELL else name
        rows.append(
            f"{position:>4} {label:<34} {len(code.splitlines()):>4}L "
            f"{('[' + writes + ']') if writes else '':<10} {summary}"
        )
    return "\n".join(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m petri.outline",
        description="List a notebook's cells without reading the notebook.",
    )
    parser.add_argument("notebook", type=Path)
    args = parser.parse_args(argv)

    path = (
        args.notebook if args.notebook.is_absolute() else PROJECT_ROOT / args.notebook
    )
    if not path.exists():
        print(f"no such notebook: {args.notebook}", file=sys.stderr)
        return 1
    try:
        print(outline(path))
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
