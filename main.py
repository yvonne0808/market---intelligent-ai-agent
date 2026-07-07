from __future__ import annotations

import csv
import hashlib
import json
import logging
import random
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import feedparser
import pandas as pd
import requests
import yaml
from bs4 import BeautifulSoup


PROJECT_DIR = Path(__file__).resolve().parent
CONFIG_PATH = PROJECT_DIR / "config.yaml"
SEEN_PATH = PROJECT_DIR / "seen_articles.json"

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Apple Silicon Mac OS X) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0 Safari/537.36"
)

ARTICLE_FIELDS = [
    "source_name",
    "source_category",
    "source_tags",
    "source_priority",
    "feed_url",
    "title",
    "link",
    "published",
    "article_id",
    "scraped_at",
    "rss_summary",
    "content_text",
    "content_html",
    "word_count",
    "content_source",
    "fetch_status",
    "fetch_error",
    "image_count",
    "image_urls",
    "image_ocr_text",
    "image_fetch_status",
    "image_fetch_error",
]

EXCEL_CELL_LIMIT = 32767


def load_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"config.yaml not found: {CONFIG_PATH}")
    with CONFIG_PATH.open("r", encoding="utf-8") as file:
        config = yaml.safe_load(file) or {}
    if not config.get("feeds"):
        raise ValueError("config.yaml must contain at least one feed in feeds.")
    return config


def setup_logging(log_dir: Path) -> Path:
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(log_path, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )
    return log_path


def load_seen() -> set[str]:
    if not SEEN_PATH.exists():
        return set()
    try:
        with SEEN_PATH.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except json.JSONDecodeError:
        logging.warning("seen_articles.json is invalid JSON. Starting with empty seen set.")
        return set()

    if isinstance(data, list):
        return {str(item) for item in data}
    if isinstance(data, dict):
        items = data.get("seen_articles", [])
        return {str(item) for item in items}
    return set()


def save_seen(seen: set[str]) -> None:
    payload = {
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "seen_articles": sorted(seen),
    }
    with SEEN_PATH.open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)


def normalize_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text or "")
    return text.strip()


def safe_filename(value: str, fallback: str = "article") -> str:
    value = re.sub(r"[^a-zA-Z0-9._-]+", "_", value or "").strip("_")
    return value[:80] or fallback


def get_image_url(img: Any, base_url: str) -> str:
    for attr in ("data-src", "data-original", "data-backsrc", "src"):
        value = img.get(attr)
        if value:
            return urljoin(base_url, value)
    return ""


def extract_image_candidates(html: str, base_url: str) -> list[dict[str, str]]:
    if not html:
        return []

    soup = BeautifulSoup(html, "lxml")
    images: list[dict[str, str]] = []
    seen_urls: set[str] = set()

    for index, img in enumerate(soup.find_all("img"), start=1):
        url = get_image_url(img, base_url)
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        images.append(
            {
                "index": str(index),
                "url": url,
                "alt": normalize_text(img.get("alt", "")),
                "title": normalize_text(img.get("title", "")),
                "data_w": str(img.get("data-w", "")),
                "data_ratio": str(img.get("data-ratio", "")),
            }
        )

    return images


def image_extension_from_response(response: requests.Response, image_url: str) -> str:
    content_type = response.headers.get("Content-Type", "").split(";")[0].strip().lower()
    if content_type == "image/png":
        return ".png"
    if content_type in {"image/jpeg", "image/jpg"}:
        return ".jpg"
    if content_type == "image/webp":
        return ".webp"
    if content_type == "image/gif":
        return ".gif"

    suffix = Path(urlparse(image_url).path).suffix.lower()
    if suffix in {".png", ".jpg", ".jpeg", ".webp", ".gif"}:
        return suffix
    return ".img"


