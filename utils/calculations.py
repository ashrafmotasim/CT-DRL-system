"""
Core scientific calculations for the CT DRL Evaluation System.

============================================================================
 SCIENTIFIC INTEGRITY NOTICE - READ BEFORE MODIFYING THIS FILE
============================================================================
Every equation, constant, and comparison rule below is copied EXACTLY from
the validated source notebook ("CT .ipynb"). Nothing has been simplified,
re-derived, or replaced. This module is the SINGLE SOURCE OF TRUTH used by
both app.py and notebook/CT_DRL_System.ipynb, which guarantees the web
application reproduces exactly the same outputs as the notebook.

The only two additions beyond the original notebook are clearly isolated
and documented in their own functions:

  1. flag_row_level_exceedances() - a per-examination DRL exceedance flag
     used purely for chart highlighting. The original notebook only
     evaluates the REGION MEDIAN against the DRL; it never flags
     individual rows. This function reuses the exact same DRL thresholds
     and the exact same ">" comparison operator used in the notebook,
     applied row-by-row instead of to the median, so dangerous individual
     exams are visible on charts without altering the notebook's approval
     methodology.

  2. detect_outliers_iqr() (in statistics.py) - the source notebook does
     not implement outlier detection. A standard 1.5x-IQR method has been
     added as a supplementary statistical tool and is always labeled as
     such in the UI and reports.

Everything else - STANDARDS values, the effective-dose formula
(E = DLP * k), the median evaluation, the approval-status logic, and the
effective-dose approval percentage - is an exact, unmodified port of the
notebook code (Cells 2 and 3).
============================================================================

INTERNATIONAL STANDARDS ADDITION
--------------------------------
INTERNATIONAL_STANDARDS (Japan, UK, EU, Australia) was added so the user can
optionally benchmark the same dataset against an international reference.
It is a SEPARATE dictionary: the Egyptian national STANDARDS dictionary
above it is completely untouched and remains the default used everywhere.
Every analysis function now accepts an optional `standards` argument that
defaults to None -> the Egyptian STANDARDS, so all pre-existing behaviour is
bit-for-bit identical when no country is chosen.
"""

import pandas as pd

# ---------------------------------------------------------------------------
# Exact copy of the `standards` dictionary from the notebook (Cell 2).
# DO NOT CHANGE THESE VALUES.
# ---------------------------------------------------------------------------
STANDARDS = {
    'brain': {'CTDIvol': 30, 'DLP': 1360, 'k': 0.0021, 'E_std': 2.86},
    'chest': {'CTDIvol': 22, 'DLP': 420, 'k': 0.0140, 'E_std': 5.88},
    'abd':   {'CTDIvol': 31, 'DLP': 1325, 'k': 0.0150, 'E_std': 19.88},
}

# ---------------------------------------------------------------------------
# ADDED: International DRL benchmarks (Japan, UK, EU, Australia).
# Values transcribed exactly from the project's international benchmark
# table. E_std = DLP * k for each region, matching the notebook's own
# effective-dose definition. The Egyptian STANDARDS above are NOT affected.
# ---------------------------------------------------------------------------
INTERNATIONAL_STANDARDS = {
    'Japan': {
        'brain': {'CTDIvol': 67.0, 'DLP': 1260.0, 'k': 0.0021, 'E_std': 2.646},
        'chest': {'CTDIvol': 11.0, 'DLP': 430.0,  'k': 0.0140, 'E_std': 6.02},
        'abd':   {'CTDIvol': 14.0, 'DLP': 720.0,  'k': 0.0150, 'E_std': 10.80},
    },
    'UK': {
        'brain': {'CTDIvol': 47.0, 'DLP': 790.0,  'k': 0.0021, 'E_std': 1.659},
        'chest': {'CTDIvol': 8.5,  'DLP': 290.0,  'k': 0.0140, 'E_std': 4.06},
        'abd':   {'CTDIvol': 10.0, 'DLP': 530.0,  'k': 0.0150, 'E_std': 7.95},
    },
    'EU': {
        'brain': {'CTDIvol': 48.0, 'DLP': 1386.0, 'k': 0.0021, 'E_std': 2.911},
        'chest': {'CTDIvol': 9.0,  'DLP': 364.0,  'k': 0.0140, 'E_std': 5.096},
        'abd':   {'CTDIvol': 9.0,  'DLP': 874.0,  'k': 0.0150, 'E_std': 13.11},
    },
    'Australia': {
        'brain': {'CTDIvol': 45.0, 'DLP': 820.0,  'k': 0.0021, 'E_std': 1.722},
        'chest': {'CTDIvol': 8.0,  'DLP': 310.0,  'k': 0.0140, 'E_std': 4.34},
        'abd':   {'CTDIvol': 10.0, 'DLP': 480.0,  'k': 0.0150, 'E_std': 7.20},
    },
}

