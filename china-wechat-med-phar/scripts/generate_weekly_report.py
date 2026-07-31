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
PROMPT_PATH = PROJECT_DIR / "prompts/Pharma/weekly_report_prompt.txt"
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
    if not api_key:
        raise RuntimeError(
            "Missing DEEPSEEK_API_KEY. Create .env from .env.example and add your key."
        )
    return {
        "api_key": api_key,
        "base_url": os.environ.get("DEEPSEEK_BASE_URL", DEFAULT_BASE_URL).rstrip("/"),
        "model": os.environ.get("DEEPSEEK_MODEL", DEFAULT_MODEL),
    }


def parse_args() -> argparse.Namespace:
    today = date.today()
    default_start = today - timedelta(days=7)
    parser = argparse.ArgumentParser(description="Generate weekly report with DeepSeek.")
    parser.add_argument("--start", default=default_start.isoformat(), help="Start date YYYY-MM-DD")
    parser.add_argument("--end", default=today.isoformat(), help="End date YYYY-MM-DD")
    parser.add_argument("--min-score", type=int, default=12, help="Minimum relevance score")
    parser.add_argument("--include-optional", action="store_true", help="Ignore include flag")
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
    ranks = {"high": 3, "medium": 2, "low": 1}
    return ranks.get(str(value).lower(), 0)


def load_analyzed_articles() -> list[dict[str, Any]]:
    if not ANALYZED_PATH.exists():
        raise FileNotFoundError(f"Analyzed file not found: {ANALYZED_PATH}")
    data = json.loads(ANALYZED_PATH.read_text(encoding="utf-8"))
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
    selected: list[dict[str, Any]] = []
    for article in articles:
        published_date = parse_published_date(article.get("published", ""))
        if not published_date or not (start_date <= published_date <= end_date):
            continue
        if not include_optional and not article.get("include_in_weekly_report", False):
            continue
        if int(article.get("relevance_score", 0) or 0) < min_score:
            continue
        selected.append(article)

    selected.sort(
        key=lambda item: (
            int(item.get("relevance_score", 0) or 0),
            importance_rank(item.get("importance_level", "")),
            int(item.get("amcor_relevance_score", 0) or 0),
        ),
        reverse=True,
    )
    return selected


def strip_code_fence(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:markdown|md)?\s*", "", text, flags=re.I)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def call_deepseek_report(
    config: dict[str, str],
    prompt_template: str,
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
                        "articles": articles,
                    },
                    ensure_ascii=False,
                ),
            },
        ],
        "temperature": 0.3,
    }
    headers = {
        "Authorization": f"Bearer {config['api_key']}",
        "Content-Type": "application/json",
    }
    response = requests.post(
        f"{config['base_url']}/chat/completions",
        headers=headers,
        json=payload,
        timeout=120,
    )
    response.raise_for_status()
    content = response.json()["choices"][0]["message"]["content"]
    return strip_code_fence(content)


def save_report_files(
    markdown: str,
    articles: list[dict[str, Any]],
    start_date: date,
    end_date: date,
    generated_at: str,
) -> tuple[Path, Path]:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    suffix = end_date.strftime("%Y%m%d")
    md_path = REPORTS_DIR / f"weekly_report_{suffix}.md"
    json_path = REPORTS_DIR / f"weekly_report_{suffix}.json"
    md_path.write_text(markdown, encoding="utf-8")
    json_path.write_text(
        json.dumps(
            {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "generated_at": generated_at,
                "article_count": len(articles),
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
    analyzed_articles = load_analyzed_articles()
    selected_articles = filter_articles(
        analyzed_articles,
        start_date,
        end_date,
        args.min_score,
        args.include_optional,
    )
    generated_at = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")

    print("Weekly report generation")
    print(f"- Date range: {start_date} to {end_date}")
    print(f"- Analyzed articles loaded: {len(analyzed_articles)}")
    print(f"- Articles included: {len(selected_articles)}")
    print(f"- Minimum relevance score: {args.min_score}")

    if not selected_articles:
        raise RuntimeError("No analyzed articles matched the report filters.")

    markdown = call_deepseek_report(
        config,
        prompt_template,
        selected_articles,
        start_date,
        end_date,
        generated_at,
    )
    md_path, json_path = save_report_files(
        markdown,
        selected_articles,
        start_date,
        end_date,
        generated_at,
    )

    print("Weekly report saved")
    print(f"- Markdown: {md_path}")
    print(f"- JSON: {json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
