# Mentor Market Intelligence Manual Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Create a Chinese, zero-programming-background operating manual for a mentor using the existing Market Intelligence workflow on macOS through Codex Desktop, delivered as editable DOCX and shareable PDF.

**Architecture:** Author one structured content source in Markdown plus a deterministic Python `python-docx` builder. The builder applies the `compact_reference_guide` tokens, real Word headings/lists/tables, code/caution/success callouts, step page breaks, header/footer, and page numbers. Render the DOCX with the documents skill renderer, inspect every page PNG, then deliver only the final DOCX and PDF.

**Tech Stack:** Markdown, Python 3, `python-docx`, documents skill `render_docx.py`, LibreOffice headless conversion, Poppler PNG rendering.

## Global Constraints

- Target reader is a non-technical mentor on macOS using Codex Desktop.
- Start state assumes the project is already cloned, software installed, WeWe RSS feeds configured, and DeepSeek API key configured locally.
- Keep each Step independent: collect, analyze, report generation, and publishing are not automatically chained.
- Date examples use an inclusive start and inclusive end, e.g. `2026-08-01` through `2026-08-31`; tell the mentor to replace both values.
- Keep Pharma and Medical Device inputs, analyzed outputs, and report outputs separate.
- Never instruct the mentor to commit `.env`, API keys, WeWe RSS SQLite data, or local raw data to GitHub.
- Use project-relative paths in the manual; explain absolute-path differences only when necessary.
- Do not ship `TODO`, `TBD`, unresolved placeholders, or commands that do not exist in the repository.

---

### Task 1: Lock the command and output map

**Files:**
- Read: `china-wechat-med-phar/MENTOR_SETUP.md`
- Read: `china-wechat-med-phar/README.md`
- Read: `docs/china-wechat-monthly-report-workflow.md`
- Read: `china-wechat-med-phar/scripts/main.py`
- Read: `china-wechat-med-phar/scripts/prepare_llm_data.py`
- Read: `china-wechat-med-phar/scripts/analyze_articles.py`
- Read: `china-wechat-med-phar/scripts/analyze_medical_device_articles.py`
- Read: `china-wechat-med-phar/scripts/generate_monthly_report.py`
- Read: `china-wechat-med-phar/scripts/generate_medical_device_monthly_report.py`
- Create: `docs/mentor_manual_command_map.md`

**Interfaces:**
- Produces a verified map of exact Codex prompts, shell commands, date flags, input paths, output paths, and success markers for Tasks 2–4.

- [ ] **Step 1: Extract exact CLI interfaces**

Run:

```bash
cd /Users/yvonne/Desktop/forecasting/monthly-report-library
../.venv/bin/python china-wechat-med-phar/scripts/main.py --help
../.venv/bin/python china-wechat-med-phar/scripts/prepare_llm_data.py --help
../.venv/bin/python china-wechat-med-phar/scripts/analyze_articles.py --help
../.venv/bin/python china-wechat-med-phar/scripts/analyze_medical_device_articles.py --help
../.venv/bin/python china-wechat-med-phar/scripts/generate_monthly_report.py --help
../.venv/bin/python china-wechat-med-phar/scripts/generate_medical_device_monthly_report.py --help
```

Expected: each command exits successfully or, if a script has no help flag, its parser and defaults are recorded from source without running a network/API action.

- [ ] **Step 2: Write the command map**

Record, for each flow, the exact command, date semantics, input JSON, analyzed JSON, Markdown/JSON/HTML/PDF outputs, and a plain-language success marker. Explicitly mark any command that calls DeepSeek or WeWe RSS.

- [ ] **Step 3: Verify no scope contradiction**

Run:

```bash
rg -n -F -e 'TODO' -e 'TBD' docs/mentor_manual_command_map.md
git diff --check -- docs/mentor_manual_command_map.md
```

Expected: no unresolved placeholders and no whitespace errors.

- [ ] **Step 4: Commit**

```bash
git add docs/mentor_manual_command_map.md
git commit -m "docs: map mentor manual commands"
```

### Task 2: Author the mentor-facing content

**Files:**
- Read: `docs/mentor_manual_command_map.md`
- Create: `docs/mentor_market_intelligence_manual.md`

**Interfaces:**
- Consumes the command map from Task 1.
- Produces one complete Chinese content source that a builder can render without inventing commands.

- [ ] **Step 1: Write the opening and safety section**

Explain GitHub, Codex, WeWe RSS, DeepSeek, and the local report project in plain language. State the starting assumptions, the “one Step at a time” rule, and the prohibition on exposing `.env`, API keys, database files, or local raw data.

- [ ] **Step 2: Write Step 1 and Step 2**

Step 1 must give a copyable Codex prompt to inspect the existing checkout, run `git pull`, show the updated commit, and stop. Step 2 must give a copyable prompt to start/verify WeWe RSS, open `http://localhost:8001`, pause for the mentor to scan with WeChat, and stop after login/source visibility is confirmed.

- [ ] **Step 3: Write Step 3 and Step 4**

Step 3 must distinguish refreshing WeWe RSS from changing the RSS database and require a visible latest-date check. Step 4 must ask for explicit `START_DATE` and `END_DATE`, use inclusive date language, run collection/LLM-ready preparation, preserve both streams, report counts, and stop before analysis.

- [ ] **Step 4: Write Step 5 and Step 6**

