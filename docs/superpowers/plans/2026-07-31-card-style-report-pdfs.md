# Card-Style Report PDFs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Export the July Medical Device and Pharma card-style HTML reports as publishable A4 PDFs.

**Architecture:** Add a narrow headless-browser exporter that accepts an input HTML path and output PDF path. It opens all weekly news details before printing, preserving the existing static report visual design without changing report data or HTML.

**Tech Stack:** Python 3.14, Playwright, `unittest`, Poppler, GitHub Pages.

## Global Constraints

- Do not alter report data, LLM output, article selection, or report HTML.
- Preserve cards, badges, weekly sections, and Other Important News lists.
- Export A4 pages with CSS background graphics enabled.
- Publish only the two existing July `report.pdf` files.

---

### Task 1: Add HTML-card PDF exporter

**Files:**
- Create: `china-wechat-med-phar/scripts/export_card_report_pdf.py`
- Create: `china-wechat-med-phar/tests/test_export_card_report_pdf.py`

**Interfaces:**
- Consumes: `input_html: Path`, `output_pdf: Path`.
- Produces: `export_card_report_pdf(input_html: Path, output_pdf: Path) -> None`.

- [ ] **Step 1: Write the failing test**

```python
def test_export_rejects_missing_html(tmp_path):
    with self.assertRaises(FileNotFoundError):
        module.export_card_report_pdf(tmp_path / "missing.html", tmp_path / "report.pdf")
```

- [ ] **Step 2: Verify the test fails**

Run `.venv/bin/python -m unittest china-wechat-med-phar/tests/test_export_card_report_pdf.py -v`.

Expected: failure because `export_card_report_pdf` is not defined.

- [ ] **Step 3: Implement the exporter**

```python
def export_card_report_pdf(input_html: Path, output_pdf: Path) -> None:
    if not input_html.exists():
        raise FileNotFoundError(input_html)
    # Chromium opens input_html.as_uri(), opens details.other-news, then prints A4.
```

Use `page.pdf(format="A4", print_background=True, margin={"top": "12mm", "right": "12mm", "bottom": "12mm", "left": "12mm"})` and write the PDF to `output_pdf`.

- [ ] **Step 4: Verify the test passes**

Run the same unittest. Expected: PASS.

- [ ] **Step 5: Commit Task 1**

Run `git add china-wechat-med-phar/scripts/export_card_report_pdf.py china-wechat-med-phar/tests/test_export_card_report_pdf.py` followed by `git commit -m "feat: export card-style report PDFs"`.

### Task 2: Render, inspect, and publish July PDFs

**Files:**
- Modify: `china-wechat-med-phar/public_share/reports/medical-device/monthly/2026-07/report.pdf`
- Modify: `china-wechat-med-phar/public_share/reports/pharma/monthly/2026-07/report.pdf`

**Interfaces:**
- Consumes both report `index.html` files and Task 1 exporter.
- Produces A4 PDFs that show the report card layout.

- [ ] **Step 1: Export both PDFs**

Run the exporter once for each July `index.html`, writing to its matching `report.pdf` path.

- [ ] **Step 2: Inspect PDF metadata and rendering**

Use `pdfinfo` to confirm A4 page size and render first/final pages with `pdftoppm -png`. Visually inspect the output for cards, page breaks, headers, and legibility.

- [ ] **Step 3: Publish only PDFs**

Stage exactly the two public PDF files in `china-wechat-med-phar/public_share`, commit with `Replace July PDFs with card-style exports`, and push `origin main`.

- [ ] **Step 4: Verify public downloads**

Fetch both public PDF URLs and require HTTP 200 with `content-type: application/pdf`.
