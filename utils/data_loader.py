"""Excel dataset loading utilities."""

import pandas as pd


def load_excel_file(uploaded_file):
    """Reads a Streamlit-uploaded .xlsx file into a DataFrame.

    Returns (df, error_message). df is None if reading failed.
    """
    try:
        df = pd.read_excel(uploaded_file)
    except Exception as exc:
        return None, f"Could not read the Excel file. Details: {exc}"

    if df is None or df.shape[0] == 0:
        return None, "The uploaded file contains no data rows."

    return df, ""


def load_dataset_from_path(path: str) -> pd.DataFrame:
    """Loads a dataset from a local .xlsx path (used for the synthetic demo dataset)."""
    return pd.read_excel(path)