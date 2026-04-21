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
            rb_run, rb_type = get_rebalance_settings(port_name, portfolio_df)
            check_freq = parse_rb_run(port_name, rb_run)
            rebalance_type = parse_rb_type(port_name, rb_type)
            print(check_freq, rebalance_type)

            # Get weights for this portfolio
            target_weights = filtered_portfolio_df[port_name].dropna()

            # Run the backtest - returns a tuple (Series, DataFrame)
            # returns_series, weights_df = run_backtest_one_portfolio(port_name, asset_returns, target_weights, check_freq, rebalance_type, band)
            port_result = run_backtest_one_portfolio(port_name, asset_returns, target_weights, check_freq, rebalance_type, band)
            
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

def run_backtest_one_portfolio(port_name, asset_returns, target_weights, check_freq='Y', rebalance_type='full', band=0.05):
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

    last_period = None

    for date in asset_returns.index:
        # Rebalance Check
        if check_freq == 'D':
            period = date
        elif check_freq == 'W':
            period = (date.year, date.isocalendar()[1])
        elif check_freq == 'M':
            period = (date.year, date.month)
        elif check_freq == 'Q':
            period = (date.year, (date.month - 1) // 3)
        elif check_freq == 'H':
            period = (date.year, 0 if date.month <= 6 else 1)
        elif check_freq == 'Y':
            period = date.year
        else:
            period = None

        if period != last_period:
            do_reset = False
            if rebalance_type == 'full':
                do_reset = True
            elif rebalance_type == 'band':
                if (current_weights - target_weights).abs().max() > band:
                    do_reset = True
            
            if do_reset:
                current_weights = target_weights.copy()
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
        check_freq=check_freq,
        rebalance_type=rebalance_type
    )

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

def parse_rb_type(name, rb_type):

    if 'sigma' == rb_type:
        rb_type_algo = "TODO"
    else:
        print(f"{name} has unknown rebalance type setting '{rb_type}', defaulting to full")
        rb_type_algo = 'full'

    return rb_type_algo

def parse_rb_run(name, rb_run):

    if 'semi-annual' == rb_run or 'half-year' == rb_run:
        run_algo = 'H'
    elif 'monthly' == rb_run:
        run_algo = 'M'
    elif 'daily' == rb_run:
        run_algo = 'D'
    elif 'yearly' == rb_run:
        run_algo = 'Y'
    else:
        print(f"{name} has unknown rebalance run setting '{rb_run}', defaulting to RunOnce")
        run_algo = 'O'

    return run_algo
