import marimo

__generated_with = "0.23.15"
app = marimo.App(width="medium")


@app.cell(hide_code=True)
def _():
    import marimo as mo
    import numpy as np
    import polars as pl

    from petri import CACHE_DIR, PROJECT_ROOT
    from petri.r_bridge import (
        np_to_r,
        pl_to_r,
        py_to_r,
        r_eval,
        r_png,
        r_to_np,
        r_to_pl,
        r_to_py,
    )

    return (
        CACHE_DIR,
        PROJECT_ROOT,
        mo,
        np,
        np_to_r,
        pl,
        pl_to_r,
        py_to_r,
        r_eval,
        r_png,
        r_to_np,
        r_to_pl,
        r_to_py,
    )


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


@app.cell
def r_to_pl_demo(r_eval, r_to_np, r_to_pl):
    # Pull data back from R to Python with `r_to_pl` and `r_to_np`.
    # Tabular R objects (data.frames) -> Polars; array-like (matrices, vectors) -> NumPy.
    # Both take the NAME of an R variable in the global environment, not an expression.

    # R data.frame -> Polars DataFrame
    r_eval(
        "df_pl <- data.frame(id = 1:3, grp = c('a', 'b', 'c'), val = c(1.5, 2.5, 3.5))"
    )
    df_roundtrip = r_to_pl("df_pl")

    # R matrix -> NumPy ndarray (a matrix is array-like, not tabular)
    r_eval("mat <- matrix(1:6, nrow = 2, dimnames = list(NULL, c('m1', 'm2', 'm3')))")
    mat_np = r_to_np("mat")

    df_roundtrip, mat_np
    return


@app.cell
def r_dict_list_demo(py_to_r, r_eval, r_to_py):
    # Pass dicts/lists between Python and R with `py_to_r` and `r_to_py`.
    # `py_to_r` pushes native Python to R: dict -> named R list, list -> R vector/list.
    # `r_to_py` pulls an R list back to its native form: named -> dict, unnamed -> list.

    # Python -> R (native dict to a named R list, recursive), read back so the
    # output shows what R actually received.
    py_to_r({"name": "alice", "scores": [90.5, 85.0], "meta": {"id": 7}}, "config")
    r_eval("cfg_str <- capture.output(str(config))")
    config_in_r = r_to_py("cfg_str")

    # R -> Python (R named list to a dict, recursion handles nesting)
    r_eval("rl <- list(x = 1:3, y = c('a', 'b'), z = 7, meta = list(p = 1, q = 2))")
    config_py = r_to_py("rl")

    config_in_r, config_py
    return


@app.cell
def np_to_r_demo(np, np_to_r, r_eval, r_to_np):
    # Push a NumPy array into R with `np_to_r`, the inverse of `r_to_np`.
    # 1-D becomes an atomic vector, 2-D a matrix, N-D an array; R is
    # column-major and the layout is preserved.
    _arr = np.arange(6.0).reshape(2, 3)
    np_to_r(_arr, "mat_from_py")

    r_eval("mat_scaled <- mat_from_py * 10")
    mat_scaled = r_to_np("mat_scaled")

    mat_scaled
    return


@app.cell(hide_code=True)
def _(CACHE_DIR, df, mo, py_to_r, r_eval, r_png):
    _ = df  # marimo DAG dependency
    plot_path = CACHE_DIR / "r_example_ggpubr.png"

    py_to_r(str(plot_path), "plot_path")

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

    # Method 4: grdevices Capture via r_bridge
    v4 = mo.image(r_png("print(p)", width=500, height=400), width=500)

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
                        "**Method 4: In-memory `grdevices` capture via `r_png()`**\n\n"
                        "`r_bridge.r_png()` wraps `rpy2.robjects.lib.grdevices` and "
                        "returns PNG bytes. Calling `grdevices` directly from a cell "
                        "raises `NotImplementedError: Conversion rules ... appear to "
                        "be missing`, because rpy2 keeps those rules in a "
                        "`ContextVar` that marimo's cell thread does not carry."
                    ),
                    v4,
                ]
            ),
        }
    )
    return


if __name__ == "__main__":
    app.run()
