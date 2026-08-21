# Full July Pharma Report Design

## Goal

Publish the July 2026 Pharma monthly report with every article that passes the
existing report filters, rather than limiting the report to 120 articles.

## Scope

- Keep the current date range, relevance threshold, ranking, report schema,
  HTML layout, and publication URL unchanged.
- Keep every selected article in the generated JSON and HTML appendix.
- Give DeepSeek a compact representation of every selected article for the
  narrative report. This avoids sending large raw article-analysis objects that
  can exceed an API context limit.
- Do not collect articles, re-run per-article analysis, or alter source data.

## Design

`generate_pharma_monthly_report.py` will continue to select and sort the complete
article set. Before calling DeepSeek, it will project each article to only the
fields required by the monthly-report prompt: identity, title, source, date,
category, relevance scores, importance, summary/takeaway, key points,
companies, drugs, targets, indications, packaging fields, business signals,
uncertainties, and source link.

The prompt receives these compact articles and week groupings. The saved JSON
continues to contain the full selected article records, so the readable HTML
generator can list every selected article without losing provenance or existing
display fields.

`--max-articles 0` will mean no cap. The July invocation will use that value,
then overwrite only these production files:

- `public_share/reports/pharma/monthly/2026-07/index.html`
- `public_share/reports/pharma/monthly/2026-07/report.json`
- `public_share/reports/pharma/monthly/2026-07/report.md`

## Failure Handling and Verification

If the report API rejects or times out on the compact payload, no website files
will be published. The generated JSON will be checked for the complete selected
count and unique article IDs; the HTML will be parsed; the nested production
checkout will commit only the three report files; and the public report URL and
homepage link will be checked after push.
