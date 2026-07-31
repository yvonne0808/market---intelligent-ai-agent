# Step 5 — Monthly Report MVP and Excel Detail

Example month: `2026-07`  
Generated: 2026-07-24

## Scope

Step 5 generates an archived monthly Markdown report, summary JSON, and four-sheet Excel
workbook from Step 4 rule-filtered articles. It is fully functional without an LLM.

No API key is read, no model/provider is instantiated, no network request occurs, and no
existing WeChat article is analyzed.

## Repeatable command

From the existing project root:

```bash
.venv/bin/python -m southeast_asia_medtech.reports.generate_monthly_report \
  --month 2026-07
```

Optional alternate inputs:

```bash
.venv/bin/python -m southeast_asia_medtech.reports.generate_monthly_report \
  --month 2026-07 \
  --input /absolute/path/articles_filtered.json \
  --scored-input /absolute/path/articles_scored.json
```

The month must use `YYYY-MM`. Rerunning the same month deterministically replaces that
month's three report files without creating duplicate rows.

Excel generation uses the bundled `@oai/artifact-tool` runtime. If executed outside the
current Codex environment, set:

```text
CODEX_NODE_EXECUTABLE=/absolute/path/to/bundled/node
CODEX_NODE_MODULES=/absolute/path/to/bundled/node_modules
```

## Archived output

```text
southeast_asia_medtech/reports/2026-07/
├── southeast_asia_medtech_monthly_report.md
├── southeast_asia_medtech_articles.xlsx
└── report_summary.json
```

Only these three deliverables remain in the month directory. QA renders and inspection logs
are stored under `southeast_asia_medtech/tmp/`, not mixed with archived reports.

## Markdown report behavior

The report contains:

1. Executive Summary
2. Regulatory and Approval Updates
   - Singapore
   - Malaysia
3. Medical Device and Consumables Market Updates
4. Procurement and Commercialization
5. Manufacturing, Capacity and Supply Chain
6. Financing, M&A and Partnerships
7. Medical Device Packaging Signals
8. Key Companies to Watch
9. Source List

Every empty section displays:

```text
No material updates identified during this reporting period.
```

Article descriptions are direct source extracts truncated at a word boundary. The generator
does not paraphrase or invent facts.

The current MDA procurement result is routed using explicit source-language evidence:
`SEBUT HARGA` together with `YANG BERJAYA` or `HARGA SETUJU TERIMA`. This deterministic
mapping is recorded as `procurement_contract_award`.

## Sorting

Article order follows:

1. official registration/approval;
2. government procurement/award;
3. factory/production/capacity;
4. export/overseas certification;
5. distribution/channel/supply chain;
6. financing/acquisition/BD;
7. commercialization;
8. consumables;
9. packaging/general updates.

Within that order, records sort by device relevance descending, packaging relevance
descending, and publication date descending.

## Excel workbook

The workbook contains exactly four sheets.

### All Articles

Contains the Step 4 automatic match set for the selected month:

```text
month, country, title, source, published_date, business_categories,
device_relevance_score, packaging_relevance_score, priority_level,
matched_keywords, summary_placeholder, url
```

`summary_placeholder` is a direct extract from the source body, not an LLM summary.

### Packaging Relevant

Contains rows with `packaging_relevance_score >= 5` and adds:

```text
packaging_material, packaging_format, sterilization_method,
sterile_barrier_relevance, ISO_11607_relevance,
possible_business_implication
```

Materials, formats, sterilization methods, and ISO relevance are populated only when the
exact evidence is present. The business-implication field is blank in the current example
because the source does not explicitly state a commercial implication.

### Companies

Contains:

```text
company_name, country, event_type, number_of_mentions, related_articles,
packaging_relevance, latest_update_date
```

Company names are extracted only from explicit labels such as `Local Company:` or tightly
bounded legal suffixes such as `Pte Ltd` and `Sdn. Bhd.`. Authority names and ordinary
sentences are excluded.

### Sources

Contains:

```text
source_name, country, organization, number_of_articles, successful_scrapes,
failed_scrapes, latest_article_date
```

This sheet reads the same month's complete Step 4 scored records so failed scrapes remain
visible even though they are not report candidates.

## Current example results

For `2026-07`:

- matched report articles: 3;
- Singapore: 1;
- Malaysia: 2;
- regulatory updates: 1;
- procurement updates: 1;
- packaging signals: 1;
- packaging-relevant Excel rows: 1;
- companies identified from explicit evidence: 2;
- sources: 2;
- LLM used: false.

The two companies are `BD Holdings Pte Ltd` and
`PINNACLE CONCEPTS SDN. BHD.`.

## LLM extension point

`reports/llm_interface.py` exposes:

```python
def generate_llm_summary(article, provider=None):
    ...
```

In Step 5 it always returns an empty string and does not access the provider. A test passes
an object that raises on every attribute access, confirming the provider is never touched.

## Validation

Run all tests:

```bash
.venv/bin/python -m unittest discover -s southeast_asia_medtech/tests -v
```

The suite contains 31 tests, including:

- month validation;
- required empty-section text;
- Malay procurement routing;
- explicit and absent packaging metadata;
- company extraction and authority-prefix removal;
- an LLM provider non-access test;
- all prior configuration, scraper, dedupe, and filtering checks.

The workbook was also:

- inspected across all four data ranges;
- scanned for `#REF!`, `#DIV/0!`, `#VALUE!`, `#NAME?`, and `#N/A`;
- rendered to PNG for a visual pass on every sheet;
- checked for readable wrapped headers, dates, scores, filters, and conditional formatting.

No formula errors or visual blockers were found.

## Final scope checks

- Existing WeChat workflow files were not modified.
- No existing WeChat article was re-analyzed.
- No LLM/API was called or configured.
- HSA and MDA remain independent configured sources.
- Scraper source failures remain isolated by the Step 3 source loop.
- Reports archive under `reports/YYYY-MM/`.
- Additional countries can later be added through `config/sources.yaml` and parser adapters,
  but Step 5 adds none.

Step 5 stops with this MVP.
