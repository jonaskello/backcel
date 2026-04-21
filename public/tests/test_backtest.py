import pytest
import pandas as pd
from public.src.backtest import rebalance_sigma # Adjust path to your package name

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