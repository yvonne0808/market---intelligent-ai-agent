# July Medical Device Concise Review PDF Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a local-only concise July Medical Device review PDF that preserves the original Executive Summary, ten ranked opportunities, weekly overviews, and combined sections 7.1–7.4.

**Architecture:** Add a dedicated renderer rather than changing the existing general key-insights renderer. The renderer consumes the existing `report.json` and `report.md`, extracts only the approved source sections, writes review-only HTML and PDF files below `output/`, and never writes to `public_share/`.

**Tech Stack:** Python standard library (`json`, `html`, `pathlib`, `re`), project `.venv`, local Chromium headless-shell for HTML-to-PDF export, Poppler `pdfinfo`/`pdftoppm`, `unittest`.

## Global Constraints

- Use only the existing July Medical Device `report.json` and `report.md` as source material.
- Do not run a crawler, call an LLM, regenerate the full report, or add sources.
- Preserve the seven Executive Summary bullets verbatim.
- Preserve the existing Monthly Amcor Relevance Ranking order for all ten opportunities.
- Keep all output outside `china-wechat-med-phar/public_share/`.
- Do not commit or push any `public_share/` change, and do not run a network publication command.
- Validate seven summary bullets, ten opportunities, five weekly summaries, four integrated-signal subsections, source links, and rendered PDF layout.

---

### Task 1: Build an isolated Medical Device review renderer

**Files:**
- Create: `china-wechat-med-phar/scripts/generate_medical_device_concise_review.py`
- Create: `china-wechat-med-phar/tests/test_generate_medical_device_concise_review.py`

**Interfaces:**
- Consumes: `report_json: dict[str, Any]`, `report_markdown: str`.
- Produces: `build_review_html(report_json, report_markdown) -> str` and CLI output at a caller-provided `--output` path.
- Input CLI: `--report-json PATH --report-markdown PATH --output PATH`.

- [ ] **Step 1: Write the failing extraction/rendering test**

```python
def test_build_review_preserves_required_sections():
    html = module.build_review_html(SAMPLE_JSON, SAMPLE_MARKDOWN)
    assert html.count('class="summary-item"') == 7
    assert html.count('class="opportunity"') == 10
    assert html.count('class="week-card"') == 5
    assert "Commercialization and volume" in html
    assert "Capacity and supply chain" in html
    assert "Packaging and sterilization evidence" in html
    assert "Follow-up opportunities" in html
    assert 'href="https://example.test/1"' in html
```

- [ ] **Step 2: Run the new test and verify it fails**

Run:

```bash
.venv/bin/python -m unittest china-wechat-med-phar/tests/test_generate_medical_device_concise_review.py -v
```

Expected: `ModuleNotFoundError` or missing `build_review_html`.

- [ ] **Step 3: Implement minimal source extraction helpers**

```python
def markdown_section(markdown: str, start: str, end: str) -> str:
    start_index = markdown.index(start)
    end_index = markdown.index(end, start_index)
    return markdown[start_index:end_index]

def numbered_bullets(section: str) -> list[str]:
    return [line.removeprefix("- ").strip() for line in section.splitlines() if line.startswith("- ")]
```

Use these helpers to extract the Executive Summary, the five `本周概览`
paragraphs, and the sections headed `### 7.1`, `### 7.2`, `### 7.3`, and
`### 7.4`. Parse the first ten data rows of the Markdown table between
`## 2. Monthly Amcor Relevance Ranking` and `## 3. Week-by-Week News Digest`;
the table's title, source/date, rationale, and final URL column are the
authoritative opportunity-card fields.

- [ ] **Step 4: Implement `build_review_html`**

Render the fixed content structure in this order:

```html
<section id="executive-summary">...</section>
<section id="top-opportunities">...</section>
<section id="weekly-overview">...</section>
<section id="integrated-signals">...</section>
<section id="reference-note">...</section>
```

Apply blue-card CSS, `break-inside: avoid` to cards, and print CSS. Include
the original article URL on every opportunity card with `target="_blank"`
and `rel="noopener"`.

- [ ] **Step 5: Run the test and verify it passes**

Run:

```bash
.venv/bin/python -m unittest china-wechat-med-phar/tests/test_generate_medical_device_concise_review.py -v
```

Expected: all tests pass.

- [ ] **Step 6: Commit the renderer and tests**

```bash
git add china-wechat-med-phar/scripts/generate_medical_device_concise_review.py \
  china-wechat-med-phar/tests/test_generate_medical_device_concise_review.py
git commit -m "feat: render medical device concise review"
```

### Task 2: Produce the local review HTML and PDF

**Files:**
- Create: `china-wechat-med-phar/output/reviews/medical-device/2026-07-concise-review.html`
- Create: `china-wechat-med-phar/output/reviews/medical-device/2026-07-concise-review.pdf`

**Interfaces:**
- Consumes: Task 1 CLI and existing July source artifacts.
- Produces: a local-only HTML source and printable PDF; neither path is inside `public_share/`.

- [ ] **Step 1: Generate review-only HTML**

Run:

```bash
.venv/bin/python china-wechat-med-phar/scripts/generate_medical_device_concise_review.py \
  --report-json china-wechat-med-phar/public_share/reports/medical-device/monthly/2026-07/report.json \
  --report-markdown china-wechat-med-phar/public_share/reports/medical-device/monthly/2026-07/report.md \
  --output china-wechat-med-phar/output/reviews/medical-device/2026-07-concise-review.html
```

- [ ] **Step 2: Check rendered HTML content mechanically**

Run a Python assertion script that confirms: seven `summary-item` elements,
ten `opportunity` elements, five `week-card` elements, headings for all four
integrated-signal subsections, and ten non-empty original-source links.

- [ ] **Step 3: Export the local PDF**

Run local Chromium headless-shell with `--headless --no-pdf-header-footer`
and `--print-to-pdf` pointing to
`china-wechat-med-phar/output/reviews/medical-device/2026-07-concise-review.pdf`.

- [ ] **Step 4: Verify PDF metadata and visual rendering**

Run:

```bash
pdfinfo china-wechat-med-phar/output/reviews/medical-device/2026-07-concise-review.pdf
pdftoppm -png -r 120 \
  china-wechat-med-phar/output/reviews/medical-device/2026-07-concise-review.pdf \
  /private/tmp/medical-device-concise-review/page
```

Inspect every generated PNG page. Require no clipped Chinese text, blank
intermediate pages, split cards, or spurious colored blocks.

- [ ] **Step 5: Verify isolation and final status**

Run:

```bash
git -C china-wechat-med-phar/public_share status --short
git status --short
```

Confirm no tracked `public_share/` path changed and no push was run. Leave
the review files local; do not stage them for the public-site repository.

- [ ] **Step 6: Commit only source code and tests if they are cleanly separated**

```bash
git add china-wechat-med-phar/scripts/generate_medical_device_concise_review.py \
  china-wechat-med-phar/tests/test_generate_medical_device_concise_review.py
git commit -m "test: verify medical device concise review"
```

Do not commit the generated review PDF unless the user explicitly asks to
version it.
