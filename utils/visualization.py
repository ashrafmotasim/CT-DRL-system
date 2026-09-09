"""Theme-aware Plotly chart builders for the CT DRL System.

Color rule (enforced throughout): examinations / regions that exceed a DRL
threshold are ALWAYS rendered in red. Normal values use medical blue or
soft green. Never black or gray for exceedance markers.

ADDED (Statistical Analysis update):
    fig_std_by_region()   clear bar visual for Standard Deviation.
    fig_var_by_region()   clear bar visual for Variance.
    fig_pair_scatter()    scatter + fitted trend line for the two metrics
                          selected for correlation.
fig_correlation() now accepts an optional `cols` list so the matrix can be
restricted to exactly the two metrics the user selected, and its visual
presentation has been upgraded (square cells, larger labels, cleaner
colour bar).
"""

import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd

from .calculations import REGION_DISPLAY_NAMES, STANDARDS
from .statistics import detect_outliers_iqr, dispersion_by_region

COLOR_PRIMARY = "#1565C0"
COLOR_SECONDARY = "#2E7D32"
COLOR_WARNING = "#F57C00"
COLOR_DANGER = "#D32F2F"

FONT_FAMILY = "Segoe UI, Roboto, Arial, sans-serif"

# Friendly axis labels used by the new correlation visuals.
METRIC_LABELS = {
    "Age": "Age (years)",
    "KVP": "KVP (kV)",
    "mAs": "mAs",
    "CTDIvol": "CTDIvol (mGy)",
    "DLP": "DLP (mGy·cm)",
    "EffectiveDose_mSv": "Effective Dose (mSv)",
}


def _label(col: str) -> str:
    return METRIC_LABELS.get(col, col)


def _layout(fig, dark_mode: bool, title: str, x_title: str = "", y_title: str = ""):
    bg = "#1E1E1E" if dark_mode else "#FFFFFF"
    font_color = "#F5F5F5" if dark_mode else "#1A1A1A"
    grid_color = "#3A3A3A" if dark_mode else "#E0E0E0"

    fig.update_layout(
        title=dict(text=title, font=dict(size=21, family=FONT_FAMILY, color=font_color)),
        xaxis_title=x_title,
        yaxis_title=y_title,
        font=dict(size=14, family=FONT_FAMILY, color=font_color),
        plot_bgcolor=bg,
        paper_bgcolor=bg,
        legend=dict(font=dict(size=13, color=font_color), bgcolor="rgba(0,0,0,0)"),
        margin=dict(t=65, l=55, r=25, b=55),
        hoverlabel=dict(font_size=13, font_family=FONT_FAMILY),
        autosize=True,
        height=440,
    )
    fig.update_xaxes(gridcolor=grid_color, zerolinecolor=grid_color,
                      title_font=dict(size=15, color=font_color), tickfont=dict(size=12, color=font_color))
    fig.update_yaxes(gridcolor=grid_color, zerolinecolor=grid_color,
                      title_font=dict(size=15, color=font_color), tickfont=dict(size=12, color=font_color))
    return fig


