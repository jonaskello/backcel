from datetime import date

import pandas as pd

from public.src import data_clean as dc
from public.src.monitor import monitor


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


def test_backfill_with_proxies_logs_proxy_chain():
    monitor.clear()
    index = pd.to_datetime(["2020-01-01", "2020-01-02", "2020-01-03"])
    asset_prices = pd.DataFrame(
        {
            "REAL": [None, None, 100.0],
            "PROXY1": [None, 50.0, 55.0],
            "PROXY2": [20.0, 21.0, 22.0],
        },
        index=index,
    )
    assets_meta_df = pd.DataFrame(
        {
            "proxy": {
                "REAL": "PROXY1",
                "PROXY1": "PROXY2",
                "PROXY2": "",
            }
        }
    )

    dc.backfill_with_proxies(asset_prices, assets_meta_df)

    assert "INFO: Proxy chain: REAL -> PROXY1 -> PROXY2" in monitor.messages


def test_format_proxy_chain_marks_cycles():
    assets_meta_df = pd.DataFrame({"proxy": {"A": "B", "B": "A"}})

    assert dc.format_proxy_chain("A", assets_meta_df) == "A -> B -> A (cycle)"
