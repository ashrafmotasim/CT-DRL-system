"""Descriptive statistics and supplementary outlier detection.

The descriptive statistics here (mean, median, min, max, std, variance,
percentiles) are standard pandas/NumPy statistics applied to the notebook's
own output columns (CTDIvol, DLP, EffectiveDose_mSv) - they do not alter or
replace anything computed in utils/calculations.py.

detect_outliers_iqr() is a SUPPLEMENTARY method: the source notebook does
not perform outlier detection. A standard 1.5x-IQR rule is used here and is
always labeled as an added statistical tool in the UI and reports.

ADDED (Statistical Analysis update):
    selected_region_statistics()  region-restricted table limited to
                                  count / median / min / max / p25 / p50 /
                                  p75 / p100.
    dispersion_by_region()        std + var per region, for the new STD/VAR
                                  visualizations.
    pair_correlation()            Pearson r for exactly two chosen metrics.
The original descriptive_stats() and region_statistics() are UNCHANGED and
are still used by the Excel export, so exports keep their existing columns.
"""

import pandas as pd

from .calculations import REGION_ORDER, REGION_DISPLAY_NAMES


def descriptive_stats(series: pd.Series) -> dict:
    series = pd.to_numeric(series, errors='coerce').dropna()
    if series.empty:
        return {}
    return {
        'count': int(series.count()),
        'mean': series.mean(),
        'median': series.median(),
        'min': series.min(),
        'max': series.max(),
        'std': series.std(),
        'var': series.var(),
        'p25': series.quantile(0.25),
        'p75': series.quantile(0.75),
        'p90': series.quantile(0.90),
        'p95': series.quantile(0.95),
    }


def region_statistics(df: pd.DataFrame, column: str) -> pd.DataFrame:
    """Per-region descriptive statistics table for a single numeric column."""
    rows = []
    for region in REGION_ORDER:
        subset = df[df['Region_Key'] == region]
        if subset.empty:
            continue
        stats = descriptive_stats(subset[column])
        if not stats:
            continue
        stats['Region'] = REGION_DISPLAY_NAMES[region]
        rows.append(stats)
    if not rows:
        return pd.DataFrame()
    out = pd.DataFrame(rows).set_index('Region')
    return out[['count', 'mean', 'median', 'min', 'max', 'std', 'var', 'p25', 'p75', 'p90', 'p95']]


# ---------------------------------------------------------------------------
# ADDED: region-restricted statistics for the Statistical Analysis page.
# ---------------------------------------------------------------------------
REGION_STATS_COLUMNS = ['count', 'median', 'min', 'max', 'p25', 'p50', 'p75', 'p100']


def percentile_stats(series: pd.Series) -> dict:
    """Only the columns requested for the Region-Based Statistics table."""
    series = pd.to_numeric(series, errors='coerce').dropna()
    if series.empty:
        return {}
    return {
        'count': int(series.count()),
        'median': series.median(),
        'min': series.min(),
        'max': series.max(),
        'p25': series.quantile(0.25),
        'p50': series.quantile(0.50),
        'p75': series.quantile(0.75),
        'p100': series.quantile(1.00),
    }


def selected_region_statistics(df: pd.DataFrame, column: str, region_key: str) -> pd.DataFrame:
    """Region-Based Statistics for ONE selected region only.

    Every value is computed from the rows of that region alone.
    """
    subset = df[df['Region_Key'] == region_key]
    stats = percentile_stats(subset[column]) if not subset.empty else {}
    if not stats:
        return pd.DataFrame()
    stats['Region'] = REGION_DISPLAY_NAMES.get(region_key, str(region_key).capitalize())
    out = pd.DataFrame([stats]).set_index('Region')
    return out[REGION_STATS_COLUMNS]


def dispersion_by_region(df: pd.DataFrame, column: str) -> pd.DataFrame:
    """Standard deviation and variance per region, used by the STD/VAR charts."""
    rows = []
    for region in REGION_ORDER:
        subset = pd.to_numeric(df.loc[df['Region_Key'] == region, column], errors='coerce').dropna()
        if subset.empty:
            continue
        rows.append({
            'Region': REGION_DISPLAY_NAMES[region],
            'Region_Key': region,
            'std': float(subset.std()),
            'var': float(subset.var()),
        })
    return pd.DataFrame(rows)


def pair_correlation(df: pd.DataFrame, x_col: str, y_col: str) -> float:
    """Pearson correlation for EXACTLY the two selected metrics.

    Returns float('nan') when either column is missing or has too few
    usable values.
    """
    if x_col not in df.columns or y_col not in df.columns:
        return float('nan')
    pair = pd.DataFrame({
        'x': pd.to_numeric(df[x_col], errors='coerce'),
        'y': pd.to_numeric(df[y_col], errors='coerce'),
    }).dropna()
    if len(pair) < 3:
        return float('nan')
    return float(pair['x'].corr(pair['y']))


def correlation_strength(r: float) -> str:
    """Plain-language reading of a Pearson coefficient (display only)."""
    if r != r:  # NaN check
        return "Not enough data"
    a = abs(r)
    direction = "positive" if r >= 0 else "negative"
    if a < 0.10:
        return "Negligible correlation"
    if a < 0.30:
        return f"Weak {direction} correlation"
    if a < 0.50:
        return f"Moderate {direction} correlation"
    if a < 0.70:
        return f"Strong {direction} correlation"
    return f"Very strong {direction} correlation"


def detect_outliers_iqr(df: pd.DataFrame, column: str) -> pd.DataFrame:
    """
    Supplementary outlier detection (NOT part of the source notebook).
    Standard 1.5x-IQR rule, applied per region so each protocol is judged
    against its own dose distribution.
    """
    df = df.copy()
    outlier_col = f'{column}_Outlier'
    df[outlier_col] = False

    for region in REGION_ORDER:
        mask = df['Region_Key'] == region
        subset = pd.to_numeric(df.loc[mask, column], errors='coerce').dropna()
        if len(subset) < 4:
            continue
        q1, q3 = subset.quantile(0.25), subset.quantile(0.75)
        iqr = q3 - q1
        lower = q1 - 1.5 * iqr
        upper = q3 + 1.5 * iqr
        col_numeric = pd.to_numeric(df.loc[mask, column], errors='coerce')
        df.loc[mask, outlier_col] = (col_numeric < lower) | (col_numeric > upper)

    return df


def outlier_summary(df: pd.DataFrame, column: str) -> dict:
    df_flagged = detect_outliers_iqr(df, column)
    outlier_col = f'{column}_Outlier'
    n_outliers = int(df_flagged[outlier_col].sum())
    n_total = int(len(df_flagged))
    pct = (n_outliers / n_total * 100) if n_total else 0.0
    return {
        'n_outliers': n_outliers,
        'n_total': n_total,
        'pct_outliers': pct,
        'data': df_flagged,
    }