def fig_dose_scatter(df: pd.DataFrame, region_key: str, dark_mode: bool = False, standards: dict = None,
                      standard_label: str = "National DRL"):
    """DLP vs CTDIvol scatter for one region with DRL threshold lines.
    Exams exceeding DRL are large RED markers; normal exams are blue."""
    standards = STANDARDS if standards is None else standards
    subset = df[df['Region_Key'] == region_key]
    std = standards[region_key]

    normal = subset[~subset['Exceeds_DRL']]
    exceeded = subset[subset['Exceeds_DRL']]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=normal['DLP'], y=normal['CTDIvol'], mode='markers', name='Within DRL',
        marker=dict(color=COLOR_PRIMARY, size=10, opacity=0.75),
        hovertemplate='DLP: %{x:.1f}<br>CTDIvol: %{y:.1f}<extra>Within DRL</extra>',
    ))
    fig.add_trace(go.Scatter(
        x=exceeded['DLP'], y=exceeded['CTDIvol'], mode='markers', name='Exceeds DRL',
        marker=dict(color=COLOR_DANGER, size=15, opacity=0.9, line=dict(width=1, color="#7A0000")),
        hovertemplate='DLP: %{x:.1f}<br>CTDIvol: %{y:.1f}<extra>Exceeds DRL</extra>',
    ))
    fig.add_vline(x=std['DLP'], line_dash="dash", line_color=COLOR_WARNING,
                  annotation_text=f"DRL DLP ({std['DLP']})", annotation_font_size=12)
    fig.add_hline(y=std['CTDIvol'], line_dash="dash", line_color=COLOR_WARNING,
                  annotation_text=f"DRL CTDIvol ({std['CTDIvol']})", annotation_font_size=12)

    return _layout(fig, dark_mode,
                    f"{REGION_DISPLAY_NAMES[region_key]}: Patient Dose vs. {standard_label}",
                    "DLP (mGy·cm)", "CTDIvol (mGy)")


def fig_region_bar(results: dict, metric_key: str, drl_key: str, dark_mode: bool = False, title: str = ""):
    """Bar chart of a median metric per region vs. its DRL. Bar turns red if the median exceeds DRL."""
    regions, values, colors, drl_values = [], [], [], []
    for res in results.values():
        if not res.get('has_data'):
            continue
        regions.append(res['region_display'])
        val = res[metric_key]
        values.append(val)
        drl = res[drl_key]
        drl_values.append(drl)
        colors.append(COLOR_DANGER if val > drl else COLOR_SECONDARY)

    fig = go.Figure()
    fig.add_trace(go.Bar(x=regions, y=values, marker_color=colors, name="Region median",
                          hovertemplate='%{x}: %{y:.2f}<extra></extra>'))
    fig.add_trace(go.Scatter(x=regions, y=drl_values, mode='markers+lines', name='DRL',
                              marker=dict(color=COLOR_WARNING, size=12, symbol='diamond'),
                              line=dict(color=COLOR_WARNING, dash='dot')))
    return _layout(fig, dark_mode, title, "Region", "Value")


def fig_histogram(df: pd.DataFrame, column: str, dark_mode: bool = False):
    plot_df = df.copy()
    plot_df['Status'] = plot_df['Exceeds_DRL'].map({True: 'Exceeds DRL', False: 'Within DRL'})
    fig = px.histogram(plot_df, x=column, color='Status',
                        color_discrete_map={'Exceeds DRL': COLOR_DANGER, 'Within DRL': COLOR_PRIMARY},
                        nbins=30, opacity=0.85)
    fig.update_layout(bargap=0.05)
    return _layout(fig, dark_mode, f"Dose Distribution: {column}", column, "Number of Exams")


def fig_pie_compliance(n_approved: int, n_rejected: int, dark_mode: bool = False,
                        title: str = "Effective Dose Compliance"):
    fig = go.Figure(data=[go.Pie(
        labels=['Approved', 'Rejected'], values=[n_approved, n_rejected],
        marker=dict(colors=[COLOR_SECONDARY, COLOR_DANGER]),
        textinfo='label+percent', textfont=dict(size=14), hole=0.45,
    )])
    return _layout(fig, dark_mode, title)


def fig_boxplot(df: pd.DataFrame, column: str, dark_mode: bool = False):
    plot_df = df.copy()
    plot_df['Region'] = plot_df['Region_Key'].map(REGION_DISPLAY_NAMES)
    fig = px.box(plot_df, x='Region', y=column, color='Region',
                 color_discrete_sequence=[COLOR_PRIMARY, COLOR_SECONDARY, COLOR_WARNING])
    fig.update_traces(marker=dict(size=6))
    fig = _layout(fig, dark_mode, f"Dispersion of {column} by Region", "Region", column)
    fig.update_layout(showlegend=False)
    return fig


