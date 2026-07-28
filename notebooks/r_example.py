import marimo

__generated_with = "0.23.15"
app = marimo.App(width="medium")


@app.cell(hide_code=True)
def _():
    import marimo as mo
    import numpy as np
    import polars as pl

    from paths import DATA_DIR, OUTPUTS_DIR, PROJECT_ROOT
    from r_bridge import pl_to_r, r_eval, r_set, r_to_pl

    return (
        DATA_DIR,
        OUTPUTS_DIR,
        PROJECT_ROOT,
        mo,
        np,
        pl,
        pl_to_r,
        r_eval,
        r_set,
        r_to_pl,
    )


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        """
        # R interop example with ggpubr & renv

        Demonstrates passing Polars DataFrames to R and rendering a `ggpubr` plot.
        """
    )
    return


@app.cell(hide_code=True)
def _(np, pl, pl_to_r):
    _rng = np.random.default_rng(42)
    _groups = ["control", "treatment"]

    df = pl.DataFrame(
        {
            "group": np.repeat(_groups, 30),
            "value": np.concatenate(
                [_rng.normal(0.0, 1.0, 30), _rng.normal(1.5, 1.0, 30)]
            ),
        }
    )

    # Transfer Polars DataFrame to R
    pl_to_r(df, "df")
    df
    return (df,)


@app.cell(hide_code=True)
def _(OUTPUTS_DIR, df, mo, r_eval, r_set):
    _ = df  # marimo DAG dependency
    plot_path = OUTPUTS_DIR / "r_example_ggpubr.png"

    r_set("plot_path", str(plot_path))

    r_eval(
        """
        suppressPackageStartupMessages(library(ggpubr))

        p <- ggboxplot(
          df, x = "group", y = "value",
          color = "group", palette = "jco", add = "jitter"
        ) + stat_compare_means(method = "t.test")

        suppressMessages(ggsave(plot_path, p, width = 5, height = 4, dpi = 150))
        """
    )

    mo.image(plot_path.read_bytes(), width=500)
    return (plot_path,)


if __name__ == "__main__":
    app.run()
