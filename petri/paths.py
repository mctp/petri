"""paths.py — Common project directory paths.

Pure Python paths helper (no rpy2 or R dependencies).
Import in any notebook: `from petri import SHARED_DIR, PROJECT_ROOT`.

Three data layers, each named for the API verb that writes it, so the mapping
from code to directory is unambiguous (see petri/docs/architecture.md):

    EXTERNAL_DIR   data/external/   load_external()   not ours. Never written
                                                      by petri, never
                                                      versioned; fingerprinted
                                                      on use.
    SHARED_DIR     data/shared/     save_shared()     ours, read by notebooks —
                                                      the only channel between
                                                      notebooks.
    PRESERVED_DIR  data/preserved/  preserve_figure() ours, read by humans and
                                    preserve_table()  journals. Terminal: never
                                    preserve_file()   read by notebook code.

`data/cache/` sits beside them but is not a fourth layer: petri never writes it
and nothing verifies it. It is scratch space with a stable path, which is why it
is the one directory here that no verb owns. `CACHE_DIR` is opt-in —
`mo.persistent_cache` defaults to `notebooks/__marimo__/cache`, which `make clean`
removes, so point it here when the cached state is expensive enough that you do
not want `make clean` to take it with the rest of the scratch:

    with mo.persistent_cache("serrf", save_path=str(CACHE_DIR)):
        ...

All four live under `data/`, which keeps the project root down to your notebooks,
your transformations and the template. There is no exported `DATA_DIR`: it is
their parent, not a layer, and nothing needs to address it.

"artifact" stays the umbrella term for anything petri writes with a manifest,
covering both shared and preserved; neither directory claims it.
"""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
_DATA = PROJECT_ROOT / "data"
EXTERNAL_DIR = _DATA / "external"
SHARED_DIR = _DATA / "shared"
PRESERVED_DIR = _DATA / "preserved"
CACHE_DIR = _DATA / "cache"
