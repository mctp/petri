"""petri — the template's own library: paths, artifact provenance, R interop.

This package is petri's infrastructure. Your code goes in `scripts/` and
`notebooks/`.

A notebook usually needs one import line. Cells define public names, and marimo
enforces one definition per name across the notebook, so importing a handful of
symbols in a single dedicated cell keeps the rest of the notebook uncluttered:

    from petri import load_external, save_shared, preserve_figure, SHARED_DIR

R interop is a separate import, since it pulls in rpy2:

    from petri.r_bridge import pl_to_r, r_eval, r_set, r_to_pl
"""

from .paths import (
    CACHE_DIR,
    DATA_DIR,
    EXTERNAL_DIR,
    PRESERVED_DIR,
    PROJECT_ROOT,
    SHARED_DIR,
)
from .provenance import (
    ArtifactError,
    CheckReport,
    check,
    external_path,
    list_preserved,
    list_shared,
    load_external,
    load_shared,
    preserve_figure,
    preserve_file,
    preserve_table,
    preserved_path,
    save_shared,
    shared_path,
)

__all__ = [
    "CACHE_DIR",
    "DATA_DIR",
    "EXTERNAL_DIR",
    "PRESERVED_DIR",
    "PROJECT_ROOT",
    "SHARED_DIR",
    "ArtifactError",
    "CheckReport",
    "check",
    "external_path",
    "list_preserved",
    "list_shared",
    "load_external",
    "load_shared",
    "preserve_figure",
    "preserve_file",
    "preserve_table",
    "preserved_path",
    "save_shared",
    "shared_path",
]
