"""Project paths resolved from the installed package location."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
INTERIM_DIR = DATA_DIR / "interim"
PROCESSED_DIR = DATA_DIR / "processed"
EXTERNAL_DIR = DATA_DIR / "external"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
NOTEBOOKS_DIR = PROJECT_ROOT / "notebooks"


def ensure_dirs() -> None:
    """Create the standard data/output directories if they are missing."""
    for path in (RAW_DIR, INTERIM_DIR, PROCESSED_DIR, EXTERNAL_DIR, OUTPUTS_DIR):
        path.mkdir(parents=True, exist_ok=True)
