"""Professional PDF report generation using ReportLab.

CHANGE LOG (report update):
    - The "Key Performance Indicators" section has been REMOVED from the
      generated PDF, as requested. The `kpis` argument is still accepted so
      every existing call site keeps working, but it is no longer rendered.
      KPIs are still produced everywhere else (Excel export, UI).
    - The remaining sections were renumbered 1-4 so the report has no gap.
    - `standard_label` was added so the cover page states which DRL standard
      the analysis was run against. It defaults to "National DRL", i.e. the
      original wording is unchanged for the Egyptian national standard.
"""

import io
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.enums import TA_CENTER
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image
)

from .calculations import REGION_DISPLAY_NAMES

PRIMARY = colors.HexColor("#1565C0")
LIGHT_ROW = colors.HexColor("#F2F6FB")
BORDER = colors.HexColor("#CCCCCC")

PROJECT_TITLE = (
    "Development of Website to Evaluate CT Radiation Doses Against "
    "Diagnostic Reference Levels (DRLs): Study in Cairo, Egypt"
)
PROJECT_SUBTITLE = (
    "Automated CT Radiation Dose Assessment System Based on "
    "Diagnostic Reference Levels (DRLs)"
)


def _styles():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='CoverTitle', fontSize=20, leading=26, alignment=TA_CENTER,
                               textColor=PRIMARY, spaceAfter=14, fontName='Helvetica-Bold'))
    styles.add(ParagraphStyle(name='CoverSubtitle', fontSize=12.5, leading=17, alignment=TA_CENTER,
                               textColor=colors.HexColor("#444444"), spaceAfter=10))
    styles.add(ParagraphStyle(name='SectionHeading', fontSize=15, leading=19, spaceBefore=14,
                               spaceAfter=8, textColor=PRIMARY, fontName='Helvetica-Bold'))
    styles.add(ParagraphStyle(name='BodyTextMed', fontSize=10, leading=14))
    return styles


def _table(data, col_widths=None):
    tbl = Table(data, colWidths=col_widths, hAlign='LEFT')
    tbl.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), PRIMARY),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 0.5, BORDER),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, LIGHT_ROW]),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    return tbl


def generate_pdf_report(df, results: dict, kpis: dict = None, chart_images: dict = None,
                         standard_label: str = "National DRL") -> bytes:
    """
    Generates the full CT DRL PDF report:
        1. Cover page
        2. Dataset summary
        3. DRL comparison (notebook median-based methodology)
        4. Effective dose results
        5. Visual analysis (embedded chart images, if provided)

    The "Key Performance Indicators" section has been removed on request.
    `kpis` is accepted but intentionally not rendered.

    `chart_images` is an optional dict of {title: png_bytes}.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=2 * cm, bottomMargin=2 * cm,
                             leftMargin=1.8 * cm, rightMargin=1.8 * cm)
    styles = _styles()
    story = []

    # --- Cover page ---
    story.append(Spacer(1, 4 * cm))
    story.append(Paragraph(PROJECT_TITLE, styles['CoverTitle']))
    story.append(Paragraph(PROJECT_SUBTITLE, styles['CoverSubtitle']))
    story.append(Spacer(1, 1 * cm))
    story.append(Paragraph(f"Report generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles['BodyTextMed']))
    story.append(Paragraph(f"Total examinations analyzed: {len(df)}", styles['BodyTextMed']))
    story.append(Paragraph(f"Standard applied: {standard_label}", styles['BodyTextMed']))
    story.append(PageBreak())

    # --- Dataset summary ---
    story.append(Paragraph("1. Dataset Summary", styles['SectionHeading']))
    region_counts = df['Region_Key'].value_counts()
    summary_data = [["Region", "Number of Exams"]]
    for region, count in region_counts.items():
        summary_data.append([REGION_DISPLAY_NAMES.get(region, str(region).capitalize()), str(count)])
    story.append(_table(summary_data, col_widths=[8 * cm, 8 * cm]))
    story.append(Spacer(1, 0.5 * cm))

    # NOTE: the "Key Performance Indicators" section was removed on request.

    # --- DRL comparison ---
    story.append(Paragraph(f"2. DRL Comparison (Region Median vs. {standard_label})", styles['SectionHeading']))
    drl_data = [["Region", "Median CTDIvol", "DRL CTDIvol", "Median DLP", "DRL DLP", "Status"]]
    for res in results.values():
        if not res.get('has_data'):
            continue
        drl_data.append([
            res['region_display'],
            f"{res['median_ctdi']:.2f}", str(res['drl_ctdi']),
            f"{res['median_dlp']:.2f}", str(res['drl_dlp']),
            res['status'],
        ])
    story.append(_table(drl_data))
    story.append(Spacer(1, 0.5 * cm))

    # --- Effective dose ---
    story.append(Paragraph("3. Effective Dose Results", styles['SectionHeading']))
    e_data = [["Region", "k-factor", "E Threshold (mSv)", "Approved (%)", "Rejected (%)"]]
    for res in results.values():
        if not res.get('has_data'):
            continue
        e_data.append([
            res['region_display'], str(res['k']), str(res['e_std']),
            f"{res['pct_approved_dose']:.1f}%", f"{res['pct_rejected_dose']:.1f}%",
        ])
    story.append(_table(e_data))
    story.append(Spacer(1, 0.5 * cm))

    # --- Charts ---
    if chart_images:
        story.append(PageBreak())
        story.append(Paragraph("4. Visual Analysis", styles['SectionHeading']))
        for title, img_bytes in chart_images.items():
            if not img_bytes:
                continue
            story.append(Paragraph(title, styles['BodyTextMed']))
            story.append(Image(io.BytesIO(img_bytes), width=16 * cm, height=8.5 * cm))
            story.append(Spacer(1, 0.4 * cm))

    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph(
        "Note: Effective-dose compliance is evaluated per examination against the region's "
        "notebook-defined threshold (E &lt;= E_std, where E = DLP x k). Region approval status is "
        "evaluated on the median CTDIvol and median DLP for the region, per the validated source "
        "notebook methodology (CT .ipynb).",
        styles['BodyTextMed']))

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()