import marimo

__generated_with = "0.23.2"
app = marimo.App()


@app.cell
def _():
    import pandas as pd
    df = pd.read_excel("C:\\Users\\jonas\\OneDrive\\Ekonomi\\portfolio-analysis\\backcel_data\\main.xlsx", engine="openpyxl", engine_kwargs={"read_only": True})
    return


if __name__ == "__main__":
    app.run()
