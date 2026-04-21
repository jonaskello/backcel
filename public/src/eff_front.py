import pandas as pd
import numpy as np
from pypfopt import EfficientFrontier, risk_models, expected_returns
import plotly.graph_objects as go

# This does not work in WASM becuase of the pypfopt dependency
def get_efficient_frontier2(portfolio_df, asset_prices_backtest):

    # Filter tickers
    portfolio_df_wo_settings = portfolio_df[~portfolio_df.index.str.startswith('__')]
    raw_tickers = portfolio_df_wo_settings.index.unique()
    active_tickers = [t for t in raw_tickers if t in asset_prices_backtest.columns]
    filtered_prices = asset_prices_backtest[active_tickers].dropna()

    # Calculate returns and risk
    mu = expected_returns.mean_historical_return(filtered_prices)
    S = risk_models.sample_cov(filtered_prices)

    # 1. Generate Frontier Points manually for Plotly
    ef = EfficientFrontier(mu, S)
    fig = go.Figure()

    # Create range of target returns for the curve
    target_returns = np.linspace(mu.min(), mu.max(), 50)
    frontier_vols = []
    
    for r in target_returns:
        try:
            ef_p = EfficientFrontier(mu, S)
            ef_p.efficient_return(r)
            _, vol, _ = ef_p.portfolio_performance()
            frontier_vols.append(vol)
        except:
            frontier_vols.append(None)

    # Plot the curve
    fig.add_trace(go.Scatter(
        x=frontier_vols, y=target_returns,
        mode='lines', name='Efficient Frontier',
        line=dict(color='black', width=2)
    ))

    # 2. Max Sharpe Portfolio
    ef_ms = EfficientFrontier(mu, S)
    w_ms = ef_ms.max_sharpe()
    ret_ms, vol_ms, _ = ef_ms.portfolio_performance()
    fig.add_trace(go.Scatter(
        x=[vol_ms], y=[ret_ms],
        mode='markers', name='Max Sharpe',
        marker=dict(color='red', size=15, symbol='star')
    ))

    # 3. Min Volatility Portfolio
    ef_mv = EfficientFrontier(mu, S)
    w_mv = ef_mv.min_volatility()
    ret_mv, vol_mv, _ = ef_mv.portfolio_performance()
    fig.add_trace(go.Scatter(
        x=[vol_mv], y=[ret_mv],
        mode='markers', name='Min Volatility',
        marker=dict(color='green', size=15, symbol='star')
    ))

    # 4. Individual Assets
    fig.add_trace(go.Scatter(
        x=np.sqrt(np.diag(S)), y=mu,
        mode='markers+text', name='Assets',
        text=active_tickers, textposition="top center",
        marker=dict(color='blue', size=8, opacity=0.5)
    ))

    fig.update_layout(
        title="Efficient Frontier",
        xaxis_title="Volatility (Risk)",
        yaxis_title="Expected Return",
        template="plotly_white",
        legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01)
    )

    # DataFrames for weights
    def get_weights_df(w):
        df = pd.DataFrame(list(w.items()), columns=['Ticker', 'Weight'])
        df['Weight %'] = (df['Weight'] * 100).round(2)
        return df.sort_values('Weight %', ascending=False).reset_index(drop=True)

    return fig, get_weights_df(w_ms), get_weights_df(w_mv)
