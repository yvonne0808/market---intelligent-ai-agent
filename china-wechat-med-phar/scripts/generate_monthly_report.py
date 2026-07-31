from __future__ import annotations

import argparse
import json
import os
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests


PROJECT_DIR = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = PROJECT_DIR.parent
ANALYZED_PATH = PROJECT_DIR / "data/analyzed/articles_analyzed.json"
PROMPT_PATH = PROJECT_DIR / "prompts/Pharma/monthly_report_prompt.txt"
AMCOR_CONTEXT_PATH = PROJECT_DIR / "prompts/amcor_apac_context.txt"
REPORTS_DIR = PROJECT_DIR / "reports" / "Pharma"

DEFAULT_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-chat"


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def load_deepseek_config() -> dict[str, str]:
    load_env_file(REPOSITORY_ROOT / ".env")
    api_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if not api_key or api_key == "your_deepseek_api_key_here":
        raise RuntimeError("Missing DEEPSEEK_API_KEY. Add it to .env first.")
    return {
        "api_key": api_key,
        "base_url": os.environ.get("DEEPSEEK_BASE_URL", DEFAULT_BASE_URL).rstrip("/"),
        "model": os.environ.get("DEEPSEEK_MODEL", DEFAULT_MODEL),
    }


def parse_args() -> argparse.Namespace:
    today = date.today()
    first_day = today.replace(day=1)
    parser = argparse.ArgumentParser(description="Generate monthly pharma report with weekly sections.")
    parser.add_argument("--input", default=str(ANALYZED_PATH), help="Analyzed JSON file to use.")
    parser.add_argument("--start", default=first_day.isoformat(), help="Start date YYYY-MM-DD")
    parser.add_argument("--end", default=today.isoformat(), help="End date YYYY-MM-DD")
    parser.add_argument("--min-score", type=int, default=12, help="Minimum relevance score")
    parser.add_argument("--include-optional", action="store_true", help="Ignore include flag")
    parser.add_argument("--max-articles", type=int, default=120, help="Maximum articles sent to LLM")
    return parser.parse_args()


def parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def parse_published_date(value: str) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return datetime.strptime(value[:10], "%Y-%m-%d").date()
        except ValueError:
            return None


def importance_rank(value: str) -> int:
    return {"high": 3, "medium": 2, "low": 1}.get(str(value).lower(), 0)


def packaging_rank(value: str) -> int:
    return {"high": 3, "medium": 2, "low": 1, "none": 0}.get(str(value).lower(), 0)


def article_rank(article: dict[str, Any]) -> tuple[int, int, int, int, str]:
    return (
        int(article.get("amcor_relevance_score", 0) or 0),
        packaging_rank(article.get("packaging_relevance", "")),
        int(article.get("relevance_score", 0) or 0),
        importance_rank(article.get("importance_level", "")),
        str(article.get("published", "")),
    )


def load_analyzed_articles(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Analyzed file not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("articles_analyzed.json must contain a JSON list.")
    return [item for item in data if isinstance(item, dict)]


def load_amcor_context() -> str:
    if not AMCOR_CONTEXT_PATH.exists():
        return ""
    return AMCOR_CONTEXT_PATH.read_text(encoding="utf-8").strip()


def filter_articles(
    articles: list[dict[str, Any]],
    start_date: date,
    end_date: date,
    min_score: int,
    include_optional: bool,
) -> list[dict[str, Any]]:
    selected = []
    for article in articles:
        published_date = parse_published_date(article.get("published", ""))
        if not published_date or not (start_date <= published_date <= end_date):
            continue
        if not include_optional and not article.get("include_in_weekly_report", False):
            continue
        if int(article.get("relevance_score", 0) or 0) < min_score:
            continue
        selected.append(article)
    selected.sort(key=article_rank, reverse=True)
    return selected


def build_week_ranges(start_date: date, end_date: date) -> list[dict[str, Any]]:
    ranges = []
    current = start_date
    index = 1
    while current <= end_date:
        week_end = min(current + timedelta(days=6), end_date)
        ranges.append(
            {
                "week": f"Week {index}",
                "start_date": current.isoformat(),
                "end_date": week_end.isoformat(),
                "articles": [],
            }
        )
        current = week_end + timedelta(days=1)
        index += 1
    return ranges


def group_articles_by_week(
    articles: list[dict[str, Any]],
    start_date: date,
    end_date: date,
) -> list[dict[str, Any]]:
    weeks = build_week_ranges(start_date, end_date)
    for article in articles:
        published_date = parse_published_date(article.get("published", ""))
        if not published_date:
            continue
        for week in weeks:
            week_start = parse_date(week["start_date"])
            week_end = parse_date(week["end_date"])
            if week_start <= published_date <= week_end:
                week["articles"].append(article)
                break
    for week in weeks:
        week["articles"].sort(key=article_rank, reverse=True)
        week["article_count"] = len(week["articles"])
    return weeks


def strip_code_fence(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:markdown|md)?\s*", "", text, flags=re.I)
    text = re.sub(r"\s*```$", "", text)
    report_start = text.find("# Monthly Pharma News Report")
    if report_start > 0:
        text = text[report_start:]
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
                        "selection_rule": "Articles are pre-filtered and sorted by Amcor relevance, packaging relevance, relevance score, importance, and date.",
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
        timeout=180,
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

    config = load_deepseek_config()
    prompt_template = PROMPT_PATH.read_text(encoding="utf-8")
    analyzed_path = Path(args.input)
    analyzed_articles = load_analyzed_articles(analyzed_path)
    selected_articles = filter_articles(
        analyzed_articles,
        start_date,
        end_date,
        args.min_score,
        args.include_optional,
    )
    if args.max_articles > 0:
        selected_articles = selected_articles[: args.max_articles]
    weeks = group_articles_by_week(selected_articles, start_date, end_date)
    generated_at = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")

    print("Monthly report generation")
    print(f"- Input: {analyzed_path}")
    print(f"- Date range: {start_date} to {end_date}")
    print(f"- Analyzed articles loaded: {len(analyzed_articles)}")
    print(f"- Articles included: {len(selected_articles)}")
    print(f"- Minimum relevance score: {args.min_score}")
    for week in weeks:
        print(f"- {week['week']} {week['start_date']} to {week['end_date']}: {week['article_count']}")

    if not selected_articles:
        raise RuntimeError("No analyzed articles matched the report filters.")

    markdown = call_deepseek_report(
        config,
        prompt_template,
        weeks,
        selected_articles,
        start_date,
        end_date,
        generated_at,
    )
    md_path, json_path = save_report_files(
        markdown,
        weeks,
        selected_articles,
        start_date,
        end_date,
        generated_at,
    )
    print("Monthly report saved")
    print(f"- Markdown: {md_path}")
    print(f"- JSON: {json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
