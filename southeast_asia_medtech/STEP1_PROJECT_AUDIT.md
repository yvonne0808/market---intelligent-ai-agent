# Southeast Asia Medical Device Monthly Report Workflow

## Step 1 — Project Audit and Proposed Structure

Audit date: 2026-07-24  
Audited project: `/Users/yvonne/Desktop/forecasting/wechat-rss-data-collector`

> Path note: the requested path used `Desktop/forcasting/...`; the project found in the
> workspace is under `Desktop/forecasting/...`. This document uses the actual path.

## 1. Scope and audit method

This step was a read-only review of the existing collector, website scraper, stored JSON,
report generators, and export code. No website crawl or LLM request was run. No existing
WeChat workflow file was changed, moved, or deleted. The only addition is this audit
document and its parent module directory.

The Git worktree already contained many modified, deleted, and untracked files before this
audit. They were treated as user-owned work and were not altered.

## 2. Existing project structure

The relevant top-level layout is:

```text
wechat-rss-data-collector/
├── config.yaml                     # WeChat/RSS feed and collector configuration
├── website_sources.yaml            # Public website source configuration
├── requirements.txt
├── seen_articles.json              # Persistent WeChat/RSS article identities
├── website_scraper/                # Shared public-site scraping package
│   ├── article_cleaner.py
│   ├── config_loader.py
│   ├── dynamic_scraper.py
│   ├── site_adapters.py
│   ├── utils.py
│   └── web_scraper.py
├── scripts/
│   ├── main.py                     # Existing WeChat/RSS collector
│   ├── run_website_scraper.py
│   ├── prepare_llm_data.py
│   ├── analyze_articles.py
│   ├── analyze_medical_device_articles.py
│   ├── generate_monthly_report.py
│   ├── generate_medical_device_monthly_report.py
│   ├── generate_readable_monthly_html.py
│   ├── convert_monthly_markdown_to_pdf.py
│   └── build_medical_device_procurement_awards_excel.mjs
├── prompts/
│   ├── Medical Device/
│   └── Pharma/
├── data/
│   ├── raw/                        # WeChat/RSS raw article data and CSV/XLSX
│   ├── llm_ready/
│   ├── analyzed/
│   ├── filtered/
│   ├── logs/
│   └── website/
│       ├── raw/
│       └── cleaned/
├── logs/
│   └── website_scraper.log
└── reports/
    ├── Medical Device/
    └── Pharma/
```

There is no established automated test suite in the reviewed project. The existing website
code is already separated from the main WeChat collector at package level, but its
configuration, outputs, log file, and orchestration are still global to the project.

## 3. Existing website scraping design

### 3.1 Unified framework already present

`website_scraper.web_scraper.WebsiteScraper` is the central dispatcher. It supports:

- `static_html` list/detail scraping with pagination;
- `dynamic_js` through Playwright;
- configurable CSS selectors;
- per-source include/exclude keyword rules;
- request timeout, retry, polite randomized delay, headers, and encoding detection;
- source isolation: a failed source produces a failed record and the run continues;
- optional site-specific adapter dispatch before the generic strategy.

`website_scraper.site_adapters` contains special handlers for sites that do not fit the
generic selector path. This is a useful extension point, but adapters should remain the
exception; new country sources should first use declarative configuration and shared
strategies.

`website_scraper.dynamic_scraper.DynamicScraper` provides a Playwright fallback for
JavaScript-rendered pages and writes debug HTML when extraction fails.

`website_sources.yaml` currently mixes pharmaceutical, Chinese medical-device, policy, and
industry sources. It includes source metadata such as category, priority, enabled flag,
strategy, frequency, keyword rules, selectors, and sometimes article limits.

### 3.2 Current website outputs

The website runner writes:

- `data/website/raw/raw_website_articles*.json`
- `data/website/cleaned/cleaned_website_articles*.json`
- `logs/website_scraper.log`

The runner currently truncates raw HTML to a debug sample rather than preserving the full
response in the raw JSON. That controls file size, but is insufficient for fully
reproducible reprocessing if a parser changes later.

## 4. Article data structures

### 4.1 WeChat/RSS raw article

`data/raw/articles.json` is a JSON list. A record currently includes:

```text
source_name, source_category, source_tags, source_priority, feed_url,
title, link, published, article_id, scraped_at, rss_summary,
content_text, content_html, word_count, content_source,
fetch_status, fetch_error, image_count, image_urls, image_ocr_text,
image_fetch_status, image_fetch_error
```

