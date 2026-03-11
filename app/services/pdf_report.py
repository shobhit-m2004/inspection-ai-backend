import os
from datetime import datetime
from typing import Any, Dict, List

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle


def _safe(v: Any) -> str:
    return "" if v is None else str(v)


def build_pdf_report(path: str, report: Dict[str, Any]) -> None:
    styles = getSampleStyleSheet()
    story = []

    title = "Compliance Gap Report"
    story.append(Paragraph(title, styles["Title"]))
    story.append(Spacer(1, 0.3 * cm))

    meta_rows = [
        ["Report ID", _safe(report.get("report_id", ""))],
        ["Generated At", _safe(report.get("generated_at", datetime.utcnow().isoformat()))],
        ["SOP", _safe(report.get("sop_title", ""))],
        ["Log", _safe(report.get("log_title", ""))],
        ["Overall Score", _safe(report.get("overall_score", ""))],
        ["Severity", _safe(report.get("severity", ""))],
    ]
    meta_table = Table(meta_rows, colWidths=[4 * cm, 12 * cm])
    meta_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    story.append(meta_table)
    story.append(Spacer(1, 0.4 * cm))

    story.append(Paragraph("Summary", styles["Heading2"]))
    story.append(Paragraph(_safe(report.get("summary", "")), styles["BodyText"]))
    story.append(Spacer(1, 0.4 * cm))

    story.append(Paragraph("Gap Overview", styles["Heading2"]))
    chart = report.get("chart", {}) or {}
    labels = chart.get("labels", []) or []
    values = chart.get("values", []) or []
    if labels and values:
        chart_rows = [["Metric", "Value"]] + [[_safe(l), _safe(v)] for l, v in zip(labels, values)]
        chart_table = Table(chart_rows, colWidths=[8 * cm, 4 * cm])
        chart_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ]
            )
        )
        story.append(chart_table)
    else:
        story.append(Paragraph("No chart data available.", styles["BodyText"]))
    story.append(Spacer(1, 0.4 * cm))

    story.append(Paragraph("Detailed Gaps", styles["Heading2"]))
    gaps: List[Dict[str, Any]] = report.get("gaps", []) or []
    if gaps:
        gap_rows = [["Expected", "Observed", "Severity", "Recommendation"]]
        for g in gaps:
            gap_rows.append([
                _safe(g.get("expected", ""))[:500],
                _safe(g.get("observed", ""))[:500],
                _safe(g.get("severity", "")),
                _safe(g.get("recommendation", "")),
            ])
        gap_table = Table(gap_rows, colWidths=[5.5 * cm, 5.5 * cm, 2 * cm, 4 * cm])
        gap_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ]
            )
        )
        story.append(gap_table)
    else:
        story.append(Paragraph("No gaps detected.", styles["BodyText"]))

    os.makedirs(os.path.dirname(path), exist_ok=True)
    doc = SimpleDocTemplate(path, pagesize=A4, title=title)
    doc.build(story)
