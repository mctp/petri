"""r_bridge.py — Clean Python bridge to the permanent embedded R session.

Initializes R with working directory = project root, so R automatically reads
.Rprofile and activates the renv project library once at startup.

Six functions move data across, paired by shape. Each pair is the other's
inverse, and each call's return type is a function of the R object's type, so
nothing guesses:

    dict / list / scalar   py_to_r  <->  r_to_py   named R list, vector, scalar
    NumPy ndarray          np_to_r  <->  r_to_np   R matrix, array, vector
    Polars DataFrame       pl_to_r  <->  r_to_pl   R data.frame

Missing values cross in both directions: Python `None` becomes the typed R `NA`,
and R `NA` comes back as `None`. R hands `NA_real_` and `NaN` to rpy2 as the
same float, so a missing double arrives as `None` either way.

R's console output reaches Python through this module, minus progress-bar
redraws: a chunk carrying a carriage return and no newline is dropped, so a
`txtProgressBar` does not fill the notebook or the transcript. Nothing else is
filtered — every line R prints, you see.

These docstrings are the contract; `petri/docs/rpy2.md` covers notebook use.
"""

import datetime as dt
import math
import os
from collections.abc import Sequence
from typing import Any

from .paths import PROJECT_ROOT

os.chdir(PROJECT_ROOT)
os.environ.setdefault("RPY2_CFFI_MODE", "ABI")

import numpy as np
import polars as pl
import rpy2.robjects as ro
from rpy2 import rinterface
from rpy2.rinterface_lib import callbacks

_conv = ro.default_converter

# A progress bar redraws one line: it writes a chunk holding a carriage return
# and no newline. That is the whole test. An earlier version also dropped any
# chunk starting with `|` that held a `%` or an `=`, which silently ate real
# output — a `| gene | 5% |` table row never reached the notebook — and caught
# nothing this rule misses. A bar drawn without a carriage return (style 1) is
# left alone rather than guessed at.
#
# `_filtering` guards against re-wrapping: marimo runs with auto_reload, so this
# module can be imported again in a live session, and wrapping the wrapper would
# grow a chain on every reload.
if not getattr(callbacks.consolewrite_print, "_petri_filtering", False):
    _orig_consolewrite_print = callbacks.consolewrite_print

    def _filtered_consolewrite_print(s: str) -> None:
        if "\r" in s and not s.endswith("\n"):
            return
        _orig_consolewrite_print(s)

    _filtered_consolewrite_print._petri_filtering = True
    callbacks.consolewrite_print = _filtered_consolewrite_print


# Two of these are quiet-output settings; `show.signif.stars` changes what R
# prints in a result, so it is a deliberate formatting choice, not noise
# control. Inside the converter context like every other rpy2 call here: rpy2
# keeps its conversion rules in a ContextVar, and a marimo cell runs in a thread
# that does not carry it.
with _conv.context():
    ro.r(
        """
        options(
            verbose = FALSE,
            show.signif.stars = FALSE,
            progressr.enable = FALSE
        )
        """
    )

# R's integer is 32-bit and spends -2^31 on NA_integer_, so that is the floor of
# the usable range, not -2^31 itself.
_INT32_MIN = -(2**31) + 1
_INT32_MAX = 2**31 - 1

_EPOCH = dt.date(1970, 1, 1)

# The typed NA sentinels rpy2 hands back. NA_real_ is not among them: it arrives
# as a plain float nan, which `_is_na` covers separately.
_NA_TYPES = tuple(type(v) for v in (ro.NA_Character, ro.NA_Integer, ro.NA_Logical))

_ATOMIC_VECTORS = (
    ro.BoolVector,
    ro.ComplexVector,
    ro.FloatVector,
    ro.IntVector,
    ro.StrVector,
)

# R stores these as plain numbers under a class attribute, so anything that reads
# the numbers without reading the class gets days or seconds instead of a time.
_TEMPORAL_CLASSES = {"Date", "POSIXct", "POSIXt", "difftime"}


def r_eval(code: str) -> ro.RObject:
    """Evaluate an R code string inside rpy2's conversion context."""
    with _conv.context():
        return ro.r(code)


