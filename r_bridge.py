"""r_bridge.py — Clean Python bridge to the permanent embedded R session.

Initializes R with working directory = project root, so R automatically reads
.Rprofile and activates the renv project library once at startup.
"""

import os
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = PROJECT_ROOT / "data"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"

os.chdir(PROJECT_ROOT)
os.environ.setdefault("RPY2_CFFI_MODE", "ABI")

import polars as pl
import rpy2.robjects as ro

_conv = ro.default_converter


def r_eval(code: str) -> ro.RObject:
    """Evaluate an R code string inside rpy2's conversion context."""
    with _conv.context():
        return ro.r(code)


def r_set(name: str, value: Any) -> None:
    """Set a variable in R's global environment."""
    with _conv.context():
        if isinstance(value, str):
            ro.globalenv[name] = ro.StrVector([value])
        elif isinstance(value, (int, float)):
            ro.globalenv[name] = ro.FloatVector([value])
        else:
            ro.globalenv[name] = value


def pl_to_r(df: pl.DataFrame, name: str) -> None:
    """Push a Polars DataFrame into R's global environment by name."""
    with _conv.context():
        ro.globalenv[name] = ro.DataFrame(
            {
                col: (
                    ro.StrVector(df[col].to_list())
                    if df[col].dtype == pl.String
                    else ro.FloatVector(df[col].to_list())
                )
                for col in df.columns
            }
        )


def r_to_pl(r_var_name: str) -> pl.DataFrame:
    """Pull an R data.frame from R's global environment into a Polars DataFrame."""
    with _conv.context():
        r_obj = ro.globalenv[r_var_name]
        return pl.DataFrame(
            {col: list(vec) for col, vec in zip(r_obj.names, r_obj, strict=False)}
        )
