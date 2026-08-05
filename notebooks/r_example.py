import marimo

__generated_with = "0.23.15"
app = marimo.App(width="medium")


@app.cell(hide_code=True)
def _():
    import marimo as mo
    import numpy as np
    import polars as pl

    from petri import CACHE_DIR, PROJECT_ROOT
    from petri.r_bridge import pl_to_r, r_eval, r_set

    return CACHE_DIR, PROJECT_ROOT, mo, np, pl, pl_to_r, r_eval, r_set


@app.cell(hide_code=True)
def _(PROJECT_ROOT, mo):
    mo.vstack(
        [
            mo.md(
                """
                # R Interop Example Notebook (`rpy2` + `ggpubr`)

                Demonstrates passing Polars DataFrames to R and rendering a `ggpubr` plot.

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
def _(CACHE_DIR, df, mo, r_eval, r_set):
    _ = df  # marimo DAG dependency
    plot_path = CACHE_DIR / "r_example_ggpubr.png"

    r_set("plot_path", str(plot_path))

    # Method 1: Persistent File (Disk Output)
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
    v1 = mo.image(plot_path.read_bytes(), width=500)

    # Method 2: In-Memory Raw PNG Bytes via R png() device
    png_raw = r_eval(
        """
        tf <- tempfile(fileext = ".png")
        png(tf, width = 5, height = 4, units = "in", res = 150)
        print(p)
        dev.off()
        bin <- readBin(tf, "raw", file.info(tf)$size)
        unlink(tf)
        bin
        """
    )
    v2 = mo.image(bytes(png_raw), width=500)

    # Method 3: In-Memory Vector SVG via svglite
    svg_str = r_eval(
        """
        library(svglite)
        s <- svgstring(width = 5, height = 4)
        print(p)
        dev.off()
        s()
        """
    )
    v3 = mo.Html(str(svg_str[0]))

    # Method 4: Direct rpy2 Graphics Capture via grdevices
    from rpy2.robjects.lib import grdevices

    with grdevices.render_to_bytesio(grdevices.png, width=500, height=400) as bio:
        r_eval("print(p)")
    v4 = mo.image(bio.getvalue(), width=500)

    mo.ui.tabs(
        {
            "1. Persistent File (Disk)": mo.vstack(
                [
                    mo.md(
                        "**Method 1: Save to disk via `ggsave` and load with `mo.image`**\n\n"
                        "Rendered to `data/cache/r_example_ggpubr.png`. Use "
                        "`preserve_figure()` for a deliverable."
                    ),
                    v1,
                ]
            ),
            "2. In-Memory Raw PNG": mo.vstack(
                [
                    mo.md(
                        "**Method 2: Render to in-memory PNG raw bytes in R**\n\n"
                        "Captures binary PNG data directly from R memory without persisting to disk."
                    ),
                    v2,
                ]
            ),
            "3. In-Memory Vector SVG": mo.vstack(
                [
                    mo.md(
                        "**Method 3: Render to vector SVG string via `svglite`**\n\n"
                        "Generates scalable vector SVG directly for web rendering with `mo.Html`."
                    ),
                    v3,
                ]
            ),
            "4. rpy2 grdevices Capture": mo.vstack(
                [
                    mo.md(
                        "**Method 4: Direct in-memory capture via `rpy2.robjects.lib.grdevices`**\n\n"
                        "Uses Python context manager (`render_to_bytesio`) to capture R plot output."
                    ),
                    v4,
                ]
            ),
        }
    )
    return


if __name__ == "__main__":
    app.run()
