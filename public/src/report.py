import marimo as mo
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from public.src.backtest import BacktestSession

def show_results(results: BacktestSession):
    # This will show a table with a row for each portfolio
    summary_table = get_stats(results)
    ui_portfolio_table = mo.Html(summary_table.to_html())

    # Calculate cumulative growth (1.0 basis)
    equity_curves = (1 + results.combined_returns).cumprod()
    fig = portfolio_perf(equity_curves)
    plt = portfolio_drawdown_plot2(equity_curves)

    # Use marimo's UI wrapper to ensure visibility in WASM
    ui_portfolio_curves = (mo.ui.plotly(fig))
    ui_drawdown_curves = mo.ui.plotly(plt)
    ui_all = mo.vstack([ui_portfolio_table, ui_portfolio_curves, ui_drawdown_curves])
    mo.output.replace(ui_all)

def get_stats(results: BacktestSession):
    stats = {}
    df = results.combined_returns
    
    # Use Log Returns for Volatility (to match bt/ffn logic)
    log_returns = np.log(1 + df).replace([np.inf, -np.inf], 0)
    
    # Time factor alignment (matching previous CAGR logic)
    start_date = df.index.min()
    end_date = df.index.max()
    stats['Start'] = start_date
    stats['End'] = end_date
    years = (end_date - start_date).days / 365.25

    # Create a mapping for the settings
    stats['RB Check'] = {name: p.check_freq for name, p in results.portfolios.items()}
    stats['RB Type'] = {name: p.rebalance_type for name, p in results.portfolios.items()}

    # Total Return (Arithmetic)
    total_return_factor = (1 + df).prod()
    stats['Total Return %'] = (total_return_factor - 1) * 100
    stats['CAGR %'] = (total_return_factor ** (1 / years) - 1) * 100

    # Annualized Daily Volatility (Standardizing to match bt's use of log-std)
    # bt often uses np.std(ddof=1) - the sample standard deviation
    daily_vol = log_returns.std(ddof=1) 
    stats['Volatility %'] = daily_vol * np.sqrt(252) * 100
    
    # Sharpe Ratio (using the daily vol calculated above)
    stats['Sharpe'] = (df.mean() / df.std(ddof=1)) * np.sqrt(252)

    # Sortino Ratio
    # Same adjustment for ddof if needed
    downside_deviation = np.sqrt((np.minimum(0, df)**2).mean())
    stats['Sortino'] = (df.mean() / downside_deviation) * np.sqrt(252)

    # Max Drawdown
    wealth = (1 + df).cumprod()
    peak = wealth.cummax()
    drawdowns = (wealth - peak) / peak
    stats['Max Drawdown %'] = drawdowns.min() * 100

    # Avg Drawdown
    def calc_avg_dd(series):
        is_in_dd = series < 0
        groups = (is_in_dd != is_in_dd.shift()).cumsum()
        # Find the minimum (worst) point of each drawdown group
        drawdown_depths = series[is_in_dd].groupby(groups).min()
        return drawdown_depths.mean() * 100

    stats['Avg Drawdown %'] = drawdowns.apply(calc_avg_dd)

    # Max Drawdown Days
    def calc_max_dd_days(series):
        is_in_dd = series < 0
        groups = (is_in_dd != is_in_dd.shift()).cumsum()
        return is_in_dd.groupby(groups).cumsum().max()

    stats['Max Drawdown Period'] = drawdowns.apply(calc_max_dd_days)

    # Format result
    result = pd.DataFrame(stats).round(2)
    
    # Convert days to years string if > 365
    result['Max Drawdown Period'] = result['Max Drawdown Period'].apply(
        lambda x: f"{round(x/365.25, 2)} years" if x > 365 else f"{int(x)} days"
    )

    return result

def get_all_max_drawdown_days(res_prices):
    """Calculates max drawdown days for every portfolio in the result."""
    dict_days = {}
    
    for col in res_prices.columns:
        prices = res_prices[col]
        rolling_max = prices.cummax()
        is_underwater = prices < rolling_max
        
        # Group consecutive True values
        drawdown_groups = (is_underwater != is_underwater.shift()).cumsum()
        
        # Only count groups where we are actually underwater
        underwater_periods = is_underwater[is_underwater].groupby(drawdown_groups[is_underwater]).size()
        
        # Store the max days (handle case with 0 drawdowns with .get)
        dict_days[col] = underwater_periods.max() if not underwater_periods.empty else 0
        
    return pd.Series(dict_days, name='max_drawdown_days')

def portfolio_perf(plot_data):

    # SAFETY CHECK: Validate first row before normalization
    if plot_data.empty:
        raise ValueError("No price data available for plotting")
    
    first_row = plot_data.iloc[0]
    if (first_row == 0).any():
        raise ValueError(
            f"Cannot normalize: first row contains zero values in columns: "
            f"{first_row[first_row == 0].index.tolist()}"
        )
    if first_row.isna().any():
        raise ValueError(
            f"Cannot normalize: first row contains NaN values in columns: "
            f"{first_row[first_row.isna()].index.tolist()}"
        )

    # Normalize to 100 based on the first day
    plot_data_norm = (plot_data / plot_data.iloc[0]) * 100

    # 2. Create the Interactive Figure
    fig = go.Figure()

    # Iterate through each column (portfolio) in the result
    for portfolio_name in plot_data_norm.columns:
        fig.add_trace(go.Scatter(
            x=plot_data_norm.index,
            y=plot_data_norm[portfolio_name],
            name=portfolio_name,
            mode='lines',
            line=dict(width=2)
        ))

    # 3. Style the Layout
    fig.update_layout(
        title='Portfolio Performance Comparison',
        xaxis_title='Date',
        yaxis_title='Growth of 100',
        hovermode='x unified',
        template='plotly_white',
        legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01)
    )

    return fig

def portfolio_drawdown_plot2(wealth_index):
    if wealth_index.empty or len(wealth_index) < 2:
        return None
    
    previous_peaks = wealth_index.cummax()
    drawdown = (wealth_index / previous_peaks) - 1

    # 2. Create Plotly Figure
    fig = go.Figure()

    for col in drawdown.columns:
        fig.add_trace(
            go.Scatter(
                x=drawdown.index,
                y=drawdown[col],
                name=col,
                mode='lines',
                fill='tozeroy',  # Standard practice for drawdown plots
                hovertemplate="<b>%{x}</b><br>Drawdown: %{y:.2%}<extra></extra>"
            )
        )

    # 3. Formatting
    fig.update_layout(
        title="Portfolio Drawdown Comparison",
        yaxis_title="Decline from Peak",
        template="plotly_white",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=0, r=0, t=50, b=0),
        height=400
    )

    # Format Y-axis as percentage
    fig.update_layout(yaxis_tickformat='.1%')
    
    # Add a zero line
    fig.add_hline(y=0, line_color="black", line_width=1)

    return fig

