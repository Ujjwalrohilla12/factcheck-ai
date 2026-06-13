"""Report export utilities."""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime
from typing import Any
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from utils.helpers import calculate_claim_statistics


class ReportGenerator:
    """Generate CSV, Markdown, and PDF reports."""

    @staticmethod
    def generate_csv_report(results: list[dict[str, Any]]) -> tuple[str, str | None]:
        """Generate a CSV report string."""
        if not results:
            return "", "No results to export."

        output = io.StringIO()
        writer = csv.DictWriter(
            output,
            fieldnames=[
                "Claim",
                "Type",
                "Status",
                "Confidence",
                "Explanation",
                "Key Finding",
                "Sources",
                "Search Query",
            ],
        )
        writer.writeheader()

        for result in results:
            sources = "; ".join(
                f"{source.get('title', 'Source')} ({source.get('url', '')})"
                for source in result.get("sources", [])
            )
            writer.writerow(
                {
                    "Claim": result.get("claim", ""),
                    "Type": result.get("type", ""),
                    "Status": result.get("status", ""),
                    "Confidence": result.get("confidence", 0),
                    "Explanation": result.get("explanation", ""),
                    "Key Finding": result.get("key_finding", ""),
                    "Sources": sources,
                    "Search Query": result.get("search_query", ""),
                }
            )

        return output.getvalue(), None

    @staticmethod
    def generate_markdown_report(
        results: list[dict[str, Any]], title: str = "FactCheck AI Report"
    ) -> tuple[str, str | None]:
        """Generate a Markdown report."""
        if not results:
            return "", "No results to export."

        stats = calculate_claim_statistics(results)
        lines = [
            f"# {title}",
            "",
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "## Summary",
            f"- Total claims: {stats['total']}",
            f"- Verified: {stats['verified']}",
            f"- Inaccurate: {stats['inaccurate']}",
            f"- False: {stats['false']}",
            f"- Unverifiable: {stats['unverifiable']}",
            f"- Average confidence: {stats['avg_confidence']}%",
            "",
            "## Detailed Results",
        ]

        for index, result in enumerate(results, start=1):
            lines.extend(
                [
                    "",
                    f"### {index}. {result.get('claim', '')}",
                    f"- Type: {result.get('type', '')}",
                    f"- Status: {result.get('status', '')}",
                    f"- Confidence: {result.get('confidence', 0)}%",
                    f"- Explanation: {result.get('explanation', '')}",
                ]
            )
            if result.get("key_finding"):
                lines.append(f"- Key finding: {result.get('key_finding')}")
            if result.get("sources"):
                lines.append("- Sources:")
                for source in result.get("sources", []):
                    lines.append(
                        f"  - [{source.get('title', 'Source')}]({source.get('url', '')})"
                    )

        return "\n".join(lines), None

    @staticmethod
    def generate_pdf_report(
        results: list[dict[str, Any]], title: str = "FactCheck AI Report"
    ) -> tuple[bytes, str | None]:
        """Generate a PDF report as bytes."""
        if not results:
            return b"", "No results to export."

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=0.55 * inch,
            leftMargin=0.55 * inch,
            topMargin=0.55 * inch,
            bottomMargin=0.55 * inch,
        )
        styles = getSampleStyleSheet()
        story = [
            Paragraph(title, styles["Title"]),
            Paragraph(
                f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                styles["Normal"],
            ),
            Spacer(1, 0.2 * inch),
        ]

        stats = calculate_claim_statistics(results)
        summary_table = Table(
            [
                [
                    "Total",
                    "Verified",
                    "Inaccurate",
                    "False",
                    "Unverifiable",
                    "Avg Confidence",
                ],
                [
                    stats["total"],
                    stats["verified"],
                    stats["inaccurate"],
                    stats["false"],
                    stats["unverifiable"],
                    f"{stats['avg_confidence']}%",
                ],
            ]
        )
        summary_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef2ff")),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cbd5e1")),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ]
            )
        )
        story.extend([summary_table, Spacer(1, 0.25 * inch)])

        for index, result in enumerate(results, start=1):
            story.append(
                Paragraph(
                    f"{index}. {escape(str(result.get('claim', '')))}",
                    styles["Heading3"],
                )
            )
            story.append(
                Paragraph(
                    f"<b>Status:</b> {escape(str(result.get('status', '')))} | "
                    f"<b>Confidence:</b> {result.get('confidence', 0)}% | "
                    f"<b>Type:</b> {escape(str(result.get('type', '')))}",
                    styles["Normal"],
                )
            )
            story.append(
                Paragraph(
                    f"<b>Explanation:</b> {escape(str(result.get('explanation', '')))}",
                    styles["BodyText"],
                )
            )
            if result.get("key_finding"):
                story.append(
                    Paragraph(
                        f"<b>Key finding:</b> {escape(str(result.get('key_finding')))}",
                        styles["BodyText"],
                    )
                )
            for source in result.get("sources", []):
                story.append(
                    Paragraph(
                        f"Source: {escape(str(source.get('title', 'Source')))} - {escape(str(source.get('url', '')))}",
                        styles["Italic"],
                    )
                )
            story.append(Spacer(1, 0.18 * inch))

        doc.build(story)
        return buffer.getvalue(), None

    @staticmethod
    def generate_json_report(
        results: list[dict[str, Any]], title: str = "FactCheck AI Report"
    ) -> tuple[str, str | None]:
        """Generate a JSON report for data integration."""
        if not results:
            return "", "No results to export."

        stats = calculate_claim_statistics(results)
        report = {
            "title": title,
            "generated": datetime.now().isoformat(),
            "summary": {
                "total_claims": stats["total"],
                "verified": stats["verified"],
                "inaccurate": stats["inaccurate"],
                "false": stats["false"],
                "unverifiable": stats["unverifiable"],
                "average_confidence": stats["avg_confidence"],
            },
            "results": results,
        }
        return json.dumps(report, indent=2), None

    @staticmethod
    def generate_html_report(
        results: list[dict[str, Any]], title: str = "FactCheck AI Report"
    ) -> tuple[str, str | None]:
        """Generate an interactive HTML report."""
        if not results:
            return "", "No results to export."

        stats = calculate_claim_statistics(results)
        html_lines = [
            "<!DOCTYPE html>",
            "<html lang='en'>",
            "<head>",
            "<meta charset='UTF-8'>",
            "<meta name='viewport' content='width=device-width, initial-scale=1.0'>",
            f"<title>{escape(title)}</title>",
            "<style>",
            "*, *::before, *::after { box-sizing: border-box; }",
            "body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 1200px; margin: 0 auto; padding: clamp(1rem, 4vw, 2rem); background: #f5f5f5; color: #1a1a1a; }",
            "h1 { color: #111; font-size: clamp(1.5rem, 4vw, 2.2rem); border-bottom: 3px solid #3b82f6; padding-bottom: 0.6rem; margin: 0 0 0.5rem; }",
            "p.generated { color: #666; font-size: 0.9rem; margin: 0 0 1.5rem; }",
            ".summary { background: white; padding: clamp(1rem, 3vw, 1.5rem); border-radius: 0.75rem; margin: 0 0 1.5rem; display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: clamp(0.75rem, 2vw, 1rem); box-shadow: 0 1px 4px rgba(0,0,0,0.1); }",
            ".stat { text-align: center; padding: 0.5rem; }",
            ".stat-value { font-size: clamp(1.4rem, 4vw, 2rem); font-weight: 800; color: #3b82f6; line-height: 1.1; }",
            ".stat-label { color: #666; font-size: clamp(0.7rem, 1.5vw, 0.85rem); margin-top: 0.3rem; }",
            ".result { background: white; padding: clamp(1rem, 3vw, 1.25rem); margin: 0 0 1rem; border-left: 4px solid #3b82f6; border-radius: 0 0.5rem 0.5rem 0; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }",
            ".claim { font-size: clamp(0.95rem, 2vw, 1.1rem); font-weight: 700; color: #111; margin: 0 0 0.6rem; line-height: 1.4; }",
            ".meta { display: flex; gap: clamp(0.5rem, 2vw, 1rem); flex-wrap: wrap; margin: 0 0 0.75rem; font-size: clamp(0.75rem, 1.5vw, 0.875rem); align-items: center; }",
            ".status { padding: 0.25rem 0.6rem; border-radius: 0.4rem; font-weight: 700; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.04em; white-space: nowrap; }",
            ".status-verified { background: #d1fae5; color: #065f46; }",
            ".status-inaccurate { background: #fed7aa; color: #92400e; }",
            ".status-false { background: #fee2e2; color: #991b1b; }",
            ".status-unverifiable { background: #f3f4f6; color: #374151; }",
            ".confidence { color: #3b82f6; font-weight: 600; }",
            ".explanation { margin: 0 0 0.75rem; color: #444; line-height: 1.7; font-size: clamp(0.875rem, 1.5vw, 1rem); }",
            ".sources { margin: 0.75rem 0 0; padding: 0.75rem 0 0; border-top: 1px solid #e5e7eb; font-size: 0.875rem; }",
            ".sources strong { display: block; margin-bottom: 0.4rem; color: #111; }",
            ".source { display: block; color: #2563eb; text-decoration: none; margin: 0.25rem 0; overflow-wrap: break-word; word-break: break-all; }",
            ".source:hover { text-decoration: underline; }",
            "footer { text-align: center; color: #999; margin: 2rem 0 0; padding: 1.5rem 0 0; border-top: 1px solid #e5e7eb; font-size: 0.85rem; }",
            "@media (max-width: 480px) {",
            "  .summary { grid-template-columns: repeat(2, 1fr); }",
            "  .result { padding: 0.875rem 0.875rem 0.875rem calc(0.875rem - 4px); }",
            "}",
            "</style>",
            "</head>",
            "<body>",
            f"<h1>{escape(title)}</h1>",
            f"<p class='generated'>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>",
            "<div class='summary'>",
            f"<div class='stat'><div class='stat-value'>{stats['total']}</div><div class='stat-label'>Total Claims</div></div>",
            f"<div class='stat'><div class='stat-value' style='color: #10b981;'>{stats['verified']}</div><div class='stat-label'>Verified</div></div>",
            f"<div class='stat'><div class='stat-value' style='color: #f97316;'>{stats['inaccurate']}</div><div class='stat-label'>Inaccurate</div></div>",
            f"<div class='stat'><div class='stat-value' style='color: #ef4444;'>{stats['false']}</div><div class='stat-label'>False</div></div>",
            f"<div class='stat'><div class='stat-value' style='color: #6b7280;'>{stats['unverifiable']}</div><div class='stat-label'>Unverifiable</div></div>",
            f"<div class='stat'><div class='stat-value'>{stats['avg_confidence']}%</div><div class='stat-label'>Avg Confidence</div></div>",
            "</div>",
        ]

        for index, result in enumerate(results, start=1):
            status_class = (
                f"status-{result.get('status', '').lower().replace(' ', '-')}"
            )
            html_lines.extend(
                [
                    "<div class='result'>",
                    f"<div class='claim'>{index}. {escape(str(result.get('claim', '')))}</div>",
                    "<div class='meta'>",
                    f"<span class='status {status_class}'>{escape(str(result.get('status', '')))}</span>",
                    f"<span class='confidence'>Confidence: {result.get('confidence', 0)}%</span>",
                    f"<span>Type: {escape(str(result.get('type', '')))}</span>",
                    "</div>",
                    f"<div class='explanation'>{escape(str(result.get('explanation', '')))}</div>",
                ]
            )

            if result.get("key_finding"):
                html_lines.append(
                    f"<p><strong>Key Finding:</strong> {escape(str(result.get('key_finding')))}</p>"
                )

            if result.get("sources"):
                html_lines.append("<div class='sources'><strong>Sources:</strong>")
                for source in result.get("sources", []):
                    html_lines.append(
                        f"<div><a class='source' href='{escape(str(source.get('url', '#')))}' target='_blank'>"
                        f"{escape(str(source.get('title', 'Source')))}</a></div>"
                    )
                html_lines.append("</div>")

            html_lines.append("</div>")

        html_lines.extend(
            [
                "<footer>",
                "Generated by FactCheck AI - Automated Fact Verification System",
                "</footer>",
                "</body>",
                "</html>",
            ]
        )

        return "\n".join(html_lines), None
