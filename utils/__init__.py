"""
CT DRL System - utility package.

Modules:
    calculations    Exact port of the validated notebook's DRL / effective
                     dose logic (single source of truth for both app.py and
                     notebook/CT_DRL_System.ipynb).
    validation       Dataset upload validation.
    data_loader      Excel loading helpers.
    statistics       Descriptive statistics and supplementary outlier detection.
    visualization    Theme-aware Plotly chart builders.
    export           Excel / CSV report builders.
    pdf_report       ReportLab PDF report builder.
    history_manager  Analysis-history persistence and password-protected deletion.
"""