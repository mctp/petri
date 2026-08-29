"""Contract tests for petri.outline.

An outline exists to keep an agent from reading a notebook whole. Every assertion
here is about that: it must be small, it must be readable without the file, and it
must not need a kernel.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from petri import outline as O
from petri.init import EXAMPLES_DIR

EXAMPLE_NOTEBOOK = EXAMPLES_DIR / "notebooks/full_example.py"


def _notebook(tmp_path: Path, body: str) -> Path:
    """A minimal marimo notebook file, written the way marimo writes one."""
    path = tmp_path / "nb.py"
    path.write_text(
        "import marimo\n\napp = marimo.App()\n\n" + textwrap.dedent(body).lstrip()
    )
    return path


def test_the_outline_is_orders_of_magnitude_smaller_than_the_file():
    """The whole point. 90 cells of a 332 KB notebook fit in single-digit KB."""
    text = O.outline(EXAMPLE_NOTEBOOK)
    assert len(text) < len(EXAMPLE_NOTEBOOK.read_text()) / 5


def test_the_outline_names_every_cell_once():
    """It is a table of contents, so nothing may be dropped from it."""
    from petri.provenance import _notebook_cells

    cells = _notebook_cells(EXAMPLE_NOTEBOOK)
    # One header line plus one line per cell.
    assert len(O.outline(EXAMPLE_NOTEBOOK).splitlines()) == len(cells) + 1


def test_a_cell_that_writes_an_artifact_is_marked(tmp_path):
    """The bundles are what a reader looks for first."""
    path = _notebook(
        tmp_path,
        """
        @app.cell
        def _():
            fig = draw()
            preserve_figure(fig, "psma_scatter", source_data=df)
            return

        @app.cell
        def _():
            save_shared(df, "cohort", inputs=[])
            return
        """,
    )
    text = O.outline(path)
    assert "[figure]" in text
    assert "[shared]" in text


def test_a_writer_named_in_a_comment_is_not_a_write(tmp_path):
    """A substring test would count this one. The outline parses instead."""
    path = _notebook(
        tmp_path,
        """
        @app.cell
        def _():
            # preserve_figure(fig, "later", source_data=df) — not yet
            x = 1
            return
        """,
    )
    assert "[figure]" not in O.outline(path)


def test_a_narrative_cell_shows_its_heading(tmp_path):
    """Which makes the outline a table of contents rather than a cell census."""
    path = _notebook(
        tmp_path,
        '''
        @app.cell
        def _():
            mo.md(
                """
                ---
                ## Phase 1: screening
                """
            )
            return
        ''',
    )
    assert "## Phase 1: screening" in O.outline(path)


def test_a_multiline_import_does_not_leak_its_continuation(tmp_path):
    """Reading "the first line" as text picked up `CACHE_DIR,` from an import."""
    path = _notebook(
        tmp_path,
        """
        @app.cell
        def _():
            from petri import (
                CACHE_DIR,
                save_shared,
            )
            df = load()
            return
        """,
    )
    row = O.outline(path).splitlines()[1]
    assert "CACHE_DIR" not in row
    assert "df = load()" in row


def test_a_cell_of_only_imports_says_so(tmp_path):
    path = _notebook(
        tmp_path,
        """
        @app.cell
        def _():
            import marimo as mo
            import polars as pl
            return
        """,
    )
    assert "(imports)" in O.outline(path).splitlines()[1]


def test_an_unnamed_cell_is_labelled_not_underscored(tmp_path):
    """marimo writes an unnamed cell as `_`; it cannot anchor an artifact."""
    path = _notebook(
        tmp_path,
        """
        @app.cell
        def _():
            x = 1
            return
        """,
    )
    assert "(unnamed)" in O.outline(path).splitlines()[1]


def test_a_cell_mid_edit_does_not_break_the_outline(tmp_path):
    """The rest of the outline is still worth having."""
    assert O._describe("df = (((") == ("", "")


def test_a_file_with_no_cells_is_rejected(tmp_path):
    path = tmp_path / "plain.py"
    path.write_text("x = 1\n")
    with pytest.raises(ValueError, match="no cells found"):
        O.outline(path)


def test_the_cli_reports_a_missing_notebook(capsys):
    assert O.main(["notebooks/no-such-notebook.py"]) == 1
    assert "no such notebook" in capsys.readouterr().err
