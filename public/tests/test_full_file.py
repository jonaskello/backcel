import traceback
import pytest
import os
import pandas as pd
from public.src.result import Err, Ok
from pathlib import Path
from public.src import data_load_main as dlm
from public.src import backtest as bn

# Identify all test workbooks
CURRENT_DIR = Path(__file__).parent
TEST_DATA_DIR = CURRENT_DIR / "data"
excel_test_files = list(TEST_DATA_DIR.glob("test_*.xlsx"))

@pytest.mark.asyncio
@pytest.mark.parametrize("test_file", excel_test_files)
async def test_full_engine_run(test_file):

    async def on_progress(msg: str):
        print(msg)

    base_dir = "./public/tests/data"
    data_load_result = await dlm.data_load_all(base_dir, on_progress, test_file)
    expected_portfolio_values, expected_portfolio_weights = await load_expected(base_dir, test_file)
    print("expected_portfolio_weights",expected_portfolio_weights.columns)
    match data_load_result:
        case Ok(data):
            portfolio_df, asset_prices_available, assets_meta_df = data
            backtest_result = bn.run_backtest_all(assets_meta_df, asset_prices_available, portfolio_df)
            match backtest_result:
                case Ok(data):
                    # Calculate cumulative growth (1.0 basis)
                    portfolio_values = (1 + data.combined_returns).cumprod()
                    # print("portfolio_values", portfolio_values)
                    # print("Results", data)
                    print("portfolio_values.columns", portfolio_values.columns)
                    print("expected_portfolio_values.columns", expected_portfolio_values.columns)
                    # Compare your backtest result to the 'Expected' sheet
                    pd.testing.assert_frame_equal(portfolio_values, expected_portfolio_values)

                    for p_name, p_result in data.portfolios.items():
                        # expected_weights_df has MultiIndex columns (Portfolio, Asset)
                        expected_p_weights = expected_portfolio_weights[[p_name]]
                        expected_p_weights = expected_portfolio_weights[[p_name]].droplevel(0, axis=1)
                        pd.testing.assert_frame_equal(
                            p_result.weights, 
                            expected_p_weights, 
                            obj=f"Weights Mismatch for Portfolio: {p_name}",
                            atol=1e-5
                        )

                case Err(e):
                    print(f"Error: {e}")
                    traceback.print_exception(e)
        case Err(e):
            print(f"Error: {e}")

async def load_expected(base_dir, test_file):
    file_path = os.path.join(base_dir, test_file)
    expected_portfolio_values = pd.read_excel(file_path, sheet_name='Expected_Portfolio_Values', index_col=0)
    expected_portfolio_weights = pd.read_excel(file_path, sheet_name='Expected_Portfolio_Weights', header=[0, 1], index_col=0)
    expected_portfolio_weights.index.name = 'Date'
    return expected_portfolio_values, expected_portfolio_weights
