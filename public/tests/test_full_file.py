import traceback
import pytest
import os
import pandas as pd
from public.src.result import Err, Ok
from pathlib import Path
from public.src import data_load_main as dlm
from public.src import backtest as bn
from public.src import report as r

# Identify all test workbooks
CURRENT_DIR = Path(__file__).parent
TEST_DATA_DIR = CURRENT_DIR / "data"
excel_test_files = list(TEST_DATA_DIR.glob("test_*.xlsx"))

@pytest.mark.asyncio
@pytest.mark.parametrize(
    "test_file", 
    excel_test_files, 
    ids=[f.name for f in excel_test_files]
)
async def test_full_engine_run(test_file):

    async def on_progress(msg: str):
        print(msg)

    print(f"\n\n----RUNNING TEST FILE {test_file}")
    base_dir = "./public/tests/data"
    data_load_result = await dlm.data_load_all(base_dir, on_progress, test_file)
    expected_values, expected_weights, expected_stats = await load_expected(base_dir, test_file)
    match data_load_result:
        case Ok(actual):
            portfolio_df, asset_prices_available, assets_meta_df = actual
            backtest_result = bn.run_backtest_all(assets_meta_df, asset_prices_available, portfolio_df)
            match backtest_result:
                case Ok(actual):
                    # Calculate cumulative growth (1.0 basis)
                    portfolio_values = (1 + actual.combined_returns).cumprod()
                    # Compare your backtest result to the 'Expected' sheet
                    pd.testing.assert_frame_equal(portfolio_values, expected_values)

                    for p_name, p_result in actual.portfolios.items():
                        # expected_weights_df has MultiIndex columns (Portfolio, Asset)
                        expected_p_weights = expected_weights[[p_name]]
                        expected_p_weights = expected_weights[[p_name]].droplevel(0, axis=1)
                        pd.testing.assert_frame_equal(
                            p_result.weights, 
                            expected_p_weights, 
                            obj=f"Weights Mismatch for Portfolio: {p_name}",
                            atol=1e-5
                        )
                    # Compare your backtest result to the 'Expected' sheet
                    actual_stats = r.get_stats(actual)
                    pd.testing.assert_frame_equal(actual_stats, expected_stats)

                case Err(e):
                    pytest.fail(f"Error: {e}")
                    traceback.print_exception(e)
        case Err(e):
            traceback.print_exception(e)
            pytest.fail(f"Error: {e}")

async def load_expected(base_dir, test_file):
    file_path = os.path.join(base_dir, test_file)
    expected_values = pd.read_excel(file_path, sheet_name='Expected_Values', index_col=0)
    expected_weights = pd.read_excel(file_path, sheet_name='Expected_Weights', header=[0, 1], index_col=0).astype(float)
    expected_weights.index.name = 'Date'
    expected_stats = pd.read_excel(file_path, sheet_name='Expected_Stats', index_col=0)
    stats_numeric_cols = expected_stats.select_dtypes(include=['number']).columns
    expected_stats[stats_numeric_cols] = expected_stats[stats_numeric_cols].astype(float)
    return expected_values, expected_weights, expected_stats
