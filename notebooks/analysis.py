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
    return clinical, de_annotation, sample_map


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


@app.cell(hide_code=True)
def _(OUTPUTS_DIR, clinical, pl, sample_map):
    # Prepare sample annotation for FOXA1 vs SPOP DE (driver_subtype, sufficient-purity tumors)
    foxa1_spop_annotation = (
        sample_map.filter(pl.col("tissue") == "tumor")
        .join(
            clinical.filter(
                (pl.col("sufficient_purity") == "yes")
                & pl.col("driver_subtype").is_in(["FOXA1", "SPOP"])
            ).select(["case_id", "driver_subtype"]),
            on="case_id",
            how="inner",
        )
        .select(["sample_barcode", "driver_subtype"])
        .with_columns(pl.col("driver_subtype").cast(pl.String))
    )

    foxa1_spop_annotation_path = OUTPUTS_DIR / "foxa1_spop_sample_annotation.csv"
    foxa1_spop_annotation.write_csv(foxa1_spop_annotation_path)

    foxa1_spop_annotation
    return (foxa1_spop_annotation,)


@app.cell(hide_code=True)
def _(OUTPUTS_DIR, foxa1_spop_annotation, mo, pl, pl_to_r, r_eval, r_set):
    # DE analysis: FOXA1 vs SPOP mutants (driver_subtype, sufficient-purity) via limma
    foxa1_spop_plot_path = OUTPUTS_DIR / "de_foxa1_spop_volcano.png"
    foxa1_spop_top_table_path = OUTPUTS_DIR / "de_foxa1_spop_topTable.csv"

    pl_to_r(foxa1_spop_annotation, "driver_annotation")
    r_set("foxa1_spop_plot_path", str(foxa1_spop_plot_path))
    r_set("foxa1_spop_top_table_path", str(foxa1_spop_top_table_path))

    _r = r_eval("""
    expr <- read.delim("data/processed/cptac4-prad_proteomics_original_dia_gg-matrix-imputed.tsv",
                        row.names=1, check.names=FALSE)
    expr <- expr[, !(colnames(expr) %in% c("Index"))]
    expr <- as.matrix(expr)

    common <- intersect(colnames(expr), driver_annotation$sample_barcode)
    expr <- expr[, common, drop=FALSE]
    driver_annotation <- driver_annotation[driver_annotation$sample_barcode %in% common, , drop=FALSE]
    driver_annotation <- driver_annotation[match(colnames(expr), driver_annotation$sample_barcode), , drop=FALSE]

    # Design: SPOP (reference) vs FOXA1 -> positive logFC = higher in FOXA1
    group <- factor(driver_annotation$driver_subtype, levels=c("SPOP", "FOXA1"))
    design <- model.matrix(~ group)

    # Limma
    library(limma)
    fit <- lmFit(expr, design)
    fit <- eBayes(fit)
    results <- topTable(fit, coef=2, number=Inf, sort.by="p")

    # Volcano plot with ggpubr + ggrepel
    library(ggpubr)
    library(ggrepel)

    results_df <- as.data.frame(results)
    results_df$gene <- rownames(results_df)

    # Highlight top hits by unadjusted P < 0.001
    results_df$sig <- ifelse(results_df$P.Value < 0.001 & results_df$logFC > 0.5, "Higher in FOXA1",
                      ifelse(results_df$P.Value < 0.001 & results_df$logFC < -0.5, "Higher in SPOP", "Not Sig"))

    # Top genes to label (top 12 by p-value)
    top_genes <- head(results_df[order(results_df$P.Value), ], 12)

    p <- ggplot(results_df, aes(x=logFC, y=-log10(P.Value), color=sig)) +
      geom_point(alpha=0.6, size=1.2) +
      scale_color_manual(values=c("Higher in FOXA1"="#d14848", "Higher in SPOP"="#2b5c8f", "Not Sig"="#b3b3b3")) +
      geom_vline(xintercept=c(-0.5, 0.5), linetype="dashed", color="grey50") +
      geom_hline(yintercept=-log10(0.001), linetype="dashed", color="grey50") +
      geom_text_repel(data=top_genes, aes(label=gene), size=3, max.overlaps=15, show.legend=FALSE) +
      labs(title="DIA Proteomics: FOXA1 vs SPOP Mutants (Sufficient-Purity)",
           subtitle="14 FOXA1 vs 11 SPOP tumors (driver_subtype)",
           x="log2 Fold Change (FOXA1 vs SPOP)",
           y="-log10(p-value)",
           color="Group") +
      theme_minimal(base_size=10)

    ggsave(foxa1_spop_plot_path, p, width=6, height=4.5, dpi=150)
    write.csv(results, foxa1_spop_top_table_path, row.names=TRUE)

    cat("FOXA1 vs SPOP DE complete\n")
    cat("Total proteins:", nrow(results), "\n")
    cat("Nominally significant (P < 0.001, |logFC| > 0.5):", sum(results_df$sig != "Not Sig"), "\n")
    """)

    _raw = pl.read_csv(foxa1_spop_top_table_path)
    _n_foxa1 = _raw.filter((pl.col("logFC") > 0.5) & (pl.col("P.Value") < 0.001)).height
    _n_spop = _raw.filter((pl.col("logFC") < -0.5) & (pl.col("P.Value") < 0.001)).height

    _top = (
        _raw.rename({_raw.columns[0]: "gene"})
        .select(["gene", "logFC", "AveExpr", "P.Value", "adj.P.Val", "B"])
        .rename({"logFC": "log2FC", "P.Value": "p_value", "adj.P.Val": "p_adj"})
        .sort("p_value")
        .head(20)
    )

    mo.vstack(
        [
            mo.md(
                f"**DIA Proteomics DE: FOXA1 vs SPOP Mutants (driver_subtype, sufficient-purity)** — "
                f"{_n_foxa1} higher in FOXA1, {_n_spop} higher in SPOP (P < 0.001, |log2FC| > 0.5)"
            ),
            mo.image(foxa1_spop_plot_path.read_bytes(), width=600),
            _top,
        ]
    )
    return (foxa1_spop_top_table_path,)


