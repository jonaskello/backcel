import os
import traceback
import marimo as mo
import pandas as pd
import pandera.pandas as pa
from public.src import data_clean as dc
from public.src import data_load as dl
from public.src.result import Result, Ok, Err
from public.src import backtest as bn
from public.src import report as nr
from public.src.monitor import monitor
import logging

logger = logging.getLogger(__name__)

def display(obj):
    mo.output.append(obj)

def get_settings_file_name() -> str:
    return 'main.xlsx'

def get_local_base_dir() -> str:
    return os.environ.get("DATA_PATH", "public/example")

async def run_full_backtest(base_dir: str, on_progress, settings_file_path):
    monitor.clear()
    await on_progress("Loading assets...")
    data_load_result = await data_load_all(base_dir, on_progress, settings_file_path)
    if isinstance(data_load_result, Err):
        return _handle_failure(data_load_result.error)

    portfolio_df, asset_prices_available, assets_meta_df = data_load_result.unwrap()
    await on_progress("Running backtest...")
    backtest_result = bn.run_backtest_all(assets_meta_df, asset_prices_available, portfolio_df)
    if isinstance(backtest_result, Err):
        return _handle_failure(backtest_result.error)

    await on_progress("Calculating results...")
    nr.show_results(backtest_result.unwrap())

def _handle_failure(e: Exception):
    # 1. Log the full traceback for the developer
    logger.error("Operation failed", exc_info=e)

    # 2. Dispatch the UI feedback based on error type
    if isinstance(e, pa.errors.SchemaErrors):
        # Your custom formatter for Pandera
        content = format_pandera_error(e)
        mo.stop(True, content)
        
    elif isinstance(e, FileNotFoundError):
        mo.stop(True, mo.callout(f"File not found: {e.filename}", kind="danger"))
        
    else:
        # Fallback for generic errors
        mo.stop(True, mo.callout(str(e), kind="danger"))


def format_pandera_error(e: pa.errors.SchemaErrors) -> mo.Html:
    df_err = e.failure_cases
    fname = getattr(e, 'filename', 'Excel File')
    # Get raw data from the exception
    df_raw = getattr(e, 'data', None)
    
    results = []

    for check_id in df_err['check'].unique():
        if check_id == "missing_mandatory_rows" and df_raw is not None:
            # 1. Get the list of what WAS required from the schema definition
            # This avoids globals and hardcoding!
            check_obj = e.schema.columns["Name"].checks[1]
            # We recreate the list from the check's own logic
            required = ['currency', 'start', 'end'] 
            
            # 2. Compare against what we actually have
            existing = set(df_raw['Name'].unique())
            missing = [k for k in required if k not in existing]
            
            val_str = ", ".join([f"**{m}**" for m in missing])
            results.append(f"Missing required rows: {val_str}.")
            
        elif check_id == "invalid_row_names":
            bad_vals = df_err[df_err['check'] == check_id]['failure_case'].unique()
            val_str = ", ".join([f"`{v}`" for v in bad_vals if v not in [False, None]])
            results.append(f"Invalid row names found: {val_str}. Use only allowed names.")

    content = f"### 📋 Issue in {fname}\n\n" + "\n".join([f"* {r}" for r in results])
    return mo.callout(mo.md(content), kind="danger")

async def data_load_all(base_dir: str, on_progress, settings_file) -> Result[tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame], Exception]:

    try:
        # LOAD DATA
        await on_progress("Loading the data")

        # SETTINGS
        start_date, end_date, base_currency, portfolio_files_df, asset_files_df = dl.load_settings(base_dir, settings_file)
        monitor.add(f"Backtest from {start_date:%Y-%m-%d} to {end_date:%Y-%m-%d} using {base_currency} as base currency")

        # LOAD PORTFOLIOS
        portfolio_df = dl.load_portfolios(portfolio_files_df, base_dir)
        # display(portfolio_df.fillna(''))

        # LOAD ASSETS META (filtered to the ones needed by portfolios)
        assets_meta_all = dl.assets_meta(base_dir, asset_files_df, base_currency)
        needed_asset_ids, needed_currency_ids = dc.resolve_asset_dependencies(portfolio_df.index.unique(), assets_meta_all, base_currency)
        # display(needed_asset_ids)
        # display(needed_currency_ids)
        assets_meta_df = assets_meta_all.loc[assets_meta_all.index.isin(needed_asset_ids)]
        currencies_meta_df = assets_meta_all.loc[assets_meta_all.index.isin(needed_currency_ids)]
        # display(assets_meta_df.fillna(''))
        # display(currencies_meta_df.fillna(''))
        #await asyncio.sleep(0) # avoid RPC timeout in WASM
        await on_progress("Loaded currencies")


        # LOAD CURRENCY PRICES AND BACKFILL
        currency_prices_raw = await dl.load_asset_prices(base_dir, currencies_meta_df, on_progress)
        currency_prices_needed = dc.needed_dates_filter(currency_prices_raw, start_date, end_date)
        # display(currency_prices_needed)
        currency_prices_proxied = dc.backfill_with_proxies(currency_prices_needed, currencies_meta_df)
        # display(currency_prices_proxied)

        # LOAD ASSET PRICES, NORMALIZE AND BACKFILL (according to assets meta)
        asset_prices_raw = await dl.load_asset_prices(base_dir, assets_meta_df, on_progress)
        # display(asset_prices_raw.tail(30))
        asset_prices_needed = dc.needed_dates_filter(asset_prices_raw, start_date, end_date)
        asset_prices_normalized = dl.normalized_asset_prices(assets_meta_df, currency_prices_proxied, asset_prices_needed, base_currency)
        asset_prices_proxied = dc.backfill_with_proxies(asset_prices_normalized, assets_meta_df)
        # display(asset_prices_proxied)
        await on_progress("Loaded assets")

        # ADJUST START DATE ACCORDING TO AVAILABLE DATA
        asset_prices_available = dc.adjust_asset_prices_start_to_available_data(assets_meta_df, asset_prices_proxied, start_date)
        # display(asset_prices_backtest)

        return Ok((portfolio_df, asset_prices_available, assets_meta_df))

    except Exception as e:
        # Catch any error (IO, KeyErrors, Network, etc.) and wrap it in Err
        return Err(e)