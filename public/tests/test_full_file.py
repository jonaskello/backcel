import pytest
import pandas as pd
from pathlib import Path
from public.src import data_load_main as dlm

# Identify all test workbooks
TEST_DATA_DIR = Path("public/tests/data")
excel_test_files = list(TEST_DATA_DIR.glob("test_*.xlsx"))

@pytest.mark.parametrize("test_file", excel_test_files)
async def test_full_engine_run(test_file):

    def on_progress(msg: str):
        print(msg)

    base_dir = "./public/tests/data"

    # 1. Load settings from the test file itself
    # Note: load_settings uses test_file as the default container
    data_load_result = await dlm.data_load_all(base_dir, on_progress, test_file)

    print("Result", data_load_result)    

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
