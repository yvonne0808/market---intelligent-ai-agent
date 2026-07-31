from __future__ import annotations

import argparse
import hashlib
import json
import logging
import shutil
import subprocess
import sys
import tempfile
from io import BytesIO
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from southeast_asia_medtech.config.config_loader import load_sources
from southeast_asia_medtech.scrapers.http_client import HttpSettings, PoliteHttpClient
from southeast_asia_medtech.scrapers.parsers import (
    DETAIL_PARSERS,
    LIST_PARSERS,
    ArticleStub,
    date_in_range,
    find_mda_document_url,
    normalize_url,
)


MODULE_DIR = Path(__file__).resolve().parents[1]
RAW_DIR = MODULE_DIR / "data" / "raw"
NORMALIZED_DIR = MODULE_DIR / "data" / "normalized"
LOG_DIR = MODULE_DIR / "logs"
RAW_PATH = RAW_DIR / "articles_raw.json"
NORMALIZED_PATH = NORMALIZED_DIR / "articles_normalized.json"
LOG_PATH = LOG_DIR / "scraper.log"

HSA_RELEVANCE_TERMS = (
    "medical device",
    "medical devices",
    "applicator",
    "sterility",
    "sterile",
    "field safety",
)
MIN_BODY_LENGTH = 80


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Collect and normalize configured HSA and MDA public announcements."
    )
    parser.add_argument("--start-date", required=True, help="Inclusive date in YYYY-MM-DD.")
    parser.add_argument("--end-date", required=True, help="Inclusive date in YYYY-MM-DD.")
    parser.add_argument(
        "--max-articles",
        type=int,
        default=5,
        help="Maximum new detail pages fetched per source (hard-capped at 5 in Step 3).",
    )
    parser.add_argument(
        "--source",
        action="append",
        default=[],
        help="Optional source_id; repeat to select multiple configured sources.",
    )
    parser.add_argument("--timeout", type=int, default=20)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--sleep-min", type=float, default=1.5)
    parser.add_argument("--sleep-max", type=float, default=3.0)
    return parser.parse_args()


def setup_logger(path: Path = LOG_PATH) -> logging.Logger:
    path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("southeast_asia_medtech.scraper")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    logger.propagate = False
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    file_handler = logging.FileHandler(path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    return logger


def parse_iso_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"Invalid date {value!r}; expected YYYY-MM-DD") from exc


def load_json_list(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, list):
        raise ValueError(f"Expected a JSON list: {path}")
    return [item for item in data if isinstance(item, dict)]


