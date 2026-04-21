import marimo

__generated_with = "0.23.1"
app = marimo.App()


@app.cell
def _():
    import anywidget
    import marimo as mo

    class SimpleWidget(anywidget.AnyWidget):
        _esm = "export default { render({ el }) { el.innerHTML = 'Hello World'; } }"

    mo.ui.anywidget(SimpleWidget())
    return


if __name__ == "__main__":
    app.run()