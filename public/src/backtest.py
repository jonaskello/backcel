import pandas as pd
from dataclasses import dataclass
from public.src.result import Result, Ok, Err

@dataclass(frozen=True)
class PortfolioResult:
    returns: pd.Series
    weights: pd.DataFrame
    check_freq: str
    rebalance_type: str

@dataclass(frozen=True)
class BacktestSession:
    combined_returns: pd.DataFrame
    portfolios: dict[str, PortfolioResult]

def run_backtest_all(assets_meta_df: pd.DataFrame, asset_prices: pd.DataFrame, portfolio_df: pd.DataFrame) -> Result[BacktestSession, Exception]:

    try:
        # Calculate percent change per day
        asset_returns = asset_prices.pct_change().fillna(0)

        # Filter out any index labels starting with '__'
        filtered_portfolio_df = portfolio_df[~portfolio_df.index.astype(str).str.startswith("__")]

        # Return dictionaries
        all_strategies_returns: dict[str, pd.Series] = {}
        all_strategies_results: dict[str, PortfolioResult] = {}

        for port_name in filtered_portfolio_df.columns:

            # Get rebalance settings for this portfolio
            rb_check_freq, rb_type = get_rebalance_settings(port_name, portfolio_df)

            # Get weights for this portfolio
            target_weights = filtered_portfolio_df[port_name].dropna()

            # Run the backtest - returns a tuple (Series, DataFrame)
            port_result = run_backtest_one_portfolio(port_name, assets_meta_df, asset_returns, target_weights, rb_check_freq, rb_type)
            
            # Store results
            all_strategies_returns[port_name] = port_result.returns
            all_strategies_results[port_name] = port_result

        # Combine all returns into a single DataFrame
        combined_returns = pd.DataFrame(all_strategies_returns)
        
        # # Return both: a DataFrame and a Dictionary
        # return Ok((combined_returns, all_strategies_weights))
        return Ok(BacktestSession(
            combined_returns=combined_returns, 
            portfolios=all_strategies_results
        ))

    except Exception as e:
        return Err(e) 


def run_backtest_one_portfolio(port_name: str, assets_meta_df: pd.DataFrame, asset_returns: pd.DataFrame, target_weights, rb_check_freq: str | None, rb_type: str | None) -> PortfolioResult:

    portfolio_assets = target_weights.index
    missing = set(portfolio_assets) - set(asset_returns.columns)
    if missing:
        raise ValueError(f"Portfolio '{port_name}' has assets missing from price data: {missing}")

    # Filter asset_returns to ONLY the assets in this specific portfolio
    asset_returns_portfolio = asset_returns[portfolio_assets]
    assets_meta_portfolio = assets_meta_df.reindex(portfolio_assets)

    current_weights = target_weights.copy()
    portfolio_returns = []
    historical_weights = []

    # Resolve period and rebalance functions
    actual_rb_check_freq = str(rb_check_freq).lower().strip() if rb_check_freq in PERIOD_MAPPING else "once"
    actual_rb_type = str(rb_type).lower().strip() if rb_type in REBALANCE_STRATEGIES else "full"
    get_period = PERIOD_MAPPING[actual_rb_check_freq]
    rb_func = REBALANCE_STRATEGIES[actual_rb_type]

    # Init period so it will trigger first rebalance directly
    last_period = "INITIAL_DUMMY_PERIOD"

    for date in asset_returns_portfolio.index:
        # Rebalance
        period = get_period(date)
        if period != last_period:
            current_weights = rb_func(current_weights, target_weights, assets_meta_portfolio)
            last_period = period

        # Store weights at the start of the day (overnight holdings)
        historical_weights.append(current_weights.copy())

        # Calculate today's portfolio return
        daily_ret = (asset_returns_portfolio.loc[date] * current_weights).sum()
        portfolio_returns.append(daily_ret)

        # Drift the weights for tomorrow, this reflects that winners now take up more of the pie
        current_weights = current_weights * (1 + asset_returns_portfolio.loc[date])
        # Re-normalize weights so they represent the new % of total value
        current_weights = current_weights / current_weights.sum()

    # Create the returns Series
    returns_series = pd.Series(portfolio_returns, index=asset_returns_portfolio.index)
    
    # Create the weights DataFrame
    weights_df = pd.DataFrame(historical_weights, index=asset_returns_portfolio.index)
    weights_df = weights_df.add_prefix(port_name + ">")


    return PortfolioResult(
        returns=returns_series,
        weights=weights_df,
        check_freq=actual_rb_check_freq,
        rebalance_type=actual_rb_type
    )

