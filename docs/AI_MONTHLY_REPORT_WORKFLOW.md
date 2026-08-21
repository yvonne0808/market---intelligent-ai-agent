# AI Execution Contract: China WeChat Monthly Report

This document is for the AI that operates this repository. It is not a mentor
tutorial. Follow it when the user asks to run, analyze, or generate the China
WeChat monthly report.

## 1. Trigger and input contract

Accept either of these forms:

```text
运行中国微信月报：START_DATE=2026-08-01 END_DATE=2026-08-31
```

or natural language such as:

```text
生成 2026 年 8 月的医药和医疗器械月报。
```

Normalize the request to explicit inclusive dates:

```text
START_DATE=YYYY-MM-DD
END_DATE=YYYY-MM-DD
```

If the year or date range is ambiguous, ask before running anything. Never use
a script's default date, the current date, or a previous chat's date silently.

The repository root is the directory containing this file and `AGENTS.md`.
All commands below are relative to that root and must use the repository's
`.venv/bin/python`.

## 2. End-to-end state machine

Run the phases in this order and do not skip a failed phase:

```text
PRECHECK
  -> WEWERS_VERIFY
  -> COLLECT
  -> PREPARE
  -> VALIDATE_LLM_INPUT
  -> PHARMA_ARTICLE_ANALYSIS
  -> DEVICE_ARTICLE_ANALYSIS
  -> PHARMA_MONTHLY_ANALYSIS
  -> DEVICE_MONTHLY_ANALYSIS
  -> FINAL_QA
```

The two article-analysis phases and the two monthly-analysis phases are four
separate DeepSeek jobs. A complete run is not complete until all four have
finished successfully.

## 3. Phase PRECHECK (no DeepSeek)

Check and report:

- The current directory is the repository root.
- `.venv/bin/python` exists and can import project dependencies.
- `.env` exists and contains a usable `DEEPSEEK_API_KEY`; never print its value.
- `http://localhost:8001` is reachable.
- Docker/WeWe RSS is running and the configured feed list is non-empty.
- `START_DATE <= END_DATE`.
- The expected output directories are writable.

If WeWe RSS is unavailable, stop with `BLOCKED` and explain the diagnostic
result. Do not call DeepSeek.

## 4. Phase WEWERS_VERIFY (manual account state)

The AI may check the local page and guide the user, but cannot replace a human
微信扫码. Ask the user to confirm that:

1. invalid WeWe RSS accounts were removed;
2. the current account was logged in by QR code; and
3. all required公众号 sources are visible.

The AI must never request a微信 password or copy the QR code into chat.

## 5. Phase COLLECT (no DeepSeek)

Run from the repository root:

```bash
.venv/bin/python china-wechat-med-phar/scripts/main.py
```

Expected raw outputs:

```text
china-wechat-med-phar/data/raw/articles.json
china-wechat-med-phar/data/raw/articles.csv
china-wechat-med-phar/data/raw/articles.xlsx
```

Report at least: configured feed count, RSS candidates, new articles,
duplicates skipped, fetch failures, and raw JSON path.

## 6. Phase PREPARE (no DeepSeek)

Prepare the inclusive date range and keep only the required source categories:

```bash
.venv/bin/python china-wechat-med-phar/scripts/prepare_llm_data.py \
  --start START_DATE \
  --end END_DATE \
  --source-category 医药 \
  --source-category 医疗器械
```

Replace `START_DATE` and `END_DATE` with the normalized values. For a single
calendar month, the generated files normally use the suffix `YYYY_MM`:

```text
china-wechat-med-phar/data/llm_ready/articles_llm_ready_YYYY_MM.json
china-wechat-med-phar/data/llm_ready/articles_llm_ready_YYYY_MM.md
```

Do not assume that the file is category-separated: this command can produce a
combined file containing both categories. Before Article Analysis, create or
select category-specific projections and verify their `source_category` values.
The raw file must not be edited.

## 7. Phase VALIDATE_LLM_INPUT (no DeepSeek)

For every candidate, validate:

- `published` parses and is inside the inclusive date range;
- `article_id` or `link` is present and unique;
- `title`, `link`, and `source_name` are present;
- the chosen LLM text field is non-empty and readable;
- the text is not obvious乱码, HTML-only content, a login page, or an error page;
- `source_category` is exactly `医药` or `医疗器械`;
- each category has a separately counted input file.

Report this table before any API call:

```text
日期范围：
有效候选总数：
医药候选数：
医疗器械候选数：
空正文数：
乱码/无效正文数：
日期范围外数量：
重复 ID 数：
医药输入文件：
医疗器械输入文件：
```

If any category has zero candidates, or if invalid text has not been excluded,
stop with `BLOCKED` and do not call DeepSeek.

