"""Excel and CSV export builders.

CHANGE LOG: build_csv_summary() gained an optional `standards` argument so
the same summary can be produced against an international DRL table. It
defaults to None -> the Egyptian national STANDARDS, so existing behaviour
is unchanged.
"""

import io
from datetime import datetime

import pandas as pd

from .calculations import STANDARDS


def build_analysis_excel(df: pd.DataFrame, results: dict, kpis: dict, region_stats: dict) -> bytes:
    """
    Builds a multi-sheet Excel workbook:
      - Summary        : headline KPI values
      - Dataset         : original dataset + calculated columns (Effective Dose, DRL exceed flags)
      - DRL Comparison  : notebook median-based DRL comparison per region
      - Stats_<column>  : region-based descriptive statistics per numeric column
    """
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
        workbook = writer.book
        header_fmt = workbook.add_format({
            'bold': True, 'bg_color': '#1565C0', 'font_color': 'white', 'border': 1,
        })

        # --- Summary sheet ---
        summary_df = pd.DataFrame(list(kpis.items()), columns=['Metric', 'Value'])
        summary_df.to_excel(writer, sheet_name='Summary', index=False)
        ws = writer.sheets['Summary']
        for col_idx, col_name in enumerate(summary_df.columns):
            ws.write(0, col_idx, col_name, header_fmt)
        ws.set_column(0, 0, 34)
        ws.set_column(1, 1, 22)

        # --- Dataset sheet ---
        export_df = df.drop(columns=['Region_Key'], errors='ignore')
        export_df.to_excel(writer, sheet_name='Dataset', index=False)
        ws = writer.sheets['Dataset']
        for col_idx, col_name in enumerate(export_df.columns):
            ws.write(0, col_idx, col_name, header_fmt)
        ws.set_column(0, len(export_df.columns), 16)

        # --- DRL Comparison sheet ---
        summary_rows = []
        for res in results.values():
            if not res.get('has_data'):
                continue
            summary_rows.append({
                'Region': res['region_display'],
                'N Exams': res['n_exams'],
                'Median CTDIvol': res['median_ctdi'],
                'DRL CTDIvol': res['drl_ctdi'],
                'Median DLP': res['median_dlp'],
                'DRL DLP': res['drl_dlp'],
                'Status': res['status'],
                'Effective Dose Approved (%)': res['pct_approved_dose'],
                'Effective Dose Rejected (%)': res['pct_rejected_dose'],
            })
        drl_df = pd.DataFrame(summary_rows)
        drl_df.to_excel(writer, sheet_name='DRL Comparison', index=False)
        ws = writer.sheets['DRL Comparison']
        for col_idx, col_name in enumerate(drl_df.columns):
            ws.write(0, col_idx, col_name, header_fmt)
        ws.set_column(0, len(drl_df.columns), 20)

        # --- Region statistics sheets ---
        for col_name, stats_df in region_stats.items():
            if stats_df is None or stats_df.empty:
                continue
            sheet_name = f'Stats_{col_name}'[:31]
            stats_df.to_excel(writer, sheet_name=sheet_name)
            ws = writer.sheets[sheet_name]
            ws.set_column(0, 12, 16)

    buffer.seek(0)
    return buffer.getvalue()


def build_csv_summary(df: pd.DataFrame, results: dict, standards: dict = None) -> bytes:
    """CSV summary: overall totals plus per-region statistics."""
    standards = STANDARDS if standards is None else standards
    rows = []

    valid = df[df['Region_Key'].isin(standards.keys())]
    if not valid.empty:
        e_threshold = valid['Region_Key'].map(lambda r: standards[r]['E_std'])
        n_exceed = int((valid['EffectiveDose_mSv'] > e_threshold).sum())
        rows.append({
            'Region': 'ALL REGIONS',
            'N Exams': int(len(valid)),
            'Mean CTDIvol': valid['CTDIvol'].mean(),
            'Mean DLP': valid['DLP'].mean(),
            'Mean Effective Dose (mSv)': valid['EffectiveDose_mSv'].mean(),
            'Median CTDIvol': valid['CTDIvol'].median(),
            'Median DLP': valid['DLP'].median(),
            'Effective Dose Approved (%)': None,
            'N Exceeding DRL (Effective Dose)': n_exceed,
            'Status': '',
        })

    for res in results.values():
        if not res.get('has_data'):
            continue
        data = res['data']
        rows.append({
            'Region': res['region_display'],
            'N Exams': res['n_exams'],
            'Mean CTDIvol': data['CTDIvol'].mean(),
            'Mean DLP': data['DLP'].mean(),
            'Mean Effective Dose (mSv)': data['E'].mean(),
            'Median CTDIvol': res['median_ctdi'],
            'Median DLP': res['median_dlp'],
            'Effective Dose Approved (%)': res['pct_approved_dose'],
            'N Exceeding DRL (Effective Dose)': res['n_rejected_dose'],
            'Status': res['status'],
        })

    return pd.DataFrame(rows).to_csv(index=False).encode('utf-8')


def history_filename() -> str:
    return f"CT_DRL_Results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"