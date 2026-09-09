"""Dataset upload validation for the CT DRL System."""

import pandas as pd

REQUIRED_COLUMNS = ['Gender', 'Age', 'Region', 'KVP', 'mAs', 'CTDIvol', 'DLP', 'Patient ID']
NUMERIC_COLUMNS = ['Age', 'KVP', 'mAs', 'CTDIvol', 'DLP']
VALID_REGIONS = {'brain', 'chest', 'abd', 'abdomen'}


def validate_extension(filename: str):
    """Returns (is_valid, error_message)."""
    if not filename or not filename.lower().endswith('.xlsx'):
        return False, "Invalid file type. Please upload an Excel (.xlsx) file only."
    return True, ""


def validate_dataframe(df: pd.DataFrame) -> dict:
    """
    Validates an uploaded CT dataset against the required schema.

    Returns:
        {
            'is_valid': bool,
            'errors': [str, ...],
            'warnings': [str, ...],
        }
    """
    errors = []
    warnings = []

    if df is None or df.empty:
        return {'is_valid': False, 'errors': ["The uploaded file is empty or could not be read."], 'warnings': []}

    missing_cols = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing_cols:
        errors.append(
            "Missing required column(s): " + ", ".join(missing_cols) +
            ". The dataset must contain exactly these columns: " + ", ".join(REQUIRED_COLUMNS)
        )
        return {'is_valid': False, 'errors': errors, 'warnings': warnings}

    # Missing values
    for col in REQUIRED_COLUMNS:
        n_missing = int(df[col].isna().sum())
        if n_missing > 0:
            errors.append(f"Column '{col}' has {n_missing} missing value(s). Please complete or remove these rows.")

    # Numeric validation
    for col in NUMERIC_COLUMNS:
        coerced = pd.to_numeric(df[col], errors='coerce')
        non_numeric = coerced.isna() & df[col].notna()
        n_bad = int(non_numeric.sum())
        if n_bad > 0:
            errors.append(f"Column '{col}' contains {n_bad} non-numeric value(s).")

    # Negative values
    for col in NUMERIC_COLUMNS:
        coerced = pd.to_numeric(df[col], errors='coerce')
        n_negative = int((coerced < 0).sum())
        if n_negative > 0:
            errors.append(f"Column '{col}' contains {n_negative} negative value(s), which is not physically valid.")

    # Region validity (warning only - unsupported regions are excluded from DRL analysis, not fatal)
    region_lower = df['Region'].astype(str).str.strip().str.lower()
    unknown_mask = ~region_lower.isin(VALID_REGIONS)
    if unknown_mask.sum() > 0:
        bad_values = sorted(df.loc[unknown_mask, 'Region'].astype(str).unique().tolist())
        warnings.append(
            f"{int(unknown_mask.sum())} row(s) have a Region value outside the supported set "
            f"(Brain, Chest, Abdomen): {', '.join(bad_values)}. These rows will be excluded from DRL analysis."
        )

    is_valid = len(errors) == 0
    return {'is_valid': is_valid, 'errors': errors, 'warnings': warnings}