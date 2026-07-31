# July 2026 Website Collection

This workflow collects July 2026 website articles from the 17 enabled source
families without calling an LLM or overwriting the earlier five-item access tests.

## Commands

```bash
.venv/bin/python -m southeast_asia_medtech.scrapers.collect_monthly_articles \
  --month 2026-07

.venv/bin/python -m southeast_asia_medtech.processors.rule_filter \
  --input southeast_asia_medtech/data/normalized/2026-07/articles_normalized.json \
  --output-dir southeast_asia_medtech/data/filtered/2026-07

.venv/bin/python -m southeast_asia_medtech.processors.prepare_llm_batch \
  --month 2026-07
```

## Outputs

- `data/raw/2026-07/articles_raw.json`: successfully extracted July page content.
- `data/normalized/2026-07/articles_normalized.json`: standardized monthly input.
- `data/normalized/2026-07/collection_summary.json`: result for every configured source.
- `data/filtered/2026-07/articles_scored.json`: all collected rows with rule scores.
- `data/filtered/2026-07/articles_filtered.json`: automatic LLM candidates.
- `data/filtered/2026-07/articles_llm_ready.json`: pending jobs for later DeepSeek analysis.
- `data/filtered/2026-07/llm_batch_manifest.json`: batch and prompt metadata.

An empty source result does not mean that the source is removed. The summary
distinguishes `no_updates_in_month` from `access_failed`. Snapshot-derived rows
retain their acquisition metadata and are never represented as live HTTP results.

## July discovery fixes

- Candidate pages with known dates are filtered before detail requests, so old
  seed URLs no longer consume the monthly article limit.
- Generic listings retain dated rows before keyword filtering; relevance is
  checked again against the full detail body.
- PhilGEPS uses the public Medical and Dental Equipment (`BusCatID=16`) and
  Medical Supplies and Laboratory Instrument (`BusCatID=15`) category pages.
  It follows every result page until the listing leaves July, then converts
  result links to stable printable bid-detail URLs. The monthly collector's
  old 250-item ceiling has been removed (the configurable safety ceiling now
  defaults to 2,000 records per source).
- Sources marked `requires_javascript` fall back to Playwright when direct HTTP
  is rejected.
- Category pages with generic titles are rejected as non-articles.

## Verified July-to-date run (2026-07-24)

- 501 normalized records
- 501 unique URLs
- 0 records outside July
- 0 empty/short bodies (minimum validation length: 80 characters)
- 489 PhilGEPS tender records across all July result pages
- 454 unique records after content/title deduplication
- 449 rule-matched records prepared for later DeepSeek analysis
- 0 LLM/API calls

Seven sources supplied July-dated records in this run. Sources with no verified
July record remain in `collection_summary.json`; this is not treated as proof
that their site published nothing when the source is marked `partial` or
`access_failed`. In particular, Vietnam NEPS remained inaccessible because of
its legacy TLS configuration/timeouts. This is a current-month snapshot; rerun
after July 31 for the final monthly corpus.