This is WeChat-oriented and should not become the Southeast Asia module's storage contract.

### 4.2 Website raw article

`data/website/raw/raw_website_articles.json` is a JSON list with:

```text
source_name, category, title, publish_date, url, author, body,
crawl_time, status, error_message, raw_html_sample
```

### 4.3 Website cleaned article

`data/website/cleaned/cleaned_website_articles.json` is a JSON list with:

```text
source_type, source_name, category, title, publish_date, url, author,
body, body_length, crawl_time, status, error_message
```

This is the closest existing schema to a reusable normalized record, but it lacks fields
needed for the new workflow: stable record ID, canonical URL, country, language, source
authority/type, discovered time, publication-date precision/timezone, content hash,
retrieval metadata, topic tags, and provenance/version fields.

### 4.4 Analyzed and report records

`data/analyzed/articles_analyzed.json` contains LLM-derived fields including relevance,
importance, categories, summary, key points, companies, regulatory stage, market
implication, packaging relevance, risk, confidence, and report inclusion.

Medical Device monthly report JSON is an object containing:

```text
report_type, start_date, end_date, generated_at, article_count,
weeks, articles, markdown_report
```

The new module can borrow concepts from these schemas, but should define a Southeast Asia
schema and prompt independently instead of feeding new records into existing WeChat
analyzed files.

## 5. Capability audit and reuse assessment

| Capability | Existing implementation | Assessment for new module |
|---|---|---|
| URL normalization | `website_scraper.utils.normalize_url`, `make_absolute_url` | Reuse after extending canonicalization to remove tracking parameters, normalize host/case/default ports, and honor canonical links |
| URL deduplication | Sets in `WebsiteScraper`, list-page logic, dynamic scraper; `seen_articles.json` in WeChat collector | Website dedupe is mainly in-memory/run-local. Build a separate persistent Southeast Asia index; do not share or modify WeChat `seen_articles.json` |
| Cross-source/content dedupe | No robust general implementation found | Add normalized-title and content-hash matching, with canonical URL as the primary identity |
| Date filtering | `scripts/run_website_scraper.py`; pagination accepts target year/month | Reuse the period-filter concept, not the narrow regex. Add multilingual parsing, timezone handling, missing-date states, and explicit inclusive period boundaries |
| HTML extraction | Configured selectors and fallbacks in `web_scraper.py`; BeautifulSoup/lxml cleaning in `article_cleaner.py`; site adapters | Reuse the framework. Extend for English and Southeast Asian pages; keep raw response snapshots so extraction can be replayed |
| JavaScript sites | `dynamic_scraper.py` with Playwright | Reuse only where static HTML, RSS, sitemap, or public API is insufficient |
| Logging | `website_scraper.utils.setup_logger`; main collector logging | Reuse formatting ideas. Use a module-specific logger and log directory, with run/source counts and failure reasons |
| Markdown reports | Medical Device/Pharma monthly generators and prompts | Reuse report grouping/file-writing patterns, but use a new prompt, schema, inputs, and output directory |
| HTML/PDF rendering | Readable monthly HTML and Markdown-to-PDF scripts | Potential later reuse through shared helpers; first keep monthly Markdown/JSON independently reproducible |
| Excel export | WeChat raw export via pandas/openpyxl; procurement-specific `.mjs` workbook | Export capability exists, but there is no generic website-news workbook exporter. Add a module-specific exporter over normalized records rather than calling WeChat save logic |
| LLM analysis | OpenAI-compatible `/chat/completions` calls configured for DeepSeek; article and report prompts | Reuse only through a small provider/client boundary. Never point it at existing WeChat files; cache by article/content hash and analysis version to prevent repeat calls |
| Tests | No established test suite found | Add fixture-based unit/contract tests before expanding source count |

## 6. Functions suitable for reuse

The following are good candidates for import or later extraction into a neutral shared
package:

- `website_scraper.config_loader.load_website_sources`
- `website_scraper.web_scraper.ScraperSettings`
- `website_scraper.web_scraper.WebsiteScraper`
- `website_scraper.article_cleaner.html_to_text`
- `website_scraper.article_cleaner.clean_body`
- `website_scraper.article_cleaner.normalize_chinese_text` only after making the name and
  behavior language-neutral
