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
import os
from pathlib import Path

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
    """A bare pl.List is not a usable override; skipping it is what rejects it."""
    assert A._schema_overrides({"x": "List(Int64)"}) == {}
    assert A._schema_overrides({"x": "Float64"}) == {"x": pl.Float64}


@pytest.mark.parametrize(
    ("series", "restorable"),
    [
        (pl.Series([1]), True),
        (pl.Series([1.5]), True),
        (pl.Series(["a"]), True),
        (pl.Series([True]), True),
        (pl.Series([1]).cast(pl.Date), True),
        (pl.Series([1]).cast(pl.Time), True),
        (pl.Series([1]).cast(pl.Datetime("us")), True),
        (pl.Series(["a"], dtype=pl.Categorical), True),
        (pl.Series([1]).cast(pl.Datetime("ms")), False),  # time unit not recorded
        (
            pl.Series([1]).cast(pl.Datetime("us", "UTC")),
            False,
        ),  # time zone not recorded
        (pl.Series(["a"], dtype=pl.Enum(["a"])), False),  # categories not recorded
        (pl.Series(["1.2"]).str.to_decimal(), False),  # precision not recorded
    ],
)
def test_unrestorable_columns_agrees_with_the_actual_round_trip(series, restorable):
    """save_shared must accept exactly what load_shared can give back.

    Publishing a dtype the schema record cannot express left a table that
    load_shared() raised on, or returned with the time zone silently dropped.
    """
    df = pl.DataFrame({"x": series})
    assert (A._unrestorable_columns(df) == []) is restorable

    try:
        back = pl.read_csv(
            io.StringIO(A._csv_bytes(df).decode()),
            schema_overrides=A._schema_overrides(A._schema_of(df)),
        )
        round_trips = back.schema == df.schema
    except Exception:
        round_trips = False
    assert round_trips is restorable, "the rule and the round trip disagree"


def test_save_shared_rejects_a_dtype_it_cannot_give_back():
    """The rejection happens before anything needs a kernel or a write."""
    df = pl.DataFrame({"t": [1]}).cast({"t": pl.Datetime("us", "UTC")})
    with pytest.raises(A.ArtifactError, match="cannot restore"):
        A.save_shared(df, "tz-table", inputs=[])


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
    paths = {d["path"] for d in deps}
    assert "processing/measurements.py" in paths
    # The package __init__ runs when a submodule is imported, so an edit there
    # changes the result too.
    assert "processing/__init__.py" in paths


def test_code_deps_follows_from_package_import_submodule():
    """`from pkg import mod` names a submodule, not an attribute.

    Recording only `pkg` hashed processing/__init__.py and left the module that
    did the work unhashed, so editing it staled nothing.
    """
    import processing.measurements  # noqa: F401

    deps = A._code_deps("from processing import measurements")
    assert "processing/measurements.py" in {d["path"] for d in deps}


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


# --- the manifest is a function of content -----------------------------------


def test_outputs_record_only_content_derived_fields():
    """An mtime here made every fresh clone rewrite the manifest.

    shared/ ships its manifests without the tables, so a rebuilt table is
    byte-identical but newly stamped, and the committed record changed for
    everyone who cloned.
    """
    for manifest_path in A.SHARED_DIR.glob("*.manifest.json"):
        for entry in json.loads(manifest_path.read_text())["outputs"]:
            assert set(entry) == {"filename", "sha256", "size"}, entry
    for manifest_path in A.PRESERVED_DIR.rglob("manifest.json"):
        for entry in json.loads(manifest_path.read_text())["outputs"]:
            assert set(entry) == {"filename", "sha256", "size"}, entry


def test_inputs_are_identified_by_content():
    """Including external/. A (size, mtime) fingerprint reported drift on clone."""
    for manifest_path in A.SHARED_DIR.glob("*.manifest.json"):
        for entry in json.loads(manifest_path.read_text())["inputs"]:
            assert entry.get("sha256"), entry
            assert "mtime" not in entry, entry


def test_verification_does_not_trust_an_mtime(tmp_path):
    """A file touched but not changed still verifies; a changed file does not."""
    target = tmp_path / "t.csv"
    target.write_bytes(b"a\n1\n")
    entry = {"filename": "t.csv", "size": 4, "sha256": A._sha256_file(target)}
    os.utime(target, (0, 0))
    assert A._verify_file(target, entry) is None
    target.write_bytes(b"a\n2\n")
    assert "content changed" in A._verify_file(target, entry)


# --- names -------------------------------------------------------------------


@pytest.mark.parametrize("name", ["", " x", "../escape", "a/b", ".hidden"])
def test_table_names_must_be_one_flat_file(name):
    with pytest.raises(A.ArtifactError, match="invalid table name"):
        A.shared_path(name)


def test_a_table_name_does_not_repeat_its_suffix():
    """shared_path("x.csv") used to return x.csv.csv."""
    with pytest.raises(A.ArtifactError, match="already ends in"):
        A.shared_path("x.csv")


@pytest.mark.parametrize("name", ["Figure 2b", "fig-2b", "a/b", "2b", ""])
def test_preserved_names_must_be_python_identifiers(name):
    """check() looks the name up among marimo's cell names.

    A name that is not an identifier can never match, so the bundle would fail
    `make check` for as long as it existed.
    """
    with pytest.raises(A.ArtifactError, match="Python identifier"):
        A.preserve_table(pl.DataFrame({"x": [1]}), name)


@pytest.mark.parametrize("filename", ["sub/x.json", "", " x"])
def test_bundle_filenames_must_be_flat(filename):
    """Only the basename is recorded, so a nested file could never verify."""
    with pytest.raises(A.ArtifactError, match="invalid filename"):
        A.preserve_file(b"x", "cell", filename=filename)


