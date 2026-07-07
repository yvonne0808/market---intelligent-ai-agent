# Mentor Setup Guide

This project collects WeChat public-account articles from a local WeWe RSS server, prepares them for LLM analysis, scores article relevance for pharma and Amcor packaging use cases, and generates weekly or monthly reports.

## 1. Prerequisites

- Python 3.10 or newer
- A local WeWe RSS instance running at `http://localhost:8001`
- A DeepSeek API key for LLM analysis

## 2. Install

```bash
cd wechat-rss-data-collector
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

## 3. Configure API key

Create a local `.env` file from the example:

```bash
cp .env.example .env
```

Then edit `.env`:

```text
DEEPSEEK_API_KEY=your_deepseek_api_key_here
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
```

Do not commit `.env` to GitHub.

## 4. Check feeds

The feed list is stored in:

```text
config.yaml
```

Each feed points to a WeWe RSS URL such as:

```text
http://localhost:8001/feeds/MP_WXS_xxxxxxxxxx.atom?limit=50
```

Make sure the same feeds are available in the mentor's local WeWe RSS instance.

## 5. Collect articles

```bash
.venv/bin/python main.py
```

Outputs are written to:

```text
data/raw/articles.json
data/raw/articles.csv
data/raw/articles.xlsx
```

## 6. Prepare June-only LLM input

```bash
.venv/bin/python prepare_llm_data.py --start 2026-06-01 --end 2026-06-30
```

This creates cleaned LLM-ready files under:

```text
data/llm_ready/
```

## 7. Analyze June articles with DeepSeek

```bash
.venv/bin/python analyze_articles.py --start 2026-06-01 --end 2026-06-30 --force
```

The analysis output is stored in:

```text
data/analyzed/articles_analyzed.json
```

## 8. Generate monthly report

```bash
.venv/bin/python generate_monthly_report.py --start 2026-06-01 --end 2026-06-30
```

This creates:

```text
reports/monthly_report_20260601_20260630.md
reports/monthly_report_20260601_20260630.json
```

## 9. Optional readable outputs

Create a PDF from the Markdown report:

```bash
.venv/bin/python scripts/convert_monthly_markdown_to_pdf.py reports/monthly_report_20260601_20260630.md reports/monthly_report_20260601_20260630.pdf
```

Create a browser-friendly HTML dashboard from the monthly JSON:

```bash
.venv/bin/python scripts/generate_readable_monthly_html.py reports/monthly_report_20260601_20260630.json reports/monthly_report_20260601_20260630.html
```

## Notes

- `prompts/amcor_apac_context.txt` contains the Amcor APAC business context used by the article analysis and report prompts.
- Raw article data, analyzed data, reports, `.env`, and the virtual environment are intentionally excluded from GitHub.
- If the mentor's WeWe RSS feed IDs differ, update `config.yaml` before running collection.

