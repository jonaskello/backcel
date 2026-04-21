import traceback
import pytest
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
    match data_load_result:
        case Ok(data):
            portfolio_df, asset_prices_available, assets_meta_df = data
            backtest_result = bn.run_backtest_all(assets_meta_df, asset_prices_available, portfolio_df)
            match backtest_result:
                case Ok(data):
                    print("Results", data)
                case Err(e):
                    print(f"Error: {e}")
                    traceback.print_exception(e)
        case Err(e):
            print(f"Error: {e}")



    # # 2. Extract Data (Simplified for the example)
    # # This would call your actual engine: run_backtest(...)
    # # For now, we simulate the 'result'
    # asset_file, asset_sheet = asset_src[0]
    # actual_data = pd.read_excel(TEST_DATA_DIR / asset_file, sheet_name=asset_sheet)
    
    # # 3. Load 'Expected' sheet from the same file
    # expected_data = pd.read_excel(test_file, sheet_name='Expected')
    
    # # 4. Assert
    # # Compare your backtest result to the 'Expected' sheet
    # pd.testing.assert_frame_equal(actual_data, actual_data) # Replace with real results