- `website_scraper.utils.make_absolute_url`
- `website_scraper.utils.normalize_url`
- `website_scraper.utils.stable_id`
- `website_scraper.utils.save_json`
- `website_scraper.utils.setup_logger`, preferably parameterized so logger names do not
  collide
- period grouping and report file-writing concepts from
  `scripts/generate_monthly_report.py`
- tabular export approach from `scripts/main.py`, but not its WeChat-specific fields or
  persistence behavior

Reuse must not import an entry-point `main()` with side effects. The Southeast Asia module
should call pure/shared functions and keep its own CLI, paths, state, prompts, and outputs.

## 7. Recommended independent directory structure

Only the audit document is created in Step 1. The structure below is a design for later
steps, not a statement that all directories/files already exist.

```text
southeast_asia_medtech/
├── README.md
├── config/
│   ├── settings.yaml               # timeouts, pacing, period, output policy
│   ├── sources.yaml                # all source definitions; enabled defaults false
│   └── topics.yaml                 # devices, consumables, sterile packaging taxonomy
├── scrapers/
│   ├── __init__.py
│   ├── runner.py                   # orchestration over shared WebsiteScraper
│   └── adapters/                   # only exceptional source-specific logic
│       └── __init__.py
├── processors/
│   ├── __init__.py
│   ├── schema.py                   # normalized record validation
│   ├── normalize.py
│   ├── dates.py
│   ├── deduplicate.py
│   ├── filter.py
│   └── analyze.py                  # LLM stage, added only when authorized
├── reports/
│   ├── __init__.py
│   ├── monthly.py
│   ├── export_excel.py
│   └── templates/
│       └── monthly_report_prompt.txt
├── data/
│   ├── raw/                        # immutable response/metadata snapshots
│   ├── normalized/                 # schema-valid articles
│   ├── filtered/                   # period/topic selections
│   ├── analyzed/                   # separate cached analysis results
│   └── state/
│       └── article_index.json      # or SQLite after scale review
├── outputs/
│   ├── markdown/
│   ├── json/
│   └── excel/
├── tests/
│   ├── fixtures/                   # saved HTML/JSON; tests require no live crawl
│   ├── test_dates.py
│   ├── test_normalize.py
│   ├── test_deduplicate.py
│   └── test_source_contracts.py
├── logs/
├── cli.py
└── STEP1_PROJECT_AUDIT.md
```

Country should be metadata in `sources.yaml` and normalized records, not a duplicated
scraper directory. Suggested source fields:

```yaml
source_id: sg_hsa_news
source_name: Singapore HSA
country: SG
authority_type: regulator
base_url: ...
list_url: ...
enabled: false
strategy: static_html
language: en
timezone: Asia/Singapore
selectors: {}
topics: [registration, safety_notice]
```

This enables Singapore, Malaysia, Thailand, Indonesia, Vietnam, and the Philippines to use
the same runner. An adapter is added only when configuration cannot express the source.

## 8. Proposed normalized article contract

Before writing production scrapers, define and test one record contract:

```text
schema_version
article_id
source_id
source_name
source_type
country
language
title
url
canonical_url
published_at
published_date_precision
discovered_at
fetched_at
author
body_text
body_length
content_hash
topics
retrieval_status
http_status
error_message
raw_snapshot_path
```

Recommended identity order:

1. normalized canonical URL;
2. source-provided stable ID when available;
3. hash of `source_id + normalized title + published date`;
4. content hash for cross-source duplicate detection.

Duplicate records should be retained as provenance links or aliases in state, not silently
discarded without trace.

## 9. Suggested Step 2–5 development order

### Step 2 — Foundation and two-source proof of concept

- Create the designed package skeleton, independent settings and source config.
- Define normalized schema, CLI boundaries, run manifest, and fixture tests.
- Select only two official sources, preferably one regulator and one procurement/government
  source from one or two countries.
- Reuse the generic static scraper first; add no LLM stage.
- Perform a small bounded validation crawl only after source URLs and robots/terms are
  reviewed.

Exit criterion: raw snapshots and normalized records are produced repeatably without
touching existing WeChat data or state.

### Step 3 — Normalization, persistent dedupe, date/topic filtering

- Implement multilingual date parsing and explicit monthly window logic.
- Add canonical URL and content hash identities with independent persistent state.
- Add taxonomy filters for registration/approval, procurement, production expansion,
  partnerships, consumables, and sterile medical-device packaging.
