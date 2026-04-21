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


@app.cell
def _():
    # CHECK FOR BASE FOLDER

    import os
    import asyncio
    from public.src import data_load_main as dlm

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
    mo.stop(base_dir == "", mo.vstack([mo.md("To get started, click the button above to mount a folder."),
                                       mo.md("It can be an empty folder or a folder with a main file.")]))

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
    import public.src.backtest as bn
    import public.src.report as nr
    from public.src.result import Ok, Err

    if run_btn.value:
        if is_wasm:
            fm.sync_filesystem()

        with mo.status.spinner(title="Running...") as _spinner:
            async def on_progress(msg):
                # print(msg)
                _spinner.update(msg)
                await asyncio.sleep(0.1)

            _spinner.update("Loading assets...")
            data_load_result = await dlm.data_load_all(base_dir, on_progress, settings_file_path)
            match data_load_result:
                case Ok(data):
                    portfolio_df, asset_prices_available, assets_meta_df = data
                case Err(e):
                    print(f"Error: {e}")
                    mo.stop(True, f"ERROR: {e}")

            _spinner.update("Running backtest...")
            backtest_result = bn.run_backtest_all(asset_prices_available, portfolio_df)
            match backtest_result:
                case Ok(data):
                    # combined_returns, weights_per_port= data
                    combined_returns = data.combined_returns
                    # Reconstruct the old weights dict for backward compatibility
                    # weights_per_port = {name: p.weights for name, p in data.portfolios.items()}
                case Err(e):
                    print(f"Error: {e}")
                    traceback.print_exception(e)
                    mo.stop(True, f"ERROR: {e}")

            _spinner.update("Calculating results...")
            nr.show_results(combined_returns)
    return


if __name__ == "__main__":
    app.run()
