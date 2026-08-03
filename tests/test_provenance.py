"""Contract tests for petri.provenance.

These pin the decisions that documentation asserts, so a future edit that
contradicts `docs/architecture.md` or `AGENTS.md` fails here rather than drifting
quietly. Several of them encode bugs that already happened once — the float
precision trap, the trailing-newline hash mismatch, the unnamed-cell collapse.

Scope is the kernel-free surface. The write path needs a live marimo runtime and
is covered by test_write_path.py.
"""

from __future__ import annotations

import inspect
import io
import json

import polars as pl
import pytest

import petri
from petri import provenance as A
from petri.paths import PROJECT_ROOT

# --- the CSV standard --------------------------------------------------------


def test_csv_does_not_pin_float_precision():
    """Pinning float_precision renders 1e-300 as 0.000000000000.

    In a repo full of p-values that is silent data corruption, not a formatting
    preference. Polars' default is shortest-round-trippable repr.
    """
    assert "float_precision" not in A.CSV_OPTS
    assert "float_scientific" not in A.CSV_OPTS


def test_tiny_floats_survive_the_csv_round_trip():
    df = pl.DataFrame({"p": [1e-300, 4.2e-8, 0.1 + 0.2]})
    text = A._csv_bytes(df).decode()
    assert "1e-300" in text
    restored = pl.read_csv(io.StringIO(text))
    assert restored["p"].to_list() == df["p"].to_list()


def test_csv_pins_the_ambiguous_settings():
    assert A.CSV_OPTS["line_terminator"] == "\n"
    assert A.CSV_OPTS["include_bom"] is False
    assert A.CSV_OPTS["include_header"] is True
    assert A.CSV_OPTS["date_format"] == "%Y-%m-%d"


def test_csv_rejects_non_polars_input():
    with pytest.raises(A.ArtifactError, match="polars DataFrame"):
        A._csv_bytes({"x": [1]})


def test_schema_round_trips_dtypes_through_csv():
    """shared/ is CSV so it stays greppable; the schema restores what CSV drops."""
    df = pl.DataFrame({"a": [1], "b": ["x"], "c": [1.5], "d": [True]})
    schema = A._schema_of(df)
    restored = pl.read_csv(
        io.StringIO(A._csv_bytes(df).decode()),
        schema_overrides=A._schema_overrides(schema),
    )
    assert restored.schema == df.schema


def test_container_dtypes_are_skipped_not_guessed():
    """A bare pl.List is not a usable override; inference is the safe fallback."""
    assert A._schema_overrides({"x": "List(Int64)"}) == {}
    assert A._schema_overrides({"x": "Float64"}) == {"x": pl.Float64}


# --- identity and hashing ----------------------------------------------------


def test_code_hash_ignores_surrounding_whitespace():
    """The kernel reports cell code with a trailing newline; the file does not.

    Hashing raw text made every artifact look stale the moment it was written.
    """
    assert A._code_hash("x = 1\n") == A._code_hash("x = 1")
    assert A._code_hash("x = 1") != A._code_hash("x = 2")


def test_scratch_cell_id_matches_marimo():
    from marimo._runtime.scratch import SCRATCH_CELL_ID

    assert A.SCRATCH_CELL_ID == SCRATCH_CELL_ID


def test_notebook_cells_returns_a_list_not_a_dict():
    """marimo names every unnamed cell `_`.

    A dict keyed by name holds one of them and drops the rest, which left the
    shared-producer scan searching an almost empty map.
    """
    cells = A._notebook_cells(PROJECT_ROOT / "notebooks/coding_patterns.py")
    assert isinstance(cells, list)
    unnamed = [n for n, _ in cells if n == A.UNNAMED_CELL]
    assert len(unnamed) > 1, "fixture should contain several unnamed cells"
    assert any(n == "pattern8_batch_effect" for n, _ in cells)


# --- code dependencies -------------------------------------------------------


def test_code_deps_records_project_local_imports():
    import processing.measurements  # noqa: F401  (must be in sys.modules)

    deps = A._code_deps("from processing.measurements import summarize_batches")
    assert [d["module"] for d in deps] == ["processing.measurements"]
    assert deps[0]["path"] == "processing/measurements.py"


def test_code_deps_excludes_the_template_and_third_party():
    """petri/ is versioned separately; hashing it would stale every artifact."""
    deps = A._code_deps("import polars\nfrom petri import save_shared")
    assert deps == []


def test_code_deps_survives_unparsable_code():
    assert A._code_deps("this is not python (") == []


# --- absences by design ------------------------------------------------------


@pytest.mark.parametrize("name", ["load_preserved", "load_artifact", "save_external"])
def test_absences_are_load_bearing(name):
    """Artifacts are terminal and external/ is read-only.

    The absence of a convenient loader is what keeps deliverables from quietly
    becoming interfaces.
    """
    assert name not in petri.__all__
    assert not hasattr(petri, name)


def test_preserved_path_exists_for_looking():
    assert "preserved_path" in petri.__all__


