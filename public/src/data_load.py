import os
import io
import sys
import logging
from typing import Any, Callable, Sequence
import pandas as pd
from public.src import data_validation as dv
import logging

logger = logging.getLogger(__name__)

def parse_excel_path(path_str, default_file):
    path_str = str(path_str).strip()
    if "!" in path_str:
        file, sheet = path_str.split("!", 1)
        return {"file": file.strip(), "sheet": sheet.strip()}
    
    # If no '!', assume it's a sheet in the main settings file
    return {"file": default_file, "sheet": path_str}

def load_settings(base_dir: str, settings_file: str, sheet_name: str):
    settings_path = os.path.join(base_dir, settings_file)
    settings_df = read_excel_with_workarounds(settings_path, sheet_name=sheet_name)
    # Filter out any rows where the Name starts with "_"
    if "Name" in settings_df.columns:
        settings_df = settings_df[~settings_df['Name'].str.startswith('_', na=False)]
    # Validate the file
    dv.validate_settings(settings_df, settings_file, sheet_name)

    # Get settings for currency and dates
    base_currency = settings_df.loc[settings_df['Name'] == 'currency', 'Value'].iloc[0]
    start_date = pd.to_datetime(settings_df.loc[settings_df['Name'] == 'start', 'Value'].iloc[0])
    end_date = pd.to_datetime(settings_df.loc[settings_df['Name'] == 'end', 'Value'].iloc[0])

    # Parse Portfolio Sources
    portfolio_raw = settings_df[settings_df['Name'] == 'portfolios']['Value'].tolist()
    portfolio_files_df = pd.DataFrame([
        parse_excel_path(p, settings_file) for p in portfolio_raw
    ])

    #  Parse Asset Sources 
    asset_raw = settings_df[settings_df['Name'] == 'assets']['Value'].tolist()
    asset_files_df = pd.DataFrame([
        parse_excel_path(a, settings_file) for a in asset_raw
    ])

    return start_date, end_date, base_currency, portfolio_files_df, asset_files_df



# Load portfolio names and weights
# The file should have columns ID, Portfolio1, Portfolio2...
# The first column is asset ID, the rest are portfolio names
# The rows contain the weigth for each asset in each portfolio
# It will ignore all portfolio names starting with underscore (_)
# which can be used to add meta columns like _Name for the asssets
# or disable a portfolio like _Portfolio3
def load_portfolios(files_df, base_dir):
    all_portfolios = {}
    for row in files_df.itertuples():
        file_name = os.path.join(base_dir, row.file)
        if not os.path.exists(file_name):
            raise FileNotFoundError(row.file)
        df = read_excel_with_workarounds(file_name, row.sheet, index_col=0)
        
        # Drop columns that start with an underscore
        cols_to_drop = [c for c in df.columns if c.startswith('_')]
        df = df.drop(columns=cols_to_drop)
        
        # Drop rows where every single column is NaN
        df = df.dropna(how='all')

        # Check for NaN in the index and just print a warning
        if df.index.hasnans:
            print("\n--- WARNING: Portfolio index (ID) contains NaN values! ---")
            print(df[df.index.isna()])

        context = f"{row.file}!{row.sheet}"
        all_portfolios[context] = df

    dv.validate_portfolios(all_portfolios)

    # Combine by merging columns on matching index (ID)
    combined_df = pd.concat(all_portfolios.values(), axis=1)

    return combined_df

