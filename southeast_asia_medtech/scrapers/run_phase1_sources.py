from __future__ import annotations

import argparse
import atexit
import hashlib
import io
import json
import logging
import re
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from pypdf import PdfReader

from southeast_asia_medtech.config.config_loader import load_sources
from southeast_asia_medtech.scrapers.http_client import HttpSettings, PoliteHttpClient
from southeast_asia_medtech.scrapers.parsers import (
    clean_text,
    parse_hsa_detail,
    parse_hsa_embedded_list,
    parse_hsa_list,
    parse_english_date,
    parse_mda_detail,
    parse_mda_list,
    parse_thai_fda_detail,
)


MODULE_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = MODULE_DIR / "data" / "phase1_samples"
SAMPLE_PATH = OUTPUT_DIR / "source_samples.json"
SUMMARY_PATH = OUTPUT_DIR / "source_sampling_summary.json"
LOG_PATH = MODULE_DIR / "logs" / "phase1_sources.log"
SNAPSHOT_DIR = MODULE_DIR / "data" / "source_snapshots"
MIN_BODY_LENGTH = 80
DATE_PATTERNS = (
    re.compile(r"\b\d{1,2}\s+[A-Za-zÀ-ÿ]+\s+20\d{2}\b"),
    re.compile(r"\b[A-Za-z]+\s+\d{1,2},?\s+20\d{2}\b"),
    re.compile(r"\b20\d{2}[-/.]\d{1,2}[-/.]\d{1,2}\b"),
    re.compile(r"\b\d{1,2}[-/.]\d{1,2}[-/.]20\d{2}\b"),
)
SKIP_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".gif", ".svg", ".css", ".js", ".zip", ".mp4", ".mp3"
}
SKIP_PATH_PARTS = ("/documents/", "/strukor/", "/category/", "/tag/", "/author/")
GENERIC_TITLES = {
    "", "home", "news", "announcements", "announcement", "notices", "notice",
    "thông báo", "healthcare packaging", "sterile barrier systems", "blog",
    "medical devices", "medical device/packaging", "medical device packaging",
    "news and media", "news and insights", "press releases", "newsroom",
    "all news", "latest news", "news release details",
}
_PLAYWRIGHT = None
_PLAYWRIGHT_BROWSER = None


def close_playwright() -> None:
    global _PLAYWRIGHT, _PLAYWRIGHT_BROWSER
    if _PLAYWRIGHT_BROWSER is not None:
        _PLAYWRIGHT_BROWSER.close()
        _PLAYWRIGHT_BROWSER = None
    if _PLAYWRIGHT is not None:
        _PLAYWRIGHT.stop()
        _PLAYWRIGHT = None


atexit.register(close_playwright)


def playwright_get_text(url: str, timeout_seconds: int = 30) -> tuple[str, int, str]:
    global _PLAYWRIGHT, _PLAYWRIGHT_BROWSER
    if _PLAYWRIGHT is None:
        from playwright.sync_api import sync_playwright

        _PLAYWRIGHT = sync_playwright().start()
        _PLAYWRIGHT_BROWSER = _PLAYWRIGHT.chromium.launch(headless=True)
    page = _PLAYWRIGHT_BROWSER.new_page(
        user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149 Safari/537.36"
        )
    )
    try:
        response = page.goto(
            url, wait_until="domcontentloaded", timeout=timeout_seconds * 1000
        )
        page.wait_for_timeout(1200)
        status = response.status if response else 200
        if status >= 400:
            raise ValueError(f"Playwright HTTP status {status}")
        return page.content(), status, page.url
    finally:
        page.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Try up to five public records from each configured Phase 1 source."
    )
    parser.add_argument("--source", action="append", default=[])
    parser.add_argument("--max-items", type=int, default=5)
    parser.add_argument("--start-date", help="Optional inclusive date in YYYY-MM-DD.")
    parser.add_argument("--end-date", help="Optional inclusive date in YYYY-MM-DD.")
    parser.add_argument("--timeout", type=int, default=25)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--sleep-min", type=float, default=1.0)
    parser.add_argument("--sleep-max", type=float, default=2.0)
    return parser.parse_args()