Step 5 must first show candidate counts, then give separate Pharma and Medical Device analysis prompts, explain incremental saving and resumability, and require a stop after analysis. Step 6 must only run after the mentor confirms analysis completeness, generate separate monthly outputs, list expected files, and include local review checks.

- [ ] **Step 5: Write the quick checklist and troubleshooting**

Add a one-page monthly checklist, date replacement template, glossary, and troubleshooting prompts for missing project, localhost failure, unchanged RSS dates, empty date range, API/network errors, interrupted analysis, and incomplete report.

- [ ] **Step 6: Run content audits**

Run:

```bash
rg -n -F -e 'TODO' -e 'TBD' -e 'your_' -e 'REPLACE_ME' docs/mentor_market_intelligence_manual.md
git diff --check -- docs/mentor_market_intelligence_manual.md
```

Expected: only intentional date placeholders such as `START_DATE` and `END_DATE` remain; no unresolved implementation placeholders.

- [ ] **Step 7: Commit**

```bash
git add docs/mentor_market_intelligence_manual.md
git commit -m "docs: author mentor market intelligence manual"
```

### Task 3: Build the DOCX and PDF

**Files:**
- Read: `docs/mentor_market_intelligence_manual.md`
- Create: `tools/build_mentor_manual.py`
- Create: `artifacts/mentor_market_intelligence_manual.docx`
- Create: `artifacts/mentor_market_intelligence_manual.pdf`

**Interfaces:**
- Builder input: the Markdown content source.
- Builder outputs: a DOCX with explicit page geometry/styles and a PDF generated from the rendered DOCX.

- [ ] **Step 1: Resolve design tokens in the builder**

Set US Letter portrait, 1-inch margins, header/footer distance 0.492 inch, Calibri 11 pt body, 1.25 line spacing, `#2E74B5` headings, `#1F4D78` Heading 3, fixed 9360-DXA tables with 120-DXA indent and 80/80/120/120 cell margins. Add real heading styles, real numbering, a fixed-width code style, caution/success callout styles, running header, and page-number footer.

- [ ] **Step 2: Implement Markdown-to-DOCX components**

Implement focused functions for title/cover, headings, numbered and bulleted lists, code blocks, caution/success callouts, two-column “操作/结果” tables, page breaks before each Step, and inline code. Do not use Unicode bullets as fake list markers or tables as page-layout hacks.

- [ ] **Step 3: Build and render**

Run:

```bash
mkdir -p artifacts/mentor_manual_render
env TMPDIR=/private/tmp python /Users/yvonne/.codex/plugins/cache/openai-primary-runtime/documents/26.805.11740/skills/documents/render_docx.py \
  artifacts/mentor_market_intelligence_manual.docx \
  --output_dir artifacts/mentor_manual_render \
  --emit_pdf
```

Expected: a DOCX, a non-empty PDF, and `page-*.png` files for every page.

- [ ] **Step 4: Commit**

```bash
git add tools/build_mentor_manual.py artifacts/mentor_market_intelligence_manual.docx artifacts/mentor_market_intelligence_manual.pdf
git commit -m "docs: build mentor manual artifacts"
```

### Task 4: Render QA and final handoff

**Files:**
- Read: `artifacts/mentor_manual_render/page-*.png`
- Modify: `tools/build_mentor_manual.py` and/or `docs/mentor_market_intelligence_manual.md` if QA finds defects.

**Interfaces:**
- Consumes final DOCX/PDF and all rendered page PNGs.
- Produces a visually verified pair of final artifacts and a short QA record.

- [ ] **Step 1: Inspect every rendered page**

Use `view_image` at high detail for every page PNG. Check Chinese glyphs, code-box wrapping, heading/page-break behavior, table widths, clipped text, overlaps, footer page numbers, and large blank gaps.

- [ ] **Step 2: Run structural audits**

Run:

```bash
python /Users/yvonne/.codex/plugins/cache/openai-primary-runtime/documents/26.805.11740/skills/documents/scripts/style_lint.py artifacts/mentor_market_intelligence_manual.docx
python /Users/yvonne/.codex/plugins/cache/openai-primary-runtime/documents/26.805.11740/skills/documents/scripts/section_audit.py artifacts/mentor_market_intelligence_manual.docx
rg -n -F -e 'TODO' -e 'TBD' -e 'REPLACE_ME' artifacts docs/mentor_market_intelligence_manual.md
```

Expected: no unresolved placeholders; page and style audits report the intended Letter geometry and explicit styles.

- [ ] **Step 3: Iterate if needed**

If any page has clipping, overlap, unreadable code, or broken tables, edit the content source or builder, rebuild, rerender, and inspect the complete page set again. Do not deliver a PDF based only on text extraction.

- [ ] **Step 4: Final verification**

Run:

```bash
test -s artifacts/mentor_market_intelligence_manual.docx
test -s artifacts/mentor_market_intelligence_manual.pdf
find artifacts/mentor_manual_render -name 'page-*.png' -size +0c | sort
```

Expected: both deliverables and every page image are non-empty.

- [ ] **Step 5: Commit QA changes**

```bash
git add docs/mentor_market_intelligence_manual.md tools/build_mentor_manual.py artifacts/mentor_market_intelligence_manual.docx artifacts/mentor_market_intelligence_manual.pdf
git commit -m "docs: verify mentor manual layout"
```
