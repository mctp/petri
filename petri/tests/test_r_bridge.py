"""Round-trip contracts for the R bridge.

Every test here is a shape that used to convert silently wrong — dropped list
elements, factor codes in place of labels, a null that raised a TypeError from
inside rpy2. They run against the real embedded R, so the whole module skips
when rpy2 or the renv library is not installed.
"""

from __future__ import annotations

import datetime as dt

import numpy as np
import polars as pl
import pytest

r_bridge = pytest.importorskip(
    "petri.r_bridge", reason="rpy2 and an R installation are needed for the R bridge"
)

np_to_r = r_bridge.np_to_r
pl_to_r = r_bridge.pl_to_r
py_to_r = r_bridge.py_to_r
r_eval = r_bridge.r_eval
r_set = r_bridge.r_set
r_to_np = r_bridge.r_to_np
r_to_pl = r_bridge.r_to_pl
r_to_py = r_bridge.r_to_py


# --- r_to_py: lists, names, NULL -------------------------------------------


def test_named_list_becomes_a_dict():
    r_eval("t_named <- list(a = 1, b = 'x', c = list(d = TRUE))")
    assert r_to_py("t_named") == {"a": 1.0, "b": "x", "c": {"d": True}}


def test_partly_named_list_keeps_every_element():
    """A dict would collide the unnamed elements onto one '' key."""
    r_eval("t_partial <- list(a = 1, 2, 3)")
    assert r_to_py("t_partial") == [1.0, 2.0, 3.0]


def test_unnamed_list_is_positional():
    r_eval("t_unnamed <- list(1, 'x')")
    assert r_to_py("t_unnamed") == [1.0, "x"]


def test_duplicate_names_raise_rather_than_collapse():
    r_eval("t_dupes <- list(a = 1, a = 2, b = 3)")
    with pytest.raises(ValueError, match="duplicate names"):
        r_to_py("t_dupes")


def test_null_becomes_none():
    r_eval("t_null <- list(a = 1, b = NULL)")
    assert r_to_py("t_null") == {"a": 1.0, "b": None}


def test_na_becomes_none():
    r_eval(
        "t_nas <- list(s = c('a', NA), i = c(1L, NA), b = c(TRUE, NA), f = c(1.5, NA))"
    )
    assert r_to_py("t_nas") == {
        "s": ["a", None],
        "i": [1, None],
        "b": [True, None],
        "f": [1.5, None],
    }


def test_factor_gives_labels_not_codes():
    r_eval("t_factor <- factor(c('lo', 'hi', 'lo'))")
    assert r_to_py("t_factor") == ["lo", "hi", "lo"]


def test_length_one_vector_scalarizes():
    r_eval("t_one <- 42")
    assert r_to_py("t_one") == 42.0


def test_wrong_shapes_point_at_the_right_function():
    r_eval("t_df <- data.frame(a = 1:2)")
    r_eval("t_mat <- matrix(1:4, nrow = 2)")
    with pytest.raises(NotImplementedError, match="r_to_pl"):
        r_to_py("t_df")
    with pytest.raises(NotImplementedError, match="r_to_np"):
        r_to_py("t_mat")


def test_unconvertible_object_raises_instead_of_leaking_rpy2():
    r_eval("t_fun <- function(x) x + 1")
    with pytest.raises(NotImplementedError, match="cannot convert"):
        r_to_py("t_fun")


# --- py_to_r ---------------------------------------------------------------


def test_dict_round_trips():
    payload = {"name": "alice", "scores": [90.5, 85.0], "meta": {"id": 7}}
    py_to_r(payload, "t_cfg")
    assert r_to_py("t_cfg") == payload


def test_int_is_an_r_integer_in_both_shapes():
    """The scalar and the list path have to agree on the type."""
    py_to_r(5, "t_scalar")
    py_to_r([5, 6], "t_list")
    assert list(r_eval("c(class(t_scalar), class(t_list))")) == ["integer", "integer"]
    assert r_to_py("t_scalar") == 5


def test_int_too_wide_for_r_widens_to_double():
    py_to_r([2**40, 1], "t_wide")
    assert list(r_eval("class(t_wide)")) == ["numeric"]
    assert r_to_py("t_wide") == [float(2**40), 1.0]