def parse_record_date(value: str) -> date | None:
    text = clean_text(value)
    if not text:
        return None
    iso_match = re.search(r"\b(20\d{2})-(\d{1,2})-(\d{1,2})\b", text)
    if iso_match:
        return date(*(int(part) for part in iso_match.groups()))
    for pattern in (
        "%d %B %Y",
        "%d %b %Y",
        "%B %d, %Y",
        "%b %d, %Y",
        "%d/%m/%Y",
        "%d.%m.%Y",
    ):
        try:
            return datetime.strptime(text, pattern).date()
        except ValueError:
            continue
    match = re.search(
        r"\b(\d{1,2})\s+([A-Za-z]+)\s+(20\d{2})\b|\b([A-Za-z]+)\s+(\d{1,2}),?\s+(20\d{2})\b",
        text,
    )
    if match:
        candidate = " ".join(part for part in match.groups() if part)
        for pattern in ("%d %B %Y", "%d %b %Y", "%B %d %Y", "%b %d %Y"):
            try:
                return datetime.strptime(candidate, pattern).date()
            except ValueError:
                continue
    return None


def setup_logger() -> logging.Logger:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("southeast_asia_medtech.phase1")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    logger.propagate = False
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    for handler in (logging.FileHandler(LOG_PATH, encoding="utf-8"), logging.StreamHandler(sys.stdout)):
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    return logger


def stable_id(source_id: str, url: str) -> str:
    digest = hashlib.sha256(f"{source_id}|{url}".encode()).hexdigest()[:20]
    return f"{source_id}_{digest}"


def record_is_valid(record: dict[str, Any]) -> bool:
    title = clean_text(str(record.get("title", ""))).casefold()
    return (
        title not in GENERIC_TITLES
        and bool(clean_text(str(record.get("published_date", ""))))
        and int(record.get("raw_text_length", 0) or 0) >= MIN_BODY_LENGTH
    )


def same_domain_or_endpoint(url: str, source: dict[str, Any]) -> bool:
    host = urlparse(url).netloc.lower()
    allowed = {
        urlparse(str(endpoint)).netloc.lower()
        for endpoint in source.get("endpoints", [source["list_url"]])
    }
    return host in allowed


def matches_article_url(url: str, source: dict[str, Any]) -> bool:
    """Reject listing/navigation URLs when a source declares article URL shapes."""
    patterns = [str(item) for item in source.get("article_url_patterns", [])]
    if patterns and not any(re.search(pattern, url, re.IGNORECASE) for pattern in patterns):
        return False
    normalized = url.rstrip("/")
    listing_urls = {
        str(endpoint).split("#", 1)[0].rstrip("/")
        for endpoint in source.get("endpoints", [source["list_url"]])
    }
    return normalized not in listing_urls


def find_date(text: str) -> str:
    for pattern in DATE_PATTERNS:
        match = pattern.search(text)
        if match:
            return match.group(0)
    return ""


def relevant(text: str, source: dict[str, Any]) -> bool:
    lowered = text.casefold()
    return any(str(term).casefold() in lowered for term in source.get("search_terms", []))


def generic_candidates(html: str, endpoint: str, source: dict[str, Any]) -> list[dict[str, str]]:
    soup = BeautifulSoup(html or "", "lxml")
    selectors = source.get("selectors", {})
    card_selector = str(selectors.get("article_card", "")).strip()
    cards = soup.select(card_selector) if card_selector else []
    if not cards:
        cards = soup.select("article, tr, li, .card, .post, .result")

    output: list[dict[str, str]] = []
    seen: set[str] = set()
    for card in cards:
        links = card.select("a[href]")
        if not links:
            continue
        title_selector = str(selectors.get("title", "")).strip()
        title_node = card.select_one(title_selector) if title_selector else None
        link = title_node.find_parent("a") if title_node and title_node.name != "a" else title_node
        if link is None or not link.get("href"):
            link = max(links, key=lambda item: len(clean_text(item.get_text(" ", strip=True))))
        url = urljoin(endpoint, str(link.get("href", "")))
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or Path(parsed.path).suffix.lower() in SKIP_EXTENSIONS:
            continue
        if parsed.fragment:
            continue
        if any(part in parsed.path.casefold() for part in SKIP_PATH_PARTS):
            continue
        if not same_domain_or_endpoint(url, source) or url in seen:
            continue
        if not matches_article_url(url, source):
            continue
        card_text = clean_text(card.get_text(" ", strip=True))
        card_date = find_date(card_text)
        title = clean_text(
            title_node.get_text(" ", strip=True) if title_node
            else link.get_text(" ", strip=True)
        )
        # A dated listing row must enter the monthly date gate even when its
        # short title does not contain one of the configured search terms.
        # Relevance is verified again against the complete detail body.
        if len(title) < 8 or (not card_date and not relevant(f"{title} {url}", source)):
            continue
        seen.add(url)
        output.append(
            {"title": title, "published_date": card_date, "url": url}
        )

    if len(output) < 10:
        for link in soup.select("a[href]"):
            url = urljoin(endpoint, str(link.get("href", "")))
            title = clean_text(link.get_text(" ", strip=True))
            if (
                url not in seen
                and len(title) >= 8
                and same_domain_or_endpoint(url, source)
                and matches_article_url(url, source)
                and relevant(f"{title} {url}", source)
                and Path(urlparse(url).path).suffix.lower() not in SKIP_EXTENSIONS
                and not urlparse(url).fragment
                and not any(part in urlparse(url).path.casefold() for part in SKIP_PATH_PARTS)
            ):
                seen.add(url)
                output.append({"title": title, "published_date": "", "url": url})
    return output[:250]