# Loads meta information about assets
# Required columns: ID, Name, Currency, StdDev
# Optional columns: 
#   Proxy -> Points to an ID to use if the asset does not have enough price data
#   File -> Filename to load prices from, defaults to same file as meta
#   Sheet -> Sheetname to load prices from, defaults to "Prices"
# Skips rows that do not have an ID so they can be used for headings etc.
def assets_meta(base_dir, files_df, base_currency):
    default_prices_sheet_name = "Prices"
    all_meta = {}

    for row in files_df.itertuples():
        file_path = os.path.join(base_dir, row.file)
        if not os.path.exists(file_path):
            raise FileNotFoundError(row.file)
            
        meta_df = read_excel_with_workarounds(file_path, sheet_name=row.sheet)
        meta_df.columns = meta_df.columns.str.lower()
        if 'id' in meta_df.columns:
            meta_df = meta_df.set_index('id')
        else:
            raise dv.DataFileValidationError([f"Missing required column: **'ID'**"], row.file + "!" + row.sheet)
        meta_df = meta_df[meta_df.index.notna()]

        # Split "prices" column to file and sheet
        if 'prices' in meta_df.columns:
            # Parse each row (handles "file.xlsx!Sheet" or just "Sheet")
            parsed = meta_df['prices'].apply(lambda x: parse_excel_path(x, row.file) if pd.notna(x) else None)
            meta_df['file'] = parsed.apply(lambda x: x['file'] if x else row.file)
            meta_df['sheet'] = parsed.apply(lambda x: x['sheet'] if x else default_prices_sheet_name)
        else:
            meta_df['file'] = row.file
            meta_df['sheet'] = default_prices_sheet_name

        # currency, proxy, stddev defaults
        meta_df['currency'] = meta_df['currency'] if 'currency' in meta_df.columns else base_currency
        meta_df['currency'] = meta_df['currency'].fillna(base_currency)
        meta_df['proxy'] = meta_df['proxy'] if 'proxy' in meta_df.columns else ""
        meta_df['proxy'] = meta_df['proxy'].fillna("")
        meta_df['stddev'] = meta_df['stddev'] if 'stddev' in meta_df.columns else 0.1
        meta_df['stddev'] = meta_df['stddev'].fillna(0.1)
        
        all_meta[str(row.file) + "!" + row.sheet] = meta_df
    
    if not all_meta:
        return pd.DataFrame()

    dv.validate_assets_meta(all_meta)
    combined_df = pd.concat(all_meta.values())

    # Final filtering of columns
    required_cols = [ 'name' ]
    optional_cols = [ 'currency', 'proxy', 'stddev']
    generated_cols = [ 'file', 'sheet']
    cols_to_keep = required_cols + optional_cols + generated_cols
    existing_keep_cols = [c for c in cols_to_keep if c in combined_df.columns]
    combined_df = combined_df[existing_keep_cols]

    return combined_df

def load_asset_prices_from_file_sheet(base_dir, file_name, sheet_name, needed_ids):
    file_path = os.path.join(base_dir, file_name)
    if not os.path.exists(file_path):
        raise FileNotFoundError(file_name)
    
    #  We need to see what columns actually exist in the file first
    # This avoids a ValueError if one of your needed_ids isn't in the Excel sheet
    try:
        preview = read_excel_with_workarounds(file_path, sheet_name=sheet_name, nrows=0)
    except ValueError:
        raise dv.DataFileValidationError([f"Worksheet named **'{sheet_name}'** not found."], file_path)

    # Identify missing IDs
    missing_ids = [id for id in needed_ids if id not in preview.columns]
    if missing_ids:
        raise dv.DataFileValidationError([f"The following IDs were not found: `{', '.join(missing_ids)}`"], file_name + "!" + sheet_name)
    # Identify the first column (Date) and find which IDs exist in the sheet
    date_col = preview.columns[0]
    valid_cols = [date_col] + [id for id in needed_ids if id in preview.columns]

    # Load only the necessary columns
    assets_prices_df = read_excel_with_workarounds(
        file_path, 
        sheet_name=sheet_name, 
        index_col=0, 
        parse_dates=[0], 
        usecols=valid_cols
    )
    dv.validate_asset_prices(assets_prices_df, file_name, sheet_name, needed_ids)

    return assets_prices_df