@app.cell(hide_code=True)
def _(OUTPUTS_DIR, foxa1_spop_top_table_path, mo, pl, r_eval, r_set):
    # GSEA Analysis: FOXA1 vs SPOP Mutants (Pre-ranked fgsea on MSigDB Hallmark)
    foxa1_spop_gsea_bar_path = OUTPUTS_DIR / "de_foxa1_spop_gsea_bar.png"
    foxa1_spop_gsea_curves_path = OUTPUTS_DIR / "de_foxa1_spop_gsea_curves.png"
    foxa1_spop_gsea_table_path = OUTPUTS_DIR / "de_foxa1_spop_gsea_topTable.csv"

    r_set("foxa1_spop_gsea_bar_path", str(foxa1_spop_gsea_bar_path))
    r_set("foxa1_spop_gsea_curves_path", str(foxa1_spop_gsea_curves_path))
    r_set("foxa1_spop_gsea_table_path", str(foxa1_spop_gsea_table_path))
    r_set("foxa1_spop_top_table_path", str(foxa1_spop_top_table_path))

    _r_gsea = r_eval("""
    library(fgsea)
    library(msigdbr)
    library(ggpubr)
    library(gridExtra)

    top_table <- read.csv(foxa1_spop_top_table_path)
    colnames(top_table)[1] <- "gene"

    ranks <- setNames(top_table$t, top_table$gene)
    ranks <- sort(ranks, decreasing = TRUE)

    m_df <- msigdbr(species = "Homo sapiens", collection = "H")
    pathways_h <- split(x = m_df$gene_symbol, f = m_df$gs_name)

    set.seed(42)
    fgsea_h <- fgsea(pathways = pathways_h, stats = ranks, minSize = 10, maxSize = 500)
    fgsea_df <- as.data.frame(fgsea_h)

    # Format leadingEdge list for CSV
    fgsea_df$leadingEdge <- sapply(fgsea_df$leadingEdge, function(x) paste(x, collapse = ";"))
    fgsea_df <- fgsea_df[order(fgsea_df$pval), ]

    write.csv(fgsea_df, foxa1_spop_gsea_table_path, row.names = FALSE)

    # Filter for top pathways (padj < 0.25)
    sig_fgsea <- fgsea_df[fgsea_df$padj < 0.25, ]
    sig_fgsea <- sig_fgsea[order(sig_fgsea$NES), ]
    sig_fgsea$clean_pathway <- gsub("HALLMARK_", "", sig_fgsea$pathway)
    sig_fgsea$clean_pathway <- factor(sig_fgsea$clean_pathway, levels = sig_fgsea$clean_pathway)
    sig_fgsea$Direction <- ifelse(sig_fgsea$NES > 0, "Higher in FOXA1", "Higher in SPOP")

    p_bar <- ggplot(sig_fgsea, aes(x = clean_pathway, y = NES, fill = Direction)) +
      geom_col(width = 0.7) +
      coord_flip() +
      scale_fill_manual(values = c("Higher in FOXA1" = "#d14848", "Higher in SPOP" = "#2b5c8f")) +
      geom_hline(yintercept = 0, linetype = "solid", color = "black", linewidth = 0.5) +
      labs(
        title = "GSEA Hallmark Pathways: FOXA1 vs SPOP Mutants",
        subtitle = "Pre-ranked fgsea on limma t-statistics (FDR < 0.25)",
        x = NULL,
        y = "Normalized Enrichment Score (NES)"
      ) +
      theme_minimal(base_size = 11) +
      theme(panel.grid.major.y = element_blank())

    ggsave(foxa1_spop_gsea_bar_path, p_bar, width = 7, height = 4.5, dpi = 150)

    p_oxphos <- plotEnrichment(pathways_h[["HALLMARK_OXIDATIVE_PHOSPHORYLATION"]], ranks) +
      labs(title = "OXPHOS (NES = +2.35, FDR = 8.9e-12)")

    p_ar <- plotEnrichment(pathways_h[["HALLMARK_ANDROGEN_RESPONSE"]], ranks) +
      labs(title = "Androgen Response (NES = -1.96, FDR = 6.5e-4)")

    p_curves <- grid.arrange(p_oxphos, p_ar, ncol = 2)
    ggsave(foxa1_spop_gsea_curves_path, p_curves, width = 8.5, height = 3.8, dpi = 150)

    cat("GSEA completed and plots saved.\n")
    """)

    _gsea_raw = pl.read_csv(foxa1_spop_gsea_table_path)
    _gsea_top = (
        _gsea_raw.select(["pathway", "size", "NES", "pval", "padj", "leadingEdge"])
        .rename({"pval": "p_value", "padj": "p_adj"})
        .sort("p_value")
        .head(15)
    )

    mo.vstack(
        [
            mo.md(
                "### GSEA Results: FOXA1 vs SPOP Mutants (MSigDB Hallmark)\n"
                "- **OXPHOS** is strongly elevated in **FOXA1** mutants ($NES = +2.35, \text{FDR} = 8.9 \times 10^{-12}$).\n"
                "- **Androgen Response** is strongly elevated in **SPOP** mutants ($NES = -1.96, \text{FDR} = 6.5 \times 10^{-4}$)."
            ),
            mo.image(foxa1_spop_gsea_bar_path.read_bytes(), width=650),
            mo.image(foxa1_spop_gsea_curves_path.read_bytes(), width=700),
            _gsea_top,
        ]
    )
    return


