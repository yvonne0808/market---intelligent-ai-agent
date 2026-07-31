from __future__ import annotations

import argparse
import json
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any

from southeast_asia_medtech.config.config_loader import load_sources
from southeast_asia_medtech.scrapers.http_client import HttpSettings, PoliteHttpClient
from southeast_asia_medtech.scrapers.run_phase1_sources import (
    MODULE_DIR,
    sample_source,
    save_json,
    setup_logger,
)


MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11,
    "december": 12, "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
    "januari": 1, "februari": 2, "maret": 3, "mei": 5, "juni": 6,
    "juli": 7, "agustus": 8, "september": 9, "oktober": 10,
    "november": 11, "desember": 12,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect one month from all enabled SEA MedTech sources.")
    parser.add_argument("--month", required=True, help="Month in YYYY-MM format.")
    parser.add_argument("--source", action="append", default=[])
    parser.add_argument(
        "--max-candidates",
        type=int,
        default=2000,
        help="Safety ceiling per source; monthly collection is otherwise unbounded.",
    )
    parser.add_argument("--timeout", type=int, default=25)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--sleep-min", type=float, default=1.0)
    parser.add_argument("--sleep-max", type=float, default=2.0)
    return parser.parse_args()


def parse_publication_date(value: str) -> date | None:
    text = " ".join(str(value or "").replace(",", " ").split()).casefold()
    if not text or text in {"undated", "2026"}:
        return None
    iso = re.search(r"\b(20\d{2})[-/.](\d{1,2})[-/.](\d{1,2})\b", text)
    if iso:
        return date(int(iso.group(1)), int(iso.group(2)), int(iso.group(3)))
    numeric = re.search(r"\b(\d{1,2})[-/.](\d{1,2})[-/.](20\d{2})\b", text)
    if numeric:
        return date(int(numeric.group(3)), int(numeric.group(2)), int(numeric.group(1)))
    day_first = re.search(r"\b(\d{1,2})\s+([a-z]+)\s+(20\d{2})\b", text)
    if day_first and day_first.group(2) in MONTHS:
        return date(int(day_first.group(3)), MONTHS[day_first.group(2)], int(day_first.group(1)))
    month_first = re.search(r"\b([a-z]+)\s+(\d{1,2})\s+(20\d{2})\b", text)
    if month_first and month_first.group(1) in MONTHS:
        return date(int(month_first.group(3)), MONTHS[month_first.group(1)], int(month_first.group(2)))
    return None


def run(args: argparse.Namespace) -> dict[str, Any]:
    try:
        month_start = datetime.strptime(args.month, "%Y-%m").date().replace(day=1)
    except ValueError as exc:
        raise ValueError("--month must use YYYY-MM") from exc
    next_month = (
        date(month_start.year + 1, 1, 1)
        if month_start.month == 12
        else date(month_start.year, month_start.month + 1, 1)
    )
    logger = setup_logger()
    config = load_sources()
    sources = [source for source in config["sources"] if source.get("enabled") is True]
    selected = set(args.source)
    if selected:
        sources = [source for source in sources if source["source_id"] in selected]
    client = PoliteHttpClient(
        HttpSettings(args.timeout, args.retries, args.sleep_min, args.sleep_max), logger
    )
    def candidate_date_filter(value: str) -> bool | None:
        if not str(value or "").strip():
            return None
        parsed = parse_publication_date(value)
        return parsed is not None and month_start <= parsed < next_month

    def record_date_filter(value: str) -> bool:
        parsed = parse_publication_date(value)
        return parsed is not None and month_start <= parsed < next_month

    raw_path = MODULE_DIR / "data" / "raw" / args.month / "articles_raw.json"
    normalized_path = MODULE_DIR / "data" / "normalized" / args.month / "articles_normalized.json"
    summary_path = MODULE_DIR / "data" / "normalized" / args.month / "collection_summary.json"
    selected_ids = {source["source_id"] for source in sources}
    existing_records = (
        json.loads(normalized_path.read_text(encoding="utf-8"))
        if selected and normalized_path.exists()
        else []
    )
    output_records: list[dict[str, Any]] = [
        record for record in existing_records
        if record.get("source_id") not in selected_ids
    ]
    existing_summaries: list[dict[str, Any]] = []
    if selected and summary_path.exists():
        existing_summary = json.loads(summary_path.read_text(encoding="utf-8"))
        existing_summaries = existing_summary.get("sources", [])
    summaries: list[dict[str, Any]] = [
        item for item in existing_summaries if item.get("source_id") not in selected_ids
    ]
    for source in sources:
        records, crawl_summary = sample_source(
            source,
            client,
            max(1, args.max_candidates),
            logger,
            candidate_date_filter=candidate_date_filter,
            record_date_filter=record_date_filter,
        )
        monthly = []
        undated = 0
        for record in records:
            parsed = parse_publication_date(str(record.get("published_date", "")))
            if parsed is None:
                undated += 1
                continue
            if month_start <= parsed < next_month:
                record["published_date"] = parsed.isoformat()
                record["report_month"] = args.month
                monthly.append(record)
        output_records.extend(monthly)
        summaries.append(
            {
                "source_id": source["source_id"],
                "source_name": source["source_name"],
                "crawl_status": crawl_summary["status"],
                "accessible_records_examined": len(records),
                "monthly_records": len(monthly),
                "undated_records_excluded": undated,
                "endpoint_errors": crawl_summary["endpoint_errors"],
                "detail_failure_count": crawl_summary["detail_failure_count"],
                "acquisition_mode": crawl_summary["acquisition_mode"],
                "status": "collected" if monthly else (
                    "access_failed" if not records else "no_updates_in_month"
                ),
            }
        )

    unique = {str(record["url"]): record for record in output_records}
    records = sorted(
        unique.values(),
        key=lambda item: (str(item.get("published_date", "")), str(item.get("source_id", ""))),
        reverse=True,
    )
    save_json(raw_path, records)
    save_json(normalized_path, records)
    result = {
        "month": args.month,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "configured_sources": len(sources),
        "articles_collected": len(records),
        "sources_with_articles": sum(item["monthly_records"] > 0 for item in summaries),
        "sources_access_failed": sum(item["status"] == "access_failed" for item in summaries),
        "sources": summaries,
        "normalized_output": str(normalized_path),
    }
    save_json(summary_path, result)
    return result


def main() -> int:
    result = run(parse_args())
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