def r_set(name: str, value: Any) -> None:
    """Set a variable in R's global environment. Legacy alias for `py_to_r`.

    Note the reversed argument order — `r_set(name, value)` but
    `py_to_r(value, name)`. Prefer `py_to_r` in new code; this stays because
    notebooks already call it. An rpy2 object passes through untouched.
    """
    with _conv.context():
        ro.globalenv[name] = (
            value if isinstance(value, rinterface.Sexp) else _py_to_r(value)
        )


def py_to_r(obj: Any, name: str) -> None:
    """Push a native Python object into R's global environment by name.

    `dict` -> named R list (recursive); `list`/`tuple` -> R vector (uniform
    scalars) or unnamed R list (mixed/nested); `str`/`int`/`float`/`bool` -> R
    scalar; `None` -> `NULL`, and inside a vector -> the typed `NA`. An `int`
    too wide for R's 32-bit integer goes as a double. NumPy arrays belong in
    `np_to_r`, Polars DataFrames in `pl_to_r`.
    """
    with _conv.context():
        ro.globalenv[name] = _py_to_r(obj)


def np_to_r(arr: np.ndarray, name: str) -> None:
    """Push a NumPy array into R's global environment by name.

    1-D becomes an atomic vector, 2-D a matrix, N-D an array — R is
    column-major, and the layout is preserved. The inverse of `r_to_np`.
    """
    with _conv.context():
        ro.globalenv[name] = _np_to_r(arr)


