from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml


PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR / "scripts") not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR / "scripts"))

from main import write_article_outputs  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sync stored raw article source metadata from current config.yaml."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only print how many records would change. Do not write files.",
    )
    return parser.parse_args()


def load_config_by_source() -> dict[str, dict[str, Any]]:
    config = yaml.safe_load((PROJECT_DIR / "config.yaml").read_text(encoding="utf-8")) or {}
    return {
        str(feed.get("name", "")): feed
        for feed in config.get("feeds", [])
        if feed.get("name")
    }


def load_articles() -> list[dict[str, Any]]:
    path = PROJECT_DIR / "data" / "raw" / "articles.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("data/raw/articles.json must contain a JSON list.")
    return [item for item in data if isinstance(item, dict)]


def sync_article(article: dict[str, Any], feed: dict[str, Any]) -> bool:
    updates = {
        "source_category": feed.get("category", ""),
        "source_tags": feed.get("tags", []),
        "source_priority": feed.get("priority", ""),
        "feed_url": feed.get("url", ""),
    }
    changed = False
    for key, value in updates.items():
        if article.get(key) != value:
            article[key] = value
            changed = True
    return changed


def main() -> int:
    args = parse_args()
    config_by_source = load_config_by_source()
    articles = load_articles()

    changed_count = 0
    missing_sources = set()
    for article in articles:
        source_name = str(article.get("source_name", ""))
        feed = config_by_source.get(source_name)
        if not feed:
            missing_sources.add(source_name)
            continue
        if sync_article(article, feed):
            changed_count += 1

    print("Source metadata sync")
    print(f"- raw articles: {len(articles)}")
    print(f"- changed records: {changed_count}")
    if missing_sources:
        print(f"- sources missing from config: {', '.join(sorted(missing_sources))}")

    if args.dry_run:
        print("Dry run only. No files were changed.")
        return 0

    output_dir = PROJECT_DIR / "data" / "raw"
    output_paths = write_article_outputs(output_dir, articles)
    print(f"- updated JSON: {output_paths['json']}")
    print(f"- updated CSV: {output_paths['csv']}")
    print(f"- updated Excel: {output_paths['xlsx']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
