# 📊 Data Documentation: Backcel

This guide explains how to structure your Excel files for successful backtests. 

---

## 🏗 Document Hierarchy
The engine follows a **"Hub and Spoke"** model, where `main.xlsx` serves as the central hub connecting all data sources.

### 📄 Sheet Classifications
The system utilizes four distinct types of Excel sheets to execute the backtest:

* **Main:** This sheet is the global settings for the backtest such as start and end date. It also points to all other sheets.
* **Asset Registry:** This type of sheet holds information about assets such as ID and name, and points to prices for each asset.
* **Asset Prices:** This type of sheet holds time-series pricing data for the assets.
* **Portfolio Definitions:** This type of sheet defines the weights and rebalancing for portfolios to backtest..

---

## 🛠 1. The `main.xlsx` File
This is the **Required** entry point. It must contain a sheet named `Main`.

Use this sheet to define global parameters using a **Name** and **Value** column.

| Name | Value | Description |
| :--- | :--- | :--- |
| **Currency** | `SEK` | The base currency for all final reports. |
| **Start** | `2012-05-12` | The starting date for the simulation. |
| **End** | `2015-07-23` | The ending date for the simulation. |
| **Portfolios**| `Portfolios.xlsx!Tech_Stocks` | Sheet name or `Filename!Sheetname` for weights, eg. `Tech_Stocks` or `Portfolios.xlsx!Tech_Stocks`. (Repeatable). |
| **Assets** | `Assets.xlsx!Stocks` | Sheet name or `Filename!Sheetname` for asset metadata/prices, eg. `Stocks` or `Assets.xlsx!Stocks `. (Repeatable). |
| **borrow_rate_asset** | `BORROW_RATE` | Asset ID for the annualized borrowing rate series used by leveraged portfolios. Required if any portfolio has `__leverage` above `1.0`. Values should be percent points, so `1.9` means 1.9%. |
| **borrow_rate_premium** | `1.5` | Optional annualized premium added to the borrowing rate, where `1.5` means 1.5%. Defaults to `0`. |

> [!TIP] 
> Setting names starting with underscore (`_`) will be ignored. This can be used to disable settings without removing them.

---

## 📂 2. Assets Registry

These are the sheets referenced by the `Assets` setting in the `Main` sheet. They define the main information about the assets, and points to where the prices for each asset is located.

### Asset sheet Columns
| Column | Requirement | Description |
| :--- | :--- | :--- |
| **ID** | **Required** | Unique identifier (Ticker/ISIN) used in portfolio sheets. |
| **Name** | **Required** | Display name for charts and tables. |
| **Currency** | *Optional* | Currency prices are quoted in (e.g., `USD`). Defaults to base currency from settings. |
| **Prices** | *Optional* | Sheet name or `Filename!Sheetname` for location of prices, eg. `Stock_Prices` or `Myfile.xlsx!Stock_Prices `. Defaults to `Prices`. |
| **Proxy** | *Optional* | Asset ID to use if this asset's history is missing. |
| **StdDev** | *Optional* | Standard Deviation, used for some rebalancing types. Defaults to 10% |

> [!TIP] 
> * **Custom Organization & Metadata**: 
> * **Extra Columns**: Any columns not listed above are ignored by the engine. You can freely store extra data like **Sector**, **Asset Class**, or **Notes** in the same table.
> * **Organization Rows**: Any rows where the **ID** column is left empty will be ignored. This allows you to insert blank rows or descriptive "category headings" (e.g., "--- EQUITIES ---") to keep your asset list organized and readable within Excel.

> [!NOTE]
> **Currencies as Assets**: To enable multi-currency backtesting, treat exchange rates (e.g., `USD`, `EUR`) exactly like assets. Provide their history relative to your base currency.

---

## 📈 3. Asset Prices
These are the sheets referenced by the `Prices` setting in your asset registry sheets. They store the time-series data.

### Sheet Structure

There are two different formats supported. Either column formatted or row formatted. If the first cell contains `ID` then row formatted is assumed, otherwise column formatted.

#### Column formatted

* **Date**: The first column must contain the price dates.
* **[Asset ID]**: Subsequent column headers must match the **IDs** defined in the registry.

| Date       | AAPL   | MSFT   | USD   |
| :--------- | -----: | -----: | ----: |
| 2023-01-01 | 150.25 | 240.10 | 10.45 |
| 2023-01-02 | 152.10 | 242.50 | 10.48 |

#### Row formatted

