"""paths.py — Common project directory paths.

Pure Python paths helper (no rpy2 or R dependencies).
Import in any notebook: `from petri import SHARED_DIR, PROJECT_ROOT`.

The four data directories live together under `data/`, which keeps the project
root down to your notebooks, your transformations and the template. Each is
named for the API verb that writes it, so the mapping from code to directory is
unambiguous (see petri/docs/architecture.md):

    DATA_DIR       data/       — the four below, and nothing else
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
    CACHE_DIR      data/cache/      you, explicitly   disposable.

CACHE_DIR is opt-in: `mo.persistent_cache` defaults to
`notebooks/__marimo__/cache` (which `make clean` removes), so point it here when
the cached state is expensive enough that you do not want `make clean` to take
it with the rest of the scratch:

    with mo.persistent_cache("serrf", save_path=str(CACHE_DIR)):
        ...

"artifact" stays the umbrella term for anything petri writes with a manifest,
covering both shared and preserved; neither directory claims it.
"""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
EXTERNAL_DIR = DATA_DIR / "external"
SHARED_DIR = DATA_DIR / "shared"
PRESERVED_DIR = DATA_DIR / "preserved"
CACHE_DIR = DATA_DIR / "cache"
