import marimo

__generated_with = "0.23.15"
app = marimo.App(width="medium")


@app.cell(hide_code=True)
def _():
    import marimo as mo
    import polars as pl

    from r_bridge import (
        DATA_DIR,
        OUTPUTS_DIR,
        PROJECT_ROOT,
        pl_to_r,
        r_eval,
        r_set,
        r_to_pl,
    )

    return (
        DATA_DIR,
        OUTPUTS_DIR,
        PROJECT_ROOT,
        mo,
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
        # Blank Analysis Notebook

        Starter template for data science work in `marimo-pi`.

        ## Documentation & Resources

        - **marimo**: [Documentation](https://docs.marimo.io/) | [API Reference](https://docs.marimo.io/api/) | [GitHub](https://github.com/marimo-team/marimo)
        - **Polars**: [User Guide](https://docs.pola.rs/) | [API Reference](https://docs.pola.rs/api/python/stable/reference/index.html)
        - **rpy2**: [Documentation](https://rpy2.github.io/doc/v3.5.x/html/index.html)
        - **renv**: [User Guide](https://rstudio.github.io/renv/articles/renv.html)
        - **Project Docs**: [Architecture](../docs/architecture.md) | [R Environment (`renv`)](../docs/renv.md) | [`rpy2` Setup](../docs/rpy2.md) | [Agent Guidelines](../AGENTS.md)
        """
    )
    return


if __name__ == "__main__":
    app.run()
