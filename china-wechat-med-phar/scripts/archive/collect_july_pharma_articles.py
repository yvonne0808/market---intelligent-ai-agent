from __future__ import annotations

import argparse
import json
import logging
import time
from datetime import date, datetime
from pathlib import Path
from typing import Any

import feedparser

from main import (
    PROJECT_DIR,
    build_article_record,
    check_wewe_rss,
    load_config,
    load_existing_articles,
    load_seen,
    save_seen,
    setup_logging,
    sleep_between_requests,
    write_article_outputs,
)


DEFAULT_START = "2026-07-01"
DEFAULT_END = "2026-07-31"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Collect July articles from feeds whose config category contains 医药."
    )
    parser.add_argument("--start", default=DEFAULT_START, help="Start date, YYYY-MM-DD.")
    parser.add_argument("--end", default=DEFAULT_END, help="End date, YYYY-MM-DD.")
    parser.add_argument(
        "--category-keyword",
        default="医药",
        help="Only collect feeds whose category contains this keyword. Default: 医药.",
    )
    parser.add_argument(
        "--exact-category",
        action="store_true",
        help="Require category to exactly equal --category-keyword instead of containing it.",
    )
    parser.add_argument(
        "--limit-per-feed",
        type=int,
        default=0,
        help="Optional max July articles per feed. 0 means no extra limit.",
    )
    parser.add_argument(
        "--no-sleep",
        action="store_true",
        help="Skip request sleep intervals for a faster focused run.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only show matched feeds and July entry counts. Do not fetch article body or write files.",
    )
    return parser.parse_args()


def parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def entry_date(entry: Any) -> date | None:
    parsed_time = entry.get("published_parsed") or entry.get("updated_parsed")
    if parsed_time:
        return date(parsed_time.tm_year, parsed_time.tm_mon, parsed_time.tm_mday)

    value = entry.get("published", "") or entry.get("updated", "")
    if not value:
        return None

    for fmt in ("%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(value[:10], fmt).date()
        except ValueError:
            continue
    return None


def entry_id(entry: Any) -> str:
    link = entry.get("link", "") or ""
    return link or entry.get("id", "") or entry.get("guid", "")


def select_feeds(
    config: dict[str, Any],
    category_keyword: str,
    exact_category: bool = False,
) -> list[dict[str, Any]]:
    feeds = config.get("feeds", [])
    selected = []
    for feed in feeds:
        category = str(feed.get("category", ""))
        if exact_category and category == category_keyword:
            selected.append(feed)
        elif not exact_category and category_keyword in category:
            selected.append(feed)
    return selected


def filter_entries_by_date(entries: list[Any], start_date: date, end_date: date) -> list[Any]:
    filtered = []
    for entry in entries:
        published_date = entry_date(entry)
        if not published_date:
            continue
        if start_date <= published_date <= end_date:
            filtered.append(entry)
    return filtered


def save_run_snapshot(articles: list[dict[str, Any]], start_date: date, end_date: date) -> Path:
    output_dir = PROJECT_DIR / "data" / "raw"
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"july_pharma_articles_{start_date.isoformat()}_{end_date.isoformat()}.json"
    path.write_text(json.dumps(articles, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def main() -> int:
    args = parse_args()
    start_date = parse_date(args.start)
    end_date = parse_date(args.end)
    if start_date > end_date:
        raise ValueError("--start must be earlier than or equal to --end")

    config = load_config()
    collector_config = config.get("collector", {})
    if args.no_sleep:
        collector_config["sleep_seconds_min"] = 0
        collector_config["sleep_seconds_max"] = 0

    output_dir = PROJECT_DIR / collector_config.get("output_dir", "data/raw")
    log_dir = PROJECT_DIR / collector_config.get("log_dir", "data/logs")
    log_path = setup_logging(log_dir)
    feeds = select_feeds(config, args.category_keyword, args.exact_category)

    existing_articles = load_existing_articles(output_dir / "articles.json")
    existing_ids = {
        str(article.get("link") or article.get("article_id") or "")
        for article in existing_articles
        if article.get("link") or article.get("article_id")
    }
    seen = load_seen()
    dedupe_ids = set(existing_ids) | set(seen)

    total_entries = 0
    july_entries = 0
    skipped_existing = 0
    success_count = 0
    failed_count = 0
    new_articles: list[dict[str, Any]] = []
    feed_summaries: list[tuple[str, int, int, int]] = []

    logging.info("Starting July pharma collector.")
    logging.info("Category keyword: %s", args.category_keyword)
    logging.info("Exact category match: %s", args.exact_category)
    logging.info("Date range: %s to %s", start_date, end_date)
    logging.info("Matched feeds: %s", len(feeds))

    for feed_config in feeds:
        feed_name = feed_config.get("name", "")
        feed_url = feed_config.get("url", "")
        logging.info("Reading feed: %s - %s", feed_name, feed_url)

        if not check_wewe_rss(feed_url):
            logging.warning("Feed URL is not accessible or returned empty content: %s", feed_url)

        parsed = feedparser.parse(feed_url)
        if parsed.bozo:
            logging.warning("feedparser warning for %s: %s", feed_name, parsed.bozo_exception)

        entries = parsed.entries or []
        total_entries += len(entries)
        july_feed_entries = filter_entries_by_date(entries, start_date, end_date)
        if args.limit_per_feed > 0:
            july_feed_entries = july_feed_entries[: args.limit_per_feed]
        july_entries += len(july_feed_entries)
        feed_new_count = 0

        logging.info(
            "Feed %s entries=%s july_entries=%s",
            feed_name,
            len(entries),
            len(july_feed_entries),
        )

        if args.dry_run:
            feed_summaries.append((feed_name, len(entries), len(july_feed_entries), 0))
            continue

        for entry in july_feed_entries:
            dedupe_key = entry_id(entry)
            if not dedupe_key:
                logging.warning("Skipping entry without link or id: %s", entry.get("title", ""))
                continue
            if dedupe_key in dedupe_ids:
                skipped_existing += 1
                continue

            article = build_article_record(feed_config, entry, collector_config)
            new_articles.append(article)
            dedupe_ids.add(dedupe_key)
            seen.add(dedupe_key)
            feed_new_count += 1

            if article["fetch_status"] == "success":
                success_count += 1
            else:
                failed_count += 1
                logging.warning(
                    "Content fetch failed: %s - %s",
                    article.get("title", ""),
                    article.get("fetch_error", ""),
                )

            sleep_between_requests(
                collector_config.get("sleep_seconds_min", 1),
                collector_config.get("sleep_seconds_max", 3),
            )

        feed_summaries.append((feed_name, len(entries), len(july_feed_entries), feed_new_count))

    snapshot_path = None
    output_paths = None
    if not args.dry_run:
        all_articles = existing_articles + new_articles
        output_paths = write_article_outputs(output_dir, all_articles)
        snapshot_path = save_run_snapshot(new_articles, start_date, end_date)
        save_seen(seen)

    logging.info("Total feed entries scanned: %s", total_entries)
    logging.info("July entries matched: %s", july_entries)
    logging.info("Skipped existing articles: %s", skipped_existing)
    logging.info("New articles: %s", len(new_articles))
    logging.info("Content fetch success: %s", success_count)
    logging.info("Content fetch failed: %s", failed_count)
    logging.info("Log file: %s", log_path)

    print("\n七月医药类公众号抓取总结")
    print(f"- 日期范围: {start_date} 至 {end_date}")
    print(f"- category 关键词: {args.category_keyword}")
    print(f"- category 匹配方式: {'完全等于' if args.exact_category else '包含'}")
    print(f"- 匹配公众号数: {len(feeds)}")
    print(f"- 扫描 feed entries: {total_entries}")
    print(f"- 七月 entries: {july_entries}")
    print(f"- 跳过已存在文章: {skipped_existing}")
    print(f"- 新增文章: {len(new_articles)}")
    print(f"- 正文成功: {success_count}")
    print(f"- 正文失败: {failed_count}")
    print(f"- 日志: {log_path}")

    if output_paths:
        print(f"- 已更新 raw JSON: {output_paths['json']}")
        print(f"- 已更新 raw CSV: {output_paths['csv']}")
        print(f"- 已更新 raw Excel: {output_paths['xlsx']}")
    if snapshot_path:
        print(f"- 本次抓取快照: {snapshot_path}")

    print("\n按公众号统计")
    for feed_name, entry_count, july_count, new_count in feed_summaries:
        print(f"- {feed_name}: feed={entry_count}, july={july_count}, new={new_count}")

    if args.dry_run:
        print("\nDry run only. No files were changed.")

    # A tiny delay keeps the final log flush predictable on some terminals.
    time.sleep(0.1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
