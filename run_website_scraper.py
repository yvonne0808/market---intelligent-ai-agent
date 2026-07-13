from __future__ import annotations

import argparse
import re
from datetime import datetime
from pathlib import Path

from website_scraper.article_cleaner import to_clean_article
from website_scraper.config_loader import load_website_sources
from website_scraper.utils import read_text_sample, save_json, setup_logger
from website_scraper.web_scraper import ScraperSettings, WebsiteScraper


PROJECT_DIR = Path(__file__).resolve().parent
CONFIG_PATH = PROJECT_DIR / "website_sources.yaml"
RAW_OUTPUT_PATH = PROJECT_DIR / "data" / "website" / "raw" / "raw_website_articles.json"
CLEANED_OUTPUT_PATH = PROJECT_DIR / "data" / "website" / "cleaned" / "cleaned_website_articles.json"
LOG_PATH = PROJECT_DIR / "logs" / "website_scraper.log"

MONTH_ALIASES = {
    "jan": (1, "January"),
    "january": (1, "January"),
    "1": (1, "January"),
    "01": (1, "January"),
    "feb": (2, "February"),
    "february": (2, "February"),
    "2": (2, "February"),
    "02": (2, "February"),
    "mar": (3, "March"),
    "march": (3, "March"),
    "3": (3, "March"),
    "03": (3, "March"),
    "apr": (4, "April"),
    "april": (4, "April"),
    "4": (4, "April"),
    "04": (4, "April"),
    "may": (5, "May"),
    "5": (5, "May"),
    "05": (5, "May"),
    "jun": (6, "June"),
    "june": (6, "June"),
    "6": (6, "June"),
    "06": (6, "June"),
    "jul": (7, "July"),
    "july": (7, "July"),
    "7": (7, "July"),
    "07": (7, "July"),
    "aug": (8, "August"),
    "august": (8, "August"),
    "8": (8, "August"),
    "08": (8, "August"),
    "sep": (9, "September"),
    "september": (9, "September"),
    "9": (9, "September"),
    "09": (9, "September"),
    "oct": (10, "October"),
    "october": (10, "October"),
    "10": (10, "October"),
    "nov": (11, "November"),
    "november": (11, "November"),
    "11": (11, "November"),
    "dec": (12, "December"),
    "december": (12, "December"),
    "12": (12, "December"),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scrape public website news articles.")
    parser.add_argument(
        "--max_articles",
        type=int,
        default=10,
        help="Maximum articles per enabled source. Use 0 for no limit on the list page.",
    )
    parser.add_argument(
        "--month",
        default="all",
        help="Only keep articles from this month, for example June, Jun, or 6. Use 'all' to disable.",
    )
    parser.add_argument(
        "--year",
        type=int,
        default=datetime.now().year,
        help="Only keep articles from this year when --month is enabled.",
    )
    parser.add_argument(
        "--max_pages",
        type=int,
        default=50,
        help="Maximum list pages to scan while paginating.",
    )
    parser.add_argument(
        "--no_paginate",
        action="store_true",
        help="Only scan the first list page.",
    )
    parser.add_argument(
        "--paginate",
        action="store_true",
        help="Scan static list pages with pagination. Month filtering enables this automatically.",
    )
    parser.add_argument("--timeout", type=int, default=20, help="Network timeout in seconds.")
    parser.add_argument("--retries", type=int, default=3, help="Retry count for each request.")
    parser.add_argument("--sleep_min", type=float, default=1.0, help="Minimum sleep seconds between requests.")
    parser.add_argument("--sleep_max", type=float, default=2.5, help="Maximum sleep seconds between requests.")
    return parser.parse_args()


def parse_month_filter(month_value: str) -> tuple[int | None, str]:
    month_value = (month_value or "").strip().lower()
    if month_value in {"", "all", "none"}:
        return None, ""
    if month_value not in MONTH_ALIASES:
        raise ValueError(f"Unsupported month filter: {month_value}")
    return MONTH_ALIASES[month_value]


def output_paths_for_period(period_label: str) -> tuple[Path, Path]:
    if not period_label:
        return RAW_OUTPUT_PATH, CLEANED_OUTPUT_PATH

    suffix = period_label.lower()
    raw_path = PROJECT_DIR / "data" / "website" / "raw" / f"raw_website_articles_{suffix}.json"
    cleaned_path = PROJECT_DIR / "data" / "website" / "cleaned" / f"cleaned_website_articles_{suffix}.json"
    return raw_path, cleaned_path


def publish_date_year_month(publish_date: str) -> tuple[int, int] | None:
    match = re.search(r"(20\d{2})[-/.年](\d{1,2})[-/.月]\d{1,2}", publish_date or "")
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def filter_articles_by_month(articles: list[dict], month_number: int | None, year: int | None) -> list[dict]:
    if month_number is None:
        return articles
    filtered_articles = []
    for article in articles:
        parsed = publish_date_year_month(article.get("publish_date", ""))
        if not parsed:
            continue
        article_year, article_month = parsed
        if article_month == month_number and (year is None or article_year == year):
            filtered_articles.append(article)
    return filtered_articles


def build_raw_output(raw_articles: list[dict]) -> list[dict]:
    """Keep raw output useful for debugging without making the JSON too huge."""
    output = []
    for article in raw_articles:
        item = dict(article)
        item["raw_html_sample"] = read_text_sample(item.pop("raw_html", ""), limit=1200)
        output.append(item)
    return output


def main() -> None:
    args = parse_args()
    logger = setup_logger(LOG_PATH)
    month_number, period_label = parse_month_filter(args.month)
    max_articles = None if args.max_articles <= 0 else args.max_articles
    raw_output_path, cleaned_output_path = output_paths_for_period(period_label)
    paginate_static = (args.paginate or month_number is not None) and not args.no_paginate

    logger.info("Website scraper started")
    if period_label:
        logger.info("Month filter enabled: %s %s", period_label, args.year)
    if max_articles is None:
        logger.info("Max articles: no limit on each list page")
    if paginate_static:
        logger.info("Pagination enabled. max_pages=%s", args.max_pages)
    sources = load_website_sources(CONFIG_PATH)
    logger.info("Enabled website sources: %s", len(sources))

    settings = ScraperSettings(
        timeout=args.timeout,
        retries=args.retries,
        sleep_min=args.sleep_min,
        sleep_max=args.sleep_max,
    )
    scraper = WebsiteScraper(settings=settings, logger=logger, project_dir=PROJECT_DIR)
    raw_articles = scraper.scrape_enabled_sources(
        sources,
        max_articles=max_articles,
        paginate_static=paginate_static,
        max_pages=args.max_pages,
        target_year=args.year if month_number is not None else None,
        target_month=month_number,
    )
    raw_count_before_filter = len(raw_articles)
    raw_articles = filter_articles_by_month(raw_articles, month_number, args.year if month_number is not None else None)

    if period_label:
        for article in raw_articles:
            article["output_period"] = period_label

    cleaned_articles = [to_clean_article(article) for article in raw_articles]
    if period_label:
        for article in cleaned_articles:
            article["output_period"] = period_label

    save_json(raw_output_path, build_raw_output(raw_articles))
    save_json(cleaned_output_path, cleaned_articles)

    success_count = sum(1 for article in cleaned_articles if article.get("status") == "success")
    failed_count = len(cleaned_articles) - success_count
    source_names = sorted({article.get("source_name", "") for article in cleaned_articles if article.get("source_name")})
    logger.info(
        "Website scraper finished. fetched_before_filter=%s kept_after_filter=%s success=%s failed=%s",
        raw_count_before_filter,
        len(cleaned_articles),
        success_count,
        failed_count,
    )
    for source_name in source_names:
        source_success_count = sum(
            1
            for article in cleaned_articles
            if article.get("source_name") == source_name and article.get("status") == "success"
        )
        source_failed_count = sum(
            1
            for article in cleaned_articles
            if article.get("source_name") == source_name and article.get("status") != "success"
        )
        logger.info("Source summary: %s success=%s failed=%s", source_name, source_success_count, source_failed_count)

    for article in cleaned_articles:
        if article.get("status") != "success":
            logger.warning("Failed article: %s | %s", article.get("url", ""), article.get("error_message", ""))

    print("")
    print("Website scraping finished")
    if period_label:
        print(f"月份过滤: {period_label} {args.year}")
    print(f"过滤前抓取: {raw_count_before_filter} 篇")
    print(f"过滤后保留: {len(cleaned_articles)} 篇")
    print(f"成功抓取: {success_count} 篇")
    print(f"失败: {failed_count} 篇")
    for source_name in source_names:
        source_success_count = sum(
            1
            for article in cleaned_articles
            if article.get("source_name") == source_name and article.get("status") == "success"
        )
        source_failed_count = sum(
            1
            for article in cleaned_articles
            if article.get("source_name") == source_name and article.get("status") != "success"
        )
        print(f"{source_name}: 成功 {source_success_count} 篇，失败 {source_failed_count} 篇")
    print(f"Raw 输出: {raw_output_path}")
    print(f"Cleaned 输出: {cleaned_output_path}")
    print(f"日志: {LOG_PATH}")


if __name__ == "__main__":
    main()
