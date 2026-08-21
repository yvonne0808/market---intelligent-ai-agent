from __future__ import annotations

import argparse
import json
import re
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import requests

from generate_pharma_monthly_report import (
    PROJECT_DIR,
    filter_articles,
    group_articles_by_week,
    load_amcor_context,
    load_analyzed_articles,
    load_deepseek_config,
    parse_date,
    render_report_outputs,
)


ANALYZED_PATH = (
    PROJECT_DIR / "data" / "analyzed" / "Medical Device" / "articles_analyzed_2026_07.json"
)
PROMPT_PATH = PROJECT_DIR / "prompts" / "Medical Device" / "monthly_report_prompt.txt"
REPORTS_DIR = PROJECT_DIR / "reports" / "Medical Device"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a Medical Device monthly report.")
    parser.add_argument(
        "--input",
        type=Path,
        default=ANALYZED_PATH,
        help="Analyzed Medical Device JSON input path.",
    )
    parser.add_argument("--start", default="2026-07-01", help="Start date YYYY-MM-DD.")
    parser.add_argument("--end", default="2026-07-15", help="End date YYYY-MM-DD.")
    parser.add_argument("--min-score", type=int, default=12, help="Minimum relevance score.")
    parser.add_argument(
        "--include-optional",
        action="store_true",
        help="Include articles even when include_in_weekly_report is false.",
    )
    parser.add_argument("--max-articles", type=int, default=120, help="Maximum LLM articles.")
    return parser.parse_args()


def strip_code_fence(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:markdown|md)?\s*", "", text, flags=re.I)
    text = re.sub(r"\s*```$", "", text)
    start = text.find("# Monthly Medical Device News Report")
    if start > 0:
        text = text[start:]
    return text.strip()


def call_deepseek_report(
    config: dict[str, str],
    prompt_template: str,
    weeks: list[dict[str, Any]],
    articles: list[dict[str, Any]],
    start_date: date,
    end_date: date,
    generated_at: str,
) -> str:
    system_prompt = prompt_template.format(
        start_date=start_date.isoformat(),
        end_date=end_date.isoformat(),
        generated_at=generated_at,
        amcor_context=load_amcor_context(),
    )
    payload = {
        "model": config["model"],
        "messages": [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "period": {
                            "start_date": start_date.isoformat(),
                            "end_date": end_date.isoformat(),
                            "generated_at": generated_at,
                        },
                        "selection_rule": (
                            "Articles were filtered by weekly-report inclusion and relevance, "
                            "then ranked by Amcor and packaging relevance."
                        ),
                        "weeks": weeks,
                        "articles": articles,
                    },
                    ensure_ascii=False,
                ),
            },
        ],
        "temperature": 0.3,
    }
    response = requests.post(
        f"{config['base_url']}/chat/completions",
        headers={
            "Authorization": f"Bearer {config['api_key']}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=300,
    )
    response.raise_for_status()
    return strip_code_fence(response.json()["choices"][0]["message"]["content"])


def save_report_files(
    markdown: str,
    weeks: list[dict[str, Any]],
    articles: list[dict[str, Any]],
    start_date: date,
    end_date: date,
    generated_at: str,
) -> tuple[Path, Path]:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    suffix = f"{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}"
    md_path = REPORTS_DIR / f"monthly_report_{suffix}.md"
    json_path = REPORTS_DIR / f"monthly_report_{suffix}.json"
    md_path.write_text(markdown, encoding="utf-8")
    json_path.write_text(
        json.dumps(
            {
                "report_type": "Medical Device",
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "generated_at": generated_at,
                "article_count": len(articles),
                "weeks": weeks,
                "articles": articles,
                "markdown_report": markdown,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return md_path, json_path


def main() -> int:
    args = parse_args()
    start_date = parse_date(args.start)
    end_date = parse_date(args.end)
    if start_date > end_date:
        raise ValueError("--start must be earlier than or equal to --end")

    analyzed_path = args.input.expanduser().resolve()
    analyzed = load_analyzed_articles(analyzed_path)
    selected = filter_articles(
        analyzed,
        start_date,
        end_date,
        args.min_score,
        args.include_optional,
    )
    if args.max_articles > 0:
        selected = selected[: args.max_articles]
    if not selected:
        raise RuntimeError("No Medical Device articles matched the report filters.")

    weeks = group_articles_by_week(selected, start_date, end_date)
    generated_at = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    print("Medical Device monthly report generation", flush=True)
    print(f"- Input: {analyzed_path}", flush=True)
    print(f"- Date range: {start_date} to {end_date}", flush=True)
    print(f"- Analyzed articles loaded: {len(analyzed)}", flush=True)
    print(f"- Articles selected: {len(selected)}", flush=True)
    print(f"- Week groups: {len(weeks)}", flush=True)

    markdown = call_deepseek_report(
        load_deepseek_config(),
        PROMPT_PATH.read_text(encoding="utf-8"),
        weeks,
        selected,
        start_date,
        end_date,
        generated_at,
    )
    md_path, json_path = save_report_files(
        markdown, weeks, selected, start_date, end_date, generated_at
    )
    print(f"- Markdown: {md_path}", flush=True)
    print(f"- JSON: {json_path}", flush=True)
    pdf_path, html_path = render_report_outputs(md_path, json_path)
    print(f"- PDF: {pdf_path}", flush=True)
    print(f"- HTML: {html_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
