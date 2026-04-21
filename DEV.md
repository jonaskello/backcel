# How to publish

Publish the marimo notebook:

```bash
# First build the wheel for the local files (workaround becuase marimo cannot load local files, only packages)
uv build public/
# Export marimo as wasm
uv run marimo export html-wasm backtest_native.py -o publish/index.html --no-sandbox --force
uv run marimo export html-wasm button_test3.py -o publish/index.html --no-sandbox --force
uv run marimo export html-wasm local_files_test.py -o publish/index.html --no-sandbox --force
```

# How to run published

Must use static web server (run this command from repo root):

uv run python -m http.server 8000 --directory publish

# How to add deps

uv add --script backtest_native.py quantstats