def gebiz_candidates(html: str, endpoint: str, source: dict[str, Any]) -> list[dict[str, str]]:
    """Extract the server-rendered public opportunity cards without a JSF session."""
    soup = BeautifulSoup(html or "", "lxml")
    output: list[dict[str, str]] = []
    for link in soup.select("a[href*='directlink.xhtml?docCode=']"):
        title = clean_text(link.get_text(" ", strip=True))
        if not relevant(title, source):
            continue
        card = link
        while card.parent is not None:
            card = card.parent
            card_text = clean_text(card.get_text(" ", strip=True))
            if "Published" in card_text and "Procurement Category" in card_text:
                break
        else:
            continue
        published = re.search(
            r"Published\s+(\d{1,2}\s+[A-Za-z]{3}\s+20\d{2})", card_text
        )
        if not published:
            continue
        output.append(
            {
                "title": title,
                "published_date": published.group(1),
                "url": urljoin(endpoint, str(link.get("href", ""))),
                "body": card_text,
            }
        )
    return output


def asean_amdc_candidates(
    html: str, endpoint: str, source: dict[str, Any]
) -> list[dict[str, str]]:
    soup = BeautifulSoup(html or "", "lxml")
    output: list[dict[str, str]] = []
    seen: set[str] = set()
    for link in soup.select('a[href*="/standards/detail/"]'):
        url = urljoin(endpoint, str(link.get("href", ""))).split("?", 1)[0].rstrip("/")
        title = clean_text(link.get_text(" ", strip=True))
        if (
            url in seen
            or title.casefold() == "[more details+]"
            or len(title) < 12
        ):
            continue
        seen.add(url)
        output.append({"title": title, "published_date": "", "url": url})
    return output


def asean_amdc_fields(body: str) -> dict[str, Any]:
    def between(start: str, end: str) -> str:
        match = re.search(
            rf"{re.escape(start)}\s+(.*?)\s+{re.escape(end)}",
            body,
            flags=re.IGNORECASE,
        )
        return clean_text(match.group(1)) if match else ""

    harmonisation = re.search(
        r"Date of harmonisation in ASEAN\s+(\d{1,2}/\d{1,2}/20\d{2})",
        body,
        flags=re.IGNORECASE,
    )
    latest_review = re.search(
        r"Date of Latest Review\s+(\d{1,2}/\d{1,2}/20\d{2})",
        body,
        flags=re.IGNORECASE,
    )
    member_text = between("Member States", "Date of harmonisation in ASEAN")
    return {
        "standard_number": between("Document number assigned by ASEAN", "ICS"),
        "asean_body": between("ASEAN Body responsible for Standard", "Member States"),
        "member_states": [
            token for token in re.findall(r"\b[A-Z]{2}\b", member_text)
        ],
        "harmonisation_date": harmonisation.group(1) if harmonisation else "",
        "latest_review_date": latest_review.group(1) if latest_review else "",
    }


def philgeps_candidates(
    html: str, endpoint: str, source: dict[str, Any]
) -> list[dict[str, str]]:
    soup = BeautifulSoup(html or "", "lxml")
    output: list[dict[str, str]] = []
    seen: set[str] = set()
    for row in soup.select("tr"):
        link = row.select_one('a[href*="refID="], a[href*="refid="]')
        if link is None:
            continue
        href = str(link.get("href", ""))
        match = re.search(r"(?:refID|refid)=(\d+)", href, flags=re.IGNORECASE)
        if not match:
            continue
        reference = match.group(1)
        url = (
            "https://notices.philgeps.gov.ph/GEPSNONPILOT/Tender/"
            f"PrintableBidNoticeAbstractUI.aspx?refid={reference}"
        )
        if url in seen:
            continue
        cells = [clean_text(cell.get_text(" ", strip=True)) for cell in row.select("td")]
        published = next(
            (cell for cell in cells if re.fullmatch(r"\d{1,2}/\d{1,2}/20\d{2}", cell)),
            "",
        )
        title = clean_text(link.get_text(" ", strip=True))
        if not title or not published:
            continue
        seen.add(url)
        output.append({"title": title, "published_date": published, "url": url})
    return output


