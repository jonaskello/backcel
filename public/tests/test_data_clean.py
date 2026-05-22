from datetime import date

import pandas as pd

from public.src import data_clean as dc


def test_adjust_asset_prices_ignores_proxy_columns_when_limiting():
    index = pd.to_datetime(["2020-01-01", "2020-01-02", "2020-01-03"])
    asset_prices = pd.DataFrame(
        {
            "REAL": [100.0, 101.0, 102.0],
            "PROXY": [None, 50.0, 51.0],
        },
        index=index,
    )
    assets_meta_df = pd.DataFrame(
        {
            "name": {
                "REAL": "Real Asset",
                "PROXY": "Proxy Asset",
            }
        }
    )

    adjusted = dc.adjust_asset_prices_start_to_available_data(
        assets_meta_df,
        asset_prices,
        date(2020, 1, 1),
        limiting_asset_ids=["REAL"],
    )

    pd.testing.assert_index_equal(adjusted.index, index)


def test_adjust_asset_prices_limits_on_requested_assets():
    index = pd.to_datetime(["2020-01-01", "2020-01-02", "2020-01-03"])
    asset_prices = pd.DataFrame(
        {
            "REAL": [None, 101.0, 102.0],
            "PROXY": [50.0, 51.0, 52.0],
        },
        index=index,
    )
    assets_meta_df = pd.DataFrame({"name": {"REAL": "Real Asset", "PROXY": "Proxy Asset"}})

    adjusted = dc.adjust_asset_prices_start_to_available_data(
        assets_meta_df,
        asset_prices,
        date(2020, 1, 1),
        limiting_asset_ids=["REAL"],
    )

    pd.testing.assert_index_equal(adjusted.index, index[1:])