def test_none_becomes_null_and_na():
    py_to_r(None, "t_none")
    py_to_r(
        {"nums": [1.0, None], "text": ["a", None], "flags": [True, None]}, "t_holes"
    )
    assert list(r_eval("class(t_none)")) == ["NULL"]
    assert list(r_eval("sapply(t_holes, function(x) sum(is.na(x)))")) == [1, 1, 1]
    assert r_to_py("t_holes") == {
        "nums": [1.0, None],
        "text": ["a", None],
        "flags": [True, None],
    }


def test_bool_beside_a_number_is_not_coerced_into_one_vector():
    py_to_r([1, True], "t_mixed")
    assert list(r_eval("class(t_mixed)")) == ["list"]
    assert r_to_py("t_mixed") == [1, True]


def test_numpy_scalars_convert_like_their_python_equivalents():
    py_to_r({"n": np.int64(3), "x": np.float64(1.5), "b": np.bool_(True)}, "t_npscalar")
    assert r_to_py("t_npscalar") == {"n": 3, "x": 1.5, "b": True}


def test_wrong_types_name_the_right_function():
    with pytest.raises(TypeError, match="np_to_r"):
        py_to_r(np.array([1.0, 2.0]), "t_bad")
    with pytest.raises(TypeError, match="pl_to_r"):
        py_to_r(pl.DataFrame({"a": [1]}), "t_bad")


# --- np_to_r / r_to_np -----------------------------------------------------


def test_matrix_round_trips_with_its_layout():
    arr = np.array([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]])
    np_to_r(arr, "t_m")
    assert list(r_eval("dim(t_m)")) == [2, 3]
    assert r_eval("t_m[1, 2]")[0] == 2.0
    assert np.array_equal(r_to_np("t_m"), arr)


def test_vector_and_nd_array_round_trip():
    np_to_r(np.array([1, 2, 3]), "t_v")
    np_to_r(np.arange(24).reshape(2, 3, 4), "t_a")
    assert np.array_equal(r_to_np("t_v"), np.array([1, 2, 3]))
    assert np.array_equal(r_to_np("t_a"), np.arange(24).reshape(2, 3, 4))


def test_r_to_np_refuses_shapes_it_would_mangle():
    r_eval("t_df2 <- data.frame(a = 1:2, b = c('x', 'y'))")
    r_eval("t_list2 <- list(a = 1, b = 2)")
    r_eval("t_fac <- factor(c('lo', 'hi'))")
    r_eval("t_naint <- c(1L, NA)")
    with pytest.raises(NotImplementedError, match="r_to_pl"):
        r_to_np("t_df2")
    with pytest.raises(NotImplementedError, match="r_to_py"):
        r_to_np("t_list2")
    with pytest.raises(NotImplementedError, match="factor"):
        r_to_np("t_fac")
    with pytest.raises(ValueError, match="NA"):
        r_to_np("t_naint")


def test_r_to_np_keeps_na_real_as_nan():
    r_eval("t_nareal <- c(1.5, NA)")
    pulled = r_to_np("t_nareal")
    assert pulled[0] == 1.5
    assert np.isnan(pulled[1])


# --- pl_to_r / r_to_pl -----------------------------------------------------


def test_dtypes_survive_the_round_trip():
    df = pl.DataFrame(
        {
            "i": [1, 2],
            "f": [1.5, 2.5],
            "b": [True, False],
            "s": ["a", "b"],
            "d": [dt.date(2020, 1, 1), dt.date(2020, 1, 2)],
        }
    )
    pl_to_r(df, "t_df3")
    assert list(r_eval("sapply(t_df3, function(x) class(x)[1])")) == [
        "integer",
        "numeric",
        "logical",
        "character",
        "Date",
    ]
    assert r_to_pl("t_df3").equals(df)


def test_nulls_cross_as_na():
    df = pl.DataFrame(
        {"n": [1.0, None], "i": [1, None], "t": ["a", None], "b": [True, None]}
    )
    pl_to_r(df, "t_holes2")
    assert list(r_eval("sapply(t_holes2, function(x) sum(is.na(x)))")) == [1, 1, 1, 1]
    assert r_to_pl("t_holes2").equals(df)


