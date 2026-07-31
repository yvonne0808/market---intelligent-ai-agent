from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


PROJECT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = PROJECT_DIR.parent / "wewe-rss-local" / "data" / "wewe-rss.db"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check July pharma source coverage across WeWeRSS DB, raw, and LLM-ready files."
    )
    parser.add_argument("--start", default="2026-07-01", help="Start date, YYYY-MM-DD.")
    parser.add_argument("--end", default="2026-08-01", help="Exclusive end date, YYYY-MM-DD.")
    parser.add_argument("--category-keyword", default="医药", help="Feed category keyword.")
    parser.add_argument("--db-path", default=str(DEFAULT_DB_PATH), help="Path to wewe-rss.db.")
    return parser.parse_args()


def load_json_list(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, list) else []


def feed_id_from_url(url: str) -> str:
    if "/feeds/" not in url:
        return ""
    return url.split("/feeds/")[-1].split(".atom")[0]


def load_feed_ids(category_keyword: str) -> set[str]:
    config = yaml.safe_load((PROJECT_DIR / "config.yaml").read_text(encoding="utf-8")) or {}
    feed_ids = set()
    for feed in config.get("feeds", []):
        if category_keyword in str(feed.get("category", "")):
            feed_id = feed_id_from_url(str(feed.get("url", "")))
            if feed_id:
                feed_ids.add(feed_id)
    return feed_ids


def article_sets() -> tuple[set[str], set[tuple[str, str, str]], set[str], set[str]]:
    raw = load_json_list(PROJECT_DIR / "data" / "raw" / "articles.json")
    llm_july = load_json_list(PROJECT_DIR / "data" / "llm_ready" / "articles_llm_ready_2026_07.json")
    llm_all = load_json_list(PROJECT_DIR / "data" / "llm_ready" / "articles_llm_ready.json")

    raw_links = {str(article.get("link", "")) for article in raw if article.get("link")}
    raw_title_source = {
        (
            str(article.get("source_name", "")),
            str(article.get("title", "")),
            str(article.get("published", ""))[:10],
        )
        for article in raw
    }
    llm_july_links = {str(article.get("link", "")) for article in llm_july if article.get("link")}
    llm_all_links = {str(article.get("link", "")) for article in llm_all if article.get("link")}
    return raw_links, raw_title_source, llm_july_links, llm_all_links


def load_db_rows(db_path: Path, start_date: str, end_date: str) -> list[tuple[str, str, str, str, int]]:
    conn = sqlite3.connect(db_path)
    return conn.execute(
        """
        select f.id, f.mp_name, a.id, a.title, a.publish_time
        from articles a
        join feeds f on f.id = a.mp_id
        where a.publish_time >= strftime('%s', ?)
          and a.publish_time < strftime('%s', ?)
        order by f.mp_name, a.publish_time desc
        """,
        (f"{start_date} 00:00:00", f"{end_date} 00:00:00"),
    ).fetchall()


def main() -> int:
    args = parse_args()
    feed_ids = load_feed_ids(args.category_keyword)
    raw_links, raw_title_source, llm_july_links, llm_all_links = article_sets()
    rows = load_db_rows(Path(args.db_path), args.start, args.end)

    source_db_counts: Counter[str] = Counter()
    source_raw_missing: Counter[str] = Counter()
    source_july_missing: Counter[str] = Counter()
    source_all_missing: Counter[str] = Counter()

    missing_raw = []
    missing_july = []
    missing_all = []

    for feed_id, source_name, article_id, title, publish_time in rows:
        if feed_id not in feed_ids:
            continue
        source_db_counts[source_name] += 1
        published = datetime.fromtimestamp(publish_time, tz=timezone.utc).date().isoformat()
        link = f"https://mp.weixin.qq.com/s/{article_id}"

        in_raw = link in raw_links or (source_name, title, published) in raw_title_source
        if not in_raw:
            source_raw_missing[source_name] += 1
            missing_raw.append((published, source_name, title, link))
        if link not in llm_july_links:
            source_july_missing[source_name] += 1
            missing_july.append((published, source_name, title, link))
        if link not in llm_all_links:
            source_all_missing[source_name] += 1
            missing_all.append((published, source_name, title, link))

    print("July pharma coverage check")
    print(f"- category keyword: {args.category_keyword}")
    print(f"- configured feeds: {len(feed_ids)}")
    print(f"- DB July articles: {sum(source_db_counts.values())}")
    print(f"- missing raw: {len(missing_raw)}")
    print(f"- missing July LLM-ready: {len(missing_july)}")
    print(f"- missing all LLM-ready: {len(missing_all)}")
    print()
    print("source\tdb_july\tmissing_raw\tmissing_july_llm\tmissing_all_llm")
    for source in sorted(source_db_counts):
        print(
            f"{source}\t{source_db_counts[source]}\t"
            f"{source_raw_missing[source]}\t"
            f"{source_july_missing[source]}\t"
            f"{source_all_missing[source]}"
        )

    for label, rows_to_print in (
        ("missing raw", missing_raw),
        ("missing July LLM-ready", missing_july),
        ("missing all LLM-ready", missing_all),
    ):
        if rows_to_print:
            print(f"\n{label} examples:")
            for published, source_name, title, link in rows_to_print[:30]:
                print(f"{published}\t{source_name}\t{title}\t{link}")

    return 0 if not (missing_raw or missing_july or missing_all) else 1


if __name__ == "__main__":
    raise SystemExit(main())
