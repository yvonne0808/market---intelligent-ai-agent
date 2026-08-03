# July 2026 Pharma Concise Review PDF Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate a local, concise July 2026 Pharma review PDF that retains the six user-selected report modules with article-level traceability.

**Architecture:** Add a dedicated Pharma renderer alongside the existing report scripts. It reads only the canonical July Pharma `report.json` and `report.md`, extracts source sections without changing their business claims, writes local HTML, and lets Chromium produce the review PDF. A focused unittest validates structure and counts before export.

**Tech Stack:** Python standard library, Chromium PDF export, `unittest`, HTML/CSS.

## Global Constraints

- Use only the existing July Pharma `report.json` and `report.md` artifacts.
- Do not crawl, invoke DeepSeek, regenerate the full report, or expand sources.
- Do not modify any file inside `china-wechat-med-phar/public_share/`.
- Write review artifacts only to `china-wechat-med-phar/output/reviews/pharma/`.
- Preserve clickable original-source links and Chinese text.
- Do not publish or push website changes.

---

### Task 1: Add tests for the Pharma concise-review structure

**Files:**
- Create: `china-wechat-med-phar/tests/test_generate_pharma_concise_review.py`

**Interfaces:**
- Consumes: `review_html(report: dict[str, Any], markdown: str) -> str` from
  `generate_pharma_concise_review.py` and the July Pharma report artifacts.
- Produces: A regression test that asserts the selected report modules and
  traceability links are present.

- [ ] **Step 1: Write the focused failing test**

```python
def test_pharma_review_keeps_selected_sections() -> None:
    html = module.review_html(REPORT, MARKDOWN)
    self.assertIn("Executive Summary 月度核心总结", html)
    self.assertIn("Top Amcor Opportunities", html)
    self.assertIn("Week-by-Week Digest", html)
    self.assertIn("Drug / Target / Technology Watchlist", html)
    self.assertIn("Packaging & Commercialization Implications for Amcor", html)
    self.assertIn("Appendix: Articles Reviewed", html)
    self.assertEqual(html.count('class="opportunity"'), 10)
    self.assertEqual(html.count('class="week-card"'), 5)
    self.assertGreater(html.count('class="appendix-article"'), 0)
```

- [ ] **Step 2: Run the test and confirm it fails before the renderer exists**

Run:

```bash
.venv/bin/python -m unittest china-wechat-med-phar/tests/test_generate_pharma_concise_review.py -v
```

Expected: FAIL because `generate_pharma_concise_review.py` does not exist.

- [ ] **Step 3: Commit the test after the renderer passes**

```bash
git add china-wechat-med-phar/tests/test_generate_pharma_concise_review.py
git commit -m "test: cover Pharma concise review"
```

### Task 2: Implement the dedicated Pharma renderer

**Files:**
- Create: `china-wechat-med-phar/scripts/generate_pharma_concise_review.py`

**Interfaces:**
- Consumes: `--report-json`, `--report-markdown`, and `--output` command-line
  arguments.
- Produces: `review_html(report, markdown)` and one local HTML file.

- [ ] **Step 1: Implement source-section parsers**

Add helpers that extract:

```python
def executive_summary(markdown: str) -> list[str]: ...
def ranked_opportunities(markdown: str) -> list[dict[str, str]]: ...
def weekly_overviews(markdown: str) -> list[dict[str, str]]: ...
def watchlist(markdown: str) -> list[dict[str, list[str]]]: ...
def packaging_sections(markdown: str) -> list[dict[str, str | list[str]]]: ...
def appendix_articles(report: dict[str, Any]) -> str: ...
```

The parsers must read report sections 1, 2, 3, 6, 7, and the article lists in
the report JSON. They must not generate new summaries or rankings.

- [ ] **Step 2: Render the six selected modules with compact HTML/CSS**

Use the Medical Device concise review visual system: summary cards, ranked
opportunity cards, five weekly cards, compact watchlist groups, concise
packaging cards, and a week-grouped appendix list. Packaging cards must show a
`Needs verification` notice for inferences not explicitly confirmed by an
original source.

- [ ] **Step 3: Add a stable command-line entry point**

```bash
.venv/bin/python china-wechat-med-phar/scripts/generate_pharma_concise_review.py \
  --report-json china-wechat-med-phar/public_share/reports/pharma/monthly/2026-07/report.json \
  --report-markdown china-wechat-med-phar/public_share/reports/pharma/monthly/2026-07/report.md \
  --output china-wechat-med-phar/output/reviews/pharma/2026-07-concise-review.html
```

- [ ] **Step 4: Run the focused test and confirm it passes**

Run:

```bash
.venv/bin/python -m unittest china-wechat-med-phar/tests/test_generate_pharma_concise_review.py -v
```

Expected: PASS with one test.

- [ ] **Step 5: Commit the renderer**

```bash
git add china-wechat-med-phar/scripts/generate_pharma_concise_review.py
git commit -m "feat: render Pharma concise review"
```

### Task 3: Export and validate the local review PDF

**Files:**
- Create: `china-wechat-med-phar/output/reviews/pharma/2026-07-concise-review.html`
- Create: `china-wechat-med-phar/output/reviews/pharma/2026-07-concise-review.pdf`

**Interfaces:**
- Consumes: The HTML written by Task 2 and the shared Chromium executable.
- Produces: A local-only review PDF with preserved source links.

- [ ] **Step 1: Generate local HTML**

Run the Task 2 command and confirm the HTML contains all six selected headings,
10 opportunity cards, five weekly cards, and appendix links.

- [ ] **Step 2: Export with Chromium**

Run Chromium in headless PDF mode against the generated local HTML. Write the
result to `output/reviews/pharma/2026-07-concise-review.pdf`.

- [ ] **Step 3: Validate PDF metadata and visual layout**

Run:

```bash
pdfinfo china-wechat-med-phar/output/reviews/pharma/2026-07-concise-review.pdf
pdftoppm -png -r 144 \
  china-wechat-med-phar/output/reviews/pharma/2026-07-concise-review.pdf \
  /private/tmp/pharma-concise-review/page
```

Inspect every rendered page for clipped Chinese text, overlapping cards,
unwanted blank pages, and readable appendix links.

- [ ] **Step 4: Verify the publication boundary**

Run:

```bash
git status --short
git -C china-wechat-med-phar/public_share status --short
```

Expected: the review output is local and untracked; no tracked
`public_share/` file has changed.

- [ ] **Step 5: Commit the implementation plan only**

```bash
git add docs/superpowers/plans/2026-08-03-pharma-concise-review.md
git commit -m "docs: plan Pharma concise review"
```