# ---------------------------------------------------------------------------
# ADDED: clear STD / VAR visuals for the Statistical Analysis page.
# The selected region is drawn in full colour; the other regions are drawn
# faded, so the selected region is immediately readable in context.
# ---------------------------------------------------------------------------
def _dispersion_bar(df, column, dark_mode, highlight_region, stat_key, title, y_title, base_color):
    disp = dispersion_by_region(df, column)
    if disp.empty:
        return _layout(go.Figure(), dark_mode, title, "Region", y_title)

    colors, widths = [], []
    for key in disp['Region_Key']:
        selected = (key == highlight_region)
        colors.append(base_color if selected else "rgba(150,160,175,0.45)")
        widths.append(2.2 if selected else 0)

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=disp['Region'], y=disp[stat_key],
        marker=dict(color=colors, line=dict(color="#0D3F73", width=widths)),
        text=[f"{v:,.2f}" for v in disp[stat_key]],
        textposition='outside',
        textfont=dict(size=14),
        hovertemplate='%{x}<br>' + y_title + ': %{y:.4f}<extra></extra>',
        name=y_title,
    ))
    fig = _layout(fig, dark_mode, title, "Region", y_title)
    fig.update_layout(showlegend=False, height=400)
    fig.update_yaxes(rangemode='tozero')
    return fig


def fig_std_by_region(df: pd.DataFrame, column: str, dark_mode: bool = False, highlight_region: str = None):
    """Standard Deviation per region for the chosen metric (selected region highlighted)."""
    return _dispersion_bar(df, column, dark_mode, highlight_region, 'std',
                            f"Standard Deviation (STD) — {column}", "Standard Deviation", COLOR_PRIMARY)


def fig_var_by_region(df: pd.DataFrame, column: str, dark_mode: bool = False, highlight_region: str = None):
    """Variance per region for the chosen metric (selected region highlighted)."""
    return _dispersion_bar(df, column, dark_mode, highlight_region, 'var',
                            f"Variance (VAR) — {column}", "Variance", COLOR_WARNING)


def fig_correlation(df: pd.DataFrame, dark_mode: bool = False, cols=None):
    """Correlation matrix.

    `cols=None` keeps the original full-metric behaviour. Passing exactly the
    two metrics the user selected restricts the matrix to that pair, so the
    correlation shown is computed for those two metrics only.
    """
    candidate_cols = cols if cols else ['Age', 'KVP', 'mAs', 'CTDIvol', 'DLP', 'EffectiveDose_mSv']
    use_cols = [c for c in candidate_cols if c in df.columns]
    corr = df[use_cols].apply(pd.to_numeric, errors='coerce').corr(numeric_only=True)

    labels = [_label(c) for c in corr.columns]
    font_color = "#F5F5F5" if dark_mode else "#1A1A1A"

    fig = go.Figure(data=go.Heatmap(
        z=corr.values,
        x=labels,
        y=labels,
        zmin=-1, zmax=1,
        colorscale='RdBu_r',
        xgap=6, ygap=6,
        text=[[f"{v:.2f}" for v in row] for row in corr.values],
        texttemplate="%{text}",
        textfont=dict(size=22, family=FONT_FAMILY),
        hovertemplate="%{y} vs %{x}<br>r = %{z:.3f}<extra></extra>",
        colorbar=dict(
            title=dict(text="r", font=dict(size=14, color=font_color)),
            tickvals=[-1, -0.5, 0, 0.5, 1],
            tickfont=dict(size=12, color=font_color),
            thickness=14, len=0.75, outlinewidth=0,
        ),
    ))
    fig = _layout(fig, dark_mode, "Correlation Matrix")
    fig.update_layout(height=430, margin=dict(t=70, l=110, r=25, b=70))
    fig.update_xaxes(showgrid=False, zeroline=False, side='bottom', tickangle=0)
    fig.update_yaxes(showgrid=False, zeroline=False, autorange='reversed')
    return fig


