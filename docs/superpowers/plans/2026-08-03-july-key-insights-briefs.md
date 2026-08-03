# July Key Insights Briefs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish two independent three-page July executive briefs, one each for Pharma and Medical Device, without altering full reports.

**Architecture:** A focused static brief generator will read the existing July report JSON, select an explicitly curated set of high-value article records, and render concise card-style HTML with direct source links. Chromium exports each HTML brief to a matching PDF.

**Tech Stack:** Python 3.14, static HTML, Chromium Headless Shell, Poppler, GitHub Pages.

## Global Constraints

- Preserve all full reports, existing PDFs, and analysis data.
- Use only current structured report data and original article links.
- Do not call the LLM or collect new articles.
- Each brief has three sections: five takeaways, four to six opportunities, watchlist and references.
- Pure policy/regulation items do not occupy a core slot without a stated business consequence.

---

### Task 1: Build reusable concise-brief renderer

**Files:**
- Create: `china-wechat-med-phar/scripts/generate_key_insights_brief.py`
- Create: `china-wechat-med-phar/tests/test_generate_key_insights_brief.py`

**Interfaces:**
- Consumes: `report_json: Path`, `report_type: str`, `output_html: Path`, and a curated list of article IDs.
- Produces: `build_brief_html(report, article_ids, report_type) -> str` with three brief sections and source links.

- [ ] **Step 1: Write a failing HTML structure test**

```python
def test_build_brief_has_three_sections_and_source_link():
    html = module.build_brief_html(sample_report, ["a-1"], "Pharma")
    self.assertIn("Five Key Takeaways", html)
    self.assertIn("Top Opportunities", html)
    self.assertIn("Watchlist & References", html)
    self.assertIn('href="https://example.test/article"', html)
```

- [ ] **Step 2: Verify the test fails**

Run `.venv/bin/python -m unittest china-wechat-med-phar/tests/test_generate_key_insights_brief.py -v`.

Expected: failure because `build_brief_html` is not defined.

- [ ] **Step 3: Implement the minimal renderer**

Render concise CSS cards using each selected article's title, source, date,
summary/takeaway, score badges, company chips, and original URL. Use one
printed A4-compatible layout and page-break CSS after each of the three
sections.

- [ ] **Step 4: Run the unit test**

Run the same unittest. Expected: PASS.

- [ ] **Step 5: Commit renderer and test**

Run `git add china-wechat-med-phar/scripts/generate_key_insights_brief.py china-wechat-med-phar/tests/test_generate_key_insights_brief.py` then `git commit -m "feat: generate July key insights briefs"`.

### Task 2: Curate, render, and inspect two July briefs

**Files:**
- Create: `china-wechat-med-phar/public_share/reports/pharma/monthly/2026-07/key-insights.html`
- Create: `china-wechat-med-phar/public_share/reports/pharma/monthly/2026-07/key-insights.pdf`
- Create: `china-wechat-med-phar/public_share/reports/medical-device/monthly/2026-07/key-insights.html`
- Create: `china-wechat-med-phar/public_share/reports/medical-device/monthly/2026-07/key-insights.pdf`

**Interfaces:**
- Consumes current July report JSON and Task 1 renderer.
- Produces two brief PDFs of three pages each and matching readable HTML pages.

- [ ] **Step 1: Select evidence articles**

Select four to six top business-opportunity articles and eight to twelve total
reference articles for each domain. Exclude policy-only articles from the core
set.

- [ ] **Step 2: Generate both brief HTML files**

Run the renderer once for the current Pharma July JSON and once for the Medical
Device July JSON.

- [ ] **Step 3: Export both HTML briefs to PDF**

Use the local Chromium Headless Shell with background printing enabled. Output
the two `key-insights.pdf` files alongside the HTML briefs.

- [ ] **Step 4: Verify content and layout**

Assert each HTML has the three required section headings and eight to twelve
original source URLs. Use `pdfinfo` to require exactly three pages for each
PDF. Render each PDF page to PNG and visually inspect the complete briefs.

### Task 3: Link and publish concise briefs

**Files:**
- Modify: `china-wechat-med-phar/public_share/index.html`

**Interfaces:**
- Produces two homepage `Key Insights Brief` links, each pointing to its July
  report's `key-insights.html`.

- [ ] **Step 1: Add concise-brief links**

Add one `Key Insights Brief` action link to each July card, beside the current
PDF link.

- [ ] **Step 2: Commit only public artifacts**

Stage the two HTML briefs, two PDF briefs, and `index.html` in the nested
checkout. Commit with `Publish July key insights briefs` and push `origin main`.

- [ ] **Step 3: Verify production**

Fetch both public brief URLs and homepage links. Confirm the PDF links return
`application/pdf` and the HTML briefs contain their three section headings.
