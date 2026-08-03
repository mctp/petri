"""Identity, provenance and integrity for what a notebook writes.

An artifact is a file written with a manifest. There are two kinds:

    shared     shared/. The channel between notebooks. save_shared() writes it.
    preserved  preserved/<notebook>/<name>/. Deliverables for people. Notebook
               code never reads them. preserve_figure(), preserve_table() and
               preserve_file() write them.

This module is the only writer of both locations. Reading and verification are
here as well, which keeps the rule structural instead of a convention.

Three functions and one inference are absent by design:

    load_preserved()  Preserved artifacts are terminal. A notebook that needs
                      another notebook's result promotes it with save_shared().
    save_external()   external/ is read-only.
    save_preserved()  The three preserve_* functions take its place. Each writes
                      different bundle contents, so the kind belongs in the name.
    name inference    The marimo kernel does not expose a cell's name at
                      runtime, only an ephemeral cell id. preserve_*() takes
                      the name as an argument. check() detects a rename.

See docs/architecture.md section 5.
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
import subprocess
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import polars as pl

from .paths import EXTERNAL_DIR, PRESERVED_DIR, PROJECT_ROOT, SHARED_DIR

MANIFEST_VERSION = 1
SCRATCH_CELL_ID = "__scratch__"

# Dependencies install under PROJECT_ROOT (.venv/), so a containment test alone
# does not separate project code from third-party code.
_VENDORED_MARKERS = frozenset({".venv", "site-packages", "renv", "node_modules"})

# Floats use the Polars defaults, which give the shortest representation that
# reads back unchanged. float_precision writes 1e-300 as 0.000000000000 and
# destroys p-values. Pin only the ambiguous settings.
CSV_OPTS: dict[str, Any] = {
    "include_bom": False,
    "include_header": True,
    "separator": ",",
    "quote_char": '"',
    "line_terminator": "\n",
    "date_format": "%Y-%m-%d",
    "datetime_format": "%Y-%m-%dT%H:%M:%S%.f",
}

# matplotlib stamps a timestamp into every format. Left in, each re-run
# produces different bytes and every write is a git diff. A format absent from
# this table has no known suppression key, so preserve_figure rejects it rather
# than write a figure that can never verify twice.
_FIG_METADATA = {
    "png": {"Software": None},
    "pdf": {"CreationDate": None},
    "svg": {"Date": None},
}


# --- errors -----------------------------------------------------------------


class ArtifactError(RuntimeError):
    """Raised when an artifact cannot be written or its identity resolved."""


@dataclass
class CheckReport:
    """Outcome of check(). Errors fail the build; warnings are advisory."""

    problems: list[dict[str, str]]
    checked: int

    @property
    def errors(self) -> list[dict[str, str]]:
        return [p for p in self.problems if p["severity"] == "error"]

    @property
    def warnings(self) -> list[dict[str, str]]:
        return [p for p in self.problems if p["severity"] == "warning"]

    @property
    def ok(self) -> bool:
        return not self.errors

    def __str__(self) -> str:
        if not self.problems:
            return f"{self.checked} artifact(s) verified, no problems"
        lines = [
            f"{self.checked} artifact(s) checked — "
            f"{len(self.errors)} error(s), {len(self.warnings)} warning(s)"
        ]
        for problem in self.problems:
            mark = "ERROR  " if problem["severity"] == "error" else "warning"
            lines.append(f"  {mark} {problem['artifact']}: {problem['message']}")
        return "\n".join(lines)


# --- names ------------------------------------------------------------------

# A name and a filename both become path components, so both must be flat. The
# two families take different names: a shared table is named for its file, a
# preserved bundle for the cell that writes it.


def _check_table_name(name: str) -> None:
    """Validate a shared table name. It becomes shared/<name>.csv."""
    if not name or name != name.strip():
        raise ArtifactError(
            f"invalid table name {name!r}: empty, or padded with whitespace"
        )
    if "/" in name or "\\" in name or name.startswith("."):
        raise ArtifactError(
            f"invalid table name {name!r}: a shared table is one flat file in "
            "shared/, so the name cannot hold a path separator or start with a dot."
        )


def _check_cell_name(name: str) -> None:
    """Validate a preserved bundle name.

    A bundle is named for the cell that writes it, and check() looks that name up
    among the notebook's cell names, which marimo requires to be Python
    identifiers. A name that is not an identifier can never match, so the bundle
    would fail `make check` for as long as it exists.
    """
    if not name.isidentifier():
        raise ArtifactError(
            f"invalid artifact name {name!r}: name the artifact after the cell "
            "that writes it, so the name must be a Python identifier. check() "
            "looks it up among the notebook's cell names."
        )


def _check_filename(filename: str) -> None:
    """Validate a filename inside a bundle. A bundle is flat."""
    if not filename or filename != filename.strip():
        raise ArtifactError(
            f"invalid filename {filename!r}: empty, or padded with whitespace"
        )
    if "/" in filename or "\\" in filename or filename.startswith("."):
        raise ArtifactError(
            f"invalid filename {filename!r}: a bundle is flat and only the "
            "basename is recorded, so a nested filename could never verify."
        )


def _check_relpath(relpath: str | Path) -> None:
    """Validate a path under external/. Nesting is allowed, escaping is not."""
    path = Path(relpath)
    if path.is_absolute() or ".." in path.parts:
        raise ArtifactError(
            f"invalid external path {str(relpath)!r}: it must be relative to "
            "external/ and must not climb out of it."
        )


# --- identity ---------------------------------------------------------------


def _runtime_context():
    try:
        from marimo._runtime.context import get_context
    except ImportError as exc:  # pragma: no cover - marimo always present
        raise ArtifactError("marimo is not importable") from exc
    try:
        return get_context()
    except Exception as exc:
        raise ArtifactError(
            "no marimo runtime context. Call preserve_*() and save_shared() "
            "from a notebook cell, not from a plain script."
        ) from exc


def _cell_identity() -> tuple[str, str]:
    """Return (notebook_stem, cell_code) for the calling cell.

    The kernel gives the notebook path and an ephemeral cell id, not the cell
    name. The public functions therefore take `name` as an argument. The cell
    code is available and anchors reproducibility.
    """
    ctx = _runtime_context()
    cell_id = getattr(ctx, "cell_id", None)
    if cell_id is None or str(cell_id) == SCRATCH_CELL_ID:
        raise ArtifactError(
            "called from the scratchpad. The scratchpad sits outside the "
            "notebook and the dependency graph, so it has no identity to "
            "anchor an artifact to. Move this call into a named cell."
        )
    filename = getattr(ctx, "filename", None)
    if not filename:
        raise ArtifactError("runtime context has no notebook filename")
    try:
        code = ctx.graph.cells[cell_id].code
    except Exception as exc:
        raise ArtifactError(f"cannot read code for cell {cell_id}") from exc
    return Path(filename).stem, code


def _notebook_relpath() -> str:
    ctx = _runtime_context()
    return _relpath(Path(ctx.filename))


# --- hashing and fingerprints -----------------------------------------------


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _code_hash(code: str) -> str:
    """Hash a cell's source, ignoring whitespace at the edges.

    The kernel reports cell code with a trailing newline. The on-disk form has
    none. The write side reads the kernel and check() reads the file, so hashing
    the raw text marks every artifact stale. Trimming the edges makes the two
    comparable. A change inside the cell still changes the hash.
    """
    return _sha256_bytes(code.strip().encode("utf-8"))


def _relpath(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path.resolve())


def _code_deps(cell_code: str) -> list[dict[str, Any]]:
    """Hash the project-local modules a cell imports.

    A transformation in `processing/` is outside the cell, so the cell hash does
    not cover it. Rewrite the function, re-run, and no recorded value changes.
    These hashes close that gap: `make check` then marks the dependent artifacts
    stale.

    Covers modules under PROJECT_ROOT, except `petri/`, `.venv/` and
    site-packages. Hashing the template marks every artifact stale on a template
    update. Dependency versions belong in `tool` and the lockfiles.
    """
    try:
        tree = ast.parse(cell_code)
    except SyntaxError:
        return []

    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            imported.add(node.module)
            # `from pkg import name` may name a submodule rather than an
            # attribute. Recording only `pkg` hashed the package __init__ and
            # left the submodule that did the work unhashed. Record both
            # candidates: only what is in sys.modules is hashed, so the wrong
            # guess costs nothing.
            imported.update(f"{node.module}.{alias.name}" for alias in node.names)

    # A package's __init__ runs when a submodule is imported, so an edit there
    # changes the result too. Hash every ancestor package as well.
    for name in list(imported):
        parts = name.split(".")
        imported.update(".".join(parts[:i]) for i in range(1, len(parts)))

    petri_root = (PROJECT_ROOT / "petri").resolve()
    deps: list[dict[str, Any]] = []
    for name in sorted(imported):
        module = sys.modules.get(name)
        filename = getattr(module, "__file__", None)
        if not filename:
            continue
        path = Path(filename).resolve()
        if not path.is_relative_to(PROJECT_ROOT) or path.is_relative_to(petri_root):
            continue
        if _VENDORED_MARKERS.intersection(path.parts):
            continue
        deps.append(
            {"module": name, "path": _relpath(path), "sha256": _sha256_file(path)}
        )
    return deps


def _describe_input(path: Path) -> dict[str, Any]:
    """Classify an input by where it lives. Every kind is identified by content.

    shared/    The hash comes from that table's manifest, which pins the input to
               the published version rather than to the bytes on disk.
    external/  Not owned by petri, so a change is a warning rather than an error.
               Hashed like anything else: a (size, mtime) fingerprint reported
               drift after a re-download of identical content and after every
               fresh clone, and load_external() reads all the bytes anyway.
    other      Hashed directly.
    """
    path = Path(path).resolve()
    if not path.exists():
        raise ArtifactError(f"declared input does not exist: {path}")
    rel = _relpath(path)

    if path.is_relative_to(SHARED_DIR.resolve()):
        manifest = _load_manifest(path.with_suffix(".manifest.json"))
        recorded = _output_entry(manifest, path.name) if manifest else None
        if recorded is None:
            raise ArtifactError(
                f"declared input {rel} is in shared/ but no manifest records it. "
                "Publish it with save_shared() first. An input with no recorded "
                "version pins nothing, and every consumer inherits the gap."
            )
        return {
            "kind": "shared",
            "path": rel,
            "name": path.stem,
            "sha256": recorded.get("sha256"),
        }

    kind = "external" if path.is_relative_to(EXTERNAL_DIR.resolve()) else "file"
    return {
        "kind": kind,
        "path": rel,
        "size": path.stat().st_size,
        "sha256": _sha256_file(path),
    }


def _git_commit() -> str | None:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() or None if out.returncode == 0 else None


# --- writing ----------------------------------------------------------------


def _write_if_changed(path: Path, data: bytes) -> str:
    """Write atomically. Skip the write when the content is unchanged.

    A preserved cell re-runs whenever its dependencies change. Rewriting
    identical bytes changes the mtime and produces a git diff each time.
    """
    digest = _sha256_bytes(data)
    if path.exists() and _sha256_file(path) == digest:
        return digest
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)
    return digest


def _require_frame(data: Any) -> pl.DataFrame:
    if not isinstance(data, pl.DataFrame):
        raise ArtifactError(
            f"expected a polars DataFrame, got {type(data).__name__}. "
            "Convert with pl.DataFrame(...) or r_to_pl(...) first."
        )
    return data


def _csv_bytes(data: pl.DataFrame) -> bytes:
    _require_frame(data)
    return data.write_csv(None, **CSV_OPTS).encode("utf-8")


def _schema_of(data: pl.DataFrame) -> dict[str, str]:
    """Record dtypes so a CSV round-trip can restore them.

    shared/ is CSV so agents can grep it; the cost is that CSV carries no
    types. The schema here is what load_shared() feeds to schema_overrides.
    """
    return {name: str(dtype) for name, dtype in data.schema.items()}


def _unrestorable_columns(data: pl.DataFrame) -> list[tuple[str, str]]:
    """Columns whose dtype load_shared() would not restore. Returns (name, dtype).

    A schema entry is `str(dtype)` and _schema_overrides() turns it back into a
    bare dtype class, so a column round-trips exactly when that class built with
    its defaults reprs the same way. Asking _schema_overrides() itself keeps the
    two sides from drifting apart.
    """
    unrestorable = []
    for column, recorded in _schema_of(data).items():
        override = _schema_overrides({column: recorded}).get(column)
        try:
            restored = str(override()) if override is not None else None
        except Exception:  # a dtype whose class cannot be built bare, e.g. Enum
            restored = None
        if restored != recorded:
            unrestorable.append((column, recorded))
    return unrestorable


def _load_manifest(path: Path) -> dict[str, Any] | None:
    """Read a manifest. Return None when it is missing or not valid JSON.

    Raises ArtifactError for a manifest written by a newer petri, which this
    version cannot interpret. Without the check an unknown schema would be read
    as if it were version 1.
    """
    if not path.exists():
        return None
    try:
        manifest = json.loads(path.read_text())
    except json.JSONDecodeError:
        return None
    version = manifest.get("manifest_version", 1)
    if version > MANIFEST_VERSION:
        raise ArtifactError(
            f"{_relpath(path)} has manifest_version {version}; this petri reads "
            f"up to {MANIFEST_VERSION}. Update the template."
        )
    return manifest


def _read_manifest(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    """Read a manifest for a reporting caller. Never raises.

    Returns (manifest, problem). A manifest petri cannot read is the kind of
    problem check() exists to report, so check() and the list_* functions
    describe it instead of failing on it. The write path keeps the raise.
    """
    try:
        manifest = _load_manifest(path)
    except ArtifactError as exc:
        return None, str(exc)
    if manifest is None:
        return None, "unreadable manifest"
    return manifest, None


def _output_entry(manifest: dict[str, Any], filename: str) -> dict[str, Any] | None:
    """Find an output entry by filename.

    A manifest may record several outputs, so index 0 is not the table.
    """
    for entry in manifest.get("outputs", []):
        if entry.get("filename") == filename:
            return entry
    return None


def _manifest_skeleton(
    kind: str,
    artifact_id: str,
    title: str | None,
    existing: dict[str, Any] | None = None,
) -> dict[str, Any]:
    # `created` is the first-seen time, not the last-written time. A new
    # timestamp on every run rewrites the manifest when nothing else changed.
    # The output hashes and the git history already show content changes.
    created = (existing or {}).get("created") or datetime.now(UTC).isoformat(
        timespec="seconds"
    )
    return {
        "manifest_version": MANIFEST_VERSION,
        "kind": kind,
        "id": artifact_id,
        "title": title,
        "notebook": _notebook_relpath(),
        "cell_code_sha256": None,
        "git_commit": _git_commit(),
        "created": created,
        "tool": {"polars": pl.__version__},
        "code_deps": [],
        "inputs": [],
        "outputs": [],
    }


def _write_manifest(path: Path, manifest: dict[str, Any]) -> None:
    data = json.dumps(manifest, indent=2, sort_keys=True).encode("utf-8") + b"\n"
    _write_if_changed(path, data)


def _resolve_inputs(inputs: Iterable[Path | str]) -> list[dict[str, Any]]:
    return [_describe_input(Path(item)) for item in inputs]


# --- bundles ----------------------------------------------------------------


def _bundle_dir(name: str) -> Path:
    stem, _ = _cell_identity()
    return PRESERVED_DIR / stem / name


def _open_bundle(
    name: str, title: str | None, inputs: Iterable[Path | str]
) -> tuple[Path, dict[str, Any]]:
    """Load or start a bundle manifest for the calling cell.

    A bundle belongs to a cell, not to a file. Several preserve_*() calls in one
    cell write into one manifest. The cell code hash decides between adding to
    the manifest and rebuilding it. When the code has changed, the first call of
    the run empties the bundle, so a deleted preserve_*() line leaves no file
    that the manifest still lists.
    """
    _, code = _cell_identity()
    code_hash = _code_hash(code)
    # Resolve inputs before the truncation below: a bad input path must not
    # first delete the bundle's existing files and only then raise.
    resolved_inputs = _resolve_inputs(inputs)
    bundle = _bundle_dir(name)
    manifest_path = bundle / "manifest.json"

    existing = _load_manifest(manifest_path)
    manifest = (
        existing if (existing or {}).get("cell_code_sha256") == code_hash else None
    )

    if manifest is None:
        if bundle.exists():
            for stale in bundle.iterdir():
                if stale.is_file():
                    stale.unlink()
        manifest = _manifest_skeleton("preserved", name, title, existing)

    manifest["cell_code_sha256"] = code_hash
    manifest["code_deps"] = _code_deps(code)
    if title is not None:
        manifest["title"] = title
    for entry in resolved_inputs:
        _record_input(manifest, entry)
    return bundle, manifest


def _record_output(manifest: dict[str, Any], path: Path, digest: str) -> None:
    """Record an output file. Replace a previous entry for the same name.

    Size and hash both come from the content, so a manifest is a function of what
    it describes. An earlier version also recorded an mtime, to let verification
    skip the hash. That made every fresh clone rewrite the manifest, because a
    rebuilt file is byte-identical but newly stamped, and shared/ ships its
    manifests without the tables. Verification hashes instead.
    """
    filename = path.name
    manifest["outputs"] = [o for o in manifest["outputs"] if o["filename"] != filename]
    manifest["outputs"].append(
        {"filename": filename, "sha256": digest, "size": path.stat().st_size}
    )
    manifest["outputs"].sort(key=lambda o: o["filename"])


def _record_input(manifest: dict[str, Any], entry: dict[str, Any]) -> None:
    """Record an input. Replace a previous entry for the same path.

    Keyed by path, not by equality. An input's fingerprint changes with its
    content, so a dedup by equality appends a second entry. The manifest then
    claims provenance from a version that no longer exists.
    """
    manifest["inputs"] = [
        i for i in manifest["inputs"] if i.get("path") != entry.get("path")
    ]
    manifest["inputs"].append(entry)
    manifest["inputs"].sort(key=lambda i: i.get("path", ""))


# --- public: shared ---------------------------------------------------------


def shared_path(name: str, suffix: str = ".csv") -> Path:
    """Path to a shared table. Does not verify. See load_shared().

    `suffix` defaults to `.csv`, which is what save_shared() writes today. A
    leading dot is optional. Other formats will need it passed explicitly.
    """
    if not suffix.startswith("."):
        suffix = "." + suffix
    _check_table_name(name)
    if name.endswith(suffix):
        raise ArtifactError(
            f"table name {name!r} already ends in {suffix!r}; pass the name "
            f"without it, or the path becomes {name}{suffix}."
        )
    return SHARED_DIR / f"{name}{suffix}"


def external_path(relpath: str | Path) -> Path:
    """Path to an unowned input under external/."""
    _check_relpath(relpath)
    return EXTERNAL_DIR / relpath


def save_shared(
    data: pl.DataFrame,
    name: str,
    *,
    inputs: Iterable[Path | str],
    description: str | None = None,
) -> Path:
    """Publish an shared table to shared/<name>.csv.

    The only writer of shared/. `inputs` is required. A shared table with no
    declared provenance cannot be verified, and every consumer inherits the gap.

    Every column must survive the CSV round trip, because load_shared() rebuilds
    dtypes from the recorded schema. A dtype carrying a time zone, a non-default
    time unit, a decimal precision or an enum's categories is rejected here
    rather than in the notebook that reads it.

    Call this outside any mo.persistent_cache block. On a cache hit marimo skips
    the block and its side effects, and the write does not happen.
    """
    # Validate, then resolve identity and inputs, then write. Anything that can
    # fail must fail before the CSV lands, or shared/ holds a table with no
    # manifest.
    _check_table_name(name)
    _require_frame(data)
    unrestorable = _unrestorable_columns(data)
    if unrestorable:
        listed = ", ".join(f"{column} ({dtype})" for column, dtype in unrestorable)
        raise ArtifactError(
            f"load_shared() cannot restore these columns: {listed}. shared/ is "
            "CSV and the manifest records a dtype by name, so a time zone, a "
            "non-default time unit, a precision or a category list is lost. Cast "
            "the column before publishing."
        )
    payload = _csv_bytes(data)
    _, code = _cell_identity()
    resolved_inputs = _resolve_inputs(inputs)

    target = shared_path(name)
    digest = _write_if_changed(target, payload)

    manifest_path = SHARED_DIR / f"{name}.manifest.json"
    manifest = _manifest_skeleton(
        "shared", name, description, _load_manifest(manifest_path)
    )
    manifest["cell_code_sha256"] = _code_hash(code)
    manifest["code_deps"] = _code_deps(code)
    manifest["inputs"] = resolved_inputs
    manifest["schema"] = _schema_of(data)
    manifest["rows"] = data.height
    _record_output(manifest, target, digest)
    _write_manifest(manifest_path, manifest)
    return target


# --- public: preserved ------------------------------------------------------


def preserve_figure(
    fig: Any,
    name: str,
    *,
    source_data: pl.DataFrame,
    filename: str = "figure",
    title: str | None = None,
    inputs: Iterable[Path | str] = (),
    formats: tuple[str, ...] = ("pdf", "png"),
) -> Path:
    """Preserve a figure bundle to preserved/<notebook>/<name>/.

    Writes `<filename>.<fmt>` for each format, plus `<filename>-source.csv` with
    the plotted rows. A journal asks for the source data, and it cannot be
    recovered from the figure object.

    Pass a distinct `filename` for each figure in a cell. Two calls sharing one
    would overwrite each other, since a bundle belongs to the cell, not the call.

    `fig` is a matplotlib Figure or a Path to a rendered file. Use the Path form
    for R output: ggsave writes the file, this function records it. A Path
    supplies one format.

    Each format in `formats` needs a timestamp-suppression key in _FIG_METADATA;
    a format without one is rejected. A Path is copied byte for byte, so an
    external renderer's timestamp is preserved: R's `pdf()` writes both a
    CreationDate and a ModDate, and those bytes change on every run, so each run
    rewrites the file. Prefer PNG or SVG from R.
    """
    unknown = [f for f in formats if f not in _FIG_METADATA]
    if unknown:
        raise ArtifactError(
            f"no timestamp-suppression key for format(s) {unknown}. "
            f"Known: {sorted(_FIG_METADATA)}. A format without one writes a "
            "new timestamp on every run and never verifies twice."
        )
    _check_cell_name(name)
    _check_filename(filename)

    # Render everything before opening the bundle. _open_bundle() empties the
    # bundle when the cell's code has changed, so a failure after that point
    # would destroy the deliverable it was about to replace.
    renders: list[tuple[str, bytes]] = []
    if isinstance(fig, (str, Path)):
        src = Path(fig)
        if not src.exists():
            raise ArtifactError(f"figure file does not exist: {src}")
        renders.append((f"{filename}{src.suffix}", src.read_bytes()))
    elif hasattr(fig, "savefig"):
        import io

        for fmt in formats:
            buf = io.BytesIO()
            fig.savefig(
                buf, format=fmt, metadata=_FIG_METADATA[fmt], bbox_inches="tight"
            )
            renders.append((f"{filename}.{fmt}", buf.getvalue()))
    else:
        raise ArtifactError(
            f"expected a matplotlib Figure or a Path, got {type(fig).__name__}"
        )
    source_payload = _csv_bytes(source_data)
    source_schema = _schema_of(source_data)

    bundle, manifest = _open_bundle(name, title, inputs)
    for out_name, payload in renders:
        digest = _write_if_changed(bundle / out_name, payload)
        _record_output(manifest, bundle / out_name, digest)

    data_name = f"{filename}-source.csv"
    digest = _write_if_changed(bundle / data_name, source_payload)
    _record_output(manifest, bundle / data_name, digest)
    manifest["schema"] = source_schema

    _write_manifest(bundle / "manifest.json", manifest)
    return bundle


def preserve_table(
    data: pl.DataFrame,
    name: str,
    *,
    filename: str = "table",
    title: str | None = None,
    inputs: Iterable[Path | str] = (),
) -> Path:
    """Preserve a deliverable table as robust CSV in preserved/<notebook>/<name>/.

    Writes `<filename>.csv`. Pass a distinct `filename` for each table in a cell.
    """
    _check_cell_name(name)
    _check_filename(filename)
    # Serialize before opening the bundle; see the note in preserve_figure().
    payload = _csv_bytes(data)
    schema = _schema_of(data)

    bundle, manifest = _open_bundle(name, title, inputs)
    out_name = f"{filename}.csv"
    digest = _write_if_changed(bundle / out_name, payload)
    _record_output(manifest, bundle / out_name, digest)
    manifest["schema"] = schema
    _write_manifest(bundle / "manifest.json", manifest)
    return bundle


def preserve_file(
    src: Path | str | bytes,
    name: str,
    *,
    filename: str | None = None,
    title: str | None = None,
    inputs: Iterable[Path | str] = (),
) -> Path:
    """Preserve an already-serialized payload into preserved/<notebook>/<name>/.

    A Path copies that file in, and `filename` defaults to its basename. bytes
    or str are written as content and `filename` is required. A str is always
    content, never a path: pass Path(...) to copy a file. The caller serializes;
    petri has no format registry and no pickle surface.

        preserve_file(json.dumps(params, indent=2), "fig2b", filename="params.json")
        preserve_file(model_path, "fig2b")
    """
    _check_cell_name(name)
    if isinstance(src, (bytes, str)):
        if filename is None:
            raise ArtifactError(
                "filename is required when src is bytes or str. To copy a file "
                "instead, pass Path(...)."
            )
        payload = src.encode("utf-8") if isinstance(src, str) else src
    else:
        path = Path(src)
        if not path.exists():
            raise ArtifactError(f"file does not exist: {path}")
        payload = path.read_bytes()
        filename = filename or path.name
    _check_filename(filename)

    bundle, manifest = _open_bundle(name, title, inputs)

    digest = _write_if_changed(bundle / filename, payload)
    _record_output(manifest, bundle / filename, digest)
    _write_manifest(bundle / "manifest.json", manifest)
    return bundle


# --- reading ----------------------------------------------------------------

# A container dtype needs an inner type, and a bare pl.List is not a usable
# override. Skipping it here is what makes _unrestorable_columns() reject such a
# column, so save_shared() never publishes one. CSV holds no nested data anyway.
_CONTAINER_DTYPES = frozenset({"List", "Struct", "Array"})


def _schema_overrides(schema: dict[str, str] | None) -> dict[str, Any]:
    overrides: dict[str, Any] = {}
    for column, name in (schema or {}).items():
        base = name.split("(")[0]
        if base in _CONTAINER_DTYPES:
            continue
        dtype = getattr(pl, base, None)
        if isinstance(dtype, type) and issubclass(dtype, pl.DataType):
            overrides[column] = dtype
    return overrides


def _verify_file(path: Path, entry: dict[str, Any]) -> str | None:
    """Return a problem description, or None when the file matches its entry.

    Size is a cheap reject before the hash. There is no mtime fast path: an mtime
    says nothing about content, and recording one made every clone rewrite the
    manifest.
    """
    if not path.exists():
        return f"{entry['filename']}: missing"
    if path.stat().st_size != entry.get("size"):
        return f"{entry['filename']}: size changed since it was written"
    if _sha256_file(path) != entry.get("sha256"):
        return f"{entry['filename']}: content changed since it was written"
    return None


def load_shared(name: str) -> pl.DataFrame:
    """Read a shared table and verify it against its manifest.

    A shared table that was edited by hand, truncated, or written by anything
    other than save_shared() fails here, before it reaches a figure.

    Dtypes come from the schema recorded at write time. shared/ is CSV so that
    it stays readable with grep, and CSV carries no types.
    """
    manifest_path = SHARED_DIR / f"{name}.manifest.json"
    manifest = _load_manifest(manifest_path)
    if manifest is None:
        raise ArtifactError(
            f"no manifest for shared table '{name}'. Either it was never "
            f"published with save_shared(), or {manifest_path.name} was lost."
        )
    target = shared_path(name)
    entry = _output_entry(manifest, target.name)
    if entry is None:
        raise ArtifactError(f"manifest for '{name}' records no output file")
    problem = _verify_file(target, entry)
    if problem is not None:
        raise ArtifactError(
            f"shared table '{name}' failed verification: {problem}. "
            "Re-run the producer notebook. Do not edit shared/ by hand."
        )
    return pl.read_csv(
        target, schema_overrides=_schema_overrides(manifest.get("schema"))
    )


def load_external(relpath: str | Path) -> pl.DataFrame:
    """Read a tabular file from external/.

    For producer notebooks. This is the one crossing of the ownership boundary.
    For a non-tabular input, use external_path() and read the file yourself.
    Declare the path in `inputs=` either way, so the fingerprint is recorded.
    """
    path = external_path(relpath)
    if not path.exists():
        raise ArtifactError(f"external input does not exist: {_relpath(path)}")
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return pl.read_csv(path)
    if suffix in {".tsv", ".txt"}:
        return pl.read_csv(path, separator="\t")
    if suffix == ".parquet":
        return pl.read_parquet(path)
    raise ArtifactError(
        f"load_external does not handle '{suffix}'. Use external_path() and "
        "read it with the appropriate library."
    )


def preserved_path(notebook: str, cell: str, filename: str) -> Path:
    """Path to a file inside a preserved bundle. Raises if it does not exist.

    `filename` has no default. A bundle's files are named by the calls that wrote
    them, and a figure built with formats=("svg",) has no PNG at all; ask
    list_preserved() which files a bundle holds.

    Use it to display, open, or view the file. There is no loader that reads
    artifact data into a notebook namespace. That absence keeps deliverables
    terminal.
    """
    _check_cell_name(cell)
    _check_filename(filename)
    path = PRESERVED_DIR / Path(notebook).stem / cell / filename
    if not path.exists():
        raise ArtifactError(f"no such artifact file: {_relpath(path)}")
    return path


def list_shared() -> list[dict[str, Any]]:
    """Summarise the shared tables, with each one's problems.

    The counterpart to list_preserved(). Without it there is no way to ask what
    the interface layer holds.
    """
    entries = []
    for manifest_path in sorted(SHARED_DIR.glob("*.manifest.json")):
        name = manifest_path.name.removesuffix(".manifest.json")
        manifest, problem = _read_manifest(manifest_path)
        if manifest is None:
            entries.append(
                {
                    "name": name,
                    "notebook": None,
                    "description": None,
                    "rows": None,
                    "path": None,
                    "created": None,
                    "problems": [{"severity": "error", "message": problem}],
                }
            )
            continue
        outputs = manifest.get("outputs") or []
        entries.append(
            {
                "name": manifest.get("id"),
                "notebook": manifest.get("notebook"),
                "description": manifest.get("title"),
                "rows": manifest.get("rows"),
                "path": _relpath(SHARED_DIR / outputs[0]["filename"])
                if outputs
                else None,
                "created": manifest.get("created"),
                "problems": _verify_manifest(manifest, SHARED_DIR),
            }
        )
    return entries


def list_preserved(notebook: str | None = None) -> list[dict[str, Any]]:
    """Summarise preserved bundles, ordered by path.

    Each entry carries `problems`, so a caller can skip a figure whose inputs
    have changed, and `files`, because a bundle's filenames come from the calls
    that wrote it.

    `notebook` takes either form the API reports: the notebook path in an entry's
    `notebook` field, or the bare stem that names the directory.
    """
    root = PRESERVED_DIR / Path(notebook).stem if notebook else PRESERVED_DIR
    if not root.exists():
        return []
    entries = []
    for manifest_path in sorted(root.rglob("manifest.json")):
        base = manifest_path.parent
        manifest, problem = _read_manifest(manifest_path)
        if manifest is None:
            entries.append(
                {
                    "id": base.name,
                    "notebook": None,
                    "title": None,
                    "path": _relpath(base),
                    "files": [],
                    "created": None,
                    "problems": [{"severity": "error", "message": problem}],
                }
            )
            continue
        entries.append(
            {
                "id": manifest.get("id"),
                "notebook": manifest.get("notebook"),
                "title": manifest.get("title"),
                "path": _relpath(base),
                "files": [o["filename"] for o in manifest.get("outputs", [])],
                "created": manifest.get("created"),
                "problems": _verify_manifest(manifest, base),
            }
        )
    return entries


# --- verification -----------------------------------------------------------


UNNAMED_CELL = "_"


def _notebook_cells(path: Path) -> list[tuple[str, str]]:
    """Return (cell name, cell code) for every cell in a notebook on disk.

    Returns a list, not a dict. marimo names every unnamed cell `_`, so a dict
    keyed by name holds one of them and drops the rest. Lookups by a real name
    still work against such a dict, so only the scan over all cells failed.

    Uses marimo's loader instead of parsing the AST here, so the code text
    matches what the kernel reports and the hashes are comparable.
    """
    try:
        from marimo._ast.load import load_app

        app = load_app(str(path))
    except Exception:
        return []
    if app is None:
        return []
    manager = app._cell_manager
    return [
        (manager.cell_name(cid), manager.cell_data_at(cid).code)
        for cid in manager.cell_ids()
    ]


def _verify_manifest(manifest: dict[str, Any], base: Path) -> list[dict[str, str]]:
    """Verify one manifest's outputs and inputs. Returns problem dicts."""
    problems: list[dict[str, str]] = []

    def add(severity: str, message: str) -> None:
        problems.append({"severity": severity, "message": message})

    for entry in manifest.get("outputs", []):
        problem = _verify_file(base / entry["filename"], entry)
        if problem:
            add("error", problem)

    for entry in manifest.get("inputs", []):
        path = PROJECT_ROOT / entry["path"]
        if not path.exists():
            add("error", f"input missing: {entry['path']}")
            continue
        kind = entry.get("kind")
        if kind == "shared":
            # Compared against the published version, not the bytes on disk. The
            # shared table's own manifest is what verifies those.
            current, _ = _read_manifest(path.with_suffix(".manifest.json"))
            recorded = _output_entry(current, path.name) if current else None
            current_sha = recorded.get("sha256") if recorded else None
            if current_sha != entry.get("sha256"):
                add(
                    "error",
                    f"built from an older version of {entry['path']}; re-run this cell",
                )
        elif entry.get("sha256") and _sha256_file(path) != entry["sha256"]:
            if kind == "external":
                # A warning, not an error: external/ is unowned, so petri reports
                # the change and leaves the decision to rebuild to you.
                add("warning", f"external input changed: {entry['path']}")
            else:
                add("error", f"input changed: {entry['path']}")

    # Transformations in processing/ are outside the cell, so the cell code
    # hash does not cover them. This is an error, not a warning: if the function
    # that produced the output changed, the output is out of date.
    for entry in manifest.get("code_deps", []):
        path = PROJECT_ROOT / entry["path"]
        if not path.exists():
            add("error", f"module missing: {entry['path']}")
        elif _sha256_file(path) != entry.get("sha256"):
            add(
                "error",
                f"{entry['module']} changed since this was written; re-run the cell",
            )

    return problems


