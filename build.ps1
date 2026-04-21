# First build the wheel for the local files (workaround becuase marimo cannot load local files, only packages)
uv build public/

# Export marimo as wasm
uv run marimo export html-wasm backtest_notebook.py -o publish/index.html --no-sandbox --force