def test_external_paths_cannot_climb_out():
    with pytest.raises(A.ArtifactError, match="invalid external path"):
        A.external_path("../../etc/passwd")


# --- a failed write leaves the previous state alone --------------------------


@pytest.fixture
def bundle_writer(tmp_path, monkeypatch):
    """A preserve_* target with no kernel: a fake cell whose code we can edit."""
    monkeypatch.setattr(A, "PRESERVED_DIR", tmp_path / "preserved")
    code = ["v1 = 1"]
    monkeypatch.setattr(A, "_cell_identity", lambda: ("nb", code[0]))
    monkeypatch.setattr(A, "_notebook_relpath", lambda: "notebooks/nb.py")
    return code


@pytest.mark.parametrize(
    ("call", "match"),
    [
        (lambda: A.preserve_table({"x": [1]}, "cell", filename="good"), "DataFrame"),
        (
            lambda: A.preserve_figure(
                object(), "cell", source_data=pl.DataFrame({"x": [1]})
            ),
            "matplotlib Figure",
        ),
    ],
)
def test_a_rejected_payload_leaves_the_bundle_intact(bundle_writer, call, match):
    """_open_bundle empties the bundle when the cell's code changed.

    Validating the payload after that point destroyed the deliverable the call
    was about to replace: a typo on a re-run left nothing at all.
    """
    A.preserve_table(pl.DataFrame({"x": [1]}), "cell", filename="good")
    bundle = A.PRESERVED_DIR / "nb" / "cell"
    assert (bundle / "good.csv").exists()

    bundle_writer[0] = "v2 = 2"  # the cell was edited, and the re-run is wrong
    with pytest.raises(A.ArtifactError, match=match):
        call()
    assert (bundle / "good.csv").exists(), "the previous deliverable was destroyed"
    assert (bundle / "manifest.json").exists()


# --- check() reports, it does not raise --------------------------------------


@pytest.fixture
def empty_tree(tmp_path, monkeypatch):
    """Point the module at an empty shared/ and preserved/."""
    shared, preserved = tmp_path / "shared", tmp_path / "preserved"
    shared.mkdir()
    preserved.mkdir()
    monkeypatch.setattr(A, "SHARED_DIR", shared)
    monkeypatch.setattr(A, "PRESERVED_DIR", preserved)
    return shared, preserved


def test_check_reports_a_manifest_it_cannot_read(empty_tree):
    """It used to raise, so `make check` traced back instead of reporting."""
    shared, _ = empty_tree
    (shared / "future.manifest.json").write_text(
        json.dumps({"manifest_version": A.MANIFEST_VERSION + 1})
    )
    report = A.check()
    assert not report.ok
    assert "manifest_version" in report.errors[0]["message"]


def test_list_functions_report_a_manifest_they_cannot_read(empty_tree):
    shared, preserved = empty_tree
    (shared / "future.manifest.json").write_text(
        json.dumps({"manifest_version": A.MANIFEST_VERSION + 1})
    )
    (preserved / "nb" / "cell").mkdir(parents=True)
    (preserved / "nb" / "cell" / "manifest.json").write_text("{not json")
    assert A.list_shared()[0]["problems"][0]["severity"] == "error"
    assert A.list_preserved()[0]["problems"][0]["severity"] == "error"


def test_check_reports_a_file_no_manifest_records(empty_tree):
    """An artifact is a file plus a manifest, so the other direction counts too.

    A hand-copied table and a figure left by an interrupted run both passed as a
    clean tree.
    """
    shared, preserved = empty_tree
    (shared / "rogue.csv").write_text("a\n1\n")
    (preserved / "nb" / "cell").mkdir(parents=True)
    (preserved / "nb" / "cell" / "sneaky.png").write_bytes(b"not from petri")

    report = A.check()
    assert not report.ok
    flagged = {p["artifact"] for p in report.errors}
    assert any(a.endswith("rogue.csv") for a in flagged), report
    assert any(a.endswith("sneaky.png") for a in flagged), report


def test_check_ignores_the_gitkeep_placeholders(empty_tree):
    shared, preserved = empty_tree
    (shared / ".gitkeep").touch()
    (preserved / ".gitkeep").touch()
    assert A.check().ok


def test_a_missing_producer_notebook_is_reported_for_shared_too(empty_tree):
    """It was silent for shared and a warning for preserved."""
    shared, _ = empty_tree
    table = shared / "t.csv"
    table.write_bytes(b"a\n1\n")
    (shared / "t.manifest.json").write_text(
        json.dumps(
            {
                "manifest_version": 1,
                "kind": "shared",
                "id": "t",
                "notebook": "notebooks/deleted.py",
                "cell_code_sha256": "deadbeef",
                "inputs": [],
                "code_deps": [],
                "outputs": [
                    {
                        "filename": "t.csv",
                        "sha256": A._sha256_file(table),
                        "size": table.stat().st_size,
                    }
                ],
            }
        )
    )
    report = A.check()
    assert report.ok, str(report)  # the contents still verify
    assert "cannot read cells" in report.warnings[0]["message"]


# --- reading back ------------------------------------------------------------


def test_list_preserved_accepts_the_notebook_field_it_reports():
    """list_preserved(notebook=entry["notebook"]) returned [] silently."""
    entries = A.list_preserved()
    assert entries, "fixture repo should hold preserved bundles"
    notebook = entries[0]["notebook"]
    assert A.list_preserved(notebook=notebook), notebook
    assert A.list_preserved(notebook=Path(notebook).stem)


def test_preserved_path_requires_a_filename():
    """A bundle built with formats=("svg",) has no figure.png to default to."""
    param = inspect.signature(A.preserved_path).parameters["filename"]
    assert param.default is inspect.Parameter.empty
