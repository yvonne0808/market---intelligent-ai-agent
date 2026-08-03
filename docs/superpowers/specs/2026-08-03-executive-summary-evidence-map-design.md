# Executive Summary Evidence Map Prompt Design

## Purpose

Make future Pharma and Medical Device monthly-report Executive Summary bullets
directly auditable against the already analyzed article JSON records.

## Scope

Modify only these prompt files:

- `china-wechat-med-phar/prompts/Medical Device/monthly_report_prompt.txt`
- `china-wechat-med-phar/prompts/Pharma/monthly_report_prompt.txt`

No article-analysis prompt, article JSON schema, report-generation script, or
existing report artifact changes.

## Required output

For every Executive Summary bullet, the monthly-report prompt must require an
`Evidence / Supporting articles` block with two to five source records. Each
record contains the article title, source name, publication date, original
link, and `article_id`.

## Data-integrity rules

- Cite only articles in the current monthly-report input.
- Never invent an `article_id`, URL, date, title, or source.
- If a summary point relies on an inference, label the evidence relationship
  as indirect rather than presenting it as a directly disclosed fact.
- The source block supports the conclusion but does not change the existing
  summary text, report ranking, or business logic.
