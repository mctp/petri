"""r_bridge.py — Clean Python bridge to the permanent embedded R session.

Initializes R with working directory = project root, so R automatically reads
.Rprofile and activates the renv project library once at startup.
"""

import os
from typing import Any

from .paths import PROJECT_ROOT

os.chdir(PROJECT_ROOT)
os.environ.setdefault("RPY2_CFFI_MODE", "ABI")

import numpy as np
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


def r_png(code: str, *, width: int = 500, height: int = 400) -> bytes:
    """Render the plot `code` draws into PNG bytes, without writing a file.

    `width` and `height` are pixels, as R's `png()` device takes them.
    """
    with _conv.context():
        # Imported here, not at module scope: the import itself calls
        # importr("grDevices"), which needs the conversion rules this context
        # installs. At module scope it would run before any context exists.
        from rpy2.robjects.lib import grdevices

        with grdevices.render_to_bytesio(
            grdevices.png, width=width, height=height
        ) as bio:
            ro.r(code)
        return bio.getvalue()


def r_to_pl(r_var_name: str) -> pl.DataFrame:
    """Pull an R data.frame from R's global environment into a Polars DataFrame."""
    with _conv.context():
        r_obj = ro.globalenv[r_var_name]
        return pl.DataFrame(
            {col: list(vec) for col, vec in zip(r_obj.names, r_obj, strict=False)}
        )


def r_to_np(r_var_name: str) -> np.ndarray:
    """Pull an R matrix or vector from the global environment into a NumPy ndarray.

    For array-like R objects only (matrices, vectors). Tabular R objects
    (data.frames) belong in `r_to_pl` instead.
    """
    with _conv.context():
        return np.asarray(ro.globalenv[r_var_name])


def py_to_r(obj: Any, name: str) -> None:
    """Push a native Python object into R's global environment by name.

    `dict` -> named R list (recursive); `list`/`tuple` -> R vector (uniform
    scalars) or unnamed R list (mixed/nested); `str`/`int`/`float`/`bool` -> R
    scalar. NumPy arrays raise: use `pl_to_r` (DataFrames) instead.
    """
    with _conv.context():
        ro.globalenv[name] = _py_to_r(obj)


def r_to_py(r_var_name: str) -> Any:
    """Pull an R object into its natural native Python form.

    Named R list -> `dict` (recursive); unnamed list / atomic vector -> `list`
    (length-1 vectors scalarize). Matrices and data.frames raise with a hint:
    they belong in `r_to_np` and `r_to_pl` respectively.
    """
    with _conv.context():
        return _r_to_py(ro.globalenv[r_var_name])


def _atomic_vector(items: list) -> Any:
    """Build an R atomic vector for a uniform list of scalars, else None."""
    if all(isinstance(x, bool) for x in items):
        return ro.BoolVector(list(items))
    if all(isinstance(x, (int, float)) for x in items):
        if all(isinstance(x, int) for x in items):
            return ro.IntVector(list(items))
        return ro.FloatVector([float(x) for x in items])
    if all(isinstance(x, str) for x in items):
        return ro.StrVector(list(items))
    return None


def _py_to_r(obj: Any) -> Any:
    if isinstance(obj, dict):
        return ro.ListVector({str(k): _py_to_r(v) for k, v in obj.items()})
    if isinstance(obj, (list, tuple)):
        if len(obj) == 0:
            return ro.r.list()
        vec = _atomic_vector(obj)
        if vec is not None:
            return vec
        return ro.r.list(*(_py_to_r(x) for x in obj))
    if isinstance(obj, bool):
        return ro.BoolVector([obj])
    if isinstance(obj, str):
        return ro.StrVector([obj])
    if isinstance(obj, (int, float)):
        return ro.FloatVector([obj])
    raise TypeError(f"cannot convert {type(obj).__name__} to R")


def _r_to_py(robj: Any) -> Any:
    rclass = list(robj.rclass) if hasattr(robj, "rclass") else []
    if "data.frame" in rclass:
        raise NotImplementedError("data.frame -> use r_to_pl()")
    if "matrix" in rclass:
        raise NotImplementedError("matrix -> use r_to_np()")
    if isinstance(robj, ro.ListVector):
        names = list(robj.names) if robj.names else None
        vals = [_r_to_py(x) for x in robj]
        if names is not None and all(n is not None for n in names):
            return dict(zip(names, vals, strict=False))
        return vals
    lst = np.asarray(robj).tolist()
    if isinstance(lst, list) and len(lst) == 1:
        return lst[0]
    return lst


__all__ = [
    "PROJECT_ROOT",
    "pl_to_r",
    "py_to_r",
    "r_eval",
    "r_png",
    "r_set",
    "r_to_np",
    "r_to_pl",
    "r_to_py",
]