# --- required arguments encode design decisions ------------------------------


def test_save_shared_requires_declared_inputs():
    param = inspect.signature(A.save_shared).parameters["inputs"]
    assert param.default is inspect.Parameter.empty


def test_preserve_figure_requires_source_data():
    param = inspect.signature(A.preserve_figure).parameters["source_data"]
    assert param.default is inspect.Parameter.empty


@pytest.mark.parametrize("fn", [A.preserve_figure, A.preserve_table, A.preserve_file])
def test_preserve_takes_name_as_second_positional(fn):
    assert list(inspect.signature(fn).parameters)[1] == "name"


# --- figure determinism ------------------------------------------------------


def test_figure_metadata_is_stripped():
    """matplotlib stamps a PDF creation date and a PNG Software tag.

    Left in, every re-run rewrites identical figures and dirties git.
    """
    assert A._FIG_METADATA["pdf"] == {"CreationDate": None}
    assert A._FIG_METADATA["png"] == {"Software": None}


# --- guards ------------------------------------------------------------------


def test_writers_raise_without_a_marimo_runtime():
    df = pl.DataFrame({"x": [1]})
    with pytest.raises(A.ArtifactError, match="runtime context"):
        A.save_shared(df, "t", inputs=[])
    with pytest.raises(A.ArtifactError, match="runtime context"):
        A.preserve_table(df, "t")


def test_missing_declared_input_is_rejected():
    with pytest.raises(A.ArtifactError, match="does not exist"):
        A._describe_input(PROJECT_ROOT / "external/definitely-not-here.csv")


def test_guarded_failure_leaves_no_partial_write(tmp_path):
    """Identity and inputs resolve before anything is written.

    Otherwise a scratchpad call would leave an unprovenanced table in shared/.
    """
    before = set(A.SHARED_DIR.glob("*"))
    with pytest.raises(A.ArtifactError):
        A.save_shared(pl.DataFrame({"x": [1]}), "should-not-appear", inputs=[])
    assert set(A.SHARED_DIR.glob("*")) == before


# --- report ------------------------------------------------------------------


def test_report_separates_errors_from_warnings():
    report = A.CheckReport(
        problems=[
            {"artifact": "a", "severity": "error", "message": "boom"},
            {"artifact": "b", "severity": "warning", "message": "meh"},
        ],
        checked=2,
    )
    assert report.ok is False
    assert len(report.errors) == 1 and len(report.warnings) == 1
    assert A.CheckReport(problems=[], checked=0).ok is True


def test_repo_artifacts_verify():
    """The committed artifacts must match their manifests."""
    report = A.check()
    assert report.ok, str(report)


# --- new-behaviour contracts -------------------------------------------------


def test_manifest_version_is_read_not_just_written(tmp_path):
    """An unknown schema must fail loudly, not be read as version 1."""
    future = tmp_path / "x.manifest.json"
    future.write_text(json.dumps({"manifest_version": A.MANIFEST_VERSION + 1}))
    with pytest.raises(A.ArtifactError, match="manifest_version"):
        A._load_manifest(future)


def test_output_entry_does_not_assume_index_zero():
    manifest = {
        "outputs": [
            {"filename": "figure-source.csv", "sha256": "aaa"},
            {"filename": "table.csv", "sha256": "bbb"},
        ]
    }
    assert A._output_entry(manifest, "table.csv")["sha256"] == "bbb"
    assert A._output_entry(manifest, "absent.csv") is None


def test_every_default_figure_format_has_a_timestamp_key():
    """A format with no suppression key writes a new timestamp on every run."""
    defaults = inspect.signature(A.preserve_figure).parameters["formats"].default
    for fmt in defaults:
        assert fmt in A._FIG_METADATA


def test_unknown_figure_format_is_rejected_before_any_write():
    df = pl.DataFrame({"x": [1]})
    with pytest.raises(A.ArtifactError, match="timestamp-suppression"):
        A.preserve_figure(object(), "n", source_data=df, formats=("eps",))


def test_str_src_is_content_not_a_path():
    """A str is always content. Copying a file needs Path(...)."""
    with pytest.raises(A.ArtifactError, match="filename is required"):
        A.preserve_file("README.md", "n")


def test_missing_file_src_is_rejected_before_any_write():
    with pytest.raises(A.ArtifactError, match="does not exist"):
        A.preserve_file(PROJECT_ROOT / "no-such-file.bin", "n")


def test_shared_path_takes_a_suffix():
    """save_shared writes CSV today; other formats need the suffix passed."""
    assert A.shared_path("x").name == "x.csv"
    assert A.shared_path("x", ".parquet").name == "x.parquet"
    assert A.shared_path("x", "parquet").name == "x.parquet"


def test_list_shared_reads_the_recorded_filename():
    """Rebuilding the path would assume .csv forever."""
    for entry in A.list_shared():
        assert entry["path"], entry
        assert entry["path"].startswith("shared/")
