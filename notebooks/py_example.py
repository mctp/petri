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

    from petri import CACHE_DIR, PROJECT_ROOT

    return CACHE_DIR, PROJECT_ROOT, mo, np, pl, plt, sns


@app.cell(hide_code=True)
def _(PROJECT_ROOT, mo):
    mo.vstack(
        [
            mo.md(
                """
                # Python Visualization Example (`matplotlib` + `seaborn`)

                Demonstrates plotting a boxplot with points and t-test annotation in pure Python.

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
def _(np, pl):
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
    df
    return (df,)


@app.cell(hide_code=True)
def _(CACHE_DIR, df, mo, pl, plt, sns):
    from scipy import stats

    # data/cache/ holds exploratory output and you can delete it. A figure that
    # ships goes through preserve_figure(). See coding_patterns.py pattern 8.
    plot_path = CACHE_DIR / "py_example_seaborn.png"

    p_df = df.to_pandas()

    fig, ax = plt.subplots(figsize=(5, 4), dpi=150)
    sns.boxplot(
        data=p_df,
        x="group",
        y="value",
        hue="group",
        palette="Set2",
        ax=ax,
        width=0.4,
    )
    sns.stripplot(
        data=p_df,
        x="group",
        y="value",
        color="black",
        alpha=0.6,
        jitter=0.2,
        ax=ax,
    )

    # Compute t-test using scipy.stats
    ctrl = df.filter(pl.col("group") == "control")["value"].to_numpy()
    trt = df.filter(pl.col("group") == "treatment")["value"].to_numpy()
    ttest = stats.ttest_ind(ctrl, trt)

    ax.set_title(f"t-test: p = {ttest.pvalue:.2e}")
    sns.despine()
    fig.tight_layout()
    fig.savefig(plot_path)
    plt.close(fig)

    mo.image(plot_path.read_bytes(), width=500)
    return


if __name__ == "__main__":
    app.run()
