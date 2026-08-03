import marimo

__generated_with = "0.23.15"
app = marimo.App(width="medium")


@app.cell(hide_code=True)
def _():
    import marimo as mo

    from petri import CACHE_DIR, external_path, load_external, save_shared

    return CACHE_DIR, external_path, load_external, mo, save_shared


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        """
        # 00 — Prepare measurements

        A **producer notebook**. It reads `external/`, calls `processing/`, and
        publishes to `shared/`. `make shared` runs every `notebooks/NN_*.py` in
        sorted order, so the numeric prefix sets the run order.

        ```
        external/  ->  processing/  ->  shared/  ->  analysis notebooks
        ```

The cell orchestrates; `processing/` computes. `coding_patterns.py` patterns
        7-10 cover the artifact API.
        """
    )
    return


@app.cell
def measurements_ranked(CACHE_DIR, external_path, load_external, mo, save_shared):
    from processing.measurements import rank_by_significance

    raw = load_external("example_measurements.csv")

    # The cache key covers the block's code and its inputs.
    with mo.persistent_cache("measurements_ranked", save_path=str(CACHE_DIR)):
        ranked = rank_by_significance(raw)

    # Outside the block: on a cache hit marimo skips the block and its writes.
    save_shared(
        ranked,
        "measurements-ranked",
        inputs=[external_path("example_measurements.csv")],
        description="Samples ordered by ascending p-value",
    )
    return (raw,)


@app.cell
def batch_stats(external_path, raw, save_shared):
    from processing.measurements import summarize_batches

    save_shared(
        summarize_batches(raw),
        "batch-stats",
        inputs=[external_path("example_measurements.csv")],
        description="Mean intensity and strongest p-value per batch and group",
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        """
        ## Output

        | Table | Contents |
        |---|---|
        | `shared/measurements-ranked` | one row per sample, sorted by p-value |
        | `shared/batch-stats` | one row per batch and group |

        Git tracks the manifests, not the CSV bytes. Run `make check` to verify
        both against their manifests.
        """
    )
    return


if __name__ == "__main__":
    app.run()
