# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "anywidget>=0.10.0",
#     "openpyxl>=3.1.5",
#     "plotly>=6.7.0",
# ]
# ///

import marimo

__generated_with = "0.23.2"
app = marimo.App(width="full", app_title="Backcel")

async with app.setup:
    import marimo as mo
    import pandas as pd
    import sys

    is_wasm = "pyodide" in sys.modules
    if is_wasm:
        # Install our own code as a package so it can be used in the browser
        import micropip
        await micropip.install(str(mo.notebook_location().joinpath("public", "dist", "portfolio_logic-0.1.0-py3-none-any.whl")))


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ## 📊 Backcel

    Welcome to backcel, the local excel based portfolio backtesting engine! To get started:

    1. Use a compatible browser: ✅ Chrome, Edge, Brave, Opera. ❌ Safari or Firefox are not supported.
    1. Create an empty folder on your drive and press the **📁 Mount Folder** button below to mount it.
    1. Press the **⬇️ Download Example Files** button that appears to fill your folder with example files.
    1. Press the **🚀 Run Backtest** button to run the backtest.
    1. Open the 📄 `main.xlsx` file and in the `Main` sheet change the `start_date` setting. Save the file in excel, and then press the **🚀 Run Backtest** button again to run with the new settings.

    _Note: All data stays on your machine; no files are uploaded to a server._ For information about the format of the excel files see [data docs](https://github.com/jonaskello/backcel/blob/main/DATA.md) or the [source code](https://github.com/jonaskello/backcel).
    """)
    return


@app.cell
def _():
    # CHECK FOR BASE FOLDER

    import os
    import asyncio
    from public.src import main as dlm

    get_base_path, set_base_path = mo.state("")
    download_btn = mo.ui.run_button(label="⬇️ Download example files")

    if is_wasm:
        import public.src.wasm_folder as fm
        fm.listen_folder_mount(set_base_path)
        mount_widget = fm.folder_mount_iframe()
        # mount_widget = fm.folder_mount_widget()
        mo.output.replace(mount_widget)
    else:
        local_path = dlm.get_local_base_dir()
        set_base_path(local_path)
        mo.output.replace(mo.md(f"Not in web browser, using base dir {local_path}."))
    return asyncio, dlm, download_btn, fm, get_base_path, os


@app.cell
async def _(dlm, download_btn, fm, get_base_path, os):
    # CHECK FOR MAIN FILE

    from public.src import data_load as dl

    base_dir = get_base_path()
    mo.stop(base_dir == "")

    settings_file_path = os.path.join(base_dir, dlm.get_settings_file_name())
    run_btn = mo.ui.run_button(label="🚀 Run backtest")

    if download_btn.value:
        mo.output.replace(mo.md("DOWNLOADING..."))
        await fm.download_example_files_wasm_iframe(base_dir)
        if os.path.exists(settings_file_path):
            mo.output.replace(run_btn)
        else:
            mo.output.replace(mo.md(f"FAILED: File {settings_file_path} not found after download. Try reloading the app."))
    elif not os.path.exists(settings_file_path):
        if is_wasm:
            mo.output.replace(mo.vstack([
                mo.md("No main file found."),
                mo.md("Create a main file in your folder or click the button below to download exmple files."), 
                download_btn
                ], justify="start"))
        else:
            mo.output.replace(mo.md(f"FAILED: File {settings_file_path} not found. Create it or copy an example file to get started."))
    else:
        mo.output.replace(run_btn)
    return base_dir, run_btn, settings_file_path


@app.cell
async def _(asyncio, base_dir, dlm, fm, run_btn, settings_file_path):
    # RUN BACKTEST

    import traceback
    from public.src import backtest as bn
    from public.src import report as nr
    from public.src.result import Ok, Err

    if run_btn.value:
        if is_wasm:
            fm.sync_filesystem()

        with mo.status.spinner(title="Running...") as _spinner:
            async def on_progress(msg):
                # print(msg)
                _spinner.update(msg)
                await asyncio.sleep(0.1)

            await dlm.run_full_backtest(base_dir, on_progress, settings_file_path)
    return


if __name__ == "__main__":
    app.run()
