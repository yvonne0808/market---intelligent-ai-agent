# Report Library Project Instructions

## AI workflow routing

When the user asks to run, analyze, or generate the China WeChat monthly
report, including requests such as:

- `运行中国微信月报`
- `生成医药和医疗器械月报`
- `分析 YYYY-MM-DD 到 YYYY-MM-DD 的公众号文章`
- `Run the China WeChat monthly report`

first read the complete execution contract at:

```text
docs/AI_MONTHLY_REPORT_WORKFLOW.md
```

Do not infer a different order from an older README, a previous chat, or a
script's default date. The workflow document is the source of truth for this
task.

## Mandatory invariants

1. Work from the current repository root. Never use a machine-specific
   absolute path such as `/Users/yvonne/...`.
2. Parse and report an explicit inclusive `START_DATE` and `END_DATE` before
   collecting or analyzing anything. If the user gives only a month name, infer
   its first and last day only when the year is unambiguous; otherwise ask.
3. Keep Pharma/医药 and Medical Device/医疗器械 inputs, prompts, analyzed
   outputs, and reports separate. Do not trust a filename alone to prove that a
   category is isolated; inspect `source_category` or the documented category
   projection.
4. Before any DeepSeek call, validate date range, non-empty readable text,
   category labels, duplicate IDs, and output paths. Report the counts first.
5. Run exactly two article-analysis jobs and two monthly-report jobs for a
   complete China WeChat run: Pharma Article, Medical Device Article, Pharma
   Monthly, and Medical Device Monthly.
6. Preserve incremental-save and existing-article skip behavior. Do not use
   `--force` unless the user explicitly asks to re-analyze existing article IDs.
7. Never print or commit `.env`, API keys, the WeWe RSS SQLite database, raw
   local data, or DeepSeek response content containing secrets.
8. Do not delete existing outputs, reset Git state, publish, push, or modify a
   remote repository unless the user explicitly requests that action.
9. If a required check fails, stop at that phase and return `BLOCKED` or
   `PARTIAL`; do not claim completion.

## Required final response

For a completed or partially completed monthly run, use the output contract in
`docs/AI_MONTHLY_REPORT_WORKFLOW.md`. At minimum include the date range,
collection counts, category counts, all four analysis statuses, exact output
paths, data-quality checks, failures, and one of `COMPLETE`, `PARTIAL`, or
`BLOCKED`.

## Publication boundary

For China WeChat report-library website updates, publish only approved static
files to the production repository:

- Repository: `https://github.com/market-insights/market-insights.github.io.git`
- Branch: `main`
- Public URL: `https://market-insights.github.io/`

The nested `china-wechat-med-phar/public_share/` checkout is configured to use
this production repository and its `main` branch. Local branches prefixed
`legacy-yvonne-` and the local `gh-pages` branch are retained only as backups;
do not push them unless the user explicitly asks for a legacy-copy update.

Before confirming a publication, verify both the homepage card and the direct
report URL on `market-insights.github.io` show the new report period.
