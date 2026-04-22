import os
import traceback
import marimo as mo
import pandas as pd
from public.src import data_clean as dc
from public.src import data_load as dl
from public.src.result import Result, Ok, Err
from public.src import backtest as bn
from public.src import report as nr

def display(obj):
    mo.output.append(obj)

def get_settings_file_name() -> str:
    return 'main.xlsx'

def get_local_base_dir() -> str:
    return os.environ.get("DATA_PATH", "public/example")

async def run_full_backtest(base_dir: str, on_progress, settings_file_path):
    await on_progress("Loading assets...")
    data_load_result = await data_load_all(base_dir, on_progress, settings_file_path)
    match data_load_result:
        case Ok(data):
            portfolio_df, asset_prices_available, assets_meta_df = data
            await on_progress("Running backtest...")
            backtest_result = bn.run_backtest_all(assets_meta_df, asset_prices_available, portfolio_df)
            match backtest_result:
                case Ok(data):
                    await on_progress("Calculating results...")
                    nr.show_results(data)
                case Err(e):
                    print(f"Error: {e}")
                    traceback.print_exception(e)
                    mo.stop(True, f"ERROR: {e}")
        case Err(e):
            print(f"Error: {e}")
            mo.stop(True, f"ERROR: {e}")

async def data_load_all(base_dir: str, on_progress, settings_file) -> Result[tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame], Exception]:

    try:

        await on_progress("Loading the data")

        # LOAD DATA

        # SETTINGS
        start_date, end_date, base_currency, portfolio_files_df, asset_files_df = dl.load_settings(base_dir, settings_file)
        print(f"Backtest from {start_date} to {end_date} using {base_currency} as base currency")

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
        asset_prices_available = dc.adjust_start_to_available_data(asset_prices_proxied, start_date)
        # display(asset_prices_backtest)

        return Ok((portfolio_df, asset_prices_available, assets_meta_df))

    except Exception as e:
        # Catch any error (IO, KeyErrors, Network, etc.) and wrap it in Err
        return Err(e)