def rebalance_full(current: pd.Series, ideal: pd.Series, assets_meta: pd.DataFrame) -> pd.Series:
    return ideal

def rebalance_sigma(current_weights: pd.Series, ideal_weights: pd.Series, assets_meta: pd.DataFrame) -> pd.Series:
    """
    Surgical rebalance:
    - Trigger: Drift > 1.0 * sigma
    - Action: Adjust trigger asset and its opposite counterpart to 0.5 * sigma
    """

    sigmas = assets_meta['stddev'].fillna(0.10)

    # 1. Calculate Relative Drift: (Current / Target) - 1
    drift_pct = (current_weights / ideal_weights) - 1
    
    # 2. Check for breach of the 1-sigma rebalance span
    breaches = drift_pct.abs() > sigmas
    
    if not breaches.any():
        return current_weights

    # 3. Identify the "Trigger" asset (furthest outside its sigma)
    # We normalize drift by sigma to see who is 'most' outside their limit
    trigger_asset = (drift_pct.abs() / sigmas).idxmax()
    
    # 4. Identify the "Counter" asset (closest to a trigger in the other direction)
    # If trigger is too high, we find the one most 'underweight' relative to its sigma
    if drift_pct[trigger_asset] > 0:
        counter_asset = (drift_pct / sigmas).idxmin()
    else:
        counter_asset = (drift_pct / sigmas).idxmax()

    # 5. Execute the adjustment to the Tolerance Band (0.5 * sigma)
    new_weights = current_weights.copy()
    
    # Move trigger asset to 0.5 sigma
    direction = 1 if drift_pct[trigger_asset] > 0 else -1
    tolerance_pct = direction * (sigmas[trigger_asset] * 0.5)
    new_weights[trigger_asset] = ideal_weights[trigger_asset] * (1 + tolerance_pct)
    
    # Adjust counter asset to absorb the difference (re-balancing the pair)
    diff = current_weights[trigger_asset] - new_weights[trigger_asset]
    new_weights[counter_asset] += diff
    
    return new_weights


def period_once(_: pd.Timestamp):
    return "CONSTANT_PERIOD"

def period_daily(date: pd.Timestamp):
    return date

def period_weekly(date: pd.Timestamp):
    return (date.year, date.isocalendar()[1])

def period_monthly(date: pd.Timestamp):
    return (date.year, date.month)

def period_quarterly(date: pd.Timestamp):
    return (date.year, (date.month - 1) // 3)

def period_half_yearly(date: pd.Timestamp):
    return (date.year, 0 if date.month <= 6 else 1)

def period_yearly(date: pd.Timestamp):
    return date.year

def get_rebalance_settings(name, df_portfolios):

    if '__rb_run' in df_portfolios.index:
        strat_row = df_portfolios.loc['__rb_run']
        rb_run = str(strat_row[name]).lower().strip()
    else:
        rb_run = None

    if '__rb_type' in df_portfolios.index:
        strat_row = df_portfolios.loc['__rb_type']
        rb_type = str(strat_row[name]).lower().strip()
    else:
        rb_type = None

    return rb_run, rb_type

PERIOD_MAPPING = {
    'daily': period_daily,
    'weekly': period_weekly,
    'monthly': period_monthly,
    'quarterly': period_quarterly,
    'half-year': period_half_yearly,
    'yearly': period_yearly,
    'once': period_once
}

REBALANCE_STRATEGIES = {
    'full': rebalance_full,
    'sigma': rebalance_sigma,
}