def philgeps_paginated_candidates(
    source: dict[str, Any],
    candidate_date_filter: Callable[[str], bool | None],
    logger: logging.Logger,
    max_pages_per_category: int = 50,
) -> tuple[list[dict[str, str]], list[str]]:
    global _PLAYWRIGHT, _PLAYWRIGHT_BROWSER
    if _PLAYWRIGHT is None:
        from playwright.sync_api import sync_playwright

        _PLAYWRIGHT = sync_playwright().start()
        _PLAYWRIGHT_BROWSER = _PLAYWRIGHT.chromium.launch(headless=True)
    endpoints = [
        str(endpoint)
        for endpoint in source.get("endpoints", [])
        if "SplashOpportunitiesSearchUI.aspx" in str(endpoint)
    ]
    output: list[dict[str, str]] = []
    errors: list[str] = []
    seen: set[str] = set()
    page = _PLAYWRIGHT_BROWSER.new_page()
    try:
        for endpoint in endpoints:
            try:
                page.goto(endpoint, wait_until="domcontentloaded", timeout=30_000)
                for page_number in range(1, max_pages_per_category + 1):
                    found = philgeps_candidates(page.content(), page.url, source)
                    new_count = 0
                    decisions: list[bool] = []
                    for item in found:
                        decision = candidate_date_filter(item["published_date"])
                        if decision is not None:
                            decisions.append(decision)
                        if decision is True and item["url"] not in seen:
                            seen.add(item["url"])
                            output.append(item)
                            new_count += 1
                    logger.info(
                        "PhilGEPS category page endpoint=%s page=%s rows=%s july_rows=%s",
                        endpoint,
                        page_number,
                        len(found),
                        new_count,
                    )
                    # Results are newest-first. Once a complete page is dated
                    # before the requested month there can be no later matches.
                    if decisions and not any(decisions):
                        break
                    next_link = page.get_by_role("link", name="<Next>", exact=True)
                    if next_link.count() != 1:
                        break
                    before = {item["url"] for item in found}
                    with page.expect_navigation(
                        wait_until="domcontentloaded", timeout=30_000
                    ):
                        next_link.click()
                    page.wait_for_timeout(500)
                    after = {
                        item["url"]
                        for item in philgeps_candidates(page.content(), page.url, source)
                    }
                    if not after or after == before:
                        break
            except Exception as exc:
                errors.append(f"{endpoint}: {type(exc).__name__}: {exc}")
    finally:
        page.close()
    return output, errors


def thai_fda_fields(title: str, body: str) -> dict[str, str]:
    text = f"{title} {body}".casefold()
    topics = (
        ("reporting", ("reporting", "record-keeping", "post-market")),
        ("registration", ("registration", "application form", "permission")),
        ("international_cooperation", ("cooperation", "harmonization", "harmonisation")),
        ("market_access", ("market access", "importation", "medical hub")),
        ("device_classification", ("classification", "regarded as the medical device")),
    )
    matched = [name for name, terms in topics if any(term in text for term in terms)]
    return {"regulatory_topic": ",".join(matched)}


def generic_detail(html: str, fallback_title: str) -> tuple[str, str, str]:
    soup = BeautifulSoup(html or "", "lxml")
    for node in soup.select("script, style, noscript, nav, footer, header, aside"):
        node.decompose()
    title_node = soup.select_one("main h1, article h1, h1")
    extracted_title = clean_text(title_node.get_text(" ", strip=True) if title_node else "")
    title = (
        fallback_title
        if not extracted_title or extracted_title.casefold() in GENERIC_TITLES
        else extracted_title
    )
    container = soup.select_one(
        "article, main, .entry-content, .article-content, .content, "
        ".detail-content, .page-content, #content"
    )
    if container is None or len(clean_text(container.get_text(" ", strip=True))) < MIN_BODY_LENGTH:
        container = soup.body
    if container is None:
        return title, "", ""
    text = clean_text(container.get_text(" ", strip=True))
    if title and text.startswith(title):
        text = text[len(title):].strip()
    published_meta = soup.select_one(
        "meta[property='article:published_time'], meta[itemprop='datePublished']"
    )
    published_date = (
        clean_text(str(published_meta.get("content", "")))
        if published_meta is not None
        else ""
    )
    if re.match(r"^\d{4}-\d{2}-\d{2}T", published_date):
        published_date = published_date[:10]
    return title, text, published_date or find_date(text)


