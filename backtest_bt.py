import marimo

__generated_with = "0.23.1"
app = marimo.App()


@app.cell
async def _():
    import marimo as mo
    import os
    from public.src import main as dlm

    def display(obj):
        mo.output.append(obj)
    def display_df(df):
        mo.output.append(mo.Html(df.to_html()))
    async def on_progress(msg):
        print(msg)

    base_dir = dlm.get_local_base_dir()
    settings_file_path = os.path.join(base_dir, dlm.get_settings_file_name())
    portfolio_df, asset_prices_available, assets_meta_df = (await dlm.data_load_all(base_dir, on_progress, settings_file_path)).unwrap()
    return (
        asset_prices_available,
        assets_meta_df,
        display,
        display_df,
        mo,
        portfolio_df,
    )


@app.cell
def _(asset_prices_available, assets_meta_df, mo, portfolio_df):
    # RUN BACKTEST
    import traceback
    from public.src import bt_backtest as b
    from public.src import backtest as nb
    from public.src.result import Ok, Err

    res = b.portfolio_backtest(portfolio_df, asset_prices_available, assets_meta_df)
    backtest_result = nb.run_backtest_all(asset_prices_available, portfolio_df)
    match backtest_result:
        case Ok(data):
            nat_returns, nat_weights = data
        case Err(e):
            print(f"Error: {e}")
            traceback.print_exception(e)
            mo.stop(True, f"ERROR: {e}")
    return nat_returns, res


@app.cell
def _():
    # DEBUG diff between bt and native
    # debug_port_name = "JK3"
    # display(res.prices[debug_port_name].pct_change())
    # display(nat_returns[debug_port_name])
    # diff_df = res.prices[debug_port_name].pct_change() - nat_returns[debug_port_name]
    # display(diff_df)
    # sorted_diffs = diff_df.sort_values(ascending=False)
    # display(sorted_diffs)

    # display(res.get_weights(debug_port_name))
    # display(nat_weights[debug_port_name])
    # weights_diff_df = res.get_weights(debug_port_name) - nat_weights[debug_port_name]
    # display(weights_diff_df)
    return


@app.cell
def _(display, display_df, nat_returns, res):
    # PRINT RESULTS
    from public.src import bt_report as r
    from public.src import report as nr

    display(r.portfolio_summary(res))
    display_df(nr.get_stats(nat_returns))

    # res.stats
    # display(res.prices)
    # display(res.prices["JK7"].pct_change())
    # display(res.get_security_weights("JK7"))
    # display(res.get_security_weights("JK7").loc['2013-12-30':'2014-01-05'])
    display(nr.portfolio_perf(res.prices))
    return nr, r


@app.cell
def _():
    # # PRINT TRANSACTIONS PER PORTFOLIO
    # # The keys of the res.backtests dictionary are the Strategy names
    # for name in res.backtests.keys():
    #     tx = res.get_transactions(name)
    #     print(f"Portfolio: {name} | Total Trades: {len(tx)}")
    #     # display(res.get_transactions(name))
    return


@app.cell
def _(nr, res):
    plt = nr.portfolio_drawdown_plot2(res.prices)
    plt
    return


@app.cell
def _(asset_prices_available, display, mo, r, res):
    ddcul = r.get_drawdown_culprits(res, asset_prices_available)
    display(mo.Html(ddcul.to_html()))
    return


@app.cell
def _(asset_prices_available, display, display_df, mo, portfolio_df):
    from public.src import eff_front as ef

    efffront, max_sharpe, max_vol = ef.get_efficient_frontier2(portfolio_df, asset_prices_available)
    display(mo.plain_text("Max Sharpe Weights:"))
    display_df(max_sharpe)
    display(mo.plain_text("\nMin Volatility Weights:"))
    display_df(max_vol)
    # display(efffront.show())
    # display(efffront.gcf())
    display(efffront)
    return


if __name__ == "__main__":
    app.run()