# Loads prices for assets specified in the assets meta dataframe
# Expects the first column to be the Date and all other columns to be asset IDs
# The rows contains the date and then the prices
# Currency is determined by meta data for the asset ID
async def load_asset_prices(base_dir: str, assets_meta_df, on_progress):
    # Group by file and sheet
    grouped = assets_meta_df.groupby(['file', 'sheet'])
    
    all_price_dfs = []

    for (file_name, sheet), group in grouped:
        id_list = group.index.tolist()
        # print(f"Loading {len(id_list)} assets from {file_name} [{sheet}]")
        
        # Load prices using your second function
        df = load_asset_prices_from_file_sheet(base_dir, file_name, sheet, id_list)
        await on_progress(f"LOADED {len(df.index)} rows from {file_name} [{sheet}]")
        all_price_dfs.append(df)

    if not all_price_dfs:
        return pd.DataFrame()

    # Concatenate all files horizontally by date (index)
    # This handles assets spread across different files/sheets
    combined_prices_df = pd.concat(all_price_dfs, axis=1)
    
    return combined_prices_df

def normalized_asset_prices(assets_meta_df, fx_data, assets_prices_df, base_currency):

    # Add pence column
    if 'GBPSEK' in fx_data.columns:
        fx_data['GBpSEK'] = fx_data['GBPSEK'] / 100

    # Align FX data to the asset price dates
    # We only care about the intersection of dates
    fx_aligned = fx_data.reindex(assets_prices_df.index).ffill()

    # Create a mapping of Asset -> FX Ticker
    # If Asset is 'AAPL' (USD) and Base is 'SEK', mapping is 'USDSEK'
    def get_fx_ticker(asset_id):
        if asset_id not in assets_meta_df.index:
            return None
        
        currency = str(assets_meta_df.loc[asset_id, 'currency'])
        if currency == base_currency or pd.isna(currency):
            return None
        
        return f"{currency}{base_currency}"

    # Build a Matrix of multipliers
    # Initialize with 1.0 (for assets already in base currency)
    multipliers = pd.DataFrame(1.0, index=assets_prices_df.index, columns=assets_prices_df.columns)

    for asset_id in assets_prices_df.columns:
        fx_ticker = get_fx_ticker(asset_id)
        
        if fx_ticker:
            if fx_ticker in fx_aligned.columns:
                multipliers[asset_id] = fx_aligned[fx_ticker]
            else:
                logging.warning(f"No FX rate found for {asset_id} (Expected {fx_ticker}).")

    # 4. Normalize: Element-wise multiplication
    assets_normalized = assets_prices_df * multipliers

    return assets_normalized

def read_excel_with_workarounds(file_path: str, sheet_name: str, index_col: int | str | None = None, nrows: int | None = None, usecols = None, parse_dates: Any = None) -> pd.DataFrame:
    try:
        # First attempt: Read directly
        df = pd.read_excel(file_path, sheet_name=sheet_name, index_col=index_col, nrows=nrows, usecols=usecols, parse_dates=parse_dates)
        return df
    except PermissionError as e:
        if sys.platform == "win32":
            import win32file
            import win32con
            # If the file is in a onedrive folder and excel is open the read will fail unless we use this method
            # Request a handle that ignores existing write locks
            handle = win32file.CreateFile(
                file_path,
                win32con.GENERIC_READ,
                win32con.FILE_SHARE_READ | win32con.FILE_SHARE_WRITE | win32con.FILE_SHARE_DELETE,
                None,
                win32con.OPEN_EXISTING,
                win32con.FILE_ATTRIBUTE_NORMAL,
                None
            )
            # Read the file content into memory via the handle
            _, data = win32file.ReadFile(handle.handle, os.path.getsize(file_path))
            win32file.CloseHandle(handle.handle)
            if isinstance(data, str):
                data = data.encode('utf-8')
            # Convert bytes to a file-like object for pandas
            df = pd.read_excel(io.BytesIO(data), sheet_name=sheet_name, index_col=index_col, nrows=nrows)
            return df
        else:
            raise e

