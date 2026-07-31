from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from prepare_llm_data import (
    PROJECT_DIR,
    filter_articles_by_date,
    prepare_article,
    save_markdown,
)


RAW_PATH = PROJECT_DIR / "data" / "raw" / "Medical Device" / "articles.json"
OUTPUT_DIR = PROJECT_DIR / "data" / "llm_ready" / "Medical Device"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare Medical Device articles for LLM analysis.")
    parser.add_argument("--start", default="2026-07-01", help="Start date, YYYY-MM-DD.")
    parser.add_argument("--end", default="2026-07-31", help="End date, YYYY-MM-DD.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    start_date = datetime.strptime(args.start, "%Y-%m-%d").date()
    end_date = datetime.strptime(args.end, "%Y-%m-%d").date()
    if start_date > end_date:
        raise ValueError("--start must be earlier than or equal to --end")

    if not RAW_PATH.exists():
        raise FileNotFoundError(f"Medical Device raw input not found: {RAW_PATH}")
    raw_articles = json.loads(RAW_PATH.read_text(encoding="utf-8"))
    if not isinstance(raw_articles, list):
        raise ValueError(f"{RAW_PATH} must contain a JSON list")

    filtered = filter_articles_by_date(raw_articles, start_date, end_date)
    prepared = [prepare_article(article) for article in filtered if isinstance(article, dict)]
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if start_date.year == end_date.year and start_date.month == end_date.month:
        suffix = f"{start_date.year}_{start_date.month:02d}"
    else:
        suffix = f"{start_date.isoformat()}_{end_date.isoformat()}".replace("-", "_")
    json_path = OUTPUT_DIR / f"articles_llm_ready_{suffix}.json"
    md_path = OUTPUT_DIR / f"articles_llm_ready_{suffix}.md"
    json_path.write_text(json.dumps(prepared, ensure_ascii=False, indent=2), encoding="utf-8")
    save_markdown(prepared, md_path)

    empty_count = sum(not article.get("main_text") for article in prepared)
    print("Medical Device LLM-ready preparation finished")
    print(f"- Raw articles: {len(raw_articles)}")
    print(f"- Date-filtered articles prepared: {len(prepared)}")
    print(f"- Empty article text: {empty_count}")
    print(f"- JSON: {json_path}")
    print(f"- Markdown: {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