def _unlisted_files() -> list[dict[str, str]]:
    """Find files in shared/ and preserved/ that no manifest lists.

    An artifact is a file plus a manifest. Verifying manifests alone leaves the
    other direction unchecked, so a hand-copied table or a figure left by an
    interrupted run passed as a clean tree. Nothing records what produced such a
    file, which is the whole claim these two directories make.
    """
    problems: list[dict[str, str]] = []

    def add(path: Path, message: str) -> None:
        problems.append(
            {"artifact": _relpath(path), "severity": "error", "message": message}
        )

    listed: set[str] = set()
    for manifest_path in SHARED_DIR.glob("*.manifest.json"):
        manifest, _ = _read_manifest(manifest_path)
        if manifest is not None:
            listed.update(o["filename"] for o in manifest.get("outputs", []))
    for path in sorted(SHARED_DIR.rglob("*")):
        if not path.is_file() or path.name == ".gitkeep":
            continue
        if path.name.endswith(".manifest.json"):
            continue
        if path.parent == SHARED_DIR and path.name in listed:
            continue
        add(path, "no manifest records this file; save_shared() did not write it")

    directories = [PRESERVED_DIR, *(p for p in PRESERVED_DIR.rglob("*") if p.is_dir())]
    for directory in sorted(directories):
        if not directory.exists():
            continue
        files = [
            p
            for p in sorted(directory.iterdir())
            if p.is_file() and p.name != ".gitkeep"
        ]
        if not files:
            continue
        manifest_path = directory / "manifest.json"
        if not manifest_path.exists():
            for path in files:
                add(path, "this directory holds files but no manifest.json")
            continue
        manifest, _ = _read_manifest(manifest_path)
        if manifest is None:
            continue  # the main pass reports the unreadable manifest
        names = {"manifest.json"} | {o["filename"] for o in manifest.get("outputs", [])}
        for path in files:
            if path.name not in names:
                add(
                    path, "no manifest records this file; preserve_*() did not write it"
                )
    return problems


