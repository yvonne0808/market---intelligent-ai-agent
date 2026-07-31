from __future__ import annotations

import argparse
import html
import re
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    HRFlowable,
    KeepTogether,
    ListFlowable,
    ListItem,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
)


PROJECT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_FONT = "/System/Library/Fonts/STHeiti Light.ttc"
DEFAULT_BOLD_FONT = "/System/Library/Fonts/STHeiti Medium.ttc"


def register_fonts() -> tuple[str, str]:
    regular = "STHeitiLight"
    bold = "STHeitiMedium"
    try:
        pdfmetrics.registerFont(TTFont(regular, DEFAULT_FONT, subfontIndex=0))
        pdfmetrics.registerFont(TTFont(bold, DEFAULT_BOLD_FONT, subfontIndex=0))
    except Exception:
        regular = "Helvetica"
        bold = "Helvetica-Bold"
    return regular, bold


def clean_markdown(text: str) -> str:
    marker = "# Monthly Pharma News Report"
    if marker in text:
        text = text[text.index(marker) :]
    text = text.replace("\u200b", "")
    return text.strip()


def inline_markup(text: str) -> str:
    text = html.escape(text.strip())
    text = re.sub(r"`([^`]+)`", r"<font name='Courier'>\1</font>", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"\*([^*]+)\*", r"<i>\1</i>", text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<link href="\2"><u>\1</u></link>', text)
    return text


def is_table_separator(line: str) -> bool:
    stripped = line.strip()
    if not stripped.startswith("|"):
        return False
    cells = [cell.strip() for cell in stripped.strip("|").split("|")]
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells)


def table_row_to_text(line: str) -> str:
    cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
    cells = [cell for cell in cells if cell and not re.fullmatch(r":?-{3,}:?", cell)]
    return " | ".join(cells)


def build_styles(font_name: str, bold_font_name: str) -> dict[str, ParagraphStyle]:
    sample = getSampleStyleSheet()
    base = ParagraphStyle(
        "BaseCJK",
        parent=sample["Normal"],
        fontName=font_name,
        fontSize=9.4,
        leading=14,
        textColor=colors.HexColor("#20242a"),
        wordWrap="CJK",
        spaceAfter=4,
    )
    return {
        "title": ParagraphStyle(
            "Title",
            parent=base,
            fontName=bold_font_name,
            fontSize=19,
            leading=25,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#14345c"),
            spaceAfter=12,
        ),
        "h2": ParagraphStyle(
            "Heading2",
            parent=base,
            fontName=bold_font_name,
            fontSize=14,
            leading=19,
            textColor=colors.HexColor("#14345c"),
            spaceBefore=12,
            spaceAfter=8,
            keepWithNext=True,
        ),
        "h3": ParagraphStyle(
            "Heading3",
            parent=base,
            fontName=bold_font_name,
            fontSize=11.5,
            leading=16,
            textColor=colors.HexColor("#2f5f8f"),
            spaceBefore=9,
            spaceAfter=5,
            keepWithNext=True,
        ),
        "h4": ParagraphStyle(
            "Heading4",
            parent=base,
            fontName=bold_font_name,
            fontSize=10.2,
            leading=14,
            textColor=colors.HexColor("#3b4856"),
            spaceBefore=6,
            spaceAfter=4,
            keepWithNext=True,
        ),
        "body": base,
        "small": ParagraphStyle(
            "Small",
            parent=base,
            fontSize=8.0,
            leading=11.5,
            textColor=colors.HexColor("#2e3338"),
        ),
        "meta": ParagraphStyle(
            "Meta",
            parent=base,
            fontSize=9,
            leading=13,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#56616f"),
        ),
        "bullet": ParagraphStyle(
            "Bullet",
            parent=base,
            leftIndent=11,
            firstLineIndent=-6,
            bulletIndent=0,
            spaceAfter=3,
        ),
        "table": ParagraphStyle(
            "TableAsText",
            parent=base,
            fontSize=7.6,
            leading=10.5,
            leftIndent=4,
            rightIndent=4,
            backColor=colors.HexColor("#f6f8fb"),
            borderColor=colors.HexColor("#d7dee8"),
            borderWidth=0.4,
            borderPadding=4,
            spaceAfter=3,
        ),
    }


