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