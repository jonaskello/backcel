import pandas as pd
import logging

logger = logging.getLogger(__name__)

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

def validate_assets_meta(meta_map: dict[str, pd.DataFrame]):
    errors = []
    required = {'name'}
    
    # 1. Local Validation (Per File)
    for fname, df in meta_map.items():
        # Check Columns
        missing = required - set(df.columns)
        if missing:
            errors.append(f"[{fname}] Missing columns: `{', '.join(missing)}`.")
        
        # Check for local duplicates within the same file
        if df.index.duplicated().any():
            dupes = df.index[df.index.duplicated()].unique().tolist()
            errors.append(f"[{fname}] Internal duplicate IDs: `{', '.join(map(str, dupes))}`.")

    # 2. Global Validation (Across all files)
    all_ids = []
    for fname, df in meta_map.items():
        all_ids.extend([(idx, fname) for idx in df.index])
    
    # Convert to a temp DF for easy grouping of global duplicates
    global_id_df = pd.DataFrame(all_ids, columns=['ID', 'Source'])
    dupes_mask = global_id_df['ID'].duplicated(keep=False)
    
    if dupes_mask.any():
        for name, group in global_id_df[dupes_mask].groupby('ID'):
            sources = group['Source'].unique()
            if len(sources) > 1:
                errors.append(f"Global duplicate ID **{name}** found across: `{', '.join(sources)}`.")

    # 3. Proxy Validation (Cross-reference)
    # Flatten all IDs into a set for fast lookup
    valid_ids = {item[0] for item in all_ids}
    for fname, df in meta_map.items():
        if 'proxy' in df.columns:
            # Check only non-empty proxy cells
            proxies = df['proxy'].replace("", pd.NA).dropna()
            for asset_id, p in proxies.items():
                if p not in valid_ids:
                    errors.append(f"[{fname}] Asset **{asset_id}** uses non-existent proxy **{p}**.")

    if errors:
        raise DataFileValidationError(errors, "Asset Files")

def validate_asset_prices(df: pd.DataFrame, file_name: str, sheet_name: str, needed_ids: list):
    errors = []
    context = f"{file_name}!{sheet_name}"

    missing = [id for id in needed_ids if id not in df.columns]
    if missing:
        errors.append(f"Missing IDs: `{', '.join(missing)}`.")

    if not pd.api.types.is_datetime64_any_dtype(df.index):
        errors.append(f"First column must contain valid dates.")

    for col in df.columns:
        if not pd.api.types.is_numeric_dtype(df[col]):
            errors.append(f"Column **'{col}'** contains non-numeric values.")

    if df.index.duplicated().any():
        dupe_series = pd.to_datetime(df.index[df.index.duplicated()].unique())
        dupes = dupe_series.strftime('%Y-%m-%d').tolist()
        errors.append(f"Duplicate dates: `{', '.join(dupes)}`.")

    if errors:
        logger.warning("context "+context)
        raise DataFileValidationError(errors, context)
    
def validate_portfolios(portfolios_map: dict[str, pd.DataFrame]):
    errors = []
    all_portfolio_names = []
    SPECIAL_IDS = ["__rb_check", "__rb_type"]

    for context, df in portfolios_map.items():
        # 1. Index Check (NaN IDs)
        if df.index.hasnans:
            errors.append(f"[{context}] Index (ID) contains NaN values.")

        # 2. Portfolio Column Validation
        for col in df.columns:
            # Drop special config rows for weight validation
            asset_weights = df[col].drop(labels=[idx for idx in SPECIAL_IDS if idx in df.index], errors='ignore')
            
            # Convert to numeric
            numeric_weights = pd.to_numeric(asset_weights, errors='coerce')
            
            # Identify values that are NOT NaN in Excel but failed conversion
            invalid_mask = numeric_weights.isna() & asset_weights.notna()
            invalid_series = asset_weights[invalid_mask]

            if not invalid_series.empty:
                errors.append(f"[{context}] Portfolio **'{col}'** contains an invalid value: `{invalid_series.iloc[0]}`.")
                continue

            # If the whole column is essentially empty/NaN after dropping special IDs
            if asset_weights.isna().all():
                errors.append(f"[{context}] Portfolio **'{col}'** has no weights defined.")
                continue

            # 3. Sum to 1.0/100% Check
            col_sum = numeric_weights.sum()
            if not (0.99 <= col_sum <= 1.01 or 99 <= col_sum <= 101):
                errors.append(f"[{context}] Portfolio **'{col}'** weights sum to {col_sum}, not 1.0 or 100%.")
            
            all_portfolio_names.append((col, context))

    # 4. Global Duplicate Check
    name_df = pd.DataFrame(all_portfolio_names, columns=['Name', 'Source'])
    dupes = name_df[name_df['Name'].duplicated(keep=False)]
    if not dupes.empty:
        for name, group in dupes.groupby('Name', sort=False):
            sources = group['Source'].unique()
            errors.append(f"Duplicate portfolio name **'{name}'** found in multiple locations: `{', '.join(sources)}`.")

    if errors:
        raise DataFileValidationError(errors, "Portfolios")
