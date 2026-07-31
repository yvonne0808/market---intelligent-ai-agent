# Customer Analysis workflow

This module turns analyzed customer-discovery news into an English, source-linked sales and business-development report. It is independent from the monthly market-report data and page.

## Monthly run

Prepare a new issue, generate its DeepSeek draft, and export the static website assets:

```bash
PYTHONPATH=. .venv/bin/python -m southeast_asia_medtech.customer_analysis.run \
  --issue 2026-08 \
  --input southeast_asia_medtech/data/analyzed/customer_discovery_2026_08/articles_analyzed.json \
  --generate --export
```

- Every run appends canonical URL-deduplicated events to `data/customer_analysis/master_events.json`.
- An issue only includes evidence published on or before its issue month, so a later run cannot backfill future events into an earlier report.
- `none` records never enter the report/explorer. Executive analysis is restricted to `direct_customer` and `competitor` evidence.

## Editorial approval

The model writes `data/customer_analysis/issues/<issue>/draft.json`. Review and edit it, then copy it to `approved.json` in the same directory. Re-run only `--export` to make the approved copy take precedence on `/customer-analysis`.

The route reads these static assets:

- `report_site/public/customer-analysis/report.json`
- `report_site/public/customer-analysis/events.json`
