import marimo

__generated_with = "0.23.15"
app = marimo.App(width="medium")


@app.cell(hide_code=True)
def _():
    import marimo as mo
    import matplotlib.pyplot as plt
    import polars as pl
    import seaborn as sns

    from petri import (
        PROJECT_ROOT,
        load_shared,
        preserve_figure,
        preserve_table,
    )

    sns.set_theme(style="ticks", font_scale=1.2)

    return (
        PROJECT_ROOT,
        load_shared,
        mo,
        pl,
        plt,
        preserve_figure,
        preserve_table,
        sns,
    )


@app.cell(hide_code=True)
def _(PROJECT_ROOT, mo):
    mo.vstack(
        [
            mo.md(
                """
                # Blank Analysis Notebook

                Starter template for data science work in `petri`.

                ## Where output goes

This is an **analysis notebook**: it reads `data/shared/` and writes
`data/preserved/`.

                | Want | Use |
                |---|---|
                | data to work from | `load_shared("name")` |
                | a quick look while iterating | plot in the cell; nothing on disk |
                | a figure that ships | `preserve_figure(fig, "<this cell's name>", source_data=df)` |
                | a deliverable table or sidecar | `preserve_table()` / `preserve_file()` |

                Name the cell to match the artifact name. `make check` verifies this and
                fails after a rename. Keep exploratory plots in the cell and preserve only
                what ships.

                To write a **new** `data/shared/` table, call `save_shared()` in a cell
                that reads `data/external/` and calls a pure function from `scripts/`.
                Return the path it gives you and take that path as an argument wherever
                you read the table back: writing a file is not an edge marimo can see.

                `make init full` installs `full_example.py`, which does all of this end to
                end — publishing a shared table, then preserving deliverables from it.

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


if __name__ == "__main__":
    app.run()