def check() -> CheckReport:
    """Verify every manifest under shared/ and preserved/.

    Covers four kinds of drift:

      content     an output or input no longer matches the hash recorded for it
      staleness   an artifact pinned to a superseded version of a shared table
      identity    a preserved bundle whose producing cell was renamed, deleted,
                  or edited since the artifact was written
      provenance  a file in either directory that no manifest records

    The identity pass covers the name argument on preserve_*(). Rename the cell
    without renaming the artifact and this check fails.

    Every hash is recomputed. Reporting problems is the job, so a manifest this
    petri cannot read is reported, not raised.
    """
    problems: list[dict[str, str]] = []
    checked = 0
    cells_by_notebook: dict[str, list[tuple[str, str]]] = {}

    def cells_for(notebook: str) -> list[tuple[str, str]]:
        if notebook not in cells_by_notebook:
            cells_by_notebook[notebook] = _notebook_cells(PROJECT_ROOT / notebook)
        return cells_by_notebook[notebook]

    def collect(artifact: str, found: list[dict[str, str]]) -> None:
        for problem in found:
            problems.append({"artifact": artifact, **problem})

    for manifest_path in sorted(SHARED_DIR.glob("*.manifest.json")):
        manifest, problem = _read_manifest(manifest_path)
        if manifest is None:
            problems.append(
                {
                    "artifact": manifest_path.name,
                    "severity": "error",
                    "message": problem or "unreadable manifest",
                }
            )
            continue
        checked += 1
        label = f"shared/{manifest.get('id')}"
        collect(label, _verify_manifest(manifest, SHARED_DIR))
        # A shared table has no cell name to anchor to: save_shared() takes the
        # table name. The only identity check available is whether some cell in
        # the producer notebook still carries the code that wrote it. Both
        # outcomes are warnings. The contents are still verified; only the path
        # back to the producer is missing.
        notebook = manifest.get("notebook")
        cells = cells_for(notebook) if notebook else []
        if not cells:
            collect(
                label,
                [
                    {
                        "severity": "warning",
                        "message": f"cannot read cells of {notebook}",
                    }
                ],
            )
        elif manifest.get("cell_code_sha256") not in {
            _code_hash(code) for _, code in cells
        }:
            collect(
                label,
                [
                    {
                        "severity": "warning",
                        "message": (
                            f"no cell in {notebook} matches the code that produced "
                            "this table; the producer was edited or removed"
                        ),
                    }
                ],
            )

    for manifest_path in sorted(PRESERVED_DIR.rglob("manifest.json")):
        manifest, problem = _read_manifest(manifest_path)
        if manifest is None:
            problems.append(
                {
                    "artifact": _relpath(manifest_path),
                    "severity": "error",
                    "message": problem or "unreadable manifest",
                }
            )
            continue
        checked += 1
        base = manifest_path.parent
        artifact_id = manifest.get("id") or base.name
        label = f"{base.parent.name}/{artifact_id}"
        collect(label, _verify_manifest(manifest, base))

        notebook = manifest.get("notebook")
        cells = cells_for(notebook) if notebook else []
        named = {n: c for n, c in cells if n != UNNAMED_CELL}
        if not cells:
            collect(
                label,
                [
                    {
                        "severity": "warning",
                        "message": f"cannot read cells of {notebook}",
                    }
                ],
            )
        elif artifact_id not in named:
            collect(
                label,
                [
                    {
                        "severity": "error",
                        "message": (
                            f"no cell named '{artifact_id}' in {notebook}; the "
                            "cell was renamed or deleted, orphaning this bundle"
                        ),
                    }
                ],
            )
        else:
            current = _code_hash(named[artifact_id])
            if current != manifest.get("cell_code_sha256"):
                collect(
                    label,
                    [
                        {
                            "severity": "error",
                            "message": (
                                f"cell '{artifact_id}' changed since this was "
                                "written; re-run it to update the artifact"
                            ),
                        }
                    ],
                )

    problems.extend(_unlisted_files())
    return CheckReport(problems=problems, checked=checked)


__all__ = [
    "ArtifactError",
    "CheckReport",
    "check",
    "external_path",
    "list_preserved",
    "load_external",
    "load_shared",
    "preserve_figure",
    "preserve_file",
    "preserve_table",
    "preserved_path",
    "save_shared",
    "shared_path",
]