def source_candidates(
    source: dict[str, Any],
    client: PoliteHttpClient,
    candidate_date_filter: Callable[[str], bool | None] | None = None,
    logger: logging.Logger | None = None,
) -> tuple[list[dict[str, str]], list[str]]:
    if (
        source["source_id"] == "ph_philgeps"
        and candidate_date_filter is not None
        and logger is not None
    ):
        return philgeps_paginated_candidates(source, candidate_date_filter, logger)
    # A small set of verified article URLs may supplement a JavaScript-backed
    # listing. These are still fetched, date-gated and validated like any other
    # candidate; they are not treated as pre-approved records.
    candidates: list[dict[str, str]] = [
        {
            "title": clean_text(str(item.get("title", ""))),
            "published_date": clean_text(str(item.get("published_date", ""))),
            "url": str(item["url"]),
        }
        for item in source.get("seed_articles", [])
        if item.get("url")
    ]
    errors: list[str] = []
    seen: set[str] = {item["url"] for item in candidates}
    for seed in source.get("seed_urls", []):
        url = str(seed["url"] if isinstance(seed, dict) else seed)
        candidates.append(
            {
                "title": str(seed.get("title", "")) if isinstance(seed, dict) else "",
                "published_date": (
                    str(seed.get("published_date", "")) if isinstance(seed, dict) else ""
                ),
                "url": url,
            }
        )
        seen.add(url)
    for endpoint in source.get("endpoints", [source["list_url"]]):
        try:
            try:
                html, _, final_url = client.get_text(str(endpoint))
            except Exception:
                if not source.get("requires_javascript"):
                    raise
                html, _, final_url = playwright_get_text(str(endpoint))
            if source["source_id"] == "asean_amdc":
                found = asean_amdc_candidates(html, final_url, source)
            elif source["source_id"] == "sg_hsa_announcements":
                embedded = parse_hsa_embedded_list(html, source)
                hsa_by_url = {
                    item.url: item for item in (*parse_hsa_list(html, source), *embedded)
                }
                hsa_items = sorted(
                    hsa_by_url.values(),
                    key=lambda item: parse_english_date(item.published_date)
                    or datetime.min.date(),
                    reverse=True,
                )
                found = [
                    {"title": item.title, "published_date": item.published_date, "url": item.url}
                    for item in hsa_items
                    if any(
                        term in item.list_text.casefold()
                        for term in (
                            "medical device",
                            "medical devices",
                            "applicator",
                            "sterility",
                            "sterile",
                            "field safety",
                        )
                    )
                ]
            elif source["source_id"] == "ph_philgeps":
                found = philgeps_candidates(html, final_url, source)
            elif source["source_id"] == "sg_gebiz":
                found = gebiz_candidates(html, final_url, source)
            elif source["source_id"] == "my_mda_mmdr" and "announcement" in str(endpoint):
                found = [
                    {"title": item.title, "published_date": item.published_date, "url": item.url}
                    for item in parse_mda_list(html, source)
                ]
            else:
                found = generic_candidates(html, final_url, source)
            for item in found:
                if item["url"] not in seen:
                    candidates.append(item)
                    seen.add(item["url"])
        except Exception as exc:
            errors.append(f"{endpoint}: {type(exc).__name__}: {exc}")
    return candidates, errors