INTERNATIONAL_COUNTRIES = ['Japan', 'UK', 'EU', 'Australia']

REGION_ORDER = ['brain', 'chest', 'abd']

REGION_DISPLAY_NAMES = {
    'brain': 'Brain',
    'chest': 'Chest',
    'abd': 'Abdomen',
}

# Accepted spellings/aliases mapped to the notebook's internal region keys.
REGION_ALIASES = {
    'brain': 'brain',
    'chest': 'chest',
    'abd': 'abd',
    'abdomen': 'abd',
}


def get_standards(country=None) -> dict:
    """ADDED. Returns the DRL table to use.

    country=None (or 'Egypt') -> the untouched Egyptian national STANDARDS.
    country in INTERNATIONAL_COUNTRIES -> that country's benchmark table.
    """
    if country is None or country == 'Egypt':
        return STANDARDS
    return INTERNATIONAL_STANDARDS.get(country, STANDARDS)


def _resolve(standards):
    """Internal helper: None -> Egyptian national STANDARDS (default behaviour)."""
    return STANDARDS if standards is None else standards


def normalize_region(value):
    """Map a free-text Region label to the notebook's internal key
    ('brain', 'chest', 'abd'), or return None if unrecognized."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    key = str(value).strip().lower()
    return REGION_ALIASES.get(key)


def perform_full_analysis(df_master: pd.DataFrame, area_name: str, standards: dict = None) -> dict:
    """
    Exact port of `perform_full_analysis()` from the source notebook (Cell 3).

    The only behavioural change vs. the notebook is that results are
    RETURNED in a dictionary instead of printed to stdout, so the Streamlit
    UI (and the notebook itself) can render them. Every calculation,
    comparison, and threshold is identical to the original notebook.

    `standards` defaults to None -> the Egyptian national STANDARDS, so the
    original behaviour is unchanged. Passing an international table only
    swaps the reference numbers; the formulas and comparisons are identical.

    Expects df_master to already contain a 'Region_Key' column produced by
    normalize_region().
    """
    standards = _resolve(standards)
    subset_df = df_master[df_master['Region_Key'] == area_name.lower()].copy()

    if subset_df.empty:
        return {'region': area_name, 'has_data': False}

    std = standards[area_name.lower()]

    # Calculate Effective Dose (E) -- E = DLP * k (notebook formula, unchanged)
    subset_df['E'] = subset_df['DLP'] * std['k']

    # Median Evaluation (notebook formula, unchanged)
    median_dlp = subset_df['DLP'].median()
    median_ctdi = subset_df['CTDIvol'].median()

    # Status Logic (notebook logic, unchanged)
    if median_dlp > std['DLP'] and median_ctdi > std['CTDIvol']:
        status = "Not Approved, Device Settings issue and Technician issue"
        status_level = "danger"
    elif median_dlp > std['DLP']:
        status = "Not Approved, Technician issue"
        status_level = "danger"
    elif median_ctdi > std['CTDIvol']:
        status = "Not Approved, Device Settings issue"
        status_level = "danger"
    else:
        status = "Approved"
        status_level = "success"

    # Effective Dose Percentage (notebook formula, unchanged)
    approved = subset_df[subset_df['E'] <= std['E_std']]
    pct_approved = (len(approved) / len(subset_df)) * 100
    pct_rejected = 100 - pct_approved

    return {
        'region': area_name.lower(),
        'region_display': REGION_DISPLAY_NAMES[area_name.lower()],
        'has_data': True,
        'n_exams': int(len(subset_df)),
        'median_dlp': median_dlp,
        'median_ctdi': median_ctdi,
        'drl_dlp': std['DLP'],
        'drl_ctdi': std['CTDIvol'],
        'status': status,
        'status_level': status_level,
        'n_approved_dose': int(len(approved)),
        'n_rejected_dose': int(len(subset_df) - len(approved)),
        'pct_approved_dose': pct_approved,
        'pct_rejected_dose': pct_rejected,
        'k': std['k'],
        'e_std': std['E_std'],
        'data': subset_df,
    }


def run_notebook_analysis(df: pd.DataFrame, standards: dict = None) -> dict:
    """
    Runs `perform_full_analysis` for brain, chest, and abd -- exactly
    mirroring the notebook's final loop:

        for area in ['brain', 'chest', 'abd']:
            perform_full_analysis(df, area)

    Returns a dict keyed by region ('brain', 'chest', 'abd').
    """
    standards = _resolve(standards)
    df = df.copy()
    df['Region_Key'] = df['Region'].apply(normalize_region)

    results = {}
    for area in REGION_ORDER:
        results[area] = perform_full_analysis(df, area, standards)
    return results


def compute_effective_dose_column(df: pd.DataFrame, standards: dict = None) -> pd.DataFrame:
    """Adds an 'EffectiveDose_mSv' column to the full dataset using the
    exact notebook formula E = DLP * k, applied per row according to each
    row's region."""
    standards = _resolve(standards)
    df = df.copy()
    if 'Region_Key' not in df.columns:
        df['Region_Key'] = df['Region'].apply(normalize_region)

    def _e(row):
        std = standards.get(row['Region_Key'])
        return row['DLP'] * std['k'] if std else None

    df['EffectiveDose_mSv'] = df.apply(_e, axis=1)
    return df


