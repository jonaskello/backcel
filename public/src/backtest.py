import pandas as pd
from dataclasses import dataclass
from public.src.result import Result, Ok, Err
from typing import Optional, Any

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

def run_backtest_all(asset_prices: pd.DataFrame, portfolio_df: pd.DataFrame, band=0.05) -> Result[BacktestSession, Exception]:

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
            port_result = run_backtest_one_portfolio(port_name, asset_returns, target_weights, rb_check_freq, rb_type, band)
            
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


def run_backtest_one_portfolio(port_name, asset_returns, target_weights, rb_check_freq: str | None, rb_type: str | None, band) -> PortfolioResult:

    # Filter asset_returns to ONLY the assets in this specific portfolio
    # This prevents extra columns from appearing in weights_df
    portfolio_assets = target_weights.index
    
    missing = set(portfolio_assets) - set(asset_returns.columns)
    if missing:
        raise ValueError(f"Portfolio '{port_name}' has assets missing from price data: {missing}")

    asset_returns = asset_returns[portfolio_assets]
    current_weights = target_weights.copy()
    portfolio_returns = []
    historical_weights = []

    # RESOLVE PERIOD FUNCTION BEFORE THE LOOP
    # If no freq, use a constant function so period != last_period is only true on day 1
    freq_key = str(rb_check_freq).lower().strip() if rb_check_freq else "once"
    get_period = PERIOD_MAPPING.get(freq_key, period_once)

    # RESOLVE REBALANCE STRATEGY BEFORE THE LOOP
    rb_type_key = str(rb_type).lower().strip() if rb_type else 'full'
    rb_func = REBALANCE_STRATEGIES.get(rb_type_key, rebalance_full)

    # last_period = None
    last_period = "INITIAL_DUMMY_PERIOD"
    # rb_type_lower = rb_type.lower().strip()
    # rb_func = REBALANCE_STRATEGIES.get(rb_type_lower, rebalance_full)

    for date in asset_returns.index:
        # Rebalance Check
        # period = get_rebalance_period(date, rb_check_freq)
        period = get_period(date)

        if period != last_period:
            current_weights = rb_func(
                current_weights=current_weights,
                ideal_weights=target_weights,
                band=band
            )
            last_period = period

        # Store weights at the start of the day (overnight holdings)
        historical_weights.append(current_weights.copy())

        # Calculate today's portfolio return
        daily_ret = (asset_returns.loc[date] * current_weights).sum()
        portfolio_returns.append(daily_ret)

        # Drift the weights for tomorrow, this reflects that winners now take up more of the pie
        current_weights = current_weights * (1 + asset_returns.loc[date])
        # Re-normalize weights so they represent the new % of total value
        current_weights = current_weights / current_weights.sum()

    # Create the returns Series
    returns_series = pd.Series(portfolio_returns, index=asset_returns.index)
    
    # Create the weights DataFrame
    weights_df = pd.DataFrame(historical_weights, index=asset_returns.index)
    weights_df = weights_df.add_prefix(port_name + ">")


    return PortfolioResult(
        returns=returns_series,
        weights=weights_df,
        check_freq=rb_check_freq,
        rebalance_type=rb_type
    )

def rebalance_full(current_weights: pd.Series, ideal_weights: pd.Series, band: float) -> pd.Series:
    """Always returns the ideal weights (full reset)."""
    return ideal_weights

def rebalance_band(current_weights: pd.Series, ideal_weights: pd.Series, band: float) -> pd.Series:
    """Returns ideal weights only if the max drift exceeds the band; otherwise returns current."""
    drift = (current_weights - ideal_weights).abs().max()
    if drift > band:
        return ideal_weights
    return current_weights

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


def get_rebalance_period(date: pd.Timestamp, freq: Optional[str]) -> Optional[Any]:
    if not freq:
        return None
    
    # Standardize and look up the period generator
    f = str(freq).lower().strip()
    period_func = PERIOD_MAPPING.get(f)
    
    if period_func:
        return period_func(date)
    
    return None

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
    'band': rebalance_band,
}

