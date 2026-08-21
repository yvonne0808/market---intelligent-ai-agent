# Full July Pharma Report Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate and publish the July Pharma monthly report with every article that passes the existing filters.

**Architecture:** Keep complete selected records in report JSON and HTML. Before the DeepSeek request, project each record to the fields needed for report writing, excluding raw body and scraper fields.

**Tech Stack:** Python 3.14, `unittest`, DeepSeek Chat Completions API, static HTML, GitHub Pages.

## Global Constraints

- Do not collect articles or re-run per-article analysis.
- Preserve filtering, ranking, report schema, HTML layout, and public URL.
- `--max-articles 0` means no cap.
- Push only the three July Pharma report artifacts in the nested checkout.

---

### Task 1: Compact the narrative API payload

**Files:**
- Create: `china-wechat-med-phar/tests/test_generate_pharma_monthly_report.py`
- Modify: `china-wechat-med-phar/scripts/generate_pharma_monthly_report.py:182-219`

**Interfaces:**
- Consumes full selected article records and weekly groups.
- Produces `compact_article_for_report(article: dict[str, Any]) -> dict[str, Any]` and `compact_weeks_for_report(weeks: list[dict[str, Any]]) -> list[dict[str, Any]]`.
- `call_deepseek_report` sends projected data, while `save_report_files` keeps the complete records.

- [ ] **Step 1: Write the failing test**

```python
def test_compact_article_keeps_report_fields_and_removes_raw_text():
    article = {
        "article_id": "a-1", "title": "Title", "main_text": "raw body",
        "llm_input_text": "LLM body", "summary_cn": "Summary",
        "published": "2026-07-20T00:00:00Z", "link": "https://example.test/a",
        "relevance_score": 18, "amcor_relevance_score": 5,
        "packaging_relevance": "high", "primary_category": "包装相关",
    }
    compact = module.compact_article_for_report(article)
    assert compact["title"] == "Title"
    assert compact["summary_cn"] == "Summary"
    assert compact["link"] == "https://example.test/a"
    assert "main_text" not in compact
    assert "llm_input_text" not in compact
```

- [ ] **Step 2: Verify the test fails**

Run `.venv/bin/python -m unittest china-wechat-med-phar/tests/test_generate_pharma_monthly_report.py -v`.

Expected: it fails because `compact_article_for_report` is not defined.

- [ ] **Step 3: Implement projection and use it in the request**

```python
COMPACT_REPORT_FIELDS = (
    "article_id", "title", "source_name", "published", "link",
    "primary_category", "secondary_categories", "relevance_score",
    "importance_level", "summary_cn", "one_sentence_takeaway", "key_points",
    "companies", "drugs", "targets_or_mechanisms", "indications",
    "clinical_or_regulatory_stage", "deal_amounts", "market_implication_cn",
    "amcor_relevance_score", "amcor_relevance_reason", "packaging_relevance",
    "packaging_related_keywords", "risks_or_uncertainties", "source_confidence",
    "why_it_matters",
)

def compact_article_for_report(article: dict[str, Any]) -> dict[str, Any]:
    return {field: article.get(field) for field in COMPACT_REPORT_FIELDS if field in article}
```

Build week dictionaries containing `week`, `start_date`, `end_date`, and compact articles. Pass compact articles and weeks to `json.dumps` in `call_deepseek_report`.

- [ ] **Step 4: Verify implementation and payload size**

Run the unittest and a Python check that selects the July articles, asserts 281 records, and prints compact JSON byte size. Expected: the test passes and the compact payload is smaller than the prior 724,927-byte full payload.

- [ ] **Step 5: Commit Task 1**

Run `git add china-wechat-med-phar/scripts/generate_pharma_monthly_report.py china-wechat-med-phar/tests/test_generate_pharma_monthly_report.py` followed by `git commit -m "feat: compact full-month pharma report input"`.

### Task 2: Generate and publish the complete report

**Files:**
- Modify: `china-wechat-med-phar/reports/Pharma/monthly_report_20260701_20260731.md`
- Modify: `china-wechat-med-phar/reports/Pharma/monthly_report_20260701_20260731.json`
- Modify: `china-wechat-med-phar/public_share/reports/pharma/monthly/2026-07/index.html`
- Modify: `china-wechat-med-phar/public_share/reports/pharma/monthly/2026-07/report.json`
- Modify: `china-wechat-med-phar/public_share/reports/pharma/monthly/2026-07/report.md`

**Interfaces:**
- Consumes `articles_analyzed_2026_07_pharma.json` and Task 1 projection functions.
- Produces report JSON with exactly 281 unique article IDs and five weeks totaling 281.

- [ ] **Step 1: Generate uncapped report**

```bash
.venv/bin/python china-wechat-med-phar/scripts/generate_pharma_monthly_report.py \
  --input china-wechat-med-phar/data/analyzed/articles_analyzed_2026_07_pharma.json \
  --start 2026-07-01 --end 2026-07-31 --min-score 12 --max-articles 0
```

- [ ] **Step 2: Render and copy production artifacts**

Run `generate_readable_monthly_html.py` with the generated JSON and output `public_share/reports/pharma/monthly/2026-07/index.html`. Copy the matching Markdown and JSON into that same public directory.

- [ ] **Step 3: Verify generated artifacts**

Use Python assertions for `article_count == 281`, 281 unique IDs, five week groups totaling 281, and period 2026-07-01 through 2026-07-31. Parse the HTML through `html.parser.HTMLParser`.

- [ ] **Step 4: Publish only report artifacts**

Stage exactly `index.html`, `report.json`, and `report.md` in the nested `public_share` checkout. Commit with `Publish complete July 2026 pharma report` and push `origin main`.

- [ ] **Step 5: Verify production page**

Fetch `https://market-insights.github.io/reports/pharma/monthly/2026-07/` and the homepage. Confirm the report page displays the July 1–31 period and the homepage card links to the report.
