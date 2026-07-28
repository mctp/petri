import marimo

__generated_with = "0.23.15"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import numpy as np
    import polars as pl

    from r_bridge import (
        OUTPUTS_DIR,
        pl_to_r,
        r_eval,
        r_set,
        r_to_pl,
    )

    return OUTPUTS_DIR, mo, np, pl, pl_to_r, r_eval, r_set, r_to_pl


@app.cell
def _(mo):
    mo.md("""
    # marimo-pi Analysis Template

    A reactive Python notebook paired with an embedded R session via `r_bridge`.
    - Python data manipulation via **Polars**
    - Project-local R library managed via **renv** (`ggplot2`, `ggpubr`)
    - Full reactivity between Python marimo UI elements and R plots
    """)
    return


@app.cell
def _(mo):
    mo.md("""
    ## R interop & reactive controls
    """)
    return


@app.cell
def _(r_eval):
    # r_bridge initializes R in PROJECT_ROOT, which automatically ran .Rprofile
    # and activated renv once.
    r_library = str(r_eval(".libPaths()")[0])
    r_library
    return


@app.cell
def _(mo):
    n_per_group = mo.ui.slider(
        10, 200, value=40, step=10, label="n per group", show_value=True
    )
    effect_size = mo.ui.slider(
        0.0, 3.0, value=1.2, step=0.1, label="treated effect (SD)", show_value=True
    )
    palette_choice = mo.ui.dropdown(
        {
            "Nature": "npg",
            "Lancet": "lancet",
            "JAMA": "jama",
            "Grayscale": "grey",
        },
        value="Nature",
        label="palette",
    )
    test_method = mo.ui.dropdown(
        {"ANOVA": "anova", "Kruskal-Wallis": "kruskal.test"},
        value="ANOVA",
        label="test",
    )
    show_points = mo.ui.switch(value=True, label="show points")

    mo.vstack(
        [
            mo.md("Every control below feeds the R session reactively:"),
            mo.hstack([n_per_group, effect_size], justify="start", gap=2),
            mo.hstack(
                [palette_choice, test_method, show_points],
                justify="start",
                gap=2,
            ),
        ]
    )
    return effect_size, n_per_group, palette_choice, show_points, test_method


@app.cell
def _(effect_size, n_per_group, np, pl, pl_to_r):
    _rng = np.random.default_rng(0)
    _groups = ["control", "treated", "rescue"]
    _n = n_per_group.value
    _locs = (0.0, effect_size.value, effect_size.value / 2)

    sample_df = pl.DataFrame(
        {
            "group": np.repeat(_groups, _n),
            "value": np.concatenate([_rng.normal(loc, 1.0, _n) for loc in _locs]),
        }
    )

    # Polars -> R data.frame via r_bridge
    pl_to_r(sample_df, "sample_df")
    sample_df
    return (sample_df,)


@app.cell
def _(r_eval, r_to_pl, sample_df):
    _ = sample_df  # marimo DAG dependency
    r_eval("group_means <- aggregate(value ~ group, sample_df, mean)")
    group_means = r_to_pl("group_means")
    group_means
    return


@app.cell
def _(
    OUTPUTS_DIR,
    mo,
    palette_choice,
    r_eval,
    r_set,
    sample_df,
    show_points,
    test_method,
):
    _ = sample_df  # marimo DAG dependency
    plot_path = OUTPUTS_DIR / "rpy2_ggpubr_example.png"

    r_set("plot_path", str(plot_path))
    r_set("plot_palette", palette_choice.value)
    r_set("plot_add", "jitter" if show_points.value else "none")
    r_set("test_method", test_method.value)

    r_eval(
        """
        suppressPackageStartupMessages(library(ggpubr))

        p <- ggboxplot(
          sample_df, x = "group", y = "value",
          color = "group", palette = plot_palette, add = plot_add
        ) + stat_compare_means(method = test_method)

        suppressMessages(ggsave(plot_path, p, width = 6, height = 4, dpi = 150))
        """
    )

    mo.image(plot_path.read_bytes(), width=600)
    return


if __name__ == "__main__":
    app.run()
