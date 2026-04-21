import pandas as pd
import plotly.graph_objects as go
import public.src.native_report as nr

def portfolio_summary(res):

    # res.set_riskfree_rate(0.02)

    # Define the custom time formatter
    def format_drawdown_time(x):
        if pd.isna(x): return "0 days"
        if x >= 365: # Change to 12 if using Monthly data
            return f"{x / 365:.2f} years"
        return f"{int(x)} days"

    # Transpose and filter
    important_metrics = ['start', 'end', 'total_return', 'cagr', 
                        'daily_vol',
                          'daily_sortino', 'daily_sharpe', 
                          'avg_drawdown', 'max_drawdown', "rf"]
    nice_summary = res.stats.loc[important_metrics].T

    # Merge with drawdown days
    drawdown_days = nr.get_all_max_drawdown_days(res.prices)
    final_stats = pd.concat([nice_summary, drawdown_days], axis=1)
    final_stats = final_stats.rename(columns={'max_drawdown_days': 'max_drawdown_period'})

    # Define your preferred order
    desired_order = [
        'start', 'end', 'total_return', 'cagr', 'daily_vol','daily_sharpe', 
          'daily_sortino', 
        'avg_drawdown', 'max_drawdown', 'max_drawdown_period', 'rf'
    ]
    
    # Reorder columns
    final_stats = final_stats[desired_order]

    # Note: You must display this 'styled' object to see the result
    styled_stats = final_stats.style.format({
        'start': '{:%Y-%m-%d}',
        'end': '{:%Y-%m-%d}',
        'total_return': '{:.2%}',
        'cagr': '{:.2%}',
        'max_drawdown': '{:.2%}',
        'daily_sharpe': '{:.2f}',
        'daily_sortino': '{:.2f}',
        'daily_vol': '{:.2%}',
        'avg_drawdown': '{:.2%}',
        'max_drawdown_period': format_drawdown_time,
        'rf': '{:.2%}',
    })

    return styled_stats

def get_drawdown_culprits(res, asset_prices_backtest):
    results_list = []
    all_drawdowns = res.prices.to_drawdown_series()

    # Use your original asset price dataframe here
    # Ensure it is the one containing the actual tickers (AAPL, MSFT, etc.)
    price_data = asset_prices_backtest 

    for name in res.backtests.keys():
        equity_curve = res.prices[name]
        drawdown_series = all_drawdowns[name]
        
        end_date = drawdown_series.idxmin()
        peak_date = equity_curve[:end_date].idxmax()
        
        # Get weights for this strategy at the peak
        peak_weights = res.get_security_weights(name).loc[peak_date]
        
        impacts = {}
        for ticker in peak_weights.index:
            # Check against your source price data
            if ticker in price_data.columns:
                p_start = price_data.loc[peak_date, ticker]
                p_end = price_data.loc[end_date, ticker]
                
                if p_start > 0:
                    change = (p_end / p_start) - 1
                    impacts[ticker] = peak_weights[ticker] * change
        
        if impacts:
            worst_asset = min(impacts, key=lambda k: impacts[k])
            results_list.append({
                'Strategy': name,
                'MDD %': drawdown_series.min() * 100,
                'Culprit': worst_asset,
                'Impact %': impacts[worst_asset] * 100,
                'Peak': peak_date.date(),
                'Valley': end_date.date()
            })

    # Guard against empty results
    if results_list:
        summary_df = pd.DataFrame(results_list).set_index('Strategy')
        return summary_df
    else:
        print("Error: No impacts calculated. Check if 'asset_prices_backtest' contains the tickers found in your portfolio weights.")

