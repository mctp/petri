import marimo

__generated_with = "0.23.15"
app = marimo.App(width="medium")


@app.cell(hide_code=True)
def _():
    import marimo as mo
    import matplotlib.pyplot as plt
    import numpy as np
    import polars as pl
    import seaborn as sns

    from petri import (
        CACHE_DIR,
        PROJECT_ROOT,
        ArtifactError,
        check,
        external_path,
        list_preserved,
        list_shared,
        load_external,
        load_shared,
        preserve_figure,
        preserve_file,
        preserve_table,
        preserved_path,
        save_shared,
        shared_path,
    )
    from petri.r_bridge import pl_to_r, r_eval, r_set, r_to_pl

    return (
        ArtifactError,
        CACHE_DIR,
        PROJECT_ROOT,
        check,
        external_path,
        list_preserved,
        list_shared,
        load_external,
        load_shared,
        mo,
        np,
        pl,
        pl_to_r,
        plt,
        preserve_figure,
        preserve_file,
        preserve_table,
        preserved_path,
        r_eval,
        r_set,
        r_to_pl,
        save_shared,
        shared_path,
        sns,
    )


@app.cell(hide_code=True)
def _(PROJECT_ROOT, mo):
    mo.vstack(
        [
            mo.md(
                """
                # Full Example — one notebook, end to end

                Reads `data/external/`, calls `scripts/`, publishes to `data/shared/`,
                then consumes that table and writes deliverables to `data/preserved/`.

                ```
                data/external/  ->  scripts/  ->  data/shared/  ->  data/preserved/
                ```

                **Install this notebook with `make init full`**, which also places
                `scripts/` and the example data it reads. `make init minimal` leaves it
                out.

                ## Publishing a shared table

                The first two cells are the *producing* side. They are the only cells
                here that write `data/shared/`, and every pattern below reads what they
                wrote. Writing a file is not a dependency marimo can see, so those
                cells return the paths they wrote and the readers take them as
                arguments. That argument is what puts them in order.

                ## Patterns

                1. **Interactive UI Widgets & Reactive DAG** (`mo.ui.slider`, `mo.ui.dropdown`)
                2. **Python $\\leftrightarrow$ R Data Exchange** (`pl_to_r`, `r_eval`, `r_to_pl`)
                3. **Bioconductor Package Interop** (`limma` differential analysis via `r_bridge`)
                4. **Supervised Clustered Heatmap** (`sns.clustermap`, Z-scored rows, category color bars)
                5. **Consume the Interface Layer** — `load_shared()` verifies and restores dtypes
                6. **Preserving a Deliverable** — `preserve_figure()` writes pdf + png + source data + manifest
                7. **Deliverable Table + Sidecar** — `preserve_table()` and `preserve_file()` sharing one bundle
                8. **Verification** — `check()` and `list_preserved()`, the same pass `make check` runs

                Two patterns live in their own notebooks rather than being repeated here,
                since `make init full` installs those too:

                - **R figure rendering recipes** (four methods: disk PNG, in-memory PNG,
                  vector SVG, `grdevices` capture) — see `r_example.py`
                - **Python plotting with statistical overlays** (`seaborn` boxplot,
                  scipy t-test) — see `py_example.py`

                Patterns 1-4 use synthetic data and write only to `data/cache/`, which you
                can delete. Patterns 5-8 use the shared table and write `data/preserved/`.
                Exploratory output is never committed; a deliverable carries a manifest and
                is committed.

                ## Project Documentation
                """
            ),
            mo.accordion(
                {
                    "Architecture & Design": mo.md(
                        (PROJECT_ROOT / "petri/docs/architecture.md").read_text()
                    ),
                    "R Environment (renv)": mo.md(
                        (PROJECT_ROOT / "petri/docs/renv.md").read_text()
                    ),
                    "rpy2 Setup": mo.md(
                        (PROJECT_ROOT / "petri/docs/rpy2.md").read_text()
                    ),
                    "Agent Guidelines": mo.md((PROJECT_ROOT / "AGENTS.md").read_text()),
                }
            ),
        ]
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.vstack(
        [
            mo.md(
                """
                ### Bioconductor Setup & Package Management

                Bioconductor packages are integrated into the project's local `renv` library:

                * **Install CRAN package:** `make r-install PKG="ggplot2"`
                * **Install Bioconductor package:** `make r-install PKG="bioc::limma"` or `PKG="bioc::DESeq2"`
                * **Restore R library on fresh clone:** `make r-restore`
                * **R-Python Bridge:** Importing `r_bridge` automatically sets working directory to project root, activating `.Rprofile` and `.renv/library/` once for the entire session.
                """
            )
        ]
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        """
        ## Publish: `data/external/` -> `scripts/` -> `data/shared/`

        The cell orchestrates; `scripts/` computes. Keep the transformation in
        `scripts/` as a pure function so it can be tested and so `check()` can hash
        it: an edit there marks every artifact built from it stale.

        `save_shared()` returns the file it wrote. Return that path, and the cells
        below that read the table take it as an argument. marimo registers a
        dependency only through an argument, and that is what puts the cells in
        order.
        """
    )
    return


@app.cell
def measurements_ranked(CACHE_DIR, external_path, load_external, mo, save_shared):
    from scripts.measurements import rank_by_significance

    raw = load_external("example_measurements.csv")

    # The cache key covers the block's code and its inputs.
    with mo.persistent_cache("measurements_ranked", save_path=str(CACHE_DIR)):
        ranked = rank_by_significance(raw)

    # Outside the block: on a cache hit marimo skips the block and its writes.
    ranked_csv = save_shared(
        ranked,
        "measurements-ranked",
        inputs=[external_path("example_measurements.csv")],
        title="Samples ordered by ascending p-value",
    )
    return ranked_csv, raw


@app.cell
def batch_stats(external_path, raw, save_shared):
    from scripts.measurements import summarize_batches

    batch_stats_csv = save_shared(
        summarize_batches(raw),
        "batch-stats",
        inputs=[external_path("example_measurements.csv")],
        title="Mean intensity and strongest p-value per batch and group",
    )
    return (batch_stats_csv,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        """
        | Table | Contents |
        |---|---|
        | `data/shared/measurements-ranked` | one row per sample, sorted by p-value |
        | `data/shared/batch-stats` | one row per batch and group |

        Git tracks the manifests, not the CSV bytes. Run `make check` to verify both
        against their manifests.
        """
    )
    return


@app.cell(hide_code=True)
def _(mo):
    # Pattern 1: Interactive Marimo UI Widgets
    samples_per_group = mo.ui.slider(10, 100, 10, value=30, label="samples per group")
    effect_size = mo.ui.slider(0.0, 3.0, 0.2, value=1.2, label="group effect size")
    cmap_choice = mo.ui.dropdown(
        options=["vlag", "coolwarm", "RdBu_r", "viridis"],
        value="vlag",
        label="heatmap colormap",
    )

    mo.vstack(
        [
            mo.md("### Pattern 1: Interactive UI Widgets & Reactive DAG"),
            mo.md(
                "The sliders feed the synthetic frame used by patterns 2-3; the "
                "dropdown feeds the heatmap in pattern 4. Moving any of them re-runs "
                "only the cells downstream of it."
            ),
            mo.hstack([samples_per_group, effect_size, cmap_choice]),
        ]
    )
    return cmap_choice, effect_size, samples_per_group


@app.cell(hide_code=True)
def _(effect_size, np, pl, samples_per_group):
    # Generate synthetic Polars DataFrame reactively based on UI slider state
    _rng = np.random.default_rng(42)
    _groups = ["Control", "Treatment_A", "Treatment_B"]
    _means = [0.0, effect_size.value * 0.8, effect_size.value * 1.5]

    _rows = []
    for _g, _m in zip(_groups, _means, strict=True):
        _rows.append(
            pl.DataFrame(
                {
                    "group": [_g] * samples_per_group.value,
                    "value": _rng.normal(_m, 1.0, samples_per_group.value),
                    "group_code": [_g[:3].upper()] * samples_per_group.value,
                }
            )
        )

    df_synth = pl.concat(_rows)
    return (df_synth,)


@app.cell(hide_code=True)
def _(df_synth, mo, pl_to_r, r_eval, r_to_pl):
    # Pattern 2: Python <-> R Data Exchange via Polars and r_bridge

    # 1. Push Polars DataFrame to R
    pl_to_r(df_synth, "r_df")

    # 2. Modify data in R (compute z-scores per group and add a summary column using dplyr)
    r_eval("""
    library(dplyr)

    r_df <- r_df %>%
      group_by(group) %>%
      mutate(
        z_score = (value - mean(value)) / sd(value),
        is_outlier = abs(z_score) > 2.0
      ) %>%
      ungroup()
    """)

    # 3. Pull modified data frame from R back into Polars
    df_transformed = r_to_pl("r_df")

    mo.vstack(
        [
            mo.md(
                "### Pattern 2: Python $\\leftrightarrow$ R DataFrame Exchange"
                " (`r_bridge`)\n"
                "Pushed `df_synth` Polars DataFrame to R, computed `z_score` and"
                " `is_outlier` flags in R (`dplyr`), and pulled back into Polars."
                " For rendering R figures, see `r_example.py`."
            ),
            df_transformed.head(10),
        ]
    )
    return


@app.cell(hide_code=True)
def _(CACHE_DIR, mo, np, pl, pl_to_r, r_eval, r_set):
    # Pattern 3: Bioconductor Package Interop (limma) via r_bridge
    _rng = np.random.default_rng(123)
    _n_features, _n_samples = 300, 30

    _samples = [f"S{i:02d}" for i in range(_n_samples)]
    _groups = ["Control"] * 15 + ["Treatment"] * 15

    # Base expression matrix
    _mat = _rng.normal(loc=8.0, scale=1.5, size=(_n_features, _n_samples))
    _features = [f"FEATURE_{i:03d}" for i in range(_n_features)]

    # Add synthetic effect to top 20 features
    _mat[:20, 15:] += _rng.normal(loc=2.0, scale=0.5, size=(20, 15))

    expr_pl = (
        pl.DataFrame(_mat, schema=_samples)
        .with_columns(pl.Series("feature", _features))
        .select(["feature", *_samples])
    )

    pheno_pl = pl.DataFrame({"sample": _samples, "group": _groups})

    # Pass data to R
    pl_to_r(expr_pl, "expr_df")
    pl_to_r(pheno_pl, "pheno_df")

    bioc_plot_path = CACHE_DIR / "pattern3_bioc_limma_volcano.png"
    bioc_csv_path = CACHE_DIR / "pattern3_bioc_limma_results.csv"

    r_set("bioc_plot_path", str(bioc_plot_path))
    r_set("bioc_csv_path", str(bioc_csv_path))

    # Execute Bioconductor limma workflow in R
    r_eval("""
    library(limma)
    library(ggplot2)
    library(ggrepel)

    expr <- as.matrix(expr_df[, -1])
    rownames(expr) <- expr_df$feature

    pheno <- as.data.frame(pheno_df)
    pheno$group <- factor(pheno$group, levels=c("Control", "Treatment"))

    # Sample Alignment Verification
    common <- intersect(colnames(expr), pheno$sample)
    expr <- expr[, common, drop=FALSE]
    pheno <- pheno[match(colnames(expr), pheno$sample), , drop=FALSE]

    design <- model.matrix(~ group, data=pheno)
    fit <- lmFit(expr, design)
    fit <- eBayes(fit)

    results <- topTable(fit, coef="groupTreatment", number=Inf, sort.by="p")
    results$feature <- rownames(results)
    results$sig <- ifelse(results$adj.P.Val < 0.05 & abs(results$logFC) > 1, "Significant", "Not Sig")

    top_labels <- head(results[order(results$P.Value), ], 10)

    p <- ggplot(results, aes(x=logFC, y=-log10(P.Value), color=sig)) +
      geom_point(alpha=0.6, size=1.5) +
      scale_color_manual(values=c("Significant"="#d14848", "Not Sig"="#b3b3b3")) +
      geom_vline(xintercept=c(-1, 1), linetype="dashed", color="grey50") +
      geom_hline(yintercept=-log10(0.05), linetype="dashed", color="grey50") +
      geom_text_repel(data=top_labels, aes(label=feature), size=3, max.overlaps=10) +
      labs(title="Pattern 3: Bioconductor limma Modeling via r_bridge",
           x="log2 Fold Change", y="-log10(p-value)") +
      theme_minimal(base_size=11)

    ggsave(bioc_plot_path, p, width=6, height=4.5, dpi=150)
    write.csv(results, bioc_csv_path, row.names=FALSE)
    """)

    bioc_results = pl.read_csv(bioc_csv_path)

    mo.vstack(
        [
            mo.md(
                "### Pattern 3: Bioconductor Package Interop (`limma` via"
                " `r_bridge`)\n"
                "Executes high-throughput linear modeling on a Polars matrix"
                " transferred to R, renders a volcano plot, and exports a"
                " `topTable`."
            ),
            mo.image(bioc_plot_path.read_bytes(), width=550),
            mo.md("#### Top Differential Features"),
            bioc_results.head(10).select(
                ["feature", "logFC", "AveExpr", "t", "P.Value", "adj.P.Val"]
            ),
        ]
    )
    return


@app.cell(hide_code=True)
def _(CACHE_DIR, cmap_choice, mo, np, plt, sns):
    # Pattern 4: Supervised Clustered Heatmap (seaborn)
    import pandas as pd
    from matplotlib.patches import Patch

    _rng = np.random.default_rng(77)
    _n_features, _n_samples = 25, 30

    _groups = ["Group_A"] * 10 + ["Group_B"] * 10 + ["Group_C"] * 10
    _sample_ids = [f"Sample_{i:02d}" for i in range(_n_samples)]

    _matrix = _rng.normal(loc=5.0, scale=1.0, size=(_n_features, _n_samples))
    # Add group-specific signal pattern
    _matrix[:8, :10] += 2.5
    _matrix[8:16, 10:20] += 2.5
    _matrix[16:, 20:] += 2.5

    # Row Z-score normalization
    _z_matrix = (_matrix - _matrix.mean(axis=1, keepdims=True)) / (
        _matrix.std(axis=1, keepdims=True) + 1e-9
    )

    _meta_df = pd.DataFrame({"Group": _groups}, index=_sample_ids)
    _meta_df["Group"] = _meta_df["Group"].astype("category")

    _palette = {
        "Group_A": "#4e79a7",
        "Group_B": "#f28e2b",
        "Group_C": "#e15759",
    }
    _col_colors = _meta_df["Group"].map(_palette)

    _g = sns.clustermap(
        _z_matrix,
        col_colors=_col_colors.to_numpy(),
        cmap=cmap_choice.value,
        center=0,
        figsize=(7, 5.5),
        xticklabels=False,
        yticklabels=[f"Feature_{i:02d}" for i in range(_n_features)],
    )

    _legend_handles = [
        Patch(color=color, label=label) for label, color in _palette.items()
    ]
    _g.ax_heatmap.legend(
        handles=_legend_handles,
        title="Group",
        loc="upper left",
        bbox_to_anchor=(1.02, 1),
    )
    _g.fig.suptitle(
        "Pattern 4: Supervised Clustered Heatmap (`sns.clustermap`)", y=1.02
    )

    _heatmap_path = CACHE_DIR / "pattern4_clustermap.png"
    _g.savefig(_heatmap_path, bbox_inches="tight")
    plt.close(_g.fig)

    mo.vstack(
        [
            mo.md("### Pattern 4: Supervised Clustered Heatmap (`seaborn`)"),
            mo.md(
                "The colormap comes from the pattern 1 dropdown, so changing it "
                "re-runs this cell and nothing else. For a boxplot with a scipy "
                "statistical overlay, see `py_example.py`."
            ),
            mo.image(_heatmap_path.read_bytes(), width=650),
        ]
    )
    return


@app.cell(hide_code=True)
def _(
    ArtifactError,
    batch_stats_csv,
    list_shared,
    load_shared,
    mo,
    ranked_csv,
    shared_path,
):
    # Pattern 5: consume the shared layer.
    #
    # load_shared() verifies against the manifest and restores dtypes, which CSV
    # does not carry. Taking ranked_csv and batch_stats_csv as arguments is what
    # puts this cell after the producing cells: reading a file is invisible to the
    # dependency graph, so the path the writer returned is the edge.
    #
    # The guard matters for an analysis notebook that has no producer of its own.
    # Git tracks manifests, not CSV bytes, so a fresh clone has no shared tables.
    # mo.stop() halts this cell and its dependents with one message.
    _ = (ranked_csv, batch_stats_csv)

    try:
        measurements = load_shared("measurements-ranked")
        batch_summary = load_shared("batch-stats")
        _problem = None
    except ArtifactError as _err:
        measurements = batch_summary = None
        _problem = str(_err)

    mo.stop(
        _problem is not None,
        mo.md(
            "### Pattern 5: Consume the Interface Layer (`data/shared/`)\n\n"
            "Re-run the producing cells above to write the tables that patterns "
            "5-8 read.\n\n"
            f"```\n{_problem}\n```"
        ),
    )

    mo.vstack(
        [
            mo.md("### Pattern 5: Consume the Interface Layer (`data/shared/`)"),
            mo.md(
                "Read from `data/shared/`, written by the producing cells above. "
                f"The sibling `{shared_path('batch-stats').stem}.manifest.json` "
                "records the input fingerprint, the producing cell's code hash, "
                "the `code_deps` hash of `scripts/`, and the Polars schema."
            ),
            mo.ui.table(batch_summary.to_dicts(), selection=None),
            mo.md(
                "`list_shared()` is the inventory of the interface layer — what a "
                "notebook may read, without opening `data/shared/` yourself. Each "
                "entry carries its own `problems`, so a table that no longer "
                "verifies is visible here before anything reads it."
            ),
            mo.ui.table(
                [
                    {
                        "name": _t["name"],
                        "rows": _t["rows"],
                        "title": _t["title"],
                        "problems": len(_t["problems"]),
                    }
                    for _t in list_shared()
                ],
                selection=None,
            ),
        ]
    )
    return (measurements,)


@app.cell(hide_code=True)
def pattern6_batch_effect(
    load_shared,
    measurements,
    mo,
    np,
    plt,
    preserve_figure,
    shared_path,
    sns,
):
    # Pattern 6: preserve a deliverable as a figure bundle.
    #
    # The cell name matches the artifact name given to preserve_figure, and
    # `make check` enforces that.
    _summary = load_shared("batch-stats")

    # A deliverable must render the same bytes twice. stripplot's jitter has no
    # seed of its own; it draws from numpy's.
    np.random.seed(0)

    _fig, _ax = plt.subplots(figsize=(6, 3.4))
    sns.stripplot(
        data=measurements.to_pandas(),
        x="group",
        y="intensity",
        hue="batch",
        dodge=True,
        ax=_ax,
    )
    _ax.set_title("Intensity by group, split on batch")
    _ax.set_xlabel("")
    _ax.set_ylabel("intensity")

    # source_data is required: the plotted table, which a figure object does
    # not carry.
    _bundle = preserve_figure(
        _fig,
        "pattern6_batch_effect",
        source_data=measurements,
        title="Intensity by group and batch",
        inputs=[shared_path("measurements-ranked")],
    )
    plt.close(_fig)

    mo.vstack(
        [
            mo.md("### Pattern 6: Preserving a Deliverable (`preserve_figure`)"),
            mo.md(
                "Writes `figure.pdf` for submission, `figure.png` for review, "
                "the plotted rows as `figure-source.csv`, and `manifest.json` into "
                f"`{_bundle.relative_to(_bundle.parents[2])}`. Unchanged content is "
                "not rewritten, so a re-run produces no git diff."
            ),
            mo.md(
                "**Read what you wrote.** An agent reads the written files, not "
                "the in-memory figure: the `read` tool on\n\n"
                f"`{(_bundle / 'figure.png').relative_to(_bundle.parents[2])}`\n\n"
                "and `print()` on `figure-source.csv`. `preserve_figure()` requires "
                "`source_data` so the plotted rows are always available as text, "
                "which is the fallback when a terminal cannot render images."
            ),
            # The cell shows the file it wrote, so the display and the
            # deliverable cannot differ.
            mo.image((_bundle / "figure.png").read_bytes(), width=650),
        ]
    )
    return


@app.cell(hide_code=True)
def pattern7_batch_table(measurements, mo, pl, preserve_file, preserve_table):
    # Pattern 7: deliverable table plus a sidecar in one bundle.
    #
    # A bundle belongs to a cell. Several preserve_* calls write into one
    # manifest; delete one and the next run removes the file it wrote.
    #
    # Aliased with a leading underscore because the producing cell above already
    # owns the public name `rank_by_significance`, and marimo allows a name to be
    # defined in exactly one cell. The import stays here rather than moving to the
    # imports cell: code_deps is read from this cell's own imports, so hoisting it
    # would drop the scripts/measurements.py hash from the manifest.
    from scripts.measurements import rank_by_significance as _rank_by_significance

    _ranked = _rank_by_significance(measurements)

    preserve_table(
        _ranked,
        "pattern7_batch_table",
        title="Samples ranked by p-value",
    )

    # preserve_file takes serialized input: a Path, or bytes/str with a
    # filename. `_json` is underscore-prefixed to stay cell-local; a bare
    # `import json` would claim the public name notebook-wide.
    import json as _json

    preserve_file(
        _json.dumps({"sort_key": "p_value", "n_rows": _ranked.height}, indent=2),
        "pattern7_batch_table",
        filename="params.json",
    )

    mo.vstack(
        [
            mo.md("### Pattern 7: Deliverable Table + Sidecar (`preserve_*`)"),
            mo.md(
                "`preserve_table` writes CSV with the Polars float defaults. "
                "`float_precision` writes `1e-300` as `0.000000000000` and destroys "
                "p-values. The smallest `p_value` below is intact."
            ),
            mo.ui.table(
                _ranked.head(4)
                .with_columns(pl.col("p_value").cast(pl.String))
                .to_dicts(),
                selection=None,
            ),
        ]
    )
    return


@app.cell(hide_code=True)
def _(check, list_preserved, mo, preserved_path):
    # Pattern 8: verification. This is what `make check` runs.
    #
    # check() reports content, staleness, identity and provenance drift.
    # list_preserved() reports problems per bundle.
    _report = check()
    _listing = list_preserved()

    # preserved_path() addresses a file inside a bundle by (notebook, cell,
    # filename) and raises if it is not there. This is how a later cell, another
    # session, or an agent reaches a deliverable without re-running the cell that
    # wrote it — the preserve_* return value is only in hand during that run.
    # There is no loader: it hands back a path to read or display, which is what
    # keeps data/preserved/ terminal. Ask list_preserved() for the filenames
    # rather than assuming one, since a bundle holds what its calls wrote.
    _figure = preserved_path("full_example", "pattern6_batch_effect", "figure.png")

    mo.vstack(
        [
            mo.md("### Pattern 8: Provenance Verification (`check`)"),
            mo.md(f"```\n{_report}\n```"),
            mo.md(
                "`preserved_path()` resolved the pattern 6 figure at "
                f"`{_figure.relative_to(_figure.parents[3])}` "
                f"({_figure.stat().st_size} bytes) without re-running that cell."
            ),
            mo.md(
                "An error makes `make check` exit non-zero. A warning does not. "
                "A changed `data/external/` input is a warning because petri does not "
                "own those files: they can be re-supplied from outside. A file in "
                "`data/shared/` or `data/preserved/` that no manifest records is an error."
            ),
            mo.ui.table(
                [
                    {
                        "artifact": _a["id"],
                        "files": ", ".join(_a["files"]),
                        "problems": len(_a["problems"]),
                    }
                    for _a in _listing
                ],
                selection=None,
            ),
        ]
    )
    return


if __name__ == "__main__":
    app.run()