## 8. Phase PHARMA_ARTICLE_ANALYSIS

Run only the Pharma/医药 input. Use the actual category-specific input path;
do not pass the combined file if it contains Medical Device articles.

The current analyzer interface is:

```bash
.venv/bin/python china-wechat-med-phar/scripts/analyze_articles.py \
  --input <PHARMA_LLM_READY_JSON> \
  --output china-wechat-med-phar/data/analyzed/Pharma/articles_analyzed_START_END.json \
  --selected-output china-wechat-med-phar/data/analyzed/Pharma/articles_analyzed_START_END.json \
  --start START_DATE \
  --end END_DATE \
  --smart-new-only \
  --skip-empty-text \
  --workers 1
```

Replace `START_END` with `YYYYMMDD_YYYYMMDD`. If the project uses a shared
incremental output file, preserve that file and use `--selected-output` for the
date-specific report input. Do not use `--force` by default.

Report selected, processed, skipped, failed, and saved counts, plus the output
path. Stop if failures are unexplained or if Medical Device articles appear in
the output.

## 9. Phase DEVICE_ARTICLE_ANALYSIS

Run only the Medical Device/医疗器械 input:

```bash
.venv/bin/python china-wechat-med-phar/scripts/analyze_medical_device_articles.py \
  --input <MEDICAL_DEVICE_LLM_READY_JSON> \
  --output "china-wechat-med-phar/data/analyzed/Medical Device/articles_analyzed_START_END.json" \
  --start START_DATE \
  --end END_DATE \
  --workers 1
```

The current script supports incremental article-ID skipping. Do not add
`--force` unless explicitly requested. Report processed, skipped, failed, and
saved counts, plus the output path.

## 10. Phase PHARMA_MONTHLY_ANALYSIS

Only start this phase after both article-analysis inputs have been checked and
the user has confirmed the candidate counts (unless the user explicitly asked
for an unattended run).

```bash
.venv/bin/python china-wechat-med-phar/scripts/generate_monthly_report.py \
  --input <PHARMA_ANALYZED_JSON> \
  --start START_DATE \
  --end END_DATE
```

This phase calls DeepSeek again. It selects target articles using the analyzed
scores and writes the Pharma Markdown/JSON report under:

```text
china-wechat-med-phar/reports/Pharma/
```

Report selected article count, report paths, and whether the generated report
contains the requested date range and source links.

## 11. Phase DEVICE_MONTHLY_ANALYSIS

```bash
.venv/bin/python china-wechat-med-phar/scripts/generate_medical_device_monthly_report.py \
  --input "<MEDICAL_DEVICE_ANALYZED_JSON>" \
  --start START_DATE \
  --end END_DATE
```

This phase calls DeepSeek again and writes the Medical Device Markdown/JSON
report under:

```text
china-wechat-med-phar/reports/Medical Device/
```

Report selected article count, report paths, and category-isolation checks.

## 12. Phase FINAL_QA

Mark the run `COMPLETE` only when all of these are true:

- exactly two Article Analysis jobs completed;
- exactly two Monthly Analysis jobs completed;
- both Markdown and JSON monthly reports exist;
- the report dates match `START_DATE` and `END_DATE`;
- Pharma and Medical Device outputs contain no cross-category articles;
- report source links are present;
- all failed items are either zero or explicitly listed with reasons.

If files exist but a required check failed, use `PARTIAL`. If execution cannot
continue without user action or an external service, use `BLOCKED`.

## 13. Required final response contract

Use this exact structure, filling every field:

```markdown
# China WeChat Monthly Report Run

Status: COMPLETE | PARTIAL | BLOCKED
Date range: START_DATE to END_DATE (inclusive)

## Collection
- WeWe RSS status:
- Raw candidates:
- New articles:
- Duplicates skipped:
- Fetch failures:

## Validated inputs
- Valid candidates:
- Pharma/医药:
- Medical Device/医疗器械:
- Empty text:
- Invalid/garbled text:
- Out-of-range:
- Duplicate IDs:
- Pharma input:
- Medical Device input:

## Analysis jobs
| Job | Input count | Processed/selected | Skipped | Failed | Output | Status |
|---|---:|---:|---:|---:|---|---|
| Pharma Article Analysis | | | | | | |
| Medical Device Article Analysis | | | | | | |
| Pharma Monthly Analysis | | | | | | |
| Medical Device Monthly Analysis | | | | | | |

## Final reports
- Pharma Markdown:
- Pharma JSON:
- Medical Device Markdown:
- Medical Device JSON:

## QA
- Date range:
- Category isolation:
- Source links:
- Failed items and reasons:
- Next action, if any:
```

Never say “完成” without the exact output paths and the four job statuses.
