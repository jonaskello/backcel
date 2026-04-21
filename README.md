# 📊 Backcel

**The Private, Browser-Native Portfolio Backtester.**

`Backcel` is a backtesting engine built with **Marimo** and **WebAssembly (WASM)**. It allows you to run complex portfolio simulations directly in your browser using local Excel files—**no data ever leaves your machine.**

> [!CAUTION]
> **Experimental Version**: This project is currently in an early experimental stage. Features may change rapidly, and you may encounter bugs. It is provided "as-is" for testing and feedback.
---

### ✨ Key Features

* **🔒 100% Client-Side Privacy**: Built with WASM, the app runs entirely in your browser. Your financial data is processed locally and never uploaded to a server.
* **📂 Excel-Driven Workflow**: Seamlessly use your existing `.xlsx` files for portfolios and assets data.
* **🌍 Multi-Currency Support**: Automatic currency conversion for global portfolio analysis.
* **📈 Proxy Data Integration**: Fill historical gaps with proxy asset data to ensure robust long-term backtests.
* **🚀 Zero Installation**: Starts from a static web page. No Python environment or complex setup required for the end-user.
* **🔓 Open Source**: Transparent and community-driven. Audit the code or customize the logic to fit your specific needs.

---

### 🚀 Quick Start

1. **Launch the App**: Open the hosted [WASM application](https://jonaskello.github.io/backcel/) in a **Chromium-based browser** (such as Google Chrome, Microsoft Edge, Brave, or Opera, needed for local folders feature).
2. **Mount Your Data**: Click the **📁 Mount Folder** button to grant the app secure access to your local Excel directory.
3. **Provide Files**: If you mounted an empty dir, press the **⬇️ Download Example Files** to fill your dir with example files.
4. **Run Backtest**: Click the **🚀 Run Backtest** button and watch the results generate in real-time.

---

### 📝 Data Requirements

To run a backtest, you must provide at least one Excel file named `main.xlsx` within your mounted folder. That file **must** contain a sheet named `main`, which acts as the configuration hub for all your backtest settings.

* **Quick Start**: The easiest way to get started is to mount an empty folder and click **📥 Download example files**. This will populate your folder with a valid template.
* **Custom Data**: For detailed information about the required columns, date formats, and portfolio definitions, see the [**Data Documentation (DATA.md)**](DATA.md).

---

### ⚠️ Disclaimer

**Not Financial Advice**: `Backcel` is an educational and analytical tool for historical backtesting purposes only. It does not provide investment advice, and the results generated do not guarantee future performance. Always consult with a qualified financial professional before making investment decisions. Use this software at your own risk.

---

### 🛠 Tech Stack

* **[Marimo](https://marimo.io/)**: For the reactive, notebook-based UI.
* **[Pyodide](https://pyodide.org/)**: To execute Python at near-native speeds in the browser via WASM.
* **[Anywidget](https://anywidget.dev/)**: For specialized browser-native components.

---

### 💻 Developer Setup

If you want to contribute or run the development environment locally using `uv`:

```bash
# Clone the repository
git clone [https://github.com/your-username/backcel.git](https://github.com/your-username/backcel.git)
cd backcel

# Sync dependencies and run the marimo editor
uv sync
uv run marimo edit main.py