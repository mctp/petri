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

    from paths import OUTPUTS_DIR, PROCESSED_DIR, PROJECT_ROOT
    from r_bridge import pl_to_r, r_eval, r_set

    return (
        OUTPUTS_DIR,
        PROCESSED_DIR,
        PROJECT_ROOT,
        mo,
        np,
        pl,
        pl_to_r,
        plt,
        r_eval,
        r_set,
        sns,
    )


@app.cell(hide_code=True)
def _(PROJECT_ROOT, mo):
    mo.vstack(
        [
            mo.md(
                """
                # Interactive Analysis Notebook

                Interactive multi-group experiment analysis with widgets, summary statistics, ANOVA, and pairwise comparisons.

                ## External Resources

                - **marimo**: [Documentation](https://docs.marimo.io/) | [API Reference](https://docs.marimo.io/api/) | [GitHub](https://github.com/marimo-team/marimo)
                - **pi**: [GitHub](https://github.com/earendil-works/pi)
                - **marimo-pair**: [GitHub](https://github.com/marimo-team/marimo-pair)

                ## Project Documentation
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
    n = mo.ui.slider(10, 200, 10, value=50, label="samples per group")
    effect_size = mo.ui.slider(0.0, 3.0, 0.1, value=1.5, label="effect size")
    n_groups = mo.ui.slider(2, 5, 1, value=3, label="number of groups")

    n
    effect_size
    n_groups
    return effect_size, n, n_groups


@app.cell(hide_code=True)
def _(effect_size, n, n_groups, np, pl):
    rng = np.random.default_rng(42)
    _groups = [f"G{i}" for i in range(n_groups.value)]
    _means = [0.0 + i * effect_size.value for i in range(n_groups.value)]

    _rows = []
    for g, m in zip(_groups, _means, strict=True):
        _rows.append(
            pl.DataFrame(
                {
                    "group": [g] * n.value,
                    "value": rng.normal(m, 1.0, n.value),
                    "group_idx": [int(g[1:])] * n.value,
                }
            )
        )

    df = pl.concat(_rows)
    df
    return (df,)


@app.cell(hide_code=True)
def _(df, pl):
    summary = (
        df.group_by("group")
        .agg(
            pl.col("value").mean().alias("mean"),
            pl.col("value").std().alias("std"),
            pl.col("value").count().alias("n"),
            pl.col("value").min().alias("min"),
            pl.col("value").max().alias("max"),
        )
        .sort("group")
    )
    summary
    return


@app.cell(hide_code=True)
def _(OUTPUTS_DIR, df, mo, pl, plt, sns):
    from scipy import stats

    plot_path = OUTPUTS_DIR / "analysis_plot.png"

    p_df = df.to_pandas()

    fig, ax = plt.subplots(figsize=(6, 4), dpi=150)
    sns.boxplot(
        data=p_df,
        x="group",
        y="value",
        hue="group",
        palette="Set2",
        ax=ax,
        width=0.5,
    )
    sns.stripplot(
        data=p_df,
        x="group",
        y="value",
        color="black",
        alpha=0.5,
        jitter=0.2,
        ax=ax,
    )

    # ANOVA
    _groups_data = [
        df.filter(pl.col("group") == g)["value"].to_numpy()
        for g in sorted(df["group"].unique().to_list())
    ]
    _f_stat, _p_anova = stats.f_oneway(*_groups_data)

    # Pairwise t-tests with Bonferroni correction
    from itertools import combinations

    _group_names = sorted(df["group"].unique().to_list())
    _pairwise_results = []
    for g1, g2 in combinations(_group_names, 2):
        d1 = df.filter(pl.col("group") == g1)["value"].to_numpy()
        d2 = df.filter(pl.col("group") == g2)["value"].to_numpy()
        _t, _p = stats.ttest_ind(d1, d2)
        _pairwise_results.append((g1, g2, _t, _p))

    _n_comparisons = len(_pairwise_results)
    pairwise_table = pl.DataFrame(
        _pairwise_results,
        orient="row",
        schema=["group_1", "group_2", "t_stat", "p_value"],
    ).with_columns(
        (pl.col("p_value") * _n_comparisons).clip(upper_bound=1.0).alias("p_bonferroni")
    )

    ax.set_title(f"ANOVA: F={_f_stat:.2f}, p={_p_anova:.2e}")
    sns.despine()
    fig.tight_layout()
    fig.savefig(plot_path)
    plt.close(fig)

    mo.vstack(
        [
            mo.image(plot_path.read_bytes(), width=550),
            mo.md(
                f"""
                **ANOVA**: F={_f_stat:.3f}, p={_p_anova:.2e}
                """
            ),
        ]
    )
    return (pairwise_table,)


@app.cell(hide_code=True)
def _(mo, pairwise_table):
    mo.md("### Pairwise t-tests (Bonferroni corrected)")

    pairwise_table
    return


@app.cell(hide_code=True)
def _(OUTPUTS_DIR, PROCESSED_DIR, pl):
    # Prepare sample annotation for tumor vs normal DE
    sample_map = pl.read_csv(
        PROCESSED_DIR / "cptac4-prad_metabolomics_derived_sample-map.csv"
    )

    clinical = pl.read_excel(
        PROCESSED_DIR / "cptac4-prad_metabolomics_original_clinical-metadata.xlsx",
        sheet_name="FinalMetaData",
    ).unique(subset="case_id")

    # Join sample-map with clinical metadata for sufficient_purity
    de_annotation = (
        sample_map.join(
            clinical.select(["case_id", "sufficient_purity"]), on="case_id", how="left"
        )
        .filter(
            ((pl.col("tissue") == "tumor") & (pl.col("sufficient_purity") == "yes"))
            | (pl.col("tissue") == "normal")
        )
        .select(["sample_barcode", "tissue"])
        .with_columns(pl.col("tissue").cast(pl.String))
    )

    # Write annotation for R
    de_annotation_path = OUTPUTS_DIR / "de_sample_annotation.csv"
    de_annotation.write_csv(de_annotation_path)

    de_annotation
    return (de_annotation,)


@app.cell(hide_code=True)
def _(OUTPUTS_DIR, de_annotation, mo, pl, pl_to_r, r_eval, r_set):
    # DE analysis: DIA proteomics tumor vs normal via limma
    de_plot_path = OUTPUTS_DIR / "de_volcano.png"
    de_top_table_path = OUTPUTS_DIR / "de_topTable.csv"

    pl_to_r(de_annotation, "de_annotation")
    r_set("de_plot_path", str(de_plot_path))
    r_set("de_top_table_path", str(de_top_table_path))

    _r = r_eval("""
    expr <- read.delim("data/processed/cptac4-prad_proteomics_original_dia_gg-matrix-imputed.tsv",
                        row.names=1, check.names=FALSE)
    expr <- expr[, !(colnames(expr) %in% c("Index"))]
    expr <- as.matrix(expr)

    common <- intersect(colnames(expr), de_annotation$sample_barcode)
    expr <- expr[, common, drop=FALSE]
    de_annotation <- de_annotation[de_annotation$sample_barcode %in% common, , drop=FALSE]
    de_annotation <- de_annotation[match(colnames(expr), de_annotation$sample_barcode), , drop=FALSE]

    group <- factor(de_annotation$tissue, levels=c("normal", "tumor"))
    design <- model.matrix(~ group)

    library(limma)
    fit <- lmFit(expr, design)
    fit <- eBayes(fit)
    results <- topTable(fit, coef=2, number=Inf, sort.by="p")

    library(ggpubr)
    results_df <- as.data.frame(results)
    results_df$gene <- rownames(results_df)
    results_df$sig <- ifelse(results_df$adj.P.Val < 0.05 & abs(results_df$logFC) > 1,
                              "Significant", "Not Sig")

    p <- ggplot(results_df, aes(x=logFC, y=-log10(P.Value), color=sig)) +
      geom_point(alpha=0.6, size=1) +
      scale_color_manual(values=c("Significant"="#d14848", "Not Sig"="#b3b3b3")) +
      geom_vline(xintercept=c(-1, 1), linetype="dashed", color="grey50") +
      geom_hline(yintercept=-log10(0.05), linetype="dashed", color="grey50") +
      labs(title="DIA Proteomics: Tumor vs Normal (Sufficient-Purity)",
           x="log2 Fold Change (Tumor vs Normal)", y="-log10(p-value)") +
      theme_minimal(base_size=10)

    ggsave(de_plot_path, p, width=6, height=4, dpi=150)
    write.csv(results, de_top_table_path, row.names=TRUE)

    cat("DE analysis complete\n")
    cat("Total proteins:", nrow(results), "\n")
    cat("Significant:", sum(results_df$sig == "Significant"), "\n")
    """)

    _raw = pl.read_csv(de_top_table_path)
    _top = (
        _raw.rename({_raw.columns[0]: "gene"})
        .select(["gene", "logFC", "AveExpr", "P.Value", "adj.P.Val", "B"])
        .rename({"logFC": "log2FC", "P.Value": "p_value", "adj.P.Val": "p_adj"})
        .sort("p_adj")
        .head(20)
    )

    mo.vstack(
        [
            mo.md("**DIA Proteomics DE: Tumor vs Normal** (sufficient-purity)"),
            mo.image(de_plot_path.read_bytes(), width=600),
            _top,
        ]
    )
    return


if __name__ == "__main__":
    app.run()