| ID   | Date       | Price  |
| :--- | :--------- | ----:  |
| AAPL | 2023-01-01 | 150.25 |
| AAPL | 2023-01-02 | 151.25 |
| MSFT | 2023-01-01 | 240.10 |
| MSFT | 2023-01-02 | 242.50 |
| USD  | 2023-01-01 | 10.45  |
| USD  | 2023-01-02 | 10.48 |


> [!TIP]
> **Populate Data Automatically**: You can use Excel's built-in `=STOCKHISTORY()` function to fetch historical data directly into your sheets. 
> 
> For example: `=STOCKHISTORY("AAPL", "2023-01-01", "2023-12-31", 0, 1, 0, 1)`
> 
> Since Excel saves the last fetched values directly in the file, the backtester can read these results as normal data. This allows you to keep your formulas active so you can easily update your backtest range or assets later.

---

## 💼 4. Portfolio Definitions

These are the sheets referenced by the `Portfolios` setting in your `main.xlsx`. They define the specific weights and allocations for your simulation.

### Sheet Structure
| Column | Requirement | Description |
| :--- | :--- | :--- |
| **ID** | **Required** | Asset ID (must match the Registry) or a **Special Setting ID**. |
| **[Portfolio Name]** | **Required** | The column header is the strategy name. Values should be decimals (e.g., `0.5`) or percentages (`50%`). |

---

### ⚙️ Rebalancing Settings
Use these **Special ID Rows** to control how allocations are maintained. Settings are per-column; missing or invalid values use defaults.

#### 1. Evaluation Schedule (`__check`)
Determines how often the engine checks whether portfolio maintenance actions should run.
* **Options:** `once` (Default), `daily`, `weekly`, `monthly`, `quarterly`, `half-year`, `yearly`.

#### 2. Execution Logic (`__rb_type`)
Determines how trades are triggered and sized.

* **`full`** – (Default) **Total Realignment**: Every check, all assets are traded back to their exact target weights.
* **`sigma`** – **Volatility-Based**: Triggered only when an asset drifts beyond its annual $StdDev$ (defined in the Asset Registry). It rebalances outliers back to within a $0.5 \times StdDev$ target buffer.

---

### 📝 Example Layout
| ID | _Name | Aggressive | Balanced |
| :--- | :--- | :--- | :--- |
| **__check** | | monthly | daily |
| **__rb_type** | | full | sigma |
| **__rb_trigger_down** | | | 1.5 |
| **__rb_trigger_up** | | | 2.5 |
| **__leverage** | | 1.25 | 1.00 |
| **AAPL** | Apple Inc. | 0.60 | 0.40 |
| **GLD** | SPDR Gold | 0.40 | 0.60 |
| **__rb_trigger_up:GLD** | | | 3.0 |

> [!TIP]
> **Organization**: Some tips for the portfolio sheet. 
>
> * **Ignore with Underscores**: Any column name starting with an underscore (e.g., `_Metadata`, `_ISIN`, `_Comments`) will be ignored by the engine. This is perfect for adding descriptive asset names or temporary notes without breaking the simulation.
> * **Disabling Portfolios**: If you want to temporarily hide a portfolio from the backtest without deleting the data, simply rename the header to start with an underscore (e.g., `_Aggressive_Strategy`).
> * **Organization Rows**: Any row where the **ID** cell is empty will be skipped. Use this to create visual headers like "--- Emerging Markets ---" to keep your allocation tables tidy.
> * **100% Allocation**: For the backtest to run correctly, the sum of values in a portfolio column should total **100%** (1.0).

#### 3. Sigma Trigger Multipliers (`__rb_trigger_down`, `__rb_trigger_up`)
Controls how far a `sigma` portfolio can drift before rebalancing.
* Missing or blank values default to `1.0`.
* `__rb_trigger_down = 1.5` means an underweight asset triggers when drift is more than $1.5 \times StdDev$ below target.
* `__rb_trigger_up = 2.5` means an overweight asset triggers when drift is more than $2.5 \times StdDev$ above target.
* Asset-specific overrides can be added with `__rb_trigger_down:ASSET_ID` and `__rb_trigger_up:ASSET_ID`.

#### 4. Leverage (`__leverage`)
Sets target gross exposure for a portfolio.
* Missing or blank values default to `1.0`.
* `1.25` means the portfolio targets 125% exposure and borrows 25% of equity.
* Leverage is adjusted on the same schedule as `__check`. If losses push actual leverage above the target, the engine does not force selling just to reduce leverage. If gains push actual leverage below the target, the engine tops back up on the next scheduled check date.
* Borrowing cost is calculated from the `borrow_rate_asset` annualized percent-point rate plus `borrow_rate_premium`.