def sample_source(
    source: dict[str, Any],
    client: PoliteHttpClient,
    max_items: int,
    logger: logging.Logger,
    candidate_date_filter: Callable[[str], bool | None] | None = None,
    record_date_filter: Callable[[str], bool] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    candidates, endpoint_errors = source_candidates(
        source, client, candidate_date_filter, logger
    )
    candidates_skipped_by_date = 0
    undated_candidates_skipped = 0
    undated_candidates_attempted = 0
    records: list[dict[str, Any]] = []
    detail_failures: list[str] = []
    acquisition_mode = "live_http"
    for item in candidates:
        if len(records) >= max_items:
            break
        if (
            source["source_id"] == "my_mida_ammi"
            and not relevant(item.get("title", ""), source)
        ):
            continue
        if candidate_date_filter is not None:
            candidate_decision = candidate_date_filter(item.get("published_date", ""))
            if candidate_decision is False:
                candidates_skipped_by_date += 1
                continue
            # Monthly runs should not crawl an entire site when a generic
            # listing exposes navigation links without publication dates.
            if candidate_decision is None:
                if undated_candidates_attempted >= 12:
                    undated_candidates_skipped += 1
                    continue
                undated_candidates_attempted += 1
        try:
            if item.get("body") and source.get("listing_body_is_detail"):
                html = ""
                status = 200
                final_url = item["url"]
                title = item["title"]
                body = clean_text(item["body"])
                body_date = item["published_date"]
                is_pdf_candidate = False
            else:
                is_pdf_candidate = (
                    source["source_id"] == "vn_vimda"
                    and "/documents/" in item["url"]
                )
                if is_pdf_candidate:
                    payload, status, final_url, content_type = client.get_bytes(item["url"])
                    if "pdf" not in content_type.casefold() and not payload.startswith(b"%PDF"):
                        raise ValueError(f"Expected PDF but received Content-Type={content_type!r}")
                    reader = PdfReader(io.BytesIO(payload))
                    body = clean_text(
                        "\n".join(page.extract_text() or "" for page in reader.pages[:40])
                    )
                    title = item["title"]
                    body_date = item["published_date"]
                    html = ""
                else:
                    try:
                        html, status, final_url = client.get_text(item["url"])
                    except Exception:
                        if not source.get("requires_javascript"):
                            raise
                        html, status, final_url = playwright_get_text(item["url"])
            if item.get("body") and source.get("listing_body_is_detail"):
                pass
            elif source["source_id"] == "sg_hsa_announcements":
                title, body = parse_hsa_detail(html, item["title"])
                body_date = ""
            elif source["source_id"] == "my_mda_mmdr":
                title, body = parse_mda_detail(html, item["title"])
                body_date = ""
            elif source["source_id"] == "th_fda_medical_devices":
                title, body, body_date = parse_thai_fda_detail(html, item["title"])
            elif not is_pdf_candidate:
                title, body, body_date = generic_detail(html, item["title"])
                if len(body) < MIN_BODY_LENGTH and source.get("requires_javascript"):
                    rendered_html, status, final_url = playwright_get_text(item["url"])
                    title, body, body_date = generic_detail(
                        rendered_html, item["title"]
                    )
            if (
                source["workflow"] == "procurement_search"
                and item["title"]
                and title.casefold() in {"opportunity details", "bid notice abstract"}
            ):
                title = item["title"]
            if source["source_id"] == "asean_amdc":
                title = item["title"]
                if "ASEAN Medical Device Committee (AMDC)" not in body:
                    raise ValueError("detail is not assigned to ASEAN AMDC")
                harmonisation = re.search(
                    r"Date of harmonisation in ASEAN\s+"
                    r"(\d{1,2}/\d{1,2}/20\d{2})",
                    body,
                    flags=re.IGNORECASE,
                )
                if harmonisation:
                    body_date = harmonisation.group(1)
            if len(body) < MIN_BODY_LENGTH:
                raise ValueError(f"body too short ({len(body)} chars)")
            if not matches_article_url(final_url, source):
                raise ValueError("detail URL is a listing or does not match the article URL pattern")
            if not relevant(f"{title} {body}", source):
                continue
            record = {
                    "article_id": stable_id(source["source_id"], final_url),
                    "source_id": source["source_id"],
                    "source_name": source["source_name"],
                    "country": source["country"],
                    "organization": source["organization"],
                    "source_type": source["source_type"],
                    "workflow": source["workflow"],
                    "category": source["category"],
                    "title": title,
                    "published_date": (
                        body_date
                        if source["source_id"] == "my_mida_ammi" and body_date
                        else item["published_date"] or body_date
                    ),
                    "collected_at": datetime.now().astimezone().isoformat(timespec="seconds"),
                    "url": final_url,
                    "language": source["language"],
                    "body": body,
                    "raw_text_length": len(body),
                    "scrape_status": "success",
                "error_message": "",
            }
            if source["source_id"] == "asean_amdc":
                record.update(asean_amdc_fields(body))
            elif source["source_id"] == "th_fda_medical_devices":
                record.update(thai_fda_fields(title, body))
            if not record_is_valid(record):
                raise ValueError("record lacks a specific title, publication date, or full body")
            if record_date_filter is not None and not record_date_filter(
                str(record.get("published_date", ""))
            ):
                candidates_skipped_by_date += 1
                continue
            records.append(record)
        except Exception as exc:
            detail_failures.append(f"{item['url']}: {type(exc).__name__}: {exc}")

    if (
        source["source_id"] == "my_mda_mmdr"
        and not records
        and (endpoint_errors or detail_failures)
    ):
        snapshot_path = SNAPSHOT_DIR / "my_mda_mmdr.json"
        if snapshot_path.exists():
            snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
            page_url = str(snapshot["source_page"])
            for item in snapshot.get("records", [])[:max_items]:
                if "body" in item:
                    url = str(item.get("url") or page_url)
                    body = clean_text(str(item["body"]))
                    record = {
                        "article_id": stable_id(source["source_id"], url),
                        "source_id": source["source_id"],
                        "source_name": source["source_name"],
                        "country": source["country"],
                        "organization": source["organization"],
                        "source_type": source["source_type"],
                        "workflow": source["workflow"],
                        "category": source["category"],
                        "title": item["title"],
                        "published_date": item["published_date"],
                        "collected_at": datetime.now().astimezone().isoformat(timespec="seconds"),
                        "url": url,
                        "language": source["language"],
                        "body": body,
                        "raw_text_length": len(body),
                        "scrape_status": "success_from_official_index_snapshot",
                        "error_message": "",
                        "capture_method": snapshot["capture_method"],
                        "snapshot_captured_at": snapshot["captured_at"],
                    }
                    if record_is_valid(record):
                        if record_date_filter is None or record_date_filter(
                            str(record.get("published_date", ""))
                        ):
                            records.append(record)
                    continue
                reference = clean_text(str(item.get("mda_reference_numbers", "")))
                url = f"{page_url}#{reference}"
                body = clean_text(
                    f"{snapshot['page_title']}. Date received: {item['published_date']}. "
                    f"Affected medical device: {item['affected_devices']}. "
                    f"Field corrective action: {item['title']}. MDA reference number: "
                    f"{reference}. MDA registration number: {item['registration_numbers']}. "
                    f"Local establishment: {item['local_establishments']}."
                )
                record = {
                    "article_id": stable_id(source["source_id"], url),
                    "source_id": source["source_id"],
                    "source_name": source["source_name"],
                    "country": source["country"],
                    "organization": source["organization"],
                    "source_type": source["source_type"],
                    "workflow": source["workflow"],
                    "category": source["category"],
                    "title": item["title"],
                    "published_date": item["published_date"],
                    "collected_at": datetime.now().astimezone().isoformat(timespec="seconds"),
                    "url": url,
                    "language": source["language"],
                    "body": body,
                    "raw_text_length": len(body),
                    "scrape_status": "success_from_official_index_snapshot",
                    "error_message": "",
                    "safety_event_type": "field_corrective_action",
                    "reporting_period": snapshot["page_title"],
                    "affected_devices": item["affected_devices"],
                    "mda_reference_numbers": reference,
                    "registration_numbers": item["registration_numbers"],
                    "local_establishments": item["local_establishments"],
                    "capture_method": snapshot["capture_method"],
                    "snapshot_captured_at": snapshot["captured_at"],
                }
                if record_is_valid(record):
                    if record_date_filter is None or record_date_filter(
                        str(record.get("published_date", ""))
                    ):
                        records.append(record)
            acquisition_mode = "official_public_search_index_snapshot"

    generic_snapshot = SNAPSHOT_DIR / f"{source['source_id']}.json"
    if (
        source["source_id"] != "my_mda_mmdr"
        and not records
        and generic_snapshot.exists()
    ):
        snapshot = json.loads(generic_snapshot.read_text(encoding="utf-8"))
        for item in snapshot.get("records", [])[:max_items]:
            url = str(item["url"])
            body = clean_text(str(item["body"]))
            record = {
                "article_id": stable_id(source["source_id"], url),
                "source_id": source["source_id"],
                "source_name": source["source_name"],
                "country": source["country"],
                "organization": source["organization"],
                "source_type": source["source_type"],
                "workflow": source["workflow"],
                "category": source["category"],
                "title": item["title"],
                "published_date": item["published_date"],
                "collected_at": datetime.now().astimezone().isoformat(timespec="seconds"),
                "url": url,
                "language": source["language"],
                "body": body,
                "raw_text_length": len(body),
                "scrape_status": "success_from_official_index_snapshot",
                "error_message": "",
                "capture_method": snapshot["capture_method"],
                "snapshot_captured_at": snapshot["captured_at"],
            }
            record.update(item.get("fields", {}))
            if record_is_valid(record) and relevant(
                f"{record['title']} {record['body']}", source
            ):
                if record_date_filter is None or record_date_filter(
                    str(record.get("published_date", ""))
                ):
                    records.append(record)
        acquisition_mode = snapshot["capture_method"]

    if len(records) < max_items:
        status = "partial" if records else "failed"
        if source.get("requires_javascript"):
            limitation = "JavaScript/search interaction required; static public attempt did not guarantee five records."
        elif source["workflow"] == "registry_targeted":
            limitation = "Registry is target-query based; public notices were sampled without full-database crawling."
        else:
            limitation = "Public listing yielded fewer than five relevant, extractable records."
    else:
        status = "success"
        limitation = ""
    summary = {
        "source_id": source["source_id"],
        "source_name": source["source_name"],
        "workflow": source["workflow"],
        "parsing_strategy": source["parsing_strategy"],
        "candidates_found": len(candidates),
        "candidates_skipped_by_date": candidates_skipped_by_date,
        "undated_candidates_skipped": undated_candidates_skipped,
        "valid_records": len(records),
        "requested_records": max_items,
        "status": status,
        "limitation": limitation,
        "endpoint_errors": endpoint_errors,
        "detail_failure_count": len(detail_failures),
        "detail_failures": detail_failures[:10],
        "acquisition_mode": acquisition_mode,
    }
    logger.info("Source summary: %s", json.dumps(summary, ensure_ascii=False))
    return records, summary


def save_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def run(args: argparse.Namespace) -> dict[str, Any]:
    max_items = max(1, min(int(args.max_items), 5))
    start_date = date.fromisoformat(args.start_date) if args.start_date else None
    end_date = date.fromisoformat(args.end_date) if args.end_date else None
    if bool(start_date) != bool(end_date):
        raise ValueError("--start-date and --end-date must be provided together")
    if start_date and end_date and start_date > end_date:
        raise ValueError("--start-date must not be after --end-date")

    def candidate_date_filter(value: str) -> bool | None:
        parsed = parse_record_date(value)
        if parsed is None or start_date is None or end_date is None:
            return None
        return start_date <= parsed <= end_date

    def record_date_filter(value: str) -> bool:
        parsed = parse_record_date(value)
        return bool(
            parsed is not None
            and start_date is not None
            and end_date is not None
            and start_date <= parsed <= end_date
        )

    logger = setup_logger()
    config = load_sources()
    sources = [item for item in config["sources"] if item.get("enabled") is True]
    selected = set(args.source)
    if selected:
        sources = [item for item in sources if item["source_id"] in selected]
    client = PoliteHttpClient(
        HttpSettings(args.timeout, args.retries, args.sleep_min, args.sleep_max), logger
    )
    previous_records = (
        json.loads(SAMPLE_PATH.read_text(encoding="utf-8"))
        if SAMPLE_PATH.exists()
        else []
    )
    selected_ids = {item["source_id"] for item in sources}
    records: list[dict[str, Any]] = [
        item for item in previous_records
        if item.get("source_id") not in selected_ids and record_is_valid(item)
    ]
    previous_summaries: list[dict[str, Any]] = []
    if SUMMARY_PATH.exists():
        previous = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
        previous_summaries = previous.get("sources", [])
    summaries: list[dict[str, Any]] = [
        item for item in previous_summaries if item.get("source_id") not in selected_ids
    ]
    for source in sources:
        source_records, summary = sample_source(
            source,
            client,
            max_items,
            logger,
            candidate_date_filter if start_date else None,
            record_date_filter if start_date else None,
        )
        records.extend(source_records)
        summaries.append(summary)
        save_json(SAMPLE_PATH, records)
        save_json(
            SUMMARY_PATH,
            {
                "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
                "configured_sources": len(sources),
                "requested_per_source": max_items,
                "valid_records": len(records),
                "sources": summaries,
                "run_status": "in_progress",
            },
        )
    generated_at = datetime.now().astimezone().isoformat(timespec="seconds")
    counts: dict[str, int] = {}
    for record in records:
        source_id = str(record.get("source_id", ""))
        counts[source_id] = counts.get(source_id, 0) + 1
    for summary in summaries:
        valid_count = counts.get(str(summary["source_id"]), 0)
        summary["valid_records"] = valid_count
        if valid_count < max_items:
            summary["status"] = "partial" if valid_count else "failed"
            if not summary.get("limitation"):
                summary["limitation"] = (
                    "Fewer than five records met the strict title, date, body and relevance checks."
                )
    result = {
        "generated_at": generated_at,
        "configured_sources": len(summaries),
        "requested_per_source": max_items,
        "valid_records": len(records),
        "sources_with_five": sum(item["valid_records"] == max_items for item in summaries),
        "sources": summaries,
        "sample_output": str(SAMPLE_PATH),
        "log": str(LOG_PATH),
    }
    save_json(SAMPLE_PATH, records)
    save_json(SUMMARY_PATH, result)
    return result


def main() -> int:
    result = run(parse_args())
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