def fig_pair_scatter(df: pd.DataFrame, x_col: str, y_col: str, dark_mode: bool = False):
    """Scatter of the two selected metrics with a least-squares trend line.

    Only the two selected columns are used; nothing else is plotted.
    """
    pair = pd.DataFrame({
        'x': pd.to_numeric(df.get(x_col), errors='coerce'),
        'y': pd.to_numeric(df.get(y_col), errors='coerce'),
    }).dropna()

    title = f"{_label(x_col)} vs. {_label(y_col)}"
    fig = go.Figure()

    if pair.empty:
        return _layout(fig, dark_mode, title, _label(x_col), _label(y_col))

    fig.add_trace(go.Scatter(
        x=pair['x'], y=pair['y'], mode='markers', name='Examinations',
        marker=dict(color=COLOR_PRIMARY, size=9, opacity=0.6,
                    line=dict(width=0.6, color="#0D3F73")),
        hovertemplate=_label(x_col) + ': %{x:.2f}<br>' + _label(y_col) + ': %{y:.2f}<extra></extra>',
    ))

    if len(pair) >= 3 and pair['x'].nunique() > 1:
        slope, intercept = np.polyfit(pair['x'].values, pair['y'].values, 1)
        x_line = np.linspace(pair['x'].min(), pair['x'].max(), 100)
        fig.add_trace(go.Scatter(
            x=x_line, y=slope * x_line + intercept, mode='lines', name='Trend line',
            line=dict(color=COLOR_DANGER, width=3, dash='solid'),
            hoverinfo='skip',
        ))

    fig = _layout(fig, dark_mode, title, _label(x_col), _label(y_col))
    fig.update_layout(height=430)
    return fig


def fig_stacked_compliance(results: dict, dark_mode: bool = False):
    regions = [r['region_display'] for r in results.values() if r.get('has_data')]
    approved = [r['n_approved_dose'] for r in results.values() if r.get('has_data')]
    rejected = [r['n_rejected_dose'] for r in results.values() if r.get('has_data')]

    fig = go.Figure()
    fig.add_trace(go.Bar(y=regions, x=approved, name='Approved', orientation='h', marker_color=COLOR_SECONDARY))
    fig.add_trace(go.Bar(y=regions, x=rejected, name='Rejected', orientation='h', marker_color=COLOR_DANGER))
    fig.update_layout(barmode='stack')
    return _layout(fig, dark_mode, "Compliance Status by Protocol - Effective Dose", "Number of Patients", "Region")


def fig_outliers(df: pd.DataFrame, column: str, dark_mode: bool = False):
    df_flagged = detect_outliers_iqr(df, column)
    outlier_col = f'{column}_Outlier'
    df_flagged = df_flagged.copy()
    df_flagged['Region'] = df_flagged['Region_Key'].map(REGION_DISPLAY_NAMES)
    df_flagged['Status'] = df_flagged[outlier_col].map({True: 'Outlier', False: 'Normal'})

    fig = px.strip(df_flagged, x='Region', y=column, color='Status',
                    color_discrete_map={'Outlier': COLOR_DANGER, 'Normal': COLOR_PRIMARY})
    fig.update_traces(marker=dict(size=9, opacity=0.8))
    return _layout(fig, dark_mode, f"Outlier Detection (1.5×IQR, supplementary) — {column}", "Region", column)


def fig_pie_region_share(df: pd.DataFrame, dark_mode: bool = False):
    plot_df = df.copy()
    plot_df['Region'] = plot_df['Region_Key'].map(REGION_DISPLAY_NAMES)
    counts = plot_df['Region'].value_counts()
    fig = go.Figure(data=[go.Pie(
        labels=counts.index.tolist(), values=counts.values.tolist(),
        marker=dict(colors=[COLOR_PRIMARY, COLOR_SECONDARY, COLOR_WARNING]),
        textinfo='label+percent', textfont=dict(size=14), hole=0.35,
    )])
    return _layout(fig, dark_mode, "Examination Share by Region")