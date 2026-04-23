import pandas as pd

class DataFileValidationError(Exception):
    def __init__(self, errors: list[str], filename: str):
        self.errors = errors
        self.filename = filename
        # Initialize parent with a summary string
        super().__init__(f"Validation failed for {filename}: {len(errors)} errors found.")

def validate_settings(df: pd.DataFrame, filename: str):
    if 'Name' not in df.columns:
        raise DataFileValidationError([f"Column **'Name'** is missing from the sheet."], filename)
    if 'Value' not in df.columns:
        raise DataFileValidationError([f"Column **'Value'** is missing from the sheet."], filename)

    required = {'currency', 'start', 'end'}
    allowed = required | {'portfolios', 'assets'}
    
    names = df['Name'].dropna().astype(str)
    existing = set(names[~names.str.startswith('_')])

    errors = []
    if missing := (required - existing):
        errors.append(f"Missing required rows: **{', '.join(sorted(missing))}**")
    
    if invalid := [n for n in existing if n not in allowed]:
        errors.append(f"Invalid row names: `{', '.join(sorted(invalid))}`")

    if errors:
        raise DataFileValidationError(errors, filename)