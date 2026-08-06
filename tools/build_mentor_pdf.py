from __future__ import annotations

import html
import re
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    KeepTogether,
    PageBreak,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs/mentor_market_intelligence_manual.md"
OUTPUT = ROOT / "artifacts/mentor_market_intelligence_manual.pdf"
FONT_PATH = "/System/Library/Fonts/STHeiti Medium.ttc"
pdfmetrics.registerFont(TTFont("CJK", FONT_PATH, subfontIndex=0))


def esc(text: str) -> str:
    return html.escape(text, quote=False)


def inline(text: str) -> str:
    text = esc(text)
    text = re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"`([^`]+)`", r"<font name='CJK'>\1</font>", text)
    return text


def header_footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("CJK", 9)
    canvas.setFillColor(colors.HexColor("#5B6770"))
    canvas.drawString(doc.leftMargin, letter[1] - 0.55 * inch, "Market Intelligence · Mentor Guide")
    canvas.drawRightString(letter[0] - doc.rightMargin, 0.52 * inch, f"Page {doc.page}")
    canvas.restoreState()


def build():
    styles = getSampleStyleSheet()
    body = ParagraphStyle("Body", parent=styles["BodyText"], fontName="CJK", fontSize=10.5, leading=15, spaceAfter=6, textColor=colors.HexColor("#0B2545"))
    h1 = ParagraphStyle("H1", parent=body, fontSize=17, leading=22, spaceBefore=16, spaceAfter=9, textColor=colors.HexColor("#2E74B5"), keepWithNext=True)
    h2 = ParagraphStyle("H2", parent=body, fontSize=13.5, leading=18, spaceBefore=12, spaceAfter=7, textColor=colors.HexColor("#2E74B5"), keepWithNext=True)
    h3 = ParagraphStyle("H3", parent=body, fontSize=12, leading=16, spaceBefore=9, spaceAfter=5, textColor=colors.HexColor("#1F4D78"), keepWithNext=True)
    bullet = ParagraphStyle("Bullet", parent=body, leftIndent=18, firstLineIndent=-10, spaceAfter=4)
    code = ParagraphStyle("Code", parent=body, fontName="CJK", fontSize=8.5, leading=11, textColor=colors.HexColor("#0B2545"))
    story = []
    lines = SOURCE.read_text(encoding="utf-8").splitlines()
    in_code = False
    code_lines = []
    table_lines = []

    def flush_table():
        nonlocal table_lines
        if not table_lines:
            return
        rows = []
        for line in table_lines:
            if re.match(r"^\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)+\|?$", line):
                continue
            rows.append([Paragraph(inline(part.strip()), body) for part in line.strip().strip("|").split("|")])
        if rows:
            t = Table(rows, colWidths=[1.9 * inch, 4.45 * inch] if len(rows[0]) == 2 else None, repeatRows=1)
            t.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E8EEF5")),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#B8C6D6")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]))
            story.extend([Spacer(1, 4), t, Spacer(1, 7)])
        table_lines = []

    for line in lines:
        if line.startswith("```"):
            flush_table()
            if in_code:
                parts = []
                for code_line in code_lines:
                    parts.append(inline(code_line))
                p = Paragraph("<br/>".join(parts), code)
                t = Table([[p]], colWidths=[6.5 * inch])
                t.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#E8EEF5")),
                    ("BOX", (0, 0), (-1, -1), 0.3, colors.HexColor("#B8C6D6")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 9),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 9),
                    ("TOPPADDING", (0, 0), (-1, -1), 7),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ]))
                story.extend([Spacer(1, 4), t, Spacer(1, 7)])
                code_lines = []
                in_code = False
            else:
                in_code = True
            continue
        if in_code:
            code_lines.append(line)
            continue
        if line.startswith("|"):
            table_lines.append(line)
            continue
        flush_table()
        if not line.strip():
            story.append(Spacer(1, 3))
            continue
        if line.strip() == "---":
            story.append(Spacer(1, 4))
            continue
        heading = re.match(r"^(#{1,3})\s+(.*)$", line)
        if heading:
            level = len(heading.group(1))
            text = inline(heading.group(2))
            if level == 1 and ("Step" in heading.group(2) or "｜" in heading.group(2)):
                story.append(PageBreak())
            story.append(Paragraph(text, (h1, h2, h3)[level - 1]))
            continue
        if line.startswith(">"):
            text = inline(line[1:].strip()).replace("停止点：", "<b>停止点：</b>")
            t = Table([[Paragraph(text, body)]], colWidths=[6.5 * inch])
            t.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FDECEC" if "停止点" in text else "#E8EEF5")),
                ("LEFTPADDING", (0, 0), (-1, -1), 9),
                ("RIGHTPADDING", (0, 0), (-1, -1), 9),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]))
            story.extend([Spacer(1, 4), t, Spacer(1, 7)])
            continue
        m = re.match(r"^\s*[-*]\s+(.*)$", line)
        if m:
            story.append(Paragraph("• " + inline(m.group(1)), bullet))
            continue
        m = re.match(r"^\s*(\d+)\.\s+(.*)$", line)
        if m:
            story.append(Paragraph(f"{m.group(1)}. {inline(m.group(2))}", bullet))
            continue
        story.append(Paragraph(inline(line.strip()), body))
    flush_table()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(OUTPUT), pagesize=letter, rightMargin=inch, leftMargin=inch, topMargin=inch, bottomMargin=inch)
    doc.build(story, onFirstPage=header_footer, onLaterPages=header_footer)
    print(OUTPUT)


if __name__ == "__main__":
    build()