@app.cell
def _(OUTPUTS_DIR, foxa1_spop_top_table_path, mo, pl, r_eval, r_set):
    # PROGENy Analysis: Pathway Activity Inference for FOXA1 vs SPOP Mutants
    foxa1_spop_progeny_bar_path = OUTPUTS_DIR / "de_foxa1_spop_progeny_bar.png"
    foxa1_spop_progeny_table_path = OUTPUTS_DIR / "de_foxa1_spop_progeny_topTable.csv"

    r_set("foxa1_spop_progeny_bar_path", str(foxa1_spop_progeny_bar_path))
    r_set("foxa1_spop_progeny_table_path", str(foxa1_spop_progeny_table_path))
    r_set("foxa1_spop_top_table_path", str(foxa1_spop_top_table_path))

    _r_progeny = r_eval("""
    library(progeny)
    library(ggplot2)
    library(dplyr)

    top_table <- read.csv(foxa1_spop_top_table_path)
    colnames(top_table)[1] <- "gene"

    t_stat_mat <- as.matrix(top_table$t)
    rownames(t_stat_mat) <- top_table$gene
    colnames(t_stat_mat) <- "FOXA1_vs_SPOP"

    prog_res <- progeny(t_stat_mat, scale = FALSE, organism = "Human", top = 100)
    raw_scores <- as.numeric(prog_res[1, ])
    z_scores <- (raw_scores - mean(raw_scores)) / sd(raw_scores)

    prog_df <- data.frame(
      Pathway = colnames(prog_res),
      Raw_Score = raw_scores,
      Z_Score = z_scores,
      stringsAsFactors = FALSE
    )

    prog_df$Direction <- ifelse(prog_df$Z_Score > 0, "Higher in FOXA1", "Higher in SPOP")
    prog_df <- prog_df[order(prog_df$Z_Score), ]
    prog_df$Pathway <- factor(prog_df$Pathway, levels = prog_df$Pathway)

    write.csv(prog_df, foxa1_spop_progeny_table_path, row.names = FALSE)

    p_prog <- ggplot(prog_df, aes(x = Pathway, y = Z_Score, fill = Direction)) +
      geom_col(width = 0.65) +
      coord_flip() +
      scale_fill_manual(values = c("Higher in FOXA1" = "#d14848", "Higher in SPOP" = "#2b5c8f")) +
      geom_hline(yintercept = 0, linetype = "solid", color = "black", linewidth = 0.5) +
      labs(
        title = "PROGENy Pathway Activity: FOXA1 vs SPOP Mutants",
        subtitle = "Inferred pathway activity z-scores from limma t-statistics (14 footprint pathways)",
        x = NULL,
        y = "Pathway Activity Z-score"
      ) +
      theme_minimal(base_size = 11) +
      theme(panel.grid.major.y = element_blank())

    ggsave(foxa1_spop_progeny_bar_path, p_prog, width = 7, height = 4.5, dpi = 150)
    cat("PROGENy pathway activity complete.\n")
    """)

    _progeny_raw = pl.read_csv(foxa1_spop_progeny_table_path)
    _progeny_top = _progeny_raw.select(
        ["Pathway", "Raw_Score", "Z_Score", "Direction"]
    ).sort("Z_Score", descending=True)

    mo.vstack(
        [
            mo.md(
                "### PROGENy Pathway Activity Analysis: FOXA1 vs SPOP Mutants\n"
                "- **Androgen signaling** is strongly suppressed in FOXA1 mutants relative to SPOP ($Z = -2.09$, highest in SPOP).\n"
                "- **NFkB** ($Z = +1.85$), **TNFa** ($Z = +1.23$), and **JAK-STAT** ($Z = +1.03$) pathways show the highest activity in **FOXA1** mutants."
            ),
            mo.image(foxa1_spop_progeny_bar_path.read_bytes(), width=650),
            _progeny_top,
        ]
    )
    return


if __name__ == "__main__":
    app.run()
