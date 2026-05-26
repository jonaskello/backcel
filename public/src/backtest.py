import pandas as pd
from dataclasses import dataclass
from public.src.result import Result, Ok, Err
from public.src.monitor import monitor

LEVERAGE_EPSILON = 1e-10

@dataclass(frozen=True)
class PortfolioResult:
    returns: pd.Series
    weights: pd.DataFrame
    check_freq: str
    rebalance_type: str
    target_leverage: float = 1.0

@dataclass(frozen=True)
class BacktestSession:
    combined_returns: pd.DataFrame
    portfolios: dict[str, PortfolioResult]

def run_backtest_all(assets_meta_df: pd.DataFrame, asset_prices: pd.DataFrame, portfolio_df: pd.DataFrame) -> Result[BacktestSession, Exception]:

    try:
        # Calculate percent change per day
        asset_returns = asset_prices.pct_change().fillna(0)
        borrow_rate_asset = portfolio_df.attrs.get("borrow_rate_asset")
        borrow_rate_premium = float(portfolio_df.attrs.get("borrow_rate_premium", 0.0) or 0.0)
        borrow_rate = None
        if borrow_rate_asset:
            if borrow_rate_asset not in asset_prices.columns:
                raise ValueError(f"Borrow rate asset '{borrow_rate_asset}' is missing from price data.")
            borrow_rate = asset_prices[borrow_rate_asset]

        # Filter out any index labels starting with '__'
        filtered_portfolio_df = portfolio_df[~portfolio_df.index.astype(str).str.startswith("__")]

        # Return dictionaries
        all_strategies_returns: dict[str, pd.Series] = {}
        all_strategies_results: dict[str, PortfolioResult] = {}

        for port_name in filtered_portfolio_df.columns:

            # Get rebalance settings for this portfolio
            check_freq, rb_type = get_rebalance_settings(port_name, portfolio_df)
            target_leverage = get_leverage_setting(port_name, portfolio_df)
            if target_leverage > 1.0 and borrow_rate is None:
                raise ValueError(f"Portfolio '{port_name}' uses leverage but no borrow_rate_asset is configured.")

            # Get weights for this portfolio
            target_weights = pd.to_numeric(filtered_portfolio_df[port_name].dropna())
            rb_trigger_down, rb_trigger_up = get_rebalance_triggers(port_name, portfolio_df, target_weights.index)

            # Run the backtest - returns a tuple (Series, DataFrame)
            port_result = run_backtest_one_portfolio(
                port_name,
                assets_meta_df,
                asset_returns,
                target_weights,
                check_freq,
                rb_type,
                target_leverage,
                borrow_rate,
                borrow_rate_premium,
                rb_trigger_down,
                rb_trigger_up,
            )
            
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


def run_backtest_one_portfolio(
    port_name: str,
    assets_meta_df: pd.DataFrame,
    asset_returns: pd.DataFrame,
    target_weights,
    check_freq: str | None,
    rb_type: str | None,
    target_leverage: float = 1.0,
    borrow_rate: pd.Series | None = None,
    borrow_rate_premium: float = 0.0,
    rb_trigger_down: pd.Series | None = None,
    rb_trigger_up: pd.Series | None = None,
) -> PortfolioResult:

    portfolio_assets = target_weights.index
    missing = set(portfolio_assets) - set(asset_returns.columns)
    if missing:
        raise ValueError(f"Portfolio '{port_name}' has assets missing from price data: {missing}")

    # Filter asset_returns to ONLY the assets in this specific portfolio
    asset_returns_portfolio = asset_returns[portfolio_assets]
    assets_meta_portfolio = assets_meta_df.reindex(portfolio_assets)

    if target_leverage < 1.0:
        raise ValueError(f"Portfolio '{port_name}' has __leverage below 1.0.")

    target_allocation = target_weights / target_weights.sum()
    current_weights = target_allocation * target_leverage
    portfolio_returns = []
    historical_weights = []

    # Resolve period and rebalance functions
    actual_check_freq = str(check_freq).lower().strip() if check_freq in PERIOD_MAPPING else "once"
    actual_rb_type = str(rb_type).lower().strip() if rb_type in REBALANCE_STRATEGIES else "full"
    get_period = PERIOD_MAPPING[actual_check_freq]
    rb_func = REBALANCE_STRATEGIES[actual_rb_type]

    # Init period so it will trigger first rebalance directly
    last_period = "INITIAL_DUMMY_PERIOD"

    for i, date in enumerate(asset_returns_portfolio.index):
        # Rebalance
        period = get_period(date)
        if period != last_period:
            current_leverage = current_weights.sum()
            managed_leverage = max(current_leverage, target_leverage)
            current_allocation = current_weights / current_leverage
            rebalanced_allocation = rb_func(
                current_allocation,
                target_allocation,
                assets_meta_portfolio,
                rb_trigger_down,
                rb_trigger_up,
            )
            current_weights = rebalanced_allocation * managed_leverage
            last_period = period

        # Store weights at the start of the day (overnight holdings)
        historical_weights.append(current_weights.copy())

        # Calculate today's portfolio return
        borrowed_amount = max(current_weights.sum() - 1.0, 0.0)
        if borrowed_amount < LEVERAGE_EPSILON:
            borrowed_amount = 0.0
        daily_borrow_rate = 0.0
        if borrowed_amount > 0.0 and i > 0:
            if borrow_rate is None:
                raise ValueError(f"Portfolio '{port_name}' uses leverage but no borrow rate data is available.")
            daily_borrow_rate = ((borrow_rate.loc[date] + borrow_rate_premium) / 100) / 365
        daily_ret = (asset_returns_portfolio.loc[date] * current_weights).sum() - (borrowed_amount * daily_borrow_rate)
        portfolio_returns.append(daily_ret)

        # Drift the weights for tomorrow, this reflects that winners now take up more of the pie
        current_weights = current_weights * (1 + asset_returns_portfolio.loc[date])
        # Scale exposures by equity after asset returns and borrowing costs.
        current_weights = current_weights / (1 + daily_ret)

    # Create the returns Series
    returns_series = pd.Series(portfolio_returns, index=asset_returns_portfolio.index)
    
    # Create the weights DataFrame
    weights_df = pd.DataFrame(historical_weights, index=asset_returns_portfolio.index)
    weights_df.columns.name = "Asset"

    return PortfolioResult(
        returns=returns_series,
        weights=weights_df,
        check_freq=actual_check_freq,
        rebalance_type=actual_rb_type,
        target_leverage=target_leverage,
    )