def test_categorical_and_enum_go_as_character():
    df = pl.DataFrame(
        {
            "c": pl.Series(["x", "y"], dtype=pl.Categorical),
            "e": pl.Series(["a", "b"], dtype=pl.Enum(["a", "b"])),
        }
    )
    pl_to_r(df, "t_cat")
    assert list(r_eval("sapply(t_cat, class)")) == ["character", "character"]
    assert r_to_pl("t_cat").to_dict(as_series=False) == {
        "c": ["x", "y"],
        "e": ["a", "b"],
    }


def test_column_names_are_not_mangled():
    pl_to_r(pl.DataFrame({"a b": [1], "x-y": [2]}), "t_names")
    assert list(r_eval("names(t_names)")) == ["a b", "x-y"]


def test_wide_ints_widen_to_double():
    pl_to_r(pl.DataFrame({"big": [2**40]}), "t_bigcol")
    assert list(r_eval("class(t_bigcol$big)")) == ["numeric"]


def test_unsupported_dtype_names_the_column():
    df = pl.DataFrame({"when": [dt.datetime(2020, 1, 1, 12)]})
    with pytest.raises(TypeError, match="when"):
        pl_to_r(df, "t_bad2")


def test_r_to_pl_gives_factor_labels_and_dates():
    r_eval(
        "t_rdf <- data.frame(g = factor(c('lo', 'hi')), "
        "d = as.Date(c('2020-01-01', '2020-01-02')), stringsAsFactors = TRUE)"
    )
    pulled = r_to_pl("t_rdf")
    assert pulled["g"].to_list() == ["lo", "hi"]
    assert pulled["d"].to_list() == [dt.date(2020, 1, 1), dt.date(2020, 1, 2)]


def test_r_to_pl_refuses_a_non_data_frame():
    r_eval("t_mat2 <- matrix(1:4, nrow = 2)")
    r_eval("t_plainlist <- list(a = 1, b = 2)")
    with pytest.raises(NotImplementedError, match="r_to_np"):
        r_to_pl("t_mat2")
    with pytest.raises(NotImplementedError, match="r_to_py"):
        r_to_pl("t_plainlist")


def test_posix_columns_raise_rather_than_arrive_as_seconds():
    r_eval("t_posix <- data.frame(when = as.POSIXct('2020-01-01 12:00', tz = 'UTC'))")
    with pytest.raises(NotImplementedError, match="time zone"):
        r_to_pl("t_posix")


# --- r_set -----------------------------------------------------------------


def test_r_set_matches_py_to_r():
    """Same converter, reversed arguments — bools and dicts included."""
    r_set("t_flag", True)
    r_set("t_cfg2", {"a": [1, 2]})
    assert list(r_eval("class(t_flag)")) == ["logical"]
    assert r_to_py("t_cfg2") == {"a": [1, 2]}


def test_r_set_passes_rpy2_objects_through():
    r_set("t_raw", r_eval("1:3"))
    assert r_to_py("t_raw") == [1, 2, 3]


def test_r_to_np_refuses_dates_that_would_arrive_as_numbers():
    r_eval("t_dates <- as.Date(c('2020-01-01', '2020-01-02'))")
    with pytest.raises(NotImplementedError, match="r_to_py"):
        r_to_np("t_dates")


def test_np_to_r_refuses_arrays_it_cannot_carry():
    with pytest.raises(TypeError, match="dtype"):
        np_to_r(np.array([{"a": 1}, {"b": 2}], dtype=object), "t_objs")
    with pytest.raises(TypeError, match="dtype"):
        np_to_r(np.array(["2020-01-01"], dtype="datetime64[D]"), "t_dt64")


def test_np_to_r_carries_strings_and_bools():
    np_to_r(np.array([["a", "b"], ["c", "d"]]), "t_strs")
    np_to_r(np.array([True, False]), "t_bools")
    assert list(r_eval("c(class(t_strs), class(t_bools))")) == [
        "matrix",
        "array",
        "logical",
    ]
    assert r_to_np("t_strs").tolist() == [["a", "b"], ["c", "d"]]
