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
* **Date**: The first column must contain the price dates.
* **[Asset ID]**: Subsequent column headers must match the **IDs** defined in the registry.

| Date | AAPL | MSFT | USD |
| :--- | :--- | :--- | :--- |
| 2023-01-01 | 150.25 | 240.10 | 10.45 |
| 2023-01-02 | 152.10 | 242.50 | 10.48 |

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

#### 1. Evaluation Schedule (`__rb_check`)
Determines how often the engine checks for portfolio drift.
* **Options:** `once` (Default), `daily`, `weekly`, `monthly`, `quarterly`, `half-year`, `yearly`.

#### 2. Execution Logic (`__rb_type`)
Determines how trades are triggered and sized.

* **`full`** – (Default) **Total Realignment**: Every check, all assets are traded back to their exact target weights.
* **`sigma`** – **Volatility-Based**: Triggered only when an asset drifts beyond its annual $StdDev$ (defined in the Asset Registry). It rebalances outliers back to within a $0.5 \times StdDev$ target buffer.

---

### 📝 Example Layout
| ID | _Name | Aggressive | Balanced |
| :--- | :--- | :--- | :--- |
| **__rb_check** | | monthly | daily |
| **__rb_type** | | full | sigma |
| **AAPL** | Apple Inc. | 0.60 | 0.40 |
| **GLD** | SPDR Gold | 0.40 | 0.60 |

> [!TIP]
> **Organization**: Some tips for the portfolio sheet. 
>
> * **Ignore with Underscores**: Any column name starting with an underscore (e.g., `_Metadata`, `_ISIN`, `_Comments`) will be ignored by the engine. This is perfect for adding descriptive asset names or temporary notes without breaking the simulation.
> * **Disabling Portfolios**: If you want to temporarily hide a portfolio from the backtest without deleting the data, simply rename the header to start with an underscore (e.g., `_Aggressive_Strategy`).
> * **Organization Rows**: Any row where the **ID** cell is empty will be skipped. Use this to create visual headers like "--- Emerging Markets ---" to keep your allocation tables tidy.
> * **100% Allocation**: For the backtest to run correctly, the sum of values in a portfolio column should total **100%** (1.0).

