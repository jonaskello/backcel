import pandas as pd
from datetime import date
from public.src.monitor import monitor

def resolve_asset_dependencies(initial_tickers, assets_meta_df, base_currency):
    all_valid_ids = set(assets_meta_df.index)
    base_currency = base_currency.upper()
    
    # Trackers
    active_tickers = set(initial_tickers)
    currency_chain = set()

    last_count = 0
    while len(active_tickers | currency_chain) > last_count:
        last_count = len(active_tickers | currency_chain)
        
        # 1. Resolve Asset Proxies
        asset_meta = assets_meta_df[assets_meta_df.index.isin(active_tickers)]
        active_tickers.update(asset_meta['proxy'].dropna())
        
        # 2. Identify and resolve Currency requirements
        # We look at currencies for both main assets AND currency proxies
        combined_meta = assets_meta_df[assets_meta_df.index.isin(active_tickers | currency_chain)]
        active_currencies = combined_meta['currency'].dropna().str.upper().unique()
        
        # Generate FX IDs (Foreign + Base)
        fx_pairs = {f"{c}{base_currency}" for c in active_currencies if c != base_currency}
        valid_fx = fx_pairs.intersection(all_valid_ids)
        
        # Add found FX pairs to the currency chain
        currency_chain.update(valid_fx)
        
        # 3. Resolve Proxies for the Currencies themselves
        curr_meta = assets_meta_df[assets_meta_df.index.isin(currency_chain)]
        currency_chain.update(curr_meta['proxy'].dropna())

    return active_tickers, currency_chain

def needed_dates_filter(asset_prices_raw: pd.DataFrame, start_date: date, end_date: date) -> pd.DataFrame:
 
    # Sort index to ensure it is monotonic (oldest to newest)
    asset_prices_filtered = asset_prices_raw.sort_index()

    # Drop rows where ALL assets are NaN (weekends/global holidays), otherwise volatility will not be correct
    asset_prices_filtered = asset_prices_filtered.dropna(how='all')

    # Forward fill the remaining gaps (individual exchange holidays)
    # Forward fill ONLY "inside" gaps 
    # This prevents filling if the asset has stopped trading/reporting
    asset_prices_filtered = asset_prices_filtered.ffill(limit_area='inside')

    # Filter rows based on the date range
    # This assumes your index is already a DatetimeIndex
    asset_prices_filtered = asset_prices_filtered.loc[start_date:end_date]

    return pd.DataFrame(asset_prices_filtered)

def backfill_with_proxies(asset_prices_df: pd.DataFrame, assets_meta_df: pd.DataFrame) -> pd.DataFrame:
    # Create a copy to avoid SettingWithCopy warnings
    filled_prices = asset_prices_df.copy()
    
    # Loop until no more gaps can be filled to handle chains (e.g., A -> B -> C)
    changes_made = True
    while changes_made:
        changes_made = False
        
        for asset_id in filled_prices.columns:
            if asset_id in assets_meta_df.index:
                proxy_id = assets_meta_df.loc[asset_id, 'proxy']
                
                # Check if proxy exists and if the asset has potential gaps to fill
                if pd.notna(proxy_id) and proxy_id in filled_prices.columns:
                    target_series = filled_prices[asset_id]
                    proxy_series = filled_prices[proxy_id]
                    
                    # Identify the first valid date for both
                    target_first = target_series.first_valid_index()
                    proxy_first = proxy_series.first_valid_index()
                    
                    # Only proceed if the proxy has data and (target is empty OR proxy starts earlier)
                    if proxy_first and (target_first is None or proxy_first < target_first):
                        if target_first is None:
                            # If asset is entirely empty, use proxy data as is
                            filled_prices[asset_id] = proxy_series
                            new_first = filled_prices[asset_id].first_valid_index()
                            print(f"Filled empty asset {asset_id} using {proxy_id} | Starts at {new_first.date()}")
                            changes_made = True
                        else:
                            # Calculate scaling ratio at the target's earliest available price
                            asset_start_price = target_series.loc[target_first]
                            proxy_price_at_overlap = proxy_series.loc[target_first]
                            
                            if pd.notna(proxy_price_at_overlap) and proxy_price_at_overlap != 0:
                                ratio = asset_start_price / proxy_price_at_overlap
                                scaled_proxy = proxy_series * ratio
                                
                                # Fill the target's leading NaNs with the scaled proxy values
                                filled_prices[asset_id] = target_series.combine_first(scaled_proxy)
                                new_first = filled_prices[asset_id].first_valid_index()
                                print(f"Backfilled {asset_id} using {proxy_id} (Ratio: {ratio:.4f}) | {new_first.date()} to {target_first.date()}")
                                changes_made = True
                            
    return filled_prices

def adjust_asset_prices_start_to_available_data(assets_meta_df: pd.DataFrame, asset_prices: pd.DataFrame, start_date: date) -> pd.DataFrame:
    # Identify assets with ANY missing prices in this range
    missing_data = asset_prices.isnull().sum()
    assets_with_nans = missing_data[missing_data > 0]
    
    # Log limiting asset
    if not assets_with_nans.empty:
        monitor.add(f"\nWARNING: Portfolio Assets with Missing Data after {start_date}")
        first_indices = asset_prices.apply(lambda col: col.first_valid_index())
        valid_indices = first_indices.dropna()
        if not valid_indices.empty:
            limiting_asset = valid_indices.idxmax()
            latest_idx = valid_indices.max()
            latest_date = pd.to_datetime(str(latest_idx)).date()
            try:
                # Assumes limiting_asset (column name) exists as an index in assets_meta_df
                asset_name = assets_meta_df.loc[limiting_asset, "name"]
                monitor.add(f"Limiting Asset: {asset_name} ({limiting_asset}) starts {latest_date}")
            except KeyError:
                monitor.add(f"Limiting Asset: {limiting_asset} (starts {latest_date})")

    # Drop rows with any missing values
    asset_prices_adjusted = asset_prices.dropna()
    
    # Check if we have data left and print the actual start date
    if not asset_prices_adjusted.empty:
        actual_start = pd.to_datetime(str(asset_prices_adjusted.index[0])).date()
        monitor.add(f"INFO: Backtest will start on: {actual_start}")
    else:
        raise ValueError(f"No overlapping data found for these assets after {start_date}")

    return asset_prices_adjusted