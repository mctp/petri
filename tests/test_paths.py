from marimo_pi import PROJECT_ROOT
from marimo_pi.paths import NOTEBOOKS_DIR


def test_project_root_contains_pyproject() -> None:
    assert (PROJECT_ROOT / "pyproject.toml").is_file()


def test_notebooks_dir_is_under_root() -> None:
    assert NOTEBOOKS_DIR.parent == PROJECT_ROOT
