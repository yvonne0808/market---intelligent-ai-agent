from __future__ import annotations

import argparse
import json
import logging
import time
from datetime import date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import feedparser

from main import (
    PROJECT_DIR,
    build_article_record,
    check_wewe_rss,
    load_config,
    load_existing_articles,
    setup_logging,
    sleep_between_requests,
    write_article_outputs,
)


DEFAULT_START = "2026-07-01"
DEFAULT_END = "2026-07-31"
TARGET_CATEGORIES = {"医疗器械", "医药，医疗器械"}
OUTPUT_DIR = PROJECT_DIR / "data" / "raw" / "Medical Device"
SEEN_PATH = OUTPUT_DIR / "seen_articles.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Collect date-filtered articles from feeds whose category is exactly 医疗器械 "
            "or 医药，医疗器械."
        )
    )
    parser.add_argument("--start", default=DEFAULT_START, help="Start date, YYYY-MM-DD.")
    parser.add_argument("--end", default=DEFAULT_END, help="End date, YYYY-MM-DD.")
    parser.add_argument(
        "--feed-limit",
        type=int,
        default=300,
        help="Request this many recent entries from each WeWe RSS feed. Default: 300.",
    )
    parser.add_argument(
        "--limit-per-feed",
        type=int,
        default=0,
        help="Optional maximum matching entries per feed. 0 means no extra limit.",
    )
    parser.add_argument(
        "--no-sleep",
        action="store_true",
        help="Skip request sleep intervals for a faster focused run.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show matched feeds and date-filtered entry counts without fetching bodies or writing files.",
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
    return str(entry.get("link", "") or entry.get("id", "") or entry.get("guid", ""))


def with_feed_limit(url: str, limit: int) -> str:
    if limit <= 0:
        return url
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query["limit"] = str(limit)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def select_medical_device_feeds(config: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        feed
        for feed in config.get("feeds", [])
        if str(feed.get("category", "")).strip() in TARGET_CATEGORIES
    ]


def filter_entries_by_date(entries: list[Any], start_date: date, end_date: date) -> list[Any]:
    return [
        entry
        for entry in entries
        if (published_date := entry_date(entry))
        and start_date <= published_date <= end_date
    ]


def load_seen() -> set[str]:
    if not SEEN_PATH.exists():
        return set()
    try:
        payload = json.loads(SEEN_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        logging.warning("Medical Device seen file is invalid; starting with an empty set.")
        return set()
    if isinstance(payload, dict):
        payload = payload.get("seen_articles", [])
    return {str(item) for item in payload} if isinstance(payload, list) else set()


def save_seen(seen: set[str]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    SEEN_PATH.write_text(
        json.dumps(
            {
                "updated_at": datetime.now().isoformat(timespec="seconds"),
                "seen_articles": sorted(seen),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def save_run_snapshot(
    articles: list[dict[str, Any]], start_date: date, end_date: date
) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / (
        f"medical_device_articles_{start_date.isoformat()}_{end_date.isoformat()}.json"
    )
    path.write_text(json.dumps(articles, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def main() -> int:
    args = parse_args()
    start_date = parse_date(args.start)
    end_date = parse_date(args.end)
    if start_date > end_date:
        raise ValueError("--start must be earlier than or equal to --end")

    config = load_config()
    collector_config = dict(config.get("collector", {}))
    if args.no_sleep:
        collector_config["sleep_seconds_min"] = 0
        collector_config["sleep_seconds_max"] = 0

    log_dir = PROJECT_DIR / "data" / "logs" / "Medical Device"
    log_path = setup_logging(log_dir)
    feeds = select_medical_device_feeds(config)

    existing_articles = load_existing_articles(OUTPUT_DIR / "articles.json")
    existing_ids = {
        str(article.get("link") or article.get("article_id") or "")
        for article in existing_articles
        if article.get("link") or article.get("article_id")
    }
    seen = load_seen()
    dedupe_ids = existing_ids | seen

    total_entries = 0
    period_entries = 0
    skipped_existing = 0
    success_count = 0
    failed_count = 0
    new_articles: list[dict[str, Any]] = []
    feed_summaries: list[tuple[str, str, int, int, int]] = []

    logging.info("Starting date-filtered Medical Device collector.")
    logging.info("Allowed categories: %s", sorted(TARGET_CATEGORIES))
    logging.info("Date range: %s to %s", start_date, end_date)
    logging.info("Matched feeds: %s", len(feeds))

    for feed_config in feeds:
        feed_name = str(feed_config.get("name", ""))
        category = str(feed_config.get("category", ""))
        feed_url = with_feed_limit(str(feed_config.get("url", "")), args.feed_limit)
        logging.info("Reading feed: %s [%s] - %s", feed_name, category, feed_url)

        if not check_wewe_rss(feed_url):
            logging.warning("Feed URL is inaccessible or returned empty content: %s", feed_url)

        parsed = feedparser.parse(feed_url)
        if parsed.bozo:
            logging.warning("feedparser warning for %s: %s", feed_name, parsed.bozo_exception)

        entries = parsed.entries or []
        total_entries += len(entries)
        matched_entries = filter_entries_by_date(entries, start_date, end_date)
        if args.limit_per_feed > 0:
            matched_entries = matched_entries[: args.limit_per_feed]
        period_entries += len(matched_entries)
        feed_new_count = 0

        logging.info(
            "Feed %s entries=%s matched_entries=%s",
            feed_name,
            len(entries),
            len(matched_entries),
        )

        if args.dry_run:
            feed_summaries.append(
                (feed_name, category, len(entries), len(matched_entries), 0)
            )
            continue

        for entry in matched_entries:
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

            if article.get("fetch_status") == "success":
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

        feed_summaries.append(
            (feed_name, category, len(entries), len(matched_entries), feed_new_count)
        )

    snapshot_path = None
    output_paths = None
    if not args.dry_run:
        all_articles = existing_articles + new_articles
        output_paths = write_article_outputs(OUTPUT_DIR, all_articles)
        period_articles = filter_entries_by_date(all_articles, start_date, end_date)
        snapshot_path = save_run_snapshot(period_articles, start_date, end_date)
        save_seen(seen)

    print("\n医疗器械公众号抓取总结")
    print(f"- 日期范围: {start_date} 至 {end_date}")
    print(f"- 允许 category: {', '.join(sorted(TARGET_CATEGORIES))}")
    print(f"- 匹配公众号数: {len(feeds)}")
    print(f"- 扫描 feed entries: {total_entries}")
    print(f"- 日期范围内 entries: {period_entries}")
    print(f"- 跳过医疗器械库已有文章: {skipped_existing}")
    print(f"- 本次新增文章: {len(new_articles)}")
    print(f"- 正文成功: {success_count}")
    print(f"- 正文失败: {failed_count}")
    print(f"- 日志: {log_path}")

    if output_paths:
        print(f"- Medical Device raw JSON: {output_paths['json']}")
        print(f"- Medical Device raw CSV: {output_paths['csv']}")
        print(f"- Medical Device raw Excel: {output_paths['xlsx']}")
    if snapshot_path:
        print(f"- 日期范围完整快照: {snapshot_path}")

    print("\n按公众号统计")
    for feed_name, category, entry_count, matched_count, new_count in feed_summaries:
        print(
            f"- {feed_name} [{category}]: "
            f"feed={entry_count}, matched={matched_count}, new={new_count}"
        )

    if args.dry_run:
        print("\nDry run only. No article files were changed.")

    time.sleep(0.1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