def pl_to_r(df: pl.DataFrame, name: str) -> None:
    """Push a Polars DataFrame into R's global environment as a data.frame.

    Column types are carried across rather than flattened: Boolean -> logical,
    integers -> integer (or double when too wide for R's 32-bit int), floats ->
    double, String/Categorical/Enum -> character, Date -> Date. Nulls become the
    typed `NA`. Column names are kept verbatim (`check.names = FALSE`), and
    strings stay character (`stringsAsFactors = FALSE`).

    Any other dtype raises rather than guessing — notably Datetime, whose R
    counterpart carries a time zone this bridge will not invent. Cast it in
    Polars first (`.dt.date()`, or an epoch integer, or a formatted string).
    """
    with _conv.context():
        columns = ro.ListVector({col: _column_to_r(df[col]) for col in df.columns})
        ro.globalenv[name] = ro.r["data.frame"](
            columns, **{"check.names": False, "stringsAsFactors": False}
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
    """Pull an R data.frame from R's global environment into a Polars DataFrame.

    data.frame only — anything else raises, naming `r_to_np` or `r_to_py`. A
    factor column comes back as its labels, not its integer codes; a Date column
    as dates; `NA` as null.
    """
    with _conv.context():
        robj = ro.globalenv[r_var_name]
        rclass = _rclass(robj)
        if "data.frame" not in rclass:
            raise NotImplementedError(
                f"{r_var_name!r} is not a data.frame (class: "
                f"{', '.join(rclass) or type(robj).__name__}) -> use "
                f"{'r_to_py()' if isinstance(robj, ro.ListVector) else 'r_to_np()'}"
            )
        return pl.DataFrame(
            {
                str(col): _vector_to_py_list(vec)
                for col, vec in zip(robj.names, robj, strict=True)
            }
        )


def r_to_np(r_var_name: str) -> np.ndarray:
    """Pull an R vector, matrix or array from the global environment into NumPy.

    For array-like R objects only. Tabular R objects (data.frames) belong in
    `r_to_pl`, lists in `r_to_py`, and both raise here rather than reshaping
    themselves into a surprise. `NA` in a numeric array arrives as `NaN`; in an
    integer, logical or character array it has no NumPy counterpart, so that
    raises too.
    """
    with _conv.context():
        robj = ro.globalenv[r_var_name]
        rclass = _rclass(robj)
        if "data.frame" in rclass:
            raise NotImplementedError(
                f"{r_var_name!r} is a data.frame -> use r_to_pl()"
            )
        if isinstance(robj, ro.ListVector):
            raise NotImplementedError(f"{r_var_name!r} is a list -> use r_to_py()")
        if "factor" in rclass:
            raise NotImplementedError(
                f"{r_var_name!r} is a factor, whose codes are not its values -> "
                "use r_to_py() for the labels, or as.integer() in R for the codes"
            )
        if _TEMPORAL_CLASSES.intersection(rclass):
            raise NotImplementedError(
                f"{r_var_name!r} has R class {', '.join(rclass)}, which NumPy would "
                "receive as bare numbers -> use r_to_py() for dates, or "
                "as.numeric() in R if the numbers are what you want"
            )
        if isinstance(robj, (ro.IntVector, ro.BoolVector, ro.StrVector)) and bool(
            ro.r["anyNA"](robj)[0]
        ):
            raise ValueError(
                f"{r_var_name!r} contains NA, which has no NumPy counterpart "
                "for its type -> use r_to_py(), or as.numeric() in R to get NaN"
            )
        array = np.asarray(robj)
        # rpy2 applies R's `dim` for numeric vectors but not for character ones,
        # where np.asarray hands back a flat array. Re-impose it from R, in
        # column-major order, so a character matrix keeps its shape.
        dim = ro.r["dim"](robj)
        if not isinstance(dim, rinterface.NULLType):
            shape = tuple(int(d) for d in dim)
            if array.shape != shape:
                array = array.reshape(shape, order="F")
        return array


def r_to_py(r_var_name: str) -> Any:
    """Pull an R object into its natural native Python form.

    Fully named R list -> `dict` (recursive); unnamed or partly named list ->
    `list`, positions kept; atomic vector -> `list`, and a length-1 vector
    scalarizes. `NULL` -> `None`, `NA` -> `None`, a factor -> its labels.
    Matrices and data.frames raise with a hint: they belong in `r_to_np` and
    `r_to_pl` respectively.
    """
    with _conv.context():
        return _r_to_py(ro.globalenv[r_var_name])


def _native(value: Any) -> Any:
    """A NumPy scalar as its Python equivalent; anything else unchanged."""
    return value.item() if isinstance(value, np.generic) else value


def _is_na(value: Any) -> bool:
    """True for R's typed NA sentinels, and for the nan carrying `NA_real_`."""
    if value is None or isinstance(value, _NA_TYPES):
        return True
    return isinstance(value, float) and math.isnan(value)


def _rclass(robj: Any) -> list[str]:
    rclass = getattr(robj, "rclass", None)
    return [] if rclass is None else [str(c) for c in rclass]


def _int_vector(values: Sequence[Any]) -> Any:
    """An R integer vector, widened to double when a value will not fit."""
    if any(v is not None and not (_INT32_MIN <= v <= _INT32_MAX) for v in values):
        return ro.FloatVector([ro.NA_Real if v is None else float(v) for v in values])
    return ro.IntVector([ro.NA_Integer if v is None else int(v) for v in values])


def _atomic_vector(items: Sequence[Any]) -> Any:
    """An R atomic vector for a uniform list of scalars (None -> NA), else None."""
    items = [_native(x) for x in items]
    present = [x for x in items if x is not None]
    if not present:
        # All missing: R's own `c(NA, NA)` is logical, so follow it.
        return ro.BoolVector([ro.NA_Logical] * len(items))
    if all(isinstance(x, bool) for x in present):
        return ro.BoolVector([ro.NA_Logical if x is None else bool(x) for x in items])
    if any(isinstance(x, bool) for x in present):
        # bool is a subclass of int, but a bool beside a number is not a uniform
        # vector — c(1, TRUE) silently coerces, so build a list instead.
        return None
    if all(isinstance(x, int) for x in present):
        return _int_vector(items)
    if all(isinstance(x, (int, float)) for x in present):
        return ro.FloatVector([ro.NA_Real if x is None else float(x) for x in items])
    if all(isinstance(x, str) for x in present):
        return ro.StrVector([ro.NA_Character if x is None else x for x in items])
    return None


def _py_to_r(obj: Any) -> Any:
    obj = _native(obj)
    if obj is None:
        return ro.NULL
    if isinstance(obj, dict):
        return ro.ListVector({str(k): _py_to_r(v) for k, v in obj.items()})
    if isinstance(obj, (list, tuple)):
        if len(obj) == 0:
            return ro.r.list()
        vec = _atomic_vector(obj)
        if vec is not None:
            return vec
        return ro.r.list(*(_py_to_r(x) for x in obj))
    if isinstance(obj, (bool, int, float, str)):
        return _atomic_vector([obj])
    if isinstance(obj, np.ndarray):
        raise TypeError("NumPy arrays go through np_to_r(), not py_to_r()")
    if isinstance(obj, pl.DataFrame):
        raise TypeError("Polars DataFrames go through pl_to_r(), not py_to_r()")
    raise TypeError(f"cannot convert {type(obj).__name__} to R")


def _np_to_r(arr: np.ndarray) -> Any:
    a = np.asarray(arr)
    # R is column-major, so unravel in Fortran order and let R re-impose `dim`.
    flat = a.ravel(order="F").tolist()
    kind = a.dtype.kind
    if kind == "b":
        vec = ro.BoolVector([bool(v) for v in flat])
    elif kind in "iu":
        vec = _int_vector([int(v) for v in flat])
    elif kind == "f":
        vec = ro.FloatVector([float(v) for v in flat])
    elif kind in "US" or (
        kind == "O" and all(v is None or isinstance(v, str) for v in flat)
    ):
        # An object array of anything but strings would be str()-ed into
        # plausible-looking nonsense, so only strings take this path.
        vec = ro.StrVector([ro.NA_Character if v is None else str(v) for v in flat])
    else:
        raise TypeError(f"cannot convert a NumPy array of dtype {a.dtype} to R")
    if a.ndim < 2:
        return vec
    if a.ndim == 2:
        return ro.r.matrix(vec, nrow=a.shape[0], ncol=a.shape[1])
    return ro.r.array(vec, dim=ro.IntVector(list(a.shape)))


def _column_to_r(series: pl.Series) -> Any:
    dtype = series.dtype
    values = series.to_list()
    if dtype == pl.Boolean:
        return ro.BoolVector([ro.NA_Logical if v is None else bool(v) for v in values])
    if dtype.is_integer():
        return _int_vector(values)
    if dtype.is_float():
        return ro.FloatVector([ro.NA_Real if v is None else float(v) for v in values])
    if dtype == pl.String or dtype.base_type() in (pl.Categorical, pl.Enum):
        return ro.StrVector([ro.NA_Character if v is None else str(v) for v in values])
    if dtype == pl.Date:
        days = [ro.NA_Real if v is None else float((v - _EPOCH).days) for v in values]
        return ro.r.structure(ro.FloatVector(days), **{"class": "Date"})
    raise TypeError(
        f"column {series.name!r} has dtype {dtype}, which does not cross the "
        "bridge; cast it to a string, an integer, a float or a date first"
    )


def _vector_to_py_list(robj: Any) -> list[Any]:
    """An R atomic vector as a native list, NA -> None."""
    rclass = _rclass(robj)
    if "factor" in rclass:
        levels = [str(level) for level in robj.do_slot("levels")]
        return [None if _is_na(c) else levels[int(c) - 1] for c in robj]
    if "Date" in rclass:
        return [None if _is_na(d) else _EPOCH + dt.timedelta(days=int(d)) for d in robj]
    if _TEMPORAL_CLASSES.intersection(rclass):
        raise NotImplementedError(
            f"R class {', '.join(rclass)} carries a time zone or unit this bridge "
            "will not guess; format() or as.numeric() it in R first"
        )
    if isinstance(robj, _ATOMIC_VECTORS):
        return [None if _is_na(v) else v for v in robj]
    raise NotImplementedError(
        f"cannot convert R object of class "
        f"{', '.join(rclass) or type(robj).__name__} to Python"
    )


def _r_to_py(robj: Any) -> Any:
    if isinstance(robj, rinterface.NULLType):
        return None
    rclass = _rclass(robj)
    if "data.frame" in rclass:
        raise NotImplementedError("data.frame -> use r_to_pl()")
    if {"matrix", "array"}.intersection(rclass):
        raise NotImplementedError("matrix/array -> use r_to_np()")
    if isinstance(robj, ro.ListVector):
        names = [str(n) for n in robj.names] if robj.names else []
        values = [_r_to_py(x) for x in robj]
        if len(names) != len(values) or not all(names):
            # Unnamed, or named only in part: a dict would silently collide the
            # blanks onto one key, so keep the positions instead.
            return values
        if len(set(names)) != len(names):
            duplicates = sorted({n for n in names if names.count(n) > 1})
            raise ValueError(
                f"R list has duplicate names {duplicates}, which a dict cannot "
                "hold; rename them in R, or index the list positionally"
            )
        return dict(zip(names, values, strict=True))
    values = _vector_to_py_list(robj)
    return values[0] if len(values) == 1 else values


__all__ = [
    "PROJECT_ROOT",
    "np_to_r",
    "pl_to_r",
    "py_to_r",
    "r_eval",
    "r_png",
    "r_set",
    "r_to_np",
    "r_to_pl",
    "r_to_py",
]
