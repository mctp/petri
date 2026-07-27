"""Shared project code, importable from marimo notebooks and tests.

Keep notebooks thin: put reusable loading/cleaning/plotting logic here so it
can be tested and imported with ``from marimo_pi import ...``.
"""

from marimo_pi.paths import DATA_DIR, OUTPUTS_DIR, PROJECT_ROOT

__all__ = ["DATA_DIR", "OUTPUTS_DIR", "PROJECT_ROOT"]