def save_json(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as file:
        json.dump(records, file, ensure_ascii=False, indent=2)
    temporary.replace(path)


def merge_by_url(
    existing: list[dict[str, Any]], updates: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Replace an existing URL record in place and append genuinely new URLs."""
    merged = [dict(item) for item in existing]
    index = {
        str(item.get("url", "")): position
        for position, item in enumerate(merged)
        if item.get("url")
    }
    for item in updates:
        url = str(item.get("url", ""))
        if url and url in index:
            merged[index[url]] = item
        else:
            if url:
                index[url] = len(merged)
            merged.append(item)
    return merged


def stable_article_id(source_id: str, url: str) -> str:
    digest = hashlib.sha256(f"{source_id}|{url}".encode("utf-8")).hexdigest()[:20]
    return f"{source_id}_{digest}"


def _is_hsa_relevant(stub: ArticleStub) -> bool:
    value = stub.list_text.lower()
    return any(term in value for term in HSA_RELEVANCE_TERMS)


def select_stubs(
    source: dict[str, Any],
    stubs: list[ArticleStub],
    start_date: date,
    end_date: date,
    known_urls: set[str],
    max_articles: int,
) -> tuple[list[ArticleStub], int]:
    period_stubs = [
        stub for stub in stubs if date_in_range(stub.published_date, start_date, end_date)
    ]
    if source["source_id"] == "sg_hsa_announcements":
        period_stubs = [stub for stub in period_stubs if _is_hsa_relevant(stub)]
    test_window = period_stubs[:max_articles]
    duplicate_count = sum(1 for stub in test_window if stub.url in known_urls)
    new_stubs = [stub for stub in test_window if stub.url not in known_urls]
    return new_stubs, duplicate_count


def reclassify_short_existing_records(records: list[dict[str, Any]]) -> int:
    """Correct older Step-3 records that contain only a heading or empty detail body."""
    corrected = 0
    for record in records:
        body = str(record.get("body", record.get("raw_text", "")) or "")
        if record.get("scrape_status") == "success" and len(body) < MIN_BODY_LENGTH:
            record["scrape_status"] = "failed"
            record["error_message"] = (
                f"body extraction too short ({len(body)} chars; minimum {MIN_BODY_LENGTH})"
            )
            corrected += 1
    return corrected


def extract_pdf_text(data: bytes) -> str:
    if not data.startswith(b"%PDF-"):
        raise ValueError("document response does not have a PDF signature")
    from pypdf import PdfReader

    reader = PdfReader(BytesIO(data))
    page_text = [page.extract_text() or "" for page in reader.pages]
    text = " ".join(" ".join(page_text).split())
    if len(text) >= MIN_BODY_LENGTH:
        return text

    tesseract = shutil.which("tesseract")
    if not tesseract:
        return text

    ocr_text: list[str] = []
    with tempfile.TemporaryDirectory(prefix="sea_medtech_mda_ocr_") as temp_dir:
        temp_path = Path(temp_dir)
        image_number = 0
        for page in reader.pages[:5]:
            for image in page.images:
                if len(image.data) < 10_000:
                    continue
                image_number += 1
                suffix = Path(image.name).suffix or ".png"
                image_path = temp_path / f"page_image_{image_number}{suffix}"
                image_path.write_bytes(image.data)
                result = subprocess.run(
                    [tesseract, str(image_path), "stdout", "-l", "eng"],
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=90,
                )
                if result.returncode == 0 and result.stdout.strip():
                    ocr_text.append(result.stdout)
        combined = " ".join(" ".join(ocr_text).split())
        return combined if len(combined) > len(text) else text


def raw_record(
    source: dict[str, Any],
    stub: ArticleStub,
    title: str,
    body: str,
    collected_at: str,
    http_status: int | None,
    status: str,
    error_message: str,
    attachment_url: str = "",
) -> dict[str, Any]:
    return {
        "source_id": source["source_id"],
        "source_name": source["source_name"],
        "country": source["country"],
        "organization": source["organization"],
        "title_from_list": stub.title,
        "title_from_detail": title,
        "published_date_raw": stub.published_date,
        "url": stub.url,
        "collected_at": collected_at,
        "http_status": http_status,
        "raw_text": body,
        "attachment_url": attachment_url,
        "scrape_status": status,
        "error_message": error_message,
    }


def normalized_record(
    source: dict[str, Any],
    stub: ArticleStub,
    title: str,
    body: str,
    collected_at: str,
    status: str,
    error_message: str,
    attachment_url: str = "",
) -> dict[str, Any]:
    canonical_url = normalize_url(source["base_url"], stub.url)
    return {
        "article_id": stable_article_id(source["source_id"], canonical_url),
        "title": title or stub.title,
        "source_name": source["source_name"],
        "country": source["country"],
        "organization": source["organization"],
        "source_type": source["source_type"],
        "published_date": stub.published_date,
        "collected_at": collected_at,
        "url": canonical_url,
        "language": source["language"],
        "body": body,
        "raw_text_length": len(body),
        "scrape_status": status,
        "error_message": error_message,
        "attachment_url": attachment_url,
    }


def scrape_one_source(
    source: dict[str, Any],
    client: PoliteHttpClient,
    logger: logging.Logger,
    start_date: date,
    end_date: date,
    known_urls: set[str],
    max_articles: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    source_id = source["source_id"]
    result = {
        "source_id": source_id,
        "list_items": 0,
        "period_items": 0,
        "duplicates_skipped": 0,
        "new_saved": 0,
        "success": 0,
        "failed": 0,
        "source_error": "",
    }
    raw_items: list[dict[str, Any]] = []
    normalized_items: list[dict[str, Any]] = []

    try:
        list_html, _list_status, _final_url = client.get_text(source["list_url"])
        stubs = LIST_PARSERS[source_id](list_html, source)
        result["list_items"] = len(stubs)
        period_items = [
            stub for stub in stubs if date_in_range(stub.published_date, start_date, end_date)
        ]
        if source_id == "sg_hsa_announcements":
            period_items = [stub for stub in period_items if _is_hsa_relevant(stub)]
            logger.warning(
                "HSA static HTML exposes the current first page only; the requested period "
                "is filtered from that page and historical client-side pagination is not "
                "claimed as covered."
            )
        result["period_items"] = len(period_items)
        selected, duplicate_count = select_stubs(
            source, stubs, start_date, end_date, known_urls, max_articles
        )
        result["duplicates_skipped"] = duplicate_count

        for stub in selected:
            collected_at = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
            title = stub.title
            body = ""
            status = "failed"
            error_message = ""
            http_status: int | None = None
            attachment_url = ""
            try:
                detail_html, http_status, _detail_url = client.get_text(stub.url)
                title, body = DETAIL_PARSERS[source_id](detail_html, stub.title)
                if len(body) < MIN_BODY_LENGTH and source_id in {
                    "my_mda_announcements", "my_mda_mmdr"
                }:
                    attachment_url = find_mda_document_url(detail_html, source["base_url"])
                    if attachment_url:
                        pdf_data, pdf_status, final_pdf_url, content_type = client.get_bytes(
                            attachment_url
                        )
                        http_status = pdf_status
                        attachment_url = final_pdf_url
                        if "pdf" not in content_type.lower():
                            raise ValueError(
                                f"MDA document is not PDF: Content-Type={content_type!r}"
                            )
                        body = extract_pdf_text(pdf_data)
                if not title:
                    error_message = "title extraction returned empty text"
                elif len(body) < MIN_BODY_LENGTH:
                    error_message = (
                        f"body extraction too short ({len(body)} chars; "
                        f"minimum {MIN_BODY_LENGTH})"
                    )
                else:
                    status = "success"
            except Exception as exc:
                error_message = f"{type(exc).__name__}: {exc}"
                logger.exception("Detail failed: %s | %s", stub.url, error_message)

            raw_items.append(
                raw_record(
                    source,
                    stub,
                    title,
                    body,
                    collected_at,
                    http_status,
                    status,
                    error_message,
                    attachment_url,
                )
            )
            normalized_items.append(
                normalized_record(
                    source,
                    stub,
                    title,
                    body,
                    collected_at,
                    status,
                    error_message,
                    attachment_url,
                )
            )
            known_urls.add(stub.url)
            result["new_saved"] += 1
            result[status] += 1

    except Exception as exc:
        result["source_error"] = f"{type(exc).__name__}: {exc}"
        result["failed"] += 1
        logger.exception("Source failed; continuing with remaining sources: %s", source_id)

    logger.info("Source summary: %s", json.dumps(result, ensure_ascii=False))
    return raw_items, normalized_items, result


def run(
    start_date: date,
    end_date: date,
    max_articles: int,
    selected_source_ids: set[str],
    settings: HttpSettings,
    logger: logging.Logger,
) -> dict[str, Any]:
    if start_date > end_date:
        raise ValueError("--start-date must not be after --end-date")
    max_articles = max(1, min(max_articles, 5))

    source_config = load_sources()
    sources = [
        source for source in source_config["sources"]
        if source.get("enabled") is True and source["source_id"] in LIST_PARSERS
    ]
    if selected_source_ids:
        unknown = selected_source_ids - {source["source_id"] for source in sources}
        if unknown:
            raise ValueError(f"Unknown or disabled source_id(s): {sorted(unknown)}")
        sources = [source for source in sources if source["source_id"] in selected_source_ids]

    existing_raw = load_json_list(RAW_PATH)
    existing_normalized = load_json_list(NORMALIZED_PATH)
    corrected_raw = reclassify_short_existing_records(existing_raw)
    corrected_normalized = reclassify_short_existing_records(existing_normalized)
    if corrected_raw or corrected_normalized:
        logger.warning(
            "Reclassified short existing records: raw=%s normalized=%s",
            corrected_raw,
            corrected_normalized,
        )
    known_urls = {
        str(item.get("url", ""))
        for item in existing_normalized
        if item.get("url") and item.get("scrape_status") == "success"
    }
    logger.info(
        "Run started: period=%s..%s sources=%s max_new_per_source=%s existing=%s",
        start_date,
        end_date,
        [source["source_id"] for source in sources],
        max_articles,
        len(existing_normalized),
    )

    client = PoliteHttpClient(settings, logger)
    summaries: list[dict[str, Any]] = []
    new_raw: list[dict[str, Any]] = []
    new_normalized: list[dict[str, Any]] = []
    for source in sources:
        raw_items, normalized_items, summary = scrape_one_source(
            source,
            client,
            logger,
            start_date,
            end_date,
            known_urls,
            max_articles,
        )
        new_raw.extend(raw_items)
        new_normalized.extend(normalized_items)
        summaries.append(summary)

    merged_raw = merge_by_url(existing_raw, new_raw)
    merged_normalized = merge_by_url(existing_normalized, new_normalized)
    save_json(RAW_PATH, merged_raw)
    save_json(NORMALIZED_PATH, merged_normalized)
    run_summary = {
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "max_articles_per_source": max_articles,
        "new_records": len(new_normalized),
        "total_records": len(merged_normalized),
        "sources": summaries,
        "raw_output": str(RAW_PATH),
        "normalized_output": str(NORMALIZED_PATH),
        "log": str(LOG_PATH),
    }
    logger.info("Run finished: %s", json.dumps(run_summary, ensure_ascii=False))
    return run_summary


def main() -> int:
    args = parse_args()
    logger = setup_logger()
    summary = run(
        parse_iso_date(args.start_date),
        parse_iso_date(args.end_date),
        args.max_articles,
        set(args.source),
        HttpSettings(args.timeout, args.retries, args.sleep_min, args.sleep_max),
        logger,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