- Add replay tests using saved fixtures, including changed HTML and duplicate cases.

Exit criterion: rerunning the same fixtures or bounded crawl creates no duplicate normalized
records and performs no analysis calls.

### Step 4 — Analysis and monthly report generation

- Add a Southeast Asia-specific LLM prompt and structured response schema.
- Introduce cache keys based on `article_id + content_hash + prompt_version + model`.
- Add a dry-run mode that shows exactly which new articles would be analyzed.
- Generate independent JSON and Markdown monthly reports; include evidence URLs and source
  confidence.
- Never read or update existing WeChat analyzed JSON as part of this workflow.

Exit criterion: only previously unanalyzed/new-version Southeast Asia records are sent to
the configured provider, and report regeneration from cached analysis makes zero API calls.

### Step 5 — Excel, operational hardening, and controlled expansion

- Export normalized and analyzed views to an independent workbook.
- Add run summaries, failure thresholds, retry/quarantine behavior, and documentation.
- Validate source-specific selectors with fixture contracts.
- Add countries/sources incrementally; enable one at a time after a bounded test.
- Consider SQLite for article state if JSON locking, lookup time, or audit requirements
  become material.

Exit criterion: a documented monthly command produces auditable JSON, Markdown, and Excel
outputs with source/run statistics and no dependency on the WeChat orchestration.

## 10. Technical risks and mitigations

1. **Official sites vary widely in quality and access controls.** Some use JavaScript,
   anti-bot protection, CAPTCHA, PDF notices, or unstable selectors. Prefer RSS, sitemap,
   official API, and static HTML in that order; use Playwright selectively and respect
   robots, terms, pacing, and access restrictions.

2. **Multilingual and local-calendar dates.** Thai Buddhist Era dates, Indonesian/Malay
   month names, Vietnamese text, timezone differences, and missing publication dates can
   break the current regex. Preserve the original date string, parsed value, timezone, and
   precision; quarantine ambiguous dates instead of guessing.

3. **PDF-heavy regulatory/procurement content.** Important details may be in linked PDFs or
   scanned attachments. Treat attachment collection/extraction as a separate processor with
   file hashes and provenance, not as ad hoc HTML body logic.

4. **False duplicates and syndicated content.** URL-only dedupe misses mirrors and tracking
   variants; title-only matching can merge distinct updates. Use layered identity and retain
   duplicate/provenance relationships.

5. **Raw-data reproducibility.** The existing website output keeps only a short HTML sample.
   The new module should retain bounded immutable response snapshots or content-addressed
   files, subject to storage and site-policy constraints.

6. **Schema mismatch with existing WeChat data.** Existing fields use both
   `link/published/content_text` and `url/publish_date/body`. Normalize through an explicit
   adapter; do not mutate legacy records to force a common shape.

7. **LLM cost and accidental re-analysis.** Existing scripts call an OpenAI-compatible
   DeepSeek endpoint directly. Require dry-run selection, deterministic cache keys,
   versioned prompts, separate analyzed storage, and an explicit LLM-enabled command.

8. **Secrets and configuration coupling.** Do not copy `.env` credentials into the new
   module or commit secrets. Read provider settings at runtime and keep source config free
   of credentials.

9. **Logger collisions and global paths.** The existing website logger uses a fixed logger
   name and global output paths. Parameterize logger identity and inject all module paths.

10. **Insufficient regression coverage.** There are no established tests. Use saved fixtures
    and contract tests before adding more countries; do not make CI depend on live official
    sites.

11. **Dirty worktree and evolving existing code.** The project currently contains extensive
    pre-existing changes. Future steps should keep edits inside
    `southeast_asia_medtech/` where possible and review every shared-file change separately.

## 11. Step 1 decision summary

- Build the new workflow as an independent package under `southeast_asia_medtech/`.
- Reuse the existing website scraper through imports/composition, not copied per-site
  scripts.
- Keep independent source config, data, logs, state, prompts, analyzed records, and outputs.
- Do not reuse the WeChat `seen_articles.json` or invoke its analysis/report entry points.
- Start with two official sources and a bounded, non-LLM proof of concept.
- Define schema, fixtures, dedupe, and dates before country expansion.
- Stop after this audit and await approval before Step 2.
