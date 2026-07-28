import marimo

__generated_with = "0.23.15"
app = marimo.App(width="medium")


@app.cell(hide_code=True)
def _():
    import marimo as mo

    from paths import PROJECT_ROOT

    return PROJECT_ROOT, mo


@app.cell(hide_code=True)
def _(PROJECT_ROOT, mo):
    mo.vstack(
        [
            mo.md(
                """
                # Blank Analysis Notebook

                Starter template for data science work in `marimo-pi`.

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


if __name__ == "__main__":
    app.run()
