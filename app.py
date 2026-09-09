"""
CT DRL Evaluation System
=========================
Evaluation of CT Radiation Doses Against Diagnostic Reference Levels (DRLs).

Streamlit front-end. All scientific calculations live in utils/calculations.py
(and are shared, unmodified, with notebook/CT_DRL_System.ipynb) so the web
application reproduces exactly the same outputs as the validated source
notebook. This file is responsible only for UI, workflow, validation,
visualization wiring, exports, and history management.

Run with:
    streamlit run app.py
"""

import os
import pandas as pd
import streamlit as st

from utils.calculations import (
    STANDARDS, INTERNATIONAL_STANDARDS, INTERNATIONAL_COUNTRIES,
    REGION_ORDER, REGION_DISPLAY_NAMES, normalize_region,
    run_notebook_analysis, compute_effective_dose_column, flag_row_level_exceedances,
    drl_reference_table,
)
from utils.validation import validate_extension, validate_dataframe, REQUIRED_COLUMNS
from utils.data_loader import load_excel_file
from utils.statistics import (
    descriptive_stats, region_statistics, outlier_summary,
    selected_region_statistics, pair_correlation, correlation_strength,
)
from utils.visualization import (
    fig_dose_scatter, fig_region_bar, fig_histogram, fig_pie_compliance,
    fig_boxplot, fig_correlation, fig_stacked_compliance, fig_outliers, fig_pie_region_share,
    fig_std_by_region, fig_var_by_region, fig_pair_scatter,
)
from utils.export import build_analysis_excel, build_csv_summary, history_filename
from utils.pdf_report import generate_pdf_report
from utils.history_manager import save_to_history, list_history, delete_history_file

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

PROJECT_TITLE = (
    "Evaluation of CT Radiation Doses Against Diagnostic Reference Levels (DRLs)"
)

# ---------------------------------------------------------------------------
# Professional, monochrome, solid inline-SVG icons (no emojis anywhere).
# Icons inherit color via currentColor, controlled through the `color` CSS
# style applied on the wrapping <span>.
# ---------------------------------------------------------------------------
ICONS = {
    "database": '<svg viewBox="0 0 24 24" width="26" height="26" fill="none" stroke="currentColor" stroke-width="2"><ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v6c0 1.7 3.6 3 8 3s8-1.3 8-3V5"/><path d="M4 11v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6"/></svg>',
    "chart": '<svg viewBox="0 0 24 24" width="26" height="26" fill="currentColor"><rect x="3" y="12" width="4" height="9"/><rect x="10" y="7" width="4" height="14"/><rect x="17" y="3" width="4" height="18"/></svg>',
    "target": '<svg viewBox="0 0 24 24" width="26" height="26" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1.3" fill="currentColor" stroke="none"/></svg>',
    "document": '<svg viewBox="0 0 24 24" width="26" height="26" fill="none" stroke="currentColor" stroke-width="2"><rect x="5" y="3" width="14" height="18" rx="2"/><line x1="8" y1="8" x2="16" y2="8"/><line x1="8" y1="12" x2="16" y2="12"/><line x1="8" y1="16" x2="13" y2="16"/></svg>',
    "shield": '<svg viewBox="0 0 24 24" width="26" height="26" fill="currentColor"><path d="M12 2l7 3v6c0 5-3.5 8.5-7 10-3.5-1.5-7-5-7-10V5l7-3z"/></svg>',
    "activity": '<svg viewBox="0 0 24 24" width="26" height="26" fill="none" stroke="currentColor" stroke-width="2"><polyline points="2,12 7,12 10,4 14,20 17,12 22,12"/></svg>',
    "clock": '<svg viewBox="0 0 24 24" width="26" height="26" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="9"/><polyline points="12,7 12,12 16,14"/></svg>',
    "info": '<svg viewBox="0 0 24 24" width="26" height="26" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="9"/><line x1="12" y1="11" x2="12" y2="16"/><circle cx="12" cy="8" r="1" fill="currentColor" stroke="none"/></svg>',
    "logo": '<svg viewBox="0 0 48 48" width="34" height="34" fill="none" stroke="currentColor" stroke-width="2.4"><circle cx="24" cy="19" r="14"/><circle cx="24" cy="19" r="5.5" fill="currentColor" stroke="none"/><line x1="6" y1="37" x2="42" y2="37" stroke-linecap="round"/><line x1="15" y1="37" x2="15" y2="41.5" stroke-linecap="round"/><line x1="24" y1="37" x2="24" y2="41.5" stroke-linecap="round"/><line x1="33" y1="37" x2="33" y2="41.5" stroke-linecap="round"/></svg>',
}

APP_LOGO_HTML = (
    f'<span style="color:var(--primary); display:inline-flex; vertical-align:middle;">'
    f'{ICONS["logo"]}</span>'
)


def icon(name, color="var(--primary)"):
    svg = ICONS.get(name, ICONS["info"])
    return f'<span style="color:{color}; display:inline-flex; vertical-align:middle;">{svg}</span>'


# ---------------------------------------------------------------------------
# Session state / theming
# ---------------------------------------------------------------------------
STANDARD_OPTIONS = ["Select a standard...", "National DRL", "International DRL"]


