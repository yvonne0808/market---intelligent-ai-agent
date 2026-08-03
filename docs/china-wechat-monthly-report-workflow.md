# China WeChat Monthly Report Workflow

This is the operating guide for the recurring China WeChat monthly reports. Read
this file before starting a Medical Device or Pharma reporting cycle.

## Purpose and scope

The project contains two independent China WeChat report streams:

- **Medical Device**
- **Pharma**

This guide covers collection, selection, DeepSeek analysis, monthly-report
generation, local review, and optional publication for those two streams only.
Do not reuse this workflow, its analysis JSON, or `seen_articles.json` for
`southeast_asia_medtech/`.

## Before starting

1. Confirm the report stream (Medical Device or Pharma) and the exact reporting
   period with Yvonne.
2. Check the existing raw, filtered, and analyzed JSON before collecting or
   analyzing. Saved `article_id` values are the duplicate-control source of
   truth: do not re-analyze an article already present in the target analyzed
   JSON.
3. Confirm the requested scope before taking any external action. Do **not**
   crawl, call DeepSeek, regenerate a report, or publish merely because files
   exist.
4. Use the repository virtual environment, from the repository root:

   ```bash
   .venv/bin/python china-wechat-med-phar/scripts/main.py
   ```

## Standard monthly workflow

### 1. Collect the requested period

Run only the relevant collection workflow after the user approves it. Keep the
Medical Device and Pharma datasets separate. Confirm every collected article is
within the requested date range before presenting the count.

### 2. Filter before LLM analysis

When the candidate pool is large, perform a first-pass relevance filter before
using DeepSeek. Keep the filter output separate from raw collection data, and
tell Yvonne the retained count before starting API analysis.

### 3. Analyze with DeepSeek, safely resumable

Use the relevant analyzer in `china-wechat-med-phar/scripts/`. The analysis
must save incrementally to the appropriate JSON under `data/analyzed/`.

- Skip already-saved `article_id` values rather than overwriting prior work.
- Retry recoverable API failures.
- At completion, report processed, failed, skipped, and unique-article counts.
- If a process ends early, report the saved count and remaining IDs; do not
  restart it without approval.

### 4. Generate and review the monthly report

Generate the Medical Device or Pharma monthly report only after analysis is
complete (or Yvonne explicitly accepts partial coverage). Inspect the report
for missing linked article lists, empty sections, and unsupported claims before
sharing it.

Use the full report as the canonical report. A concise PDF is a separate,
local review artifact; it must not replace or modify the full report.

### 5. Publish only with explicit approval

Local review and public deployment are separate actions. Publish only when
Yvonne explicitly says to publish, deploy, or push the approved report.

The production website checkout is:

```text
china-wechat-med-phar/public_share/
```

It publishes to:

```text
https://github.com/market-insights/market-insights.github.io.git
branch: main
site: https://market-insights.github.io/
```

After publication, verify both the relevant homepage card and the exact report
URL. If the user sees an old version, check the deployed file and browser/CDN
cache before changing the source again.

## Report content decisions

Apply these current editorial preferences to both Medical Device and Pharma
monthly reports:

- Keep **Executive Summary 月度核心总结** as the principal monthly conclusion.
- Each Executive Summary point needs an **Evidence / Supporting articles**
  block with 2–5 input articles. Include article ID, title, source, date, and
  original link; label inferential support as `indirect`.
- Retain ranked **Top Opportunities**. This is a ranking of opportunities, not
  merely a list of companies.
- Every weekly **Other Important ... News** section must include the associated
  article entries and original links rather than an empty heading.
- Give regulation-only stories lower priority. They can remain as background
  information, but should not independently dominate the Executive Summary,
  top ranking, or featured opportunity unless the article explicitly supports a
  commercial, capacity, procurement, supply-chain, packaging, or customer
  consequence.
- Keep confirmed facts and interpretation separate. Packaging or sterilization
  claims require source support; otherwise clearly describe them as a signal or
  follow-up item rather than a confirmed fact.

### Concise Medical Device review PDF

For the July 2026 Medical Device concise review, preserve the existing
Executive Summary, Top Opportunities, combined weekly overview, integrated
signals, and compact Appendix: Articles Reviewed. The review PDF remains local
until Yvonne explicitly approves website publication.

## Output map

Use project-relative paths so this guide works on any machine:

```text
china-wechat-med-phar/
├── data/
│   ├── raw/                 # collected source articles
│   ├── filtered/            # first-pass relevance selections
│   └── analyzed/            # incremental DeepSeek analysis JSON
├── prompts/
│   ├── Medical Device/      # Medical Device report prompt
│   └── Pharma/              # Pharma report prompt
├── scripts/                 # collectors, filters, analyzers, generators
├── public_share/
│   └── reports/             # publishable HTML/PDF/report assets
├── reports/                 # local report working files when applicable
├── config.yaml
├── website_sources.yaml
└── seen_articles.json       # collection de-duplication state
```

Frequently used scripts include:

```text
scripts/analyze_articles.py
scripts/analyze_medical_device_articles.py
scripts/generate_monthly_report.py
scripts/generate_medical_device_monthly_report.py
scripts/generate_readable_monthly_html.py
scripts/convert_monthly_markdown_to_pdf.py
```

The July 2026 concise-review renderer is deliberately isolated until it is
approved for the main project. Its current local-review location is:

```text
.worktrees/medical-device-concise-review/china-wechat-med-phar/scripts/generate_medical_device_concise_review.py
```

## Handoff checklist for future runs

Before acting, a future agent should:

1. Read this file and confirm the period plus stream with Yvonne.
2. Inspect existing `data/analyzed/` JSON and report artifacts to prevent
   duplicate DeepSeek work.
3. State the proposed phase (collect, filter, analyze, generate, review, or
   publish) and wait for approval whenever it triggers crawling, API use,
   regeneration, or deployment.
4. Keep Medical Device and Pharma inputs, analyzed JSON, and report outputs
   separate.
5. Verify local output before calling it complete; verify the live homepage and
   direct URL only after an approved publication.

## Related technical records

These records explain individual implementation decisions; this workflow guide
is the primary starting point for recurring work.

- `docs/superpowers/specs/2026-08-03-medical-device-concise-review-design.md`
- `docs/superpowers/plans/2026-08-03-medical-device-concise-review.md`
- `docs/superpowers/specs/2026-08-03-executive-summary-evidence-map-design.md`
- `docs/superpowers/plans/2026-08-03-executive-summary-evidence-map.md`
- `docs/superpowers/specs/2026-08-03-regulation-priority-design.md`