def header_footer(canvas, doc) -> None:
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor("#d9e1ec"))
    canvas.setLineWidth(0.5)
    canvas.line(18 * mm, 284 * mm, 192 * mm, 284 * mm)
    canvas.setFillColor(colors.HexColor("#667080"))
    canvas.setFont("Helvetica", 7.5)
    canvas.drawString(18 * mm, 288 * mm, "Monthly Pharma News Report")
    canvas.drawRightString(192 * mm, 10 * mm, f"Page {doc.page}")
    canvas.restoreState()


def flush_paragraph(buffer: list[str], story: list, styles: dict[str, ParagraphStyle]) -> None:
    if not buffer:
        return
    text = " ".join(part.strip() for part in buffer if part.strip())
    if text:
        story.append(Paragraph(inline_markup(text), styles["body"]))
    buffer.clear()


def markdown_to_story(markdown: str, styles: dict[str, ParagraphStyle]) -> list:
    story: list = []
    paragraph_buffer: list[str] = []
    bullet_items: list[ListItem] = []
    in_code = False
    first_title = True

    def flush_bullets() -> None:
        nonlocal bullet_items
        if bullet_items:
            story.append(ListFlowable(bullet_items, bulletType="bullet", start="circle", leftIndent=14))
            bullet_items = []

    for raw_line in markdown.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()

        if stripped.startswith("```"):
            flush_paragraph(paragraph_buffer, story, styles)
            flush_bullets()
            in_code = not in_code
            continue
        if in_code:
            if stripped:
                story.append(Paragraph(inline_markup(stripped), styles["small"]))
            continue
        if not stripped:
            flush_paragraph(paragraph_buffer, story, styles)
            flush_bullets()
            continue
        if stripped == "---":
            flush_paragraph(paragraph_buffer, story, styles)
            flush_bullets()
            story.append(HRFlowable(width="100%", color=colors.HexColor("#d7dee8"), thickness=0.6))
            story.append(Spacer(1, 5))
            continue
        if is_table_separator(stripped):
            continue
        if stripped.startswith("|"):
            flush_paragraph(paragraph_buffer, story, styles)
            flush_bullets()
            row_text = table_row_to_text(stripped)
            if row_text:
                story.append(Paragraph(inline_markup(row_text), styles["table"]))
            continue
        if stripped.startswith("# "):
            flush_paragraph(paragraph_buffer, story, styles)
            flush_bullets()
            if not first_title:
                story.append(PageBreak())
            story.append(Paragraph(inline_markup(stripped[2:]), styles["title"]))
            first_title = False
            continue
        if stripped.startswith("## "):
            flush_paragraph(paragraph_buffer, story, styles)
            flush_bullets()
            story.append(KeepTogether([Spacer(1, 4), Paragraph(inline_markup(stripped[3:]), styles["h2"])]))
            continue
        if stripped.startswith("### "):
            flush_paragraph(paragraph_buffer, story, styles)
            flush_bullets()
            story.append(Paragraph(inline_markup(stripped[4:]), styles["h3"]))
            continue
        if stripped.startswith("#### "):
            flush_paragraph(paragraph_buffer, story, styles)
            flush_bullets()
            story.append(Paragraph(inline_markup(stripped[5:]), styles["h4"]))
            continue
        bullet_match = re.match(r"^[-*]\s+(.+)$", stripped)
        numbered_match = re.match(r"^\d+\.\s+(.+)$", stripped)
        if bullet_match or numbered_match:
            flush_paragraph(paragraph_buffer, story, styles)
            text = bullet_match.group(1) if bullet_match else numbered_match.group(1)
            bullet_items.append(ListItem(Paragraph(inline_markup(text), styles["bullet"])))
            continue
        paragraph_buffer.append(stripped)

    flush_paragraph(paragraph_buffer, story, styles)
    flush_bullets()
    return story


def convert(markdown_path: Path, pdf_path: Path) -> None:
    font_name, bold_font_name = register_fonts()
    styles = build_styles(font_name, bold_font_name)
    markdown = clean_markdown(markdown_path.read_text(encoding="utf-8"))
    story = markdown_to_story(markdown, styles)
    pdf_path.parent.mkdir(parents=True, exist_ok=True)

    doc = BaseDocTemplate(
        str(pdf_path),
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=markdown_path.stem,
        author="Codex",
    )
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="normal")
    doc.addPageTemplates([PageTemplate(id="page", frames=[frame], onPage=header_footer)])
    doc.build(story)


def main() -> int:
    parser = argparse.ArgumentParser(description="Convert monthly Markdown report to PDF.")
    parser.add_argument("markdown", type=Path)
    parser.add_argument("pdf", type=Path)
    args = parser.parse_args()
    convert(args.markdown, args.pdf)
    print(args.pdf)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
