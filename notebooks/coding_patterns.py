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
    from scipy import stats

    from paths import OUTPUTS_DIR, PROJECT_ROOT
    from r_bridge import pl_to_r, r_eval, r_set, r_to_pl

    return (
        OUTPUTS_DIR,
        PROJECT_ROOT,
        mo,
        np,
        pl,
        pl_to_r,
        plt,
        r_eval,
        r_set,
        r_to_pl,
        sns,
        stats,
    )


@app.cell(hide_code=True)
def _(PROJECT_ROOT, mo):
    mo.vstack(
        [
            mo.md(
                """
                # Python-R Interop, Bioconductor & Visualization Patterns

                A reference guide focused on **Python $\\leftrightarrow$ R interop (`r_bridge`)**,
                **Bioconductor package integration**, **marimo UI/DAG reactivity**, and **figure rendering recipes**.

                All examples use self-contained **synthetic data** (no private dataset dependencies).

                ## Core Patterns Included

                1. **Python $\\leftrightarrow$ R Data Exchange** (`pl_to_r`, `r_eval`, `r_to_pl` with Polars)
                2. **Bioconductor Package Interop via `r_bridge`** (`limma` differential analysis on synthetic matrices)
                3. **R Figure Rendering Recipes** (4 Methods: Disk PNG, In-Memory PNG, Vector SVG, `grdevices` capture)
                4. **Interactive Marimo UI Widgets & Reactive DAG** (`mo.ui.slider`, `mo.ui.dropdown`, dynamic reactivity)
                5. **Python Plotting & Statistical Overlays** (`matplotlib` + `seaborn` boxplots, scipy stats)
                6. **Supervised Clustered Heatmaps** (`sns.clustermap` with Z-score row normalization & category color bars)
                """
            ),
            mo.accordion(
                {
                    "Architecture & Design": mo.md(
                        (PROJECT_ROOT / "docs/architecture.md").read_text()
                    ),
                    "R Environment (renv)": mo.md(
                        (PROJECT_ROOT / "docs/renv.md").read_text()
                    ),
                    "rpy2 Setup": mo.md((PROJECT_ROOT / "docs/rpy2.md").read_text()),
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
                * **R-Python Bridge:** Importing `r_bridge` automatically sets working directory to project root, activating `.Rprofile` and `renv/library/` once for the entire session.
                """
            )
        ]
    )
    return


@app.cell(hide_code=True)
def _(mo):
    # Pattern 1: Interactive Marimo UI Widgets
    samples_per_group = mo.ui.slider(10, 100, 10, value=30, label="samples per group")
    effect_size = mo.ui.slider(0.0, 3.0, 0.2, value=1.2, label="group effect size")
    palette_choice = mo.ui.dropdown(
        options=["Set2", "Set1", "viridis", "muted"],
        value="Set2",
        label="color palette",
    )

    mo.vstack(
        [
            mo.md("### Pattern 1: Interactive UI Widgets & Reactive DAG"),
            mo.hstack([samples_per_group, effect_size, palette_choice]),
        ]
    )
    return effect_size, palette_choice, samples_per_group


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
            ),
            df_transformed.head(10),
        ]
    )
    return (df_transformed,)


@app.cell(hide_code=True)
def _(OUTPUTS_DIR, mo, np, pl, pl_to_r, r_eval, r_set):
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

    bioc_plot_path = OUTPUTS_DIR / "pattern3_bioc_limma_volcano.png"
    bioc_csv_path = OUTPUTS_DIR / "pattern3_bioc_limma_results.csv"

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
def _(OUTPUTS_DIR, df_transformed, mo, r_eval, r_set):
    # Pattern 4: R Plotting (ggplot2 / ggpubr) — 4 Rendering Methods
    _ = df_transformed  # marimo DAG dependency

    r_plot_disk = OUTPUTS_DIR / "pattern4_r_ggpubr.png"
    r_set("plot_path", str(r_plot_disk))

    # Method 1: Persistent File (Disk)
    r_eval("""
    suppressPackageStartupMessages(library(ggpubr))

    p_r <- ggboxplot(
      r_df, x = "group", y = "value",
      color = "group", palette = "jco", add = "jitter"
    ) + stat_compare_means(method = "anova")

    ggsave(plot_path, p_r, width = 5.5, height = 4.0, dpi = 150)
    """)
    _v1 = mo.image(r_plot_disk.read_bytes(), width=500)

    # Method 2: In-Memory Raw PNG Bytes via R png() device
    _png_raw = r_eval("""
    tf <- tempfile(fileext = ".png")
    png(tf, width = 5.5, height = 4.0, units = "in", res = 150)
    print(p_r)
    dev.off()
    bin <- readBin(tf, "raw", file.info(tf)$size)
    unlink(tf)
    bin
    """)
    _v2 = mo.image(bytes(_png_raw), width=500)

    # Method 3: In-Memory Vector SVG string via svglite
    _svg_str = r_eval("""
    library(svglite)
    s <- svgstring(width = 5.5, height = 4.0)
    print(p_r)
    dev.off()
    s()
    """)
    _v3 = mo.Html(str(_svg_str[0]))

    # Method 4: Direct rpy2 grdevices Capture
    from rpy2.robjects.lib import grdevices

    with grdevices.render_to_bytesio(grdevices.png, width=550, height=400) as _bio:
        r_eval("print(p_r)")
    _v4 = mo.image(_bio.getvalue(), width=500)

    mo.vstack(
        [
            mo.md("### Pattern 4: R Figure Rendering Recipes (4 Methods)"),
            mo.ui.tabs(
                {
                    "1. Disk File (PNG)": mo.vstack(
                        [
                            mo.md(
                                "**Method 1: Save to disk via `ggsave` and"
                                " display with `mo.image`**\n"
                                "Artifact saved in"
                                f" `{r_plot_disk.relative_to(OUTPUTS_DIR.parent)}`."
                            ),
                            _v1,
                        ]
                    ),
                    "2. In-Memory Raw PNG": mo.vstack(
                        [
                            mo.md(
                                "**Method 2: Render to in-memory PNG raw"
                                " bytes in R**\n"
                                "Captures binary PNG data from R temp device"
                                " without persisting to project output."
                            ),
                            _v2,
                        ]
                    ),
                    "3. Vector SVG": mo.vstack(
                        [
                            mo.md(
                                "**Method 3: Render to SVG string via"
                                " `svglite`**\n"
                                "Generates scalable vector SVG directly for web"
                                " rendering with `mo.Html`."
                            ),
                            _v3,
                        ]
                    ),
                    "4. rpy2 grdevices Capture": mo.vstack(
                        [
                            mo.md(
                                "**Method 4: In-memory capture via"
                                " `rpy2.robjects.lib.grdevices`**\n"
                                "Uses Python context manager"
                                " (`render_to_bytesio`) to capture graphics"
                                " device output."
                            ),
                            _v4,
                        ]
                    ),
                }
            ),
        ]
    )
    return


@app.cell(hide_code=True)
def _(OUTPUTS_DIR, df_synth, mo, palette_choice, pl, plt, sns, stats):
    # Pattern 5: Python Plotting (matplotlib + seaborn) with Scipy Statistics
    _p_df = df_synth.to_pandas()

    _fig, _ax = plt.subplots(figsize=(6, 4), dpi=150)
    sns.boxplot(
        data=_p_df,
        x="group",
        y="value",
        hue="group",
        palette=palette_choice.value,
        ax=_ax,
        width=0.4,
    )
    sns.stripplot(
        data=_p_df,
        x="group",
        y="value",
        color="black",
        alpha=0.5,
        jitter=0.2,
        ax=_ax,
    )

    # Compute ANOVA via scipy.stats
    _g_data = [
        df_synth.filter(pl.col("group") == g)["value"].to_numpy()
        for g in sorted(df_synth["group"].unique().to_list())
    ]
    _f_stat, _p_anova = stats.f_oneway(*_g_data)

    _ax.set_title(f"Python Plot (Seaborn): ANOVA F={_f_stat:.2f}, p={_p_anova:.2e}")
    sns.despine()
    _fig.tight_layout()

    _plot_path = OUTPUTS_DIR / "pattern5_python_seaborn.png"
    _fig.savefig(_plot_path)
    plt.close(_fig)

    # Summary table in Polars
    _summary = (
        df_synth.group_by("group")
        .agg(
            pl.col("value").mean().round(3).alias("mean"),
            pl.col("value").std().round(3).alias("std"),
            pl.col("value").count().alias("n"),
        )
        .sort("group")
    )

    mo.vstack(
        [
            mo.md("### Pattern 5: Python Plotting & Statistical Summary"),
            mo.image(_plot_path.read_bytes(), width=550),
            _summary,
        ]
    )
    return


@app.cell(hide_code=True)
def _(OUTPUTS_DIR, mo, np, plt, sns):
    # Pattern 6: Supervised Clustered Heatmap (seaborn)
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
        cmap="vlag",
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
        "Pattern 6: Supervised Clustered Heatmap (`sns.clustermap`)", y=1.02
    )

    _heatmap_path = OUTPUTS_DIR / "pattern6_clustermap.png"
    _g.savefig(_heatmap_path, bbox_inches="tight")
    plt.close(_g.fig)

    mo.vstack(
        [
            mo.md("### Pattern 6: Supervised Clustered Heatmap (`seaborn`)"),
            mo.image(_heatmap_path.read_bytes(), width=650),
        ]
    )
    return


if __name__ == "__main__":
    app.run()
