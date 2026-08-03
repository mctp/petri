"""Transformations over the example measurement table.

Shows the shape of a module in this package: functions that take frames and
return frames, with no knowledge of the source of the data or the destination of
the result.
"""

from __future__ import annotations

import polars as pl


def summarize_batches(measurements: pl.DataFrame) -> pl.DataFrame:
    """Mean intensity and strongest p-value per batch x group.

    Args:
        measurements: rows with `batch`, `group`, `intensity`, `p_value`.

    Returns:
        One row per (group, batch), sorted. A transformation that changes the
        row order between runs changes the CSV bytes and causes a write on
        every run.
    """
    return (
        measurements.group_by("batch", "group")
        .agg(
            n=pl.len(),
            mean_intensity=pl.col("intensity").mean().round(4),
            min_p=pl.col("p_value").min(),
        )
        .sort("group", "batch")
    )


def rank_by_significance(measurements: pl.DataFrame) -> pl.DataFrame:
    """Samples ordered by ascending p-value, most significant first."""
    return measurements.sort("p_value").select(
        "sample_id", "batch", "group", "intensity", "p_value"
    )
