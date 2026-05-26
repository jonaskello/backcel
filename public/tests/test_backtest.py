import pytest
import pandas as pd
from public.src.backtest import rebalance_sigma, run_backtest_all

def test_sigma_rebalance_trigger():
    # Setup data
    ids = ['EQ', 'BD']
    ideal = pd.Series([0.6, 0.4], index=ids)
    current = pd.Series([0.8, 0.2], index=ids) # Massive drift
    meta = pd.DataFrame({'stddev': [0.1, 0.05]}, index=ids)

    # Run
    result = rebalance_sigma(current, ideal, meta)

    # Verify: EQ should have been pulled back from 0.8
    assert result['EQ'] < 0.8
    assert result.sum() == pytest.approx(1.0)

def test_sigma_no_trigger():
    ids = ['EQ', 'BD']
    ideal = pd.Series([0.6, 0.4], index=ids)
    current = pd.Series([0.61, 0.39], index=ids) # Tiny drift (1.6%)
    meta = pd.DataFrame({'stddev': [0.1, 0.05]}, index=ids)

    # Run
    result = rebalance_sigma(current, ideal, meta)

    # Verify: No change because drift < sigma (10%)
    pd.testing.assert_series_equal(result, current)

def test_sigma_respects_asymmetric_up_trigger():
    ids = ['EQ', 'BD']
    ideal = pd.Series([0.5, 0.5], index=ids)
    current = pd.Series([0.62, 0.38], index=ids)
    meta = pd.DataFrame({'stddev': [0.1, 0.1]}, index=ids)
    trigger_down = pd.Series([3.0, 3.0], index=ids)

    no_rebalance = rebalance_sigma(
        current,
        ideal,
        meta,
        trigger_down,
        pd.Series([2.5, 3.0], index=ids),
    )
    pd.testing.assert_series_equal(no_rebalance, current)

    rebalanced = rebalance_sigma(
        current,
        ideal,
        meta,
        trigger_down,
        pd.Series([2.0, 3.0], index=ids),
    )
    assert rebalanced['EQ'] == pytest.approx(0.525)
    assert rebalanced['BD'] == pytest.approx(0.475)

def test_sigma_respects_asymmetric_down_trigger():
    ids = ['EQ', 'BD']
    ideal = pd.Series([0.5, 0.5], index=ids)
    current = pd.Series([0.38, 0.62], index=ids)
    meta = pd.DataFrame({'stddev': [0.1, 0.1]}, index=ids)
    trigger_up = pd.Series([3.0, 3.0], index=ids)

    no_rebalance = rebalance_sigma(
        current,
        ideal,
        meta,
        pd.Series([2.5, 3.0], index=ids),
        trigger_up,
    )
    pd.testing.assert_series_equal(no_rebalance, current)

    rebalanced = rebalance_sigma(
        current,
        ideal,
        meta,
        pd.Series([1.5, 3.0], index=ids),
        trigger_up,
    )
    assert rebalanced['EQ'] == pytest.approx(0.475)
    assert rebalanced['BD'] == pytest.approx(0.525)

def test_leverage_rises_after_loss_without_forced_deleveraging():
    dates = pd.to_datetime(["2020-01-01", "2020-01-02", "2020-01-03"])
    prices = pd.DataFrame({"EQ": [100.0, 80.0, 80.0], "BORROW": [0.0, 0.0, 0.0]}, index=dates)
    portfolio = pd.DataFrame({"Levered": [1.0, 1.25]}, index=["EQ", "__leverage"])
    portfolio.attrs["borrow_rate_asset"] = "BORROW"
    meta = pd.DataFrame({"stddev": [0.1]}, index=["EQ"])

    result = run_backtest_all(meta, prices, portfolio).unwrap()
    weights = result.portfolios["Levered"].weights

    assert result.combined_returns.loc[dates[1], "Levered"] == pytest.approx(-0.25)
    assert weights.loc[dates[2], "EQ"] == pytest.approx(1.0 / 0.75)

def test_leverage_top_up_happens_on_rebalance_check_date():
    dates = pd.to_datetime(["2020-01-01", "2020-01-02", "2020-01-03"])
    prices = pd.DataFrame({"EQ": [100.0, 110.0, 110.0], "BORROW": [0.0, 0.0, 0.0]}, index=dates)
    portfolio = pd.DataFrame(
        {"Levered": [1.0, "daily", 1.25]},
        index=["EQ", "__check", "__leverage"],
    )
    portfolio.attrs["borrow_rate_asset"] = "BORROW"
    meta = pd.DataFrame({"stddev": [0.1]}, index=["EQ"])

    result = run_backtest_all(meta, prices, portfolio).unwrap()
    weights = result.portfolios["Levered"].weights

    assert result.combined_returns.loc[dates[1], "Levered"] == pytest.approx(0.125)
    assert weights.loc[dates[2], "EQ"] == pytest.approx(1.25)

def test_leverage_pays_borrowing_cost_from_configured_rate_asset():
    dates = pd.to_datetime(["2020-01-01", "2020-01-02"])
    prices = pd.DataFrame({"EQ": [100.0, 100.0], "BORROW": [36.5, 36.5]}, index=dates)
    portfolio = pd.DataFrame({"Levered": [1.0, 1.25]}, index=["EQ", "__leverage"])
    portfolio.attrs["borrow_rate_asset"] = "BORROW"
    meta = pd.DataFrame({"stddev": [0.1]}, index=["EQ"])

    result = run_backtest_all(meta, prices, portfolio).unwrap()

    assert result.combined_returns.loc[dates[0], "Levered"] == pytest.approx(0.0)
    assert result.combined_returns.loc[dates[1], "Levered"] == pytest.approx(-0.00025)