def download_image(image_url: str, image_dir: Path, image_index: int) -> Path:
    response = requests.get(image_url, headers={"User-Agent": USER_AGENT}, timeout=20)
    response.raise_for_status()
    extension = image_extension_from_response(response, image_url)
    image_path = image_dir / f"image_{image_index:03d}{extension}"
    image_path.write_bytes(response.content)
    return image_path


def run_tesseract_ocr(image_path: Path, language: str) -> str:
    if not shutil.which("tesseract"):
        return ""
    result = subprocess.run(
        ["tesseract", str(image_path), "stdout", "-l", language],
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.returncode != 0:
        logging.warning("OCR failed for %s: %s", image_path, result.stderr.strip())
        return ""
    return normalize_text(result.stdout)


def enrich_content_with_images(
    article: dict[str, Any],
    collector_config: dict[str, Any],
    force_ocr: bool = False,
) -> dict[str, Any]:
    if not collector_config.get("extract_images", True):
        article.setdefault("image_count", 0)
        article.setdefault("image_urls", [])
        article.setdefault("image_ocr_text", "")
        article.setdefault("image_fetch_status", "skipped")
        article.setdefault("image_fetch_error", "image extraction disabled")
        return article

    content_html = article.get("content_html", "") or ""
    link = article.get("link", "") or ""
    images = extract_image_candidates(content_html, link)
    article["image_count"] = len(images)
    article["image_urls"] = [image["url"] for image in images]

    if not images:
        article["image_ocr_text"] = ""
        article["image_fetch_status"] = "skipped"
        article["image_fetch_error"] = "no images found in content_html"
        return article

    image_notes = []
    for image in images:
        note_parts = [f"图片{image['index']}: {image['url']}"]
        if image.get("alt"):
            note_parts.append(f"alt={image['alt']}")
        if image.get("title"):
            note_parts.append(f"title={image['title']}")
        image_notes.append(" | ".join(note_parts))

    ocr_enabled = collector_config.get("ocr_images", False)
    ocr_texts: list[str] = []
    errors: list[str] = []

    should_run_ocr = ocr_enabled and (force_ocr or not article.get("image_ocr_text"))

    if should_run_ocr:
        if not shutil.which("tesseract"):
            errors.append("tesseract not installed; image OCR skipped")
        else:
            image_root = PROJECT_DIR / collector_config.get("image_dir", "data/raw/images")
            article_key = article.get("article_id") or article.get("link") or article.get("title") or "article"
            article_hash = hashlib.sha1(str(article_key).encode("utf-8")).hexdigest()[:12]
            article_dir = image_root / safe_filename(article.get("title", ""), article_hash)
            article_dir.mkdir(parents=True, exist_ok=True)
            ocr_language = collector_config.get("ocr_language", "chi_sim+eng")

            for idx, image in enumerate(images, start=1):
                try:
                    image_path = download_image(image["url"], article_dir, idx)
                    ocr_text = run_tesseract_ocr(image_path, ocr_language)
                    if ocr_text:
                        ocr_texts.append(f"图片{idx} OCR: {ocr_text}")
                except Exception as exc:  # noqa: BLE001 - keep article processing resilient.
                    errors.append(f"image {idx} failed: {exc}")

    image_context_parts = []
    if image_notes:
        image_context_parts.append("[图片信息]\n" + "\n".join(image_notes))
    if ocr_texts:
        image_context_parts.append("[图片OCR文字]\n" + "\n".join(ocr_texts))

    if ocr_texts:
        article["image_ocr_text"] = "\n".join(ocr_texts)
    else:
        article["image_ocr_text"] = article.get("image_ocr_text", "")
    article["image_fetch_status"] = "success" if image_notes or ocr_texts else "failed"
    article["image_fetch_error"] = "; ".join(errors)

    if image_context_parts:
        original_text = article.get("content_text", "") or ""
        original_text = re.sub(
            r"\s*\[图片OCR文字\]\n.*$",
            "",
            original_text,
            flags=re.S,
        )
        article["content_text"] = normalize_text(
            original_text + "\n\n" + "\n\n".join(image_context_parts)
        )
        article["word_count"] = len(article["content_text"])

    return article


def get_entry_summary(entry: Any) -> str:
    for key in ("summary", "description"):
        value = entry.get(key)
        if value:
            return normalize_text(BeautifulSoup(value, "lxml").get_text(" ", strip=True))

    content = entry.get("content")
    if isinstance(content, list) and content:
        value = content[0].get("value", "")
        if value:
            return normalize_text(BeautifulSoup(value, "lxml").get_text(" ", strip=True))

    return ""


def get_entry_content_html(entry: Any) -> str:
    content = entry.get("content")
    if isinstance(content, list) and content:
        value = content[0].get("value", "")
        if value:
            return value

    for key in ("summary", "description"):
        value = entry.get(key)
        if value:
            return value

    return ""


def extract_text_and_html_from_rss(entry: Any) -> tuple[str, str, str]:
    html = get_entry_content_html(entry)
    if not html:
        return "", "", "empty"
    soup = BeautifulSoup(html, "lxml")
    text = normalize_text(soup.get_text(" ", strip=True))
    if text:
        return text, html, "rss"
    return "", "", "empty"


def fetch_wechat_page(link: str, timeout: int = 20) -> dict[str, str]:
    if not link:
        return {
            "content_text": "",
            "content_html": "",
            "content_source": "empty",
            "fetch_status": "failed",
            "fetch_error": "empty article link",
        }

    try:
        response = requests.get(
            link,
            headers={"User-Agent": USER_AGENT},
            timeout=timeout,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        return {
            "content_text": "",
            "content_html": "",
            "content_source": "empty",
            "fetch_status": "failed",
            "fetch_error": f"request failed: {exc}",
        }

    soup = BeautifulSoup(response.text, "lxml")
    content_div = soup.select_one("div#js_content")
    if content_div:
        content_html = str(content_div)
        content_text = normalize_text(content_div.get_text(" ", strip=True))
        if content_text:
            return {
                "content_text": content_text,
                "content_html": content_html,
                "content_source": "wechat_page",
                "fetch_status": "success",
                "fetch_error": "",
            }

    meta_description = soup.select_one('meta[name="description"]')
    if meta_description and meta_description.get("content"):
        content_text = normalize_text(meta_description["content"])
        return {
            "content_text": content_text,
            "content_html": "",
            "content_source": "meta_description",
            "fetch_status": "success",
            "fetch_error": "",
        }

    return {
        "content_text": "",
        "content_html": "",
        "content_source": "empty",
        "fetch_status": "failed",
        "fetch_error": "div#js_content and meta description not found",
    }


def build_article_record(
    feed_config: dict[str, Any],
    entry: Any,
    collector_config: dict[str, Any],
) -> dict[str, Any]:
    link = entry.get("link", "") or ""
    article_id = entry.get("id", "") or entry.get("guid", "") or link
    rss_summary = get_entry_summary(entry)
    rss_text, rss_html, rss_source = extract_text_and_html_from_rss(entry)

    if rss_text:
        content = {
            "content_text": rss_text,
            "content_html": rss_html,
            "content_source": rss_source,
            "fetch_status": "success",
            "fetch_error": "",
        }
    else:
        content = fetch_wechat_page(link)

    content_text = content["content_text"]

    article = {
        "source_name": feed_config.get("name", ""),
        "source_category": feed_config.get("category", ""),
        "source_tags": feed_config.get("tags", []),
        "source_priority": feed_config.get("priority", ""),
        "feed_url": feed_config.get("url", ""),
        "title": entry.get("title", "") or "",
        "link": link,
        "published": entry.get("published", "") or entry.get("updated", "") or "",
        "article_id": article_id,
        "scraped_at": datetime.now().isoformat(timespec="seconds"),
        "rss_summary": rss_summary,
        "content_text": content_text,
        "content_html": content["content_html"],
        "word_count": len(content_text),
        "content_source": content["content_source"],
        "fetch_status": content["fetch_status"],
        "fetch_error": content["fetch_error"],
    }
    return enrich_content_with_images(article, collector_config)


def load_existing_articles(json_path: Path) -> list[dict[str, Any]]:
    if not json_path.exists():
        return []
    try:
        with json_path.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except json.JSONDecodeError:
        logging.warning("Existing articles.json is invalid JSON. Keeping a backup is recommended.")
        return []
    if isinstance(data, list):
        return data
    return []


def record_for_csv(article: dict[str, Any]) -> dict[str, Any]:
    row = article.copy()
    row["source_tags"] = ", ".join(row.get("source_tags", []))
    row["image_urls"] = json.dumps(row.get("image_urls", []), ensure_ascii=False)
    return row


def record_for_excel(article: dict[str, Any]) -> dict[str, Any]:
    row = record_for_csv(article)
    for key, value in list(row.items()):
        if isinstance(value, str) and len(value) > EXCEL_CELL_LIMIT:
            row[key] = value[: EXCEL_CELL_LIMIT - 20] + "\n...[truncated]"
    return row


def write_article_outputs(
    output_dir: Path,
    all_articles: list[dict[str, Any]],
) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "articles.csv"
    json_path = output_dir / "articles.json"
    xlsx_path = output_dir / "articles.xlsx"

    with json_path.open("w", encoding="utf-8") as file:
        json.dump(all_articles, file, ensure_ascii=False, indent=2)

    with csv_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=ARTICLE_FIELDS)
        writer.writeheader()
        for article in all_articles:
            writer.writerow(record_for_csv(article))

    df = pd.DataFrame([record_for_excel(article) for article in all_articles], columns=ARTICLE_FIELDS)
    df.to_excel(xlsx_path, index=False)

    return {
        "csv": csv_path,
        "json": json_path,
        "xlsx": xlsx_path,
    }


def save_articles(output_dir: Path, new_articles: list[dict[str, Any]]) -> dict[str, Path]:
    existing_articles = load_existing_articles(output_dir / "articles.json")
    all_articles = existing_articles + new_articles
    return write_article_outputs(output_dir, all_articles)


def check_wewe_rss(feed_url: str) -> bool:
    try:
        response = requests.get(feed_url, headers={"User-Agent": USER_AGENT}, timeout=10)
        return response.status_code < 500 and bool(response.text.strip())
    except requests.RequestException:
        return False


def sleep_between_requests(min_seconds: float, max_seconds: float) -> None:
    if max_seconds <= 0:
        return
    delay = random.uniform(max(0, min_seconds), max(min_seconds, max_seconds))
    time.sleep(delay)


def backfill_existing_image_context(
    output_dir: Path,
    collector_config: dict[str, Any],
) -> tuple[int, int]:
    if not collector_config.get("backfill_existing_images", True):
        return 0, 0

    json_path = output_dir / "articles.json"
    articles = load_existing_articles(json_path)
    if not articles:
        return 0, 0

    updated_count = 0
    image_article_count = 0
    ocr_enabled = collector_config.get("ocr_images", False)
    for article in articles:
        already_enriched = "image_count" in article and "image_urls" in article
        needs_ocr = (
            ocr_enabled
            and article.get("image_count", 0)
            and not article.get("image_ocr_text")
        )
        if already_enriched and not needs_ocr:
            if article.get("image_count", 0):
                image_article_count += 1
            continue

        before_text = article.get("content_text", "")
        enrich_content_with_images(article, collector_config, force_ocr=needs_ocr)
        if article.get("image_count", 0):
            image_article_count += 1
        if article.get("content_text", "") != before_text or "image_count" in article:
            updated_count += 1

    if updated_count:
        write_article_outputs(output_dir, articles)

    return updated_count, image_article_count


def main() -> int:
    config = load_config()
    collector_config = config.get("collector", {})
    output_dir = PROJECT_DIR / collector_config.get("output_dir", "data/raw")
    log_dir = PROJECT_DIR / collector_config.get("log_dir", "data/logs")
    log_path = setup_logging(log_dir)

    feeds = config.get("feeds", [])
    seen = load_seen()
    new_articles: list[dict[str, Any]] = []

    total_entries = 0
    content_success_count = 0
    content_failed_count = 0
    wewe_accessible = False

    logging.info("Starting WeChat RSS data collector.")
    logging.info("Feeds configured: %s", len(feeds))

    for feed_config in feeds:
        feed_name = feed_config.get("name", "")
        feed_url = feed_config.get("url", "")
        logging.info("Reading feed: %s - %s", feed_name, feed_url)

        if check_wewe_rss(feed_url):
            wewe_accessible = True
        else:
            logging.warning("Feed URL is not accessible or returned empty content: %s", feed_url)

        parsed = feedparser.parse(feed_url)
        if parsed.bozo:
            logging.warning("feedparser warning for %s: %s", feed_name, parsed.bozo_exception)

        entries = parsed.entries or []
        total_entries += len(entries)
        logging.info("Feed %s entries found: %s", feed_name, len(entries))

        for entry in entries:
            link = entry.get("link", "") or ""
            article_id = entry.get("id", "") or entry.get("guid", "") or link
            dedupe_key = link or article_id

            if not dedupe_key:
                logging.warning("Skipping entry without link or id: %s", entry.get("title", ""))
                continue

            if dedupe_key in seen:
                continue

            article = build_article_record(feed_config, entry, collector_config)
            new_articles.append(article)
            seen.add(dedupe_key)

            if article["fetch_status"] == "success":
                content_success_count += 1
            else:
                content_failed_count += 1
                logging.warning(
                    "Content fetch failed: %s - %s",
                    article.get("title", ""),
                    article.get("fetch_error", ""),
                )

            sleep_between_requests(
                collector_config.get("sleep_seconds_min", 1),
                collector_config.get("sleep_seconds_max", 3),
            )

    output_paths = save_articles(output_dir, new_articles)
    backfilled_count, image_article_count = backfill_existing_image_context(
        output_dir,
        collector_config,
    )
    save_seen(seen)

    logging.info("Scanned entries: %s", total_entries)
    logging.info("New articles: %s", len(new_articles))
    logging.info("Content fetch success: %s", content_success_count)
    logging.info("Content fetch failed: %s", content_failed_count)
    logging.info("Existing articles image backfilled: %s", backfilled_count)
    logging.info("Articles with images: %s", image_article_count)
    logging.info("Saved CSV: %s", output_paths["csv"])
    logging.info("Saved JSON: %s", output_paths["json"])
    logging.info("Saved XLSX: %s", output_paths["xlsx"])
    logging.info("Log file: %s", log_path)

    print("\n运行总结")
    print(f"- WeWe RSS 是否可访问: {'是' if wewe_accessible else '否'}")
    print(f"- 本次读取了几个公众号: {len(feeds)}")
    print(f"- 本次扫描了多少篇文章: {total_entries}")
    print(f"- 本次新增了多少篇文章: {len(new_articles)}")
    print(f"- 成功抓取正文多少篇: {content_success_count}")
    print(f"- 正文抓取失败多少篇: {content_failed_count}")
    print(f"- 已补充图片信息的旧文章: {backfilled_count}")
    print(f"- 含图片的文章数量: {image_article_count}")
    print(f"- CSV 保存位置: {output_paths['csv']}")
    print(f"- JSON 保存位置: {output_paths['json']}")
    print(f"- Excel 保存位置: {output_paths['xlsx']}")
    print(f"- 日志保存位置: {log_path}")

    if not new_articles:
        print("没有发现新文章，可能是 seen_articles.json 已经记录过这些文章。")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