def flag_row_level_exceedances(df: pd.DataFrame, standards: dict = None) -> pd.DataFrame:
    """
    ADDED FOR VISUALIZATION ONLY - not part of the source notebook's
    calculation logic (see module docstring, item 1).

    Reuses the exact same DRL thresholds and the exact same ">" comparison
    used in the notebook's median-based status logic, applied per-row
    instead of to the median, so individual dangerous exams are visible.
    """
    standards = _resolve(standards)
    df = df.copy()
    if 'Region_Key' not in df.columns:
        df['Region_Key'] = df['Region'].apply(normalize_region)

    def _ctdi_exceeds(row):
        std = standards.get(row['Region_Key'])
        return bool(std) and row['CTDIvol'] > std['CTDIvol']

    def _dlp_exceeds(row):
        std = standards.get(row['Region_Key'])
        return bool(std) and row['DLP'] > std['DLP']

    df['CTDIvol_Exceeds_DRL'] = df.apply(_ctdi_exceeds, axis=1)
    df['DLP_Exceeds_DRL'] = df.apply(_dlp_exceeds, axis=1)
    df['Exceeds_DRL'] = df['CTDIvol_Exceeds_DRL'] | df['DLP_Exceeds_DRL']
    return df


def drl_reference_table(standards: dict = None) -> pd.DataFrame:
    """Read-only DRL reference table for display (Upload page)."""
    standards = _resolve(standards)
    rows = []
    for key in REGION_ORDER:
        std = standards[key]
        rows.append({
            'Region': REGION_DISPLAY_NAMES[key],
            'DRL CTDIvol (mGy)': std['CTDIvol'],
            'DRL DLP (mGy·cm)': std['DLP'],
            'Effective Dose k-factor (mSv/mGy·cm)': std['k'],
            'Effective Dose Threshold, E_std (mSv)': std['E_std'],
        })
    return pd.DataFrame(rows)