def init_state():
    defaults = {
        "dark_mode": False,
        "df_raw": None,
        "uploaded_filename": None,
        "uploaded_file_count": 0,
        "upload_signature": None,
        "validation": None,
        "standard_type": STANDARD_OPTIONS[0],
        "drl_country": None,
        "show_country_dialog": False,
        "df_analyzed": None,
        "results": None,
        "kpis": None,
        "analysis_signature": None,
        "last_history_filename": None,
        "pdf_bytes": None,
        "pdf_signature": None,
        "preview_file": None,
        "uploader_key": 0,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def load_css():
    css_path = os.path.join(BASE_DIR, "assets", "style.css")
    try:
        with open(css_path, "r", encoding="utf-8") as f:
            base_css = f.read()
        st.markdown(f"<style>{base_css}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        pass

    if st.session_state.get("dark_mode"):
        st.markdown("""
        <style>
        :root {
          --bg-color: #121212;
          --card-bg: #1E1E1E;
          --text-color: #F2F2F2;
          --text-muted: #B5B5B5;
          --primary: #4FA3E3;
          --primary-soft: rgba(79,163,227,0.16);
          --secondary: #66BB6A;
          --secondary-soft: rgba(102,187,106,0.18);
          --warning: #FFB74D;
          --warning-soft: rgba(255,183,77,0.18);
          --danger: #EF5350;
          --danger-soft: rgba(239,83,80,0.18);
          --border-color: #333333;
          --shadow: 0 2px 10px rgba(0,0,0,0.4);
        }
        </style>
        """, unsafe_allow_html=True)


SESSION_KEYS = [
    "df_raw", "uploaded_filename", "upload_signature", "validation", "df_analyzed",
    "results", "kpis", "analysis_signature", "last_history_filename", "pdf_bytes",
    "pdf_signature", "preview_file",
]


def clear_session():
    for k in SESSION_KEYS:
        st.session_state[k] = None
    st.session_state["uploaded_file_count"] = 0
    st.session_state["standard_type"] = STANDARD_OPTIONS[0]
    st.session_state["drl_country"] = None
    st.session_state["show_country_dialog"] = False
    st.session_state["uploader_key"] = st.session_state.get("uploader_key", 0) + 1
    if "standard_type_radio" in st.session_state:
        del st.session_state["standard_type_radio"]


def delete_uploaded_dataset():
    """Manual removal of the currently loaded dataset (requested 'delete option').

    The dataset otherwise stays loaded for the whole session, so navigating to
    another page and back does NOT lose it.
    """
    for k in ["df_raw", "uploaded_filename", "upload_signature", "validation",
              "df_analyzed", "results", "kpis", "analysis_signature",
              "pdf_bytes", "pdf_signature"]:
        st.session_state[k] = None
    st.session_state["uploaded_file_count"] = 0
    # Bump the uploader key so the file_uploader widget itself is emptied too.
    st.session_state["uploader_key"] = st.session_state.get("uploader_key", 0) + 1


def active_standard():
    """Returns (standards_dict, human_label) for the standard currently selected."""
    country = st.session_state.get("drl_country")
    if st.session_state.get("standard_type") == "International DRL" and country:
        return INTERNATIONAL_STANDARDS[country], f"{country} DRL"
    return STANDARDS, "National DRL"


def render_sidebar():
    with st.sidebar:
        st.markdown(
            f'<div class="main-title" style="font-size:22px; margin-bottom:0;">'
            f'{APP_LOGO_HTML}<span style="margin-left:8px; vertical-align:middle;">CT DRL System</span></div>',
            unsafe_allow_html=True)
        st.markdown("---")
        page = st.radio(
            "Navigation",
            ["Home", "Upload Dataset", "Analysis Results", "Analysis History", "About"],
            label_visibility="collapsed",
            key="nav_page",
        )
        st.markdown("---")
        st.toggle("Dark Mode", key="dark_mode")
        st.markdown("---")
        if st.session_state.get("df_analyzed") is not None:
            st.caption(f"Loaded dataset: {len(st.session_state.df_analyzed)} examinations")
        else:
            st.caption("No dataset loaded")
        if st.button("Clear Session", use_container_width=True):
            clear_session()
            st.rerun()
        st.markdown('<div class="app-footer">Version 1.0</div>', unsafe_allow_html=True)
    return page


# ---------------------------------------------------------------------------
# Analysis pipeline (uses utils.calculations exclusively - see that module's
# docstring for the scientific-integrity notice)
# ---------------------------------------------------------------------------
def compute_kpis(df: pd.DataFrame, results: dict) -> dict:
    total = int(len(df))
    mean_ctdi = df["CTDIvol"].mean()
    mean_dlp = df["DLP"].mean()
    mean_e = df["EffectiveDose_mSv"].mean()
    max_ctdi = df["CTDIvol"].max()
    max_dlp = df["DLP"].max()
    max_e = df["EffectiveDose_mSv"].max()
    n_exceed = int(df["Exceeds_DRL"].sum())
    pct_exceed = (n_exceed / total * 100) if total else 0.0

    n_outliers_total = 0
    for col in ["CTDIvol", "DLP"]:
        n_outliers_total += outlier_summary(df, col)["n_outliers"]

    def _fmt(v):
        return round(float(v), 2) if pd.notna(v) else "N/A"

    return {
        "Total Examinations": total,
        "Mean CTDIvol (mGy)": _fmt(mean_ctdi),
        "Mean DLP (mGy.cm)": _fmt(mean_dlp),
        "Mean Effective Dose (mSv)": _fmt(mean_e),
        "Maximum CTDIvol (mGy)": _fmt(max_ctdi),
        "Maximum DLP (mGy.cm)": _fmt(max_dlp),
        "Maximum Effective Dose (mSv)": _fmt(max_e),
        "DRL Exceeding Cases": n_exceed,
        "Percentage Above DRL": f"{pct_exceed:.1f}%",
        "Number of Outliers (CTDIvol + DLP)": n_outliers_total,
    }


def run_analysis(df_raw: pd.DataFrame, standards: dict = None):
    """Runs the full, notebook-faithful analysis pipeline on a validated dataset."""
    standards = STANDARDS if standards is None else standards
    df = df_raw.copy()
    df["Region_Key"] = df["Region"].apply(normalize_region)
    df = df[df["Region_Key"].isin(standards.keys())].copy()

    results = run_notebook_analysis(df, standards)
    df = compute_effective_dose_column(df, standards)
    df = flag_row_level_exceedances(df, standards)
    kpis = compute_kpis(df, results)
    return df, results, kpis


# ---------------------------------------------------------------------------
# Home page
# ---------------------------------------------------------------------------
def render_home():
    st.markdown(f"""
    <div class="hero-banner">
        <div class="main-title">{PROJECT_TITLE}</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown(f"""
    <div class="med-card">
        {icon("shield")}
        <h3 style="display:inline-block; margin-left:8px; vertical-align:middle;">System Overview</h3>
        <p class="body-text">
        This system automatically evaluates CT radiation doses using Diagnostic Reference Levels (DRLs).
        It provides dose assessment, statistical analysis, and reporting tools for CT examinations performed
        at hospitals in Cairo, Egypt.
        </p>
        <p class="body-text">
        User uploads a dataset and the system compares patient doses against DRLs, calculate effective dose,
        flags examinations that exceed the DRL, and generates exportable Excel, CSV, and PDF reports.
        </p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<div class="section-title">CT Region Reference Information</div>', unsafe_allow_html=True)
    st.markdown(
        "<p class='body-text'>DRL values are based on country-specific reference levels and they vary by "
        "country. The system applies the selected country&rsquo;s DRL values for assessment and compliance "
        "evaluation. (see the Upload Dataset page).</p>"
        "<p class='body-text'>When a patient undergoes a CT scan of the brain, the machine measures the "
        "radiation received using two main values:</p>", unsafe_allow_html=True)

    col_ctdi, col_dlp = st.columns(2)
    with col_ctdi:
        st.markdown(f"""
        <div class="med-card">
            <h3 style="margin-top:0;">CTDIvol - clinical information</h3>
            <p class="body-text">
            shows the "intensity" of the dose; the higher the number, the stronger the dose in each slice,
            and it's estimated nationwide in the range of:
            </p>
            <p class="body-text">
            Brain: 30.0-67.0 mGy.<br>
            Chest: 8.0-22.0 mGy.<br>
            Abdomen: 9.0-31.0 mGy.
            </p>
        </div>
        """, unsafe_allow_html=True)
    with col_dlp:
        st.markdown(f"""
        <div class="med-card">
            <h3 style="margin-top:0;">DLP - clinical information</h3>
            <p class="body-text">
            shows the "total" dose the patient received across the entire scan (scan length &times; dose
            intensity), and it's estimated nationwide in the range of:
            </p>
            <p class="body-text">
            Brain: 790.0-1386.0 mGy&middot;cm.<br>
            Chest: 290.0-430.0 mGy&middot;cm.<br>
            Abdomen: 480.0-1325.0 mGy&middot;cm.
            </p>
        </div>
        """, unsafe_allow_html=True)

    st.markdown('<div class="section-title">Understanding Effective Dose</div>', unsafe_allow_html=True)
    st.markdown("""
    <div class="med-card">
        <h3 style="margin-top:0;">Effective Dose - clinical information</h3>
        <p class="body-text">
        <b>Definition:</b> Effective dose (E) is a calculated radiation-protection quantity that estimates the
        whole-body stochastic health risk from a non-uniform exposure, such as a CT scan of one body region,
        by weighting the dose received by each irradiated organ/tissue according to its relative
        radiosensitivity.
        </p>
        <p class="body-text">
        <b>Unit:</b> millisievert (mSv).
        </p>
        <p class="body-text">
        <b>Importance in radiation protection:</b> Effective dose allows comparison of risk across different
        imaging protocols and modalities on a common scale, and supports the ALARA (As Low As Reasonably
        Achievable) principle.
        </p>
        <p class="body-text">
        <b>Formula used in this system (unchanged from the source notebook):</b><br>
        <code>E = DLP &times; k</code>, where DLP is the Dose-Length Product (mGy·cm) reported by the
        scanner and k is a region-specific conversion factor (mSv per mGy·cm): Brain k = 0.0021,
        Chest k = 0.0140, Abdomen k = 0.0150.
        </p>
        <p class="body-text">
        <b>Interpretation:</b> Low effective doses (a few mSv) are broadly comparable to a few years of
        natural background radiation. Higher effective doses (tens of mSv, e.g., some multiphase abdominal
        or oncologic staging protocols) carry proportionally higher theoretical stochastic risk and warrant
        clinical justification.
        </p>
    </div>
    """, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# International DRL country picker (pop-up window)
# ---------------------------------------------------------------------------
def _country_picker_body():
    st.markdown(
        "<p class='body-text'>Choose the country whose DRL standard should be applied. "
        "The DRL Reference Table and the dataset analysis will then use that country's values.</p>",
        unsafe_allow_html=True,
    )
    current = st.session_state.get("drl_country")
    index = INTERNATIONAL_COUNTRIES.index(current) if current in INTERNATIONAL_COUNTRIES else 0
    choice = st.radio("Country", INTERNATIONAL_COUNTRIES, index=index, key="country_choice_radio")

    b1, b2 = st.columns(2)
    with b1:
        if st.button("Apply", key="apply_country_btn", use_container_width=True):
            st.session_state["drl_country"] = choice
            st.session_state["show_country_dialog"] = False
            # A different standard means the previous analysis is no longer valid.
            st.session_state["df_analyzed"] = None
            st.session_state["results"] = None
            st.session_state["kpis"] = None
            st.session_state["analysis_signature"] = None
            st.session_state["pdf_bytes"] = None
            st.session_state["pdf_signature"] = None
            st.rerun()
    with b2:
        if st.button("Cancel", key="cancel_country_btn", use_container_width=True):
            st.session_state["show_country_dialog"] = False
            st.rerun()


_dialog_decorator = getattr(st, "dialog", None) or getattr(st, "experimental_dialog", None)

if _dialog_decorator is not None:
    @_dialog_decorator("Select International DRL Country")
    def open_country_picker():
        _country_picker_body()
else:
    def open_country_picker():
        # Fallback for Streamlit versions without modal dialogs: render the
        # same picker inline, styled as a card.
        with st.container(border=True):
            st.markdown('<div class="card-title">Select International DRL Country</div>',
                         unsafe_allow_html=True)
            _country_picker_body()


# ---------------------------------------------------------------------------
# Upload Dataset page
# ---------------------------------------------------------------------------
def render_upload():
    st.markdown('<div class="section-title">Standard Selection</div>', unsafe_allow_html=True)
    st.markdown(
        "<p class='body-text'>Choose which DRL standard to apply before uploading a dataset. "
        "Nothing else on this page is shown until a standard is selected.</p>", unsafe_allow_html=True)

    saved = st.session_state.get("standard_type") or STANDARD_OPTIONS[0]
    if saved not in STANDARD_OPTIONS:
        saved = STANDARD_OPTIONS[0]

    standard_type = st.radio(
        "Standard Type",
        STANDARD_OPTIONS,
        index=STANDARD_OPTIONS.index(saved),
        horizontal=True,
        key="standard_type_radio",
    )

    if standard_type != st.session_state.get("standard_type"):
        st.session_state["standard_type"] = standard_type
        st.session_state["df_analyzed"] = None
        st.session_state["results"] = None
        st.session_state["kpis"] = None
        st.session_state["analysis_signature"] = None
        st.session_state["pdf_bytes"] = None
        st.session_state["pdf_signature"] = None
        if standard_type == "International DRL":
            # Open the country pop-up as soon as International DRL is chosen.
            st.session_state["show_country_dialog"] = True
        else:
            st.session_state["drl_country"] = None

    if standard_type == "Select a standard...":
        st.info("Select 'National DRL' or 'International DRL' above to continue.")
        return

    # --- International DRL: pick a country in a pop-up window first ---
    if standard_type == "International DRL":
        if st.session_state.get("show_country_dialog"):
            st.session_state["show_country_dialog"] = False
            open_country_picker()

        country = st.session_state.get("drl_country")
        if not country:
            st.info("Select a country to continue. Available international standards: "
                    + ", ".join(INTERNATIONAL_COUNTRIES) + ".")
            if st.button("Choose Country", key="open_country_btn"):
                st.session_state["show_country_dialog"] = True
                st.rerun()
            return

        cc1, cc2 = st.columns([3, 1])
        with cc1:
            st.success(f"International DRL standard applied: {country}")
        with cc2:
            if st.button("Change Country", key="change_country_btn", use_container_width=True):
                st.session_state["show_country_dialog"] = True
                st.rerun()

    standards, standard_label = active_standard()
    reference_title = ("National DRL Reference Table" if standard_type == "National DRL"
                        else f"{st.session_state.get('drl_country')} DRL Reference Table")

    # --- Uploader and the DRL reference table for the selected standard ---
    st.markdown('<div class="section-title">Upload Dataset</div>', unsafe_allow_html=True)

    left, right = st.columns([1.15, 1])

    with left:
        with st.container(border=True):
            st.markdown(f'{icon("document")} <span class="card-title" style="margin-left:8px;">'
                         f'CT Examination Dataset</span>', unsafe_allow_html=True)
            st.markdown(
                "<p class='body-text'>Upload one or more Excel (.xlsx) files containing CT examination "
                "records. Each file must contain exactly these columns: <b>" + ", ".join(REQUIRED_COLUMNS) +
                "</b>. When several files are selected they are combined into a single dataset.</p>",
                unsafe_allow_html=True,
            )
            uploaded = st.file_uploader(
                "Upload CT dataset (.xlsx)",
                type=["xlsx"],
                accept_multiple_files=True,
                label_visibility="collapsed",
                key=f"ct_uploader_{st.session_state.get('uploader_key', 0)}",
            )

    with right:
        with st.container(border=True):
            st.markdown(f'{icon("target")} <span class="card-title" style="margin-left:8px;">'
                         f'{reference_title}</span>', unsafe_allow_html=True)
            st.markdown("<p class='body-text'>Read-only reference values used for automatic comparison.</p>",
                         unsafe_allow_html=True)
            st.table(drl_reference_table(standards).set_index("Region"))

    # --- Read every selected file and combine them into one dataset ---
    if uploaded:
        frames, names, file_errors = [], [], []
        for uf in uploaded:
            ok, ext_err = validate_extension(uf.name)
            if not ok:
                file_errors.append(f"{uf.name}: {ext_err}")
                continue
            df_loaded, load_err = load_excel_file(uf)
            if load_err:
                file_errors.append(f"{uf.name}: {load_err}")
                continue
            frames.append(df_loaded)
            names.append(uf.name)

        for msg in file_errors:
            st.error(msg)

        if frames:
            combined = pd.concat(frames, ignore_index=True) if len(frames) > 1 else frames[0]
            signature = (tuple(names), int(len(combined)))
            if st.session_state.get("upload_signature") != signature:
                st.session_state.df_raw = combined
                st.session_state.uploaded_filename = ", ".join(names)
                st.session_state.uploaded_file_count = len(names)
                st.session_state.upload_signature = signature
                st.session_state.validation = validate_dataframe(combined)
                st.session_state.df_analyzed = None
                st.session_state.results = None
                st.session_state.kpis = None
                st.session_state.analysis_signature = None
                st.session_state.pdf_bytes = None
                st.session_state.pdf_signature = None

    # --- The loaded dataset stays available across page navigation ---
    if st.session_state.df_raw is not None:
        n_files = st.session_state.get("uploaded_file_count") or 1
        st.markdown('<div class="section-title">Current Dataset</div>', unsafe_allow_html=True)
        dc1, dc2 = st.columns([3, 1])
        with dc1:
            st.markdown(
                f"<p class='body-text'>Loaded file(s) (<b>{n_files}</b>): "
                f"<b>{st.session_state.uploaded_filename}</b> &nbsp;|&nbsp; "
                f"<b>{len(st.session_state.df_raw)}</b> rows.<br>"
                f"This dataset stays loaded while you move between pages. Use "
                f"<b>Delete Dataset</b> when you are finished with it.</p>",
                unsafe_allow_html=True,
            )
        with dc2:
            if st.button("Delete Dataset", key="delete_dataset_btn", use_container_width=True):
                delete_uploaded_dataset()
                st.rerun()

        validation = st.session_state.validation
        st.markdown('<div class="section-title">Validation Results</div>', unsafe_allow_html=True)

        if validation["is_valid"]:
            st.success(f"Dataset '{st.session_state.uploaded_filename}' passed validation "
                        f"({len(st.session_state.df_raw)} rows).")
        else:
            for err in validation["errors"]:
                st.error(err)

        for warn in validation.get("warnings", []):
            st.warning(warn)

        with st.expander("Preview Uploaded Data", expanded=False):
            st.dataframe(st.session_state.df_raw.head(50), use_container_width=True)

        if validation["is_valid"]:
            analysis_sig = (
                st.session_state.uploaded_filename,
                int(len(st.session_state.df_raw)),
                standard_label,
            )
            if (st.session_state.df_analyzed is None
                    or st.session_state.get("analysis_signature") != analysis_sig):
                with st.spinner("Running automatic DRL analysis..."):
                    df_analyzed, results, kpis = run_analysis(st.session_state.df_raw, standards)
                st.session_state.df_analyzed = df_analyzed
                st.session_state.results = results
                st.session_state.kpis = kpis
                st.session_state.analysis_signature = analysis_sig

            st.success("Automatic DRL analysis complete. View results on the 'Analysis Results' page.")

            # --- Saving to history is an explicit user action only ---
            st.markdown('<div class="section-title">Save to Analysis History</div>', unsafe_allow_html=True)
            st.markdown(
                "<p class='body-text'>Uploaded datasets are <b>not</b> saved automatically. "
                "Click the button below when you want this analysis stored in Analysis History.</p>",
                unsafe_allow_html=True,
            )
            sc1, sc2 = st.columns([1, 2])
            with sc1:
                save_clicked = st.button("Save Analysis to History", key="save_history_btn",
                                          use_container_width=True)
            if save_clicked:
                df_analyzed = st.session_state.df_analyzed
                region_stats = {
                    col: region_statistics(df_analyzed, col)
                    for col in ["CTDIvol", "DLP", "EffectiveDose_mSv"]
                }
                excel_bytes = build_analysis_excel(
                    df_analyzed, st.session_state.results, st.session_state.kpis, region_stats
                )
                fname = history_filename()
                save_to_history(excel_bytes, fname)
                st.session_state.last_history_filename = fname
                st.success(f"Analysis saved to Analysis History as {fname}")


# ---------------------------------------------------------------------------
# Analysis Results page
# ---------------------------------------------------------------------------
CORRELATION_PAIRS = {
    "Age vs CTDIvol": ("Age", "CTDIvol"),
    "Age vs DLP": ("Age", "DLP"),
    "Age vs Effective Dose": ("Age", "EffectiveDose_mSv"),
    "KVP vs CTDIvol": ("KVP", "CTDIvol"),
    "KVP vs DLP": ("KVP", "DLP"),
    "KVP vs Effective Dose": ("KVP", "EffectiveDose_mSv"),
    "mAs vs CTDIvol": ("mAs", "CTDIvol"),
    "mAs vs DLP": ("mAs", "DLP"),
    "mAs vs Effective Dose": ("mAs", "EffectiveDose_mSv"),
}


def render_results():
    if st.session_state.df_analyzed is None or st.session_state.results is None:
        st.warning("No analysis available yet. Please upload a dataset on the 'Upload Dataset' page first.")
        return

    df = st.session_state.df_analyzed
    results = st.session_state.results
    kpis = st.session_state.kpis
    dark = st.session_state.dark_mode
    standards, standard_label = active_standard()

    st.caption(f"Standard applied: {standard_label}")

    tabs = st.tabs(["Region Status", "DRL Comparison Charts", "Statistical Analysis", "Outlier Detection", "Exports"])

    # --- Tab 1: Region Status ---
    with tabs[0]:
        for region in REGION_ORDER:
            res = results.get(region)
            if not res or not res.get("has_data"):
                continue
            badge_class = "status-approved" if res["status_level"] == "success" else "status-rejected"
            st.markdown(f"""
            <div class="med-card">
                <h3>{res['region_display']}</h3>
                <p class="body-text">
                    Examinations: <b>{res['n_exams']}</b> &nbsp;|&nbsp;
                    Median CTDIvol: <b>{res['median_ctdi']:.2f} mGy</b> (DRL {res['drl_ctdi']}) &nbsp;|&nbsp;
                    Median DLP: <b>{res['median_dlp']:.2f} mGy·cm</b> (DRL {res['drl_dlp']})
                </p>
                <span class="status-badge {badge_class}">{res['status']}</span>
                <p class="body-text" style="margin-top:10px;">
                    Effective Dose Compliance: <b>{res['pct_approved_dose']:.1f}% Approved</b>,
                    {res['pct_rejected_dose']:.1f}% Rejected (E &le; {res['e_std']} mSv threshold)
                </p>
            </div>
            """, unsafe_allow_html=True)

    # --- Tab 2: DRL Comparison Charts ---
    with tabs[1]:
        c1, c2 = st.columns(2)
        with c1:
            st.plotly_chart(fig_region_bar(results, "median_ctdi", "drl_ctdi", dark, "Median CTDIvol vs. DRL"),
                              use_container_width=True)
        with c2:
            st.plotly_chart(fig_region_bar(results, "median_dlp", "drl_dlp", dark, "Median DLP vs. DRL"),
                              use_container_width=True)

        st.plotly_chart(fig_stacked_compliance(results, dark), use_container_width=True)

        active_regions = [r for r in REGION_ORDER if results.get(r, {}).get("has_data")]
        if active_regions:
            region_tabs = st.tabs([REGION_DISPLAY_NAMES[r] for r in active_regions])
            for rt, region in zip(region_tabs, active_regions):
                with rt:
                    st.plotly_chart(
                        fig_dose_scatter(df, region, dark, standards, standard_label),
                        use_container_width=True,
                    )

        c3, c4 = st.columns(2)
        with c3:
            n_app = sum(r["n_approved_dose"] for r in results.values() if r.get("has_data"))
            n_rej = sum(r["n_rejected_dose"] for r in results.values() if r.get("has_data"))
            st.plotly_chart(fig_pie_compliance(n_app, n_rej, dark), use_container_width=True)
        with c4:
            st.plotly_chart(fig_pie_region_share(df, dark), use_container_width=True)

    # --- Tab 3: Statistical Analysis ---
    with tabs[2]:
        available_regions = [r for r in REGION_ORDER if (df["Region_Key"] == r).any()]
        if not available_regions:
            st.info("No supported scan regions are present in the current dataset.")
        else:
            region_labels = [REGION_DISPLAY_NAMES[r] for r in available_regions]
            label_to_key = {REGION_DISPLAY_NAMES[r]: r for r in available_regions}

            sc1, sc2 = st.columns(2)
            with sc1:
                region_label = st.selectbox("Select scan region", region_labels, key="stats_region")
            with sc2:
                metric = st.selectbox("Select metric",
                                       ["CTDIvol", "DLP", "EffectiveDose_mSv", "Age", "KVP", "mAs"],
                                       key="stats_metric")

            region_key = label_to_key[region_label]
            region_df = df[df["Region_Key"] == region_key]

            st.caption(f"All statistics below are calculated from the {region_label} region only "
                        f"({len(region_df)} examinations).")

            st.markdown(f"<h3 class='card-title'>Region-Based Statistics: {metric}</h3>", unsafe_allow_html=True)
            stats_table = selected_region_statistics(df, metric, region_key)
            if stats_table.empty:
                st.info("No numeric values available for this metric in the selected region.")
            else:
                st.table(stats_table.round(2))

            # --- Standard Deviation and Variance visuals ---
            st.markdown("<h3 class='card-title'>Dispersion: Standard Deviation and Variance</h3>",
                         unsafe_allow_html=True)
            series = pd.to_numeric(region_df[metric], errors="coerce").dropna()
            std_value = float(series.std()) if len(series) > 1 else float("nan")
            var_value = float(series.var()) if len(series) > 1 else float("nan")
            cv_value = (std_value / float(series.mean()) * 100) if len(series) > 1 and series.mean() else float("nan")

            def _fmt_stat(v, suffix=""):
                return "N/A" if v != v else f"{v:,.2f}{suffix}"

            d1, d2, d3 = st.columns(3)
            with d1:
                st.markdown(f'<div class="kpi-card"><div class="kpi-value">{_fmt_stat(std_value)}</div>'
                             f'<div class="kpi-label">Standard Deviation ({region_label})</div></div>',
                             unsafe_allow_html=True)
            with d2:
                st.markdown(f'<div class="kpi-card"><div class="kpi-value warning">{_fmt_stat(var_value)}</div>'
                             f'<div class="kpi-label">Variance ({region_label})</div></div>',
                             unsafe_allow_html=True)
            with d3:
                st.markdown(f'<div class="kpi-card"><div class="kpi-value success">{_fmt_stat(cv_value, "%")}</div>'
                             f'<div class="kpi-label">Coefficient of Variation</div></div>',
                             unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)
            v1, v2 = st.columns(2)
            with v1:
                st.plotly_chart(fig_std_by_region(df, metric, dark, region_key), use_container_width=True)
            with v2:
                st.plotly_chart(fig_var_by_region(df, metric, dark, region_key), use_container_width=True)

            # --- Distribution charts, restricted to the selected region ---
            if metric in ["CTDIvol", "DLP"]:
                c1, c2 = st.columns(2)
                with c1:
                    st.plotly_chart(fig_histogram(region_df, metric, dark), use_container_width=True)
                with c2:
                    st.plotly_chart(fig_boxplot(region_df, metric, dark), use_container_width=True)
            elif metric != "EffectiveDose_mSv":
                # The "Dispersion of EffectiveDose_mSv by Region" box plot was removed on request.
                st.plotly_chart(fig_boxplot(region_df, metric, dark), use_container_width=True)

            # --- Correlation for exactly two user-selected metrics ---
            st.markdown("<h3 class='card-title'>Correlation Analysis</h3>", unsafe_allow_html=True)
            pair_label = st.selectbox("Select metrics for correlation",
                                       list(CORRELATION_PAIRS.keys()), key="corr_pair")
            x_col, y_col = CORRELATION_PAIRS[pair_label]
            r_value = pair_correlation(region_df, x_col, y_col)

            st.caption(f"Correlation is calculated for {pair_label} only, using the "
                        f"{region_label} region.")

            r_display = "N/A" if r_value != r_value else f"{r_value:.3f}"
            rc1, rc2 = st.columns(2)
            with rc1:
                st.markdown(f'<div class="kpi-card"><div class="kpi-value">{r_display}</div>'
                             f'<div class="kpi-label">Pearson r — {pair_label}</div></div>',
                             unsafe_allow_html=True)
            with rc2:
                st.markdown(f'<div class="kpi-card"><div class="kpi-value success" style="font-size:20px;">'
                             f'{correlation_strength(r_value)}</div>'
                             f'<div class="kpi-label">Interpretation</div></div>',
                             unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)
            mc1, mc2 = st.columns(2)
            with mc1:
                st.plotly_chart(fig_correlation(region_df, dark, cols=[x_col, y_col]),
                                  use_container_width=True)
            with mc2:
                st.plotly_chart(fig_pair_scatter(region_df, x_col, y_col, dark),
                                  use_container_width=True)

    # --- Tab 4: Outlier Detection ---
    with tabs[3]:
        st.markdown(
            "<p class='body-text'>Supplementary outlier detection using the standard 1.5&times;IQR rule, "
            "applied per region. <b>This method is not part of the original notebook</b> and is provided as "
            "an additional statistical quality-control tool.</p>", unsafe_allow_html=True)
        outlier_metric = st.selectbox("Select metric for outlier detection", ["CTDIvol", "DLP"], key="outlier_metric")
        osum = outlier_summary(df, outlier_metric)

        oc1, oc2, oc3 = st.columns(3)
        with oc1:
            st.markdown(f'<div class="kpi-card"><div class="kpi-value">{osum["n_total"]}</div>'
                         f'<div class="kpi-label">Total Exams</div></div>', unsafe_allow_html=True)
        with oc2:
            st.markdown(f'<div class="kpi-card"><div class="kpi-value danger">{osum["n_outliers"]}</div>'
                         f'<div class="kpi-label">Outliers</div></div>', unsafe_allow_html=True)
        with oc3:
            st.markdown(f'<div class="kpi-card"><div class="kpi-value warning">{osum["pct_outliers"]:.1f}%</div>'
                         f'<div class="kpi-label">Outlier Percentage</div></div>', unsafe_allow_html=True)

        st.plotly_chart(fig_outliers(df, outlier_metric, dark), use_container_width=True)

    # --- Tab 5: Exports ---
    with tabs[4]:
        st.markdown("<h3 class='card-title'>Export Reports</h3>", unsafe_allow_html=True)
        region_stats = {col: region_statistics(df, col) for col in ["CTDIvol", "DLP", "EffectiveDose_mSv"]}
        excel_bytes = build_analysis_excel(df, results, kpis, region_stats)
        csv_bytes = build_csv_summary(df, results, standards)
        excel_filename = st.session_state.get("last_history_filename") or history_filename()

        # The PDF is built up-front so "Download PDF Report" downloads directly.
        # There is no separate "Generate PDF Report" step any more.
        pdf_sig = (st.session_state.get("uploaded_filename"), int(len(df)), standard_label)
        if st.session_state.get("pdf_signature") != pdf_sig or not st.session_state.get("pdf_bytes"):
            with st.spinner("Preparing PDF report..."):
                chart_images = {}
                try:
                    chart_images["Median CTDIvol vs. DRL"] = fig_region_bar(
                        results, "median_ctdi", "drl_ctdi", False, "Median CTDIvol vs. DRL"
                    ).to_image(format="png", scale=2)
                    chart_images["Compliance by Protocol - Effective Dose"] = fig_stacked_compliance(
                        results, False
                    ).to_image(format="png", scale=2)
                except Exception:
                    chart_images = {}
                st.session_state["pdf_bytes"] = generate_pdf_report(
                    df, results, chart_images=chart_images, standard_label=standard_label
                )
                st.session_state["pdf_signature"] = pdf_sig

        e1, e2, e3 = st.columns(3)
        with e1:
            st.download_button("Download Excel Report", data=excel_bytes, file_name=excel_filename,
                                use_container_width=True)
        with e2:
            st.download_button("Download CSV Summary", data=csv_bytes, file_name="CT_DRL_Summary.csv",
                                mime="text/csv", use_container_width=True)
        with e3:
            st.download_button("Download PDF Report", data=st.session_state["pdf_bytes"],
                                file_name="CT_DRL_Report.pdf", mime="application/pdf",
                                use_container_width=True)


# ---------------------------------------------------------------------------
# Analysis History page
# ---------------------------------------------------------------------------
def render_history():
    st.markdown('<div class="section-title">Analysis History</div>', unsafe_allow_html=True)
    entries = list_history()

    if not entries:
        st.info("No analyses have been saved yet. Upload a dataset, then use "
                "'Save Analysis to History' on the Upload Dataset page to store it here.")
        return

    st.markdown(f"<p class='body-text'>{len(entries)} saved analysis file(s).</p>", unsafe_allow_html=True)

    for entry in entries:
        with st.container(border=True):
            c1, c2, c3, c4 = st.columns([3, 1.2, 1.2, 1.6])
            with c1:
                st.markdown(f"<b>{entry['filename']}</b>", unsafe_allow_html=True)
                st.caption(f"Saved: {entry['modified']}  |  {entry['size_kb']} KB")
            with c2:
                if st.button("Preview", key=f"prev_{entry['filename']}", use_container_width=True):
                    st.session_state["preview_file"] = entry["path"]
            with c3:
                with open(entry["path"], "rb") as f:
                    st.download_button("Download", data=f.read(), file_name=entry["filename"],
                                        key=f"dl_{entry['filename']}", use_container_width=True)
            with c4:
                with st.popover("Delete", use_container_width=True):
                    st.markdown("<p class='body-text'>Deletion requires a password.</p>", unsafe_allow_html=True)
                    pw = st.text_input("Password", type="password", key=f"pw_{entry['filename']}")
                    if st.button("Confirm Delete", key=f"del_{entry['filename']}"):
                        success, msg = delete_history_file(entry["filename"], pw)
                        if success:
                            st.success(msg)
                            if st.session_state.get("preview_file") == entry["path"]:
                                st.session_state["preview_file"] = None
                            st.rerun()
                        else:
                            st.error(msg)

    if st.session_state.get("preview_file"):
        st.markdown('<div class="section-title">Report Preview</div>', unsafe_allow_html=True)
        try:
            preview_df = pd.read_excel(st.session_state["preview_file"], sheet_name="Dataset")
            st.dataframe(preview_df.head(100), use_container_width=True)
        except Exception as exc:
            st.error(f"Could not preview file: {exc}")


# ---------------------------------------------------------------------------
# About page
# ---------------------------------------------------------------------------
TEAM_MEMBERS = [
    ("Ahmed Yousif", "Research Team", "var(--primary)", "AY"),
    ("Ashraf Motasim", "Research Team", "var(--secondary)", "AM"),
    ("Azza Adil", "Research Team", "var(--warning)", "AA"),
]


def person_card(name: str, role: str, color: str, initials: str) -> str:
    """Card with a circular initials avatar instead of a top-left icon.
    Names and roles are unchanged."""
    return f"""
    <div class="feature-card person-card" style="border-top-color:{color};">
        <div class="avatar-initials" style="background:{color};">{initials}</div>
        <h4>{name}</h4>
        <p>{role}</p>
    </div>
    """


def render_about():
    st.markdown('<div class="section-title">Project Team</div>', unsafe_allow_html=True)

    cols = st.columns(3)
    for col, (name, role, color, initials) in zip(cols, TEAM_MEMBERS):
        with col:
            st.markdown(person_card(name, role, color, initials), unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    with c1:
        st.markdown(person_card("Manahil Awad Bashari", "Project Supervisor", "var(--danger)", "MB"),
                     unsafe_allow_html=True)
    with c2:
        st.markdown(person_card("Biomedical Engineering", "Sudan International University",
                                 "var(--primary)", "BE"), unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main():
    st.set_page_config(
        page_title="CT DRL Evaluation System",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    init_state()
    load_css()
    page = render_sidebar()

    if page == "Home":
        render_home()
    elif page == "Upload Dataset":
        render_upload()
    elif page == "Analysis Results":
        render_results()
    elif page == "Analysis History":
        render_history()
    elif page == "About":
        render_about()

    st.markdown(
        '<div class="app-footer">CT DRL Evaluation System &mdash; Biomedical Engineering Graduation Project '
        '&mdash; Cairo, Egypt</div>',
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()