def rebalance_full(
    current: pd.Series,
    ideal: pd.Series,
    assets_meta: pd.DataFrame,
    rb_trigger_down: pd.Series | None = None,
    rb_trigger_up: pd.Series | None = None,
) -> pd.Series:
    return ideal

def rebalance_sigma(
    current_weights: pd.Series,
    ideal_weights: pd.Series,
    assets_meta: pd.DataFrame,
    rb_trigger_down: pd.Series | None = None,
    rb_trigger_up: pd.Series | None = None,
) -> pd.Series:
    """
    Surgical rebalance:
    - Trigger: Drift outside configured sigma multipliers
    - Action: Adjust trigger asset and its opposite counterpart to 0.5 * sigma
    """

    sigmas = assets_meta['stddev'].fillna(0.10)
    trigger_down = rb_trigger_down.reindex(ideal_weights.index).fillna(1.0) if rb_trigger_down is not None else pd.Series(1.0, index=ideal_weights.index)
    trigger_up = rb_trigger_up.reindex(ideal_weights.index).fillna(1.0) if rb_trigger_up is not None else pd.Series(1.0, index=ideal_weights.index)

    # 1. Calculate Relative Drift: (Current / Target) - 1
    drift_pct = (current_weights / ideal_weights) - 1
    
    # 2. Check for breach of the configured sigma rebalance span
    breaches = (
        ((drift_pct < 0) & (drift_pct.abs() > sigmas * trigger_down)) |
        ((drift_pct > 0) & (drift_pct.abs() > sigmas * trigger_up))
    )

    if not breaches.any():
        return current_weights

    # 3. Identify the "Trigger" asset (furthest outside its sigma)
    # We normalize drift by sigma to see who is 'most' outside their limit
    trigger_thresholds = pd.Series(
        [trigger_up[asset_id] if drift_pct[asset_id] > 0 else trigger_down[asset_id] for asset_id in drift_pct.index],
        index=drift_pct.index,
    )
    trigger_asset = (drift_pct.abs() / (sigmas * trigger_thresholds)).idxmax()
    
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

    if '__check' in df_portfolios.index:
        strat_row = df_portfolios.loc['__check']
        check_freq = str(strat_row[name]).lower().strip()
    else:
        check_freq = None

    if '__rb_type' in df_portfolios.index:
        strat_row = df_portfolios.loc['__rb_type']
        rb_type = str(strat_row[name]).lower().strip()
    else:
        rb_type = None

    return check_freq, rb_type

def get_leverage_setting(name, df_portfolios) -> float:
    if '__leverage' not in df_portfolios.index:
        return 1.0

    leverage = df_portfolios.loc['__leverage', name]
    if pd.isna(leverage) or str(leverage).strip() == "":
        return 1.0

    return float(leverage)

def get_rebalance_triggers(name, df_portfolios, portfolio_assets) -> tuple[pd.Series, pd.Series]:
    trigger_down = pd.Series(1.0, index=portfolio_assets, dtype=float)
    trigger_up = pd.Series(1.0, index=portfolio_assets, dtype=float)

    apply_rebalance_trigger_row(df_portfolios, name, "__rb_trigger_down", trigger_down)
    apply_rebalance_trigger_row(df_portfolios, name, "__rb_trigger_up", trigger_up)

    return trigger_down, trigger_up

def apply_rebalance_trigger_row(df_portfolios, name, row_id: str, triggers: pd.Series):
    if row_id in df_portfolios.index:
        value = df_portfolios.loc[row_id, name]
        if pd.notna(value) and str(value).strip() != "":
            triggers.loc[:] = float(value)

    prefix = row_id + ":"
    override_rows = [idx for idx in df_portfolios.index if str(idx).startswith(prefix)]
    for override_row in override_rows:
        asset_id = str(override_row)[len(prefix):]
        if asset_id not in triggers.index:
            continue

        value = df_portfolios.loc[override_row, name]
        if pd.notna(value) and str(value).strip() != "":
            triggers.loc[asset_id] = float(value)

    if (triggers <= 0).any():
        raise ValueError(f"Rebalance trigger '{row_id}' must be greater than 0.")

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

