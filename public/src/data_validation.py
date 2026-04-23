import pandas as pd

class DataFileValidationError(Exception):
    def __init__(self, errors: list[str], filename: str):
        self.errors = errors
        self.filename = filename
        # Initialize parent with a summary string
        super().__init__(f"Validation failed for {filename}: {len(errors)} errors found.")

def validate_settings(df: pd.DataFrame, filename: str):
    if 'Name' not in df.columns:
        raise DataFileValidationError([f"Column **'Name'** is missing."], filename)
    if 'Value' not in df.columns:
        raise DataFileValidationError([f"Column **'Value'** is missing."], filename)

    required = {'currency', 'start', 'end'}
    single_only = required # These must appear exactly once
    allowed = required | {'portfolios', 'assets'}
    
    # Extract names, ignore nulls and comments
    names_series = df['Name'].dropna().astype(str)
    names_series = names_series[~names_series.str.startswith('_')]
    existing = set(names_series)

    errors = []

    # 1. Check Missing
    if missing := (required - existing):
        errors.append(f"Missing required rows: **{', '.join(sorted(missing))}**")
    
    # 2. Check Invalid
    if invalid := [n for n in existing if n not in allowed]:
        errors.append(f"Invalid row names: `{', '.join(sorted(invalid))}`")

    # 3. Check for Duplicates (Only for currency, start, end)
    counts = names_series.value_counts()
    duplicates = [n for n in single_only if counts.get(n, 0) > 1]
    if duplicates:
        errors.append(f"Duplicate rows found for: **{', '.join(sorted(duplicates))}** (must only appear once)")

    if errors:
        raise DataFileValidationError(errors, filename)

def validate_assets_meta(df: pd.DataFrame, filename: str):
    errors = []
    
    # 1. Check Index (ID)
    if df.index.name != "ID":
        errors.append("Missing index column **'ID'**.")
    
    # Check for empty IDs (though they should be filtered before calling this)
    if any(df.index.isna()):
        errors.append("Found rows with **empty IDs**.")

    # 2. Check Required Columns (Case-insensitive check)
    required = {'name'} # Based on your code's required_cols
    existing_cols = set(df.columns)
    if missing := (required - existing_cols):
        errors.append(f"Missing required columns: **{', '.join(sorted(missing))}**")

    # 3. Global ID Uniqueness
    if df.index.duplicated().any():
        dupes = df.index[df.index.duplicated()].unique().tolist()
        errors.append(f"Duplicate IDs found: `{', '.join(map(str, dupes))}`")

    # 4. Proxy Integrity
    if 'proxy' in df.columns:
        # Get unique proxies that aren't empty/null
        proxies_used = {p for p in df['proxy'].dropna().unique() if str(p).strip() != ""}
        # Compare against the ID index
        invalid_proxies = proxies_used - set(df.index)
        if invalid_proxies:
            errors.append(f"Proxies defined but not found in ID column: `{', '.join(map(str, invalid_proxies))}`")

    if errors:
        raise DataFileValidationError(errors, filename)
