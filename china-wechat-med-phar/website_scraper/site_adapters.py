from __future__ import annotations

import base64
import hashlib
import json
import logging
from pathlib import Path
import re
import time
from typing import Any
import zlib
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from website_scraper.article_cleaner import html_to_text
from website_scraper.dynamic_scraper import DynamicScraper
from website_scraper.utils import make_absolute_url, normalize_url, now_iso
from website_scraper.web_scraper import ScraperSettings


def scrape_with_adapter(
    source: dict[str, Any],
    max_articles: int | None,
    settings: ScraperSettings,
    logger: logging.Logger,
    project_dir: Path,
) -> list[dict[str, Any]] | None:
    """Return adapter results for special sites, or None to use the generic scraper."""
    if source.get("source_name") == "动脉网 7x24H情报":
        return scrape_vbdata_intel_list(source, max_articles, settings, logger, project_dir)
    if source.get("source_name") == "米内网新闻":
        return scrape_menet_news(source, max_articles, settings, logger)
    if source.get("source_name") == "药智新闻":
        return scrape_yaozh_news(source, max_articles, settings, logger)
    if source.get("source_name") == "器械之家":
        return scrape_qixieke(source, max_articles, settings, logger)
    if source.get("source_name") == "国家医保局":
        return scrape_nhsa(source, max_articles, settings, logger)
    if source.get("source_name") == "CDE 药品审评中心":
        return scrape_cde_from_homepage(source, max_articles, settings, logger)
    return None


def scrape_cde_from_homepage(
    source: dict[str, Any],
    max_articles: int | None,
    settings: ScraperSettings,
    logger: logging.Logger,
) -> list[dict[str, Any]]:
    """CDE list/detail pages are protected; use the public homepage news blocks as a stable fallback."""
    homepage_url = "https://www.cde.org.cn/"
    try:
        response = requests.get(homepage_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=settings.timeout)
        response.raise_for_status()
        if not response.encoding or response.encoding.lower() == "iso-8859-1":
            response.encoding = response.apparent_encoding
    except Exception as exc:
        logger.error("CDE 首页抓取失败: %s", exc)
        return [failed_article(source, source.get("list_url", ""), str(exc))]

    soup = BeautifulSoup(response.text, "lxml")
    articles: list[dict[str, Any]] = []
    seen_urls: set[str] = set()

    for link in soup.select("a[href*='/main/news/viewInfoCommon/']"):
        title = clean_text(link.get_text(" ", strip=True) or link.get("title", ""))
        url = normalize_url(make_absolute_url(homepage_url, link.get("href", "")))
        if not title or not url or url in seen_urls:
            continue

        context_nodes = [link, link.parent, getattr(link.parent, "parent", None)]
        context = clean_text(" ".join(node.get_text(" ", strip=True) for node in context_nodes if node))
        publish_date = extract_compact_date(context)
        keyword_text = f"{title} {context}"
        if not matches_keyword_rules(source, keyword_text):
            continue

        seen_urls.add(url)
        articles.append(
            {
                "source_name": source.get("source_name", ""),
                "category": source.get("category", ""),
                "title": title,
                "publish_date": publish_date,
                "url": url,
                "author": "CDE 药品审评中心",
                "raw_html": json.dumps(
                    {
                        "source": "cde_homepage_fallback",
                        "homepage_url": homepage_url,
                        "list_url": source.get("list_url", ""),
                        "title": title,
                        "publish_date": publish_date,
                        "url": url,
                        "context": context,
                    },
                    ensure_ascii=False,
                ),
                "body": title,
                "crawl_time": now_iso(),
                "status": "success",
                "error_message": "CDE list/detail pages are protected; used homepage title fallback",
            }
        )

        if max_articles is not None and len(articles) >= max_articles:
            break

    logger.info("CDE 首页兜底抓取成功: %s 篇", len(articles))
    if not articles:
        return [failed_article(source, source.get("list_url", ""), "no CDE homepage records matched keywords")]
    return articles


def extract_compact_date(text: str) -> str:
    match = re.search(r"(20\d{2})(\d{2})(\d{2})", text or "")
    if match:
        return f"{match.group(1)}-{match.group(2)}-{match.group(3)}"
    match = re.search(r"20\d{2}-\d{1,2}-\d{1,2}", text or "")
    return match.group(0) if match else ""


def scrape_nhsa(
    source: dict[str, Any],
    max_articles: int | None,
    settings: ScraperSettings,
    logger: logging.Logger,
) -> list[dict[str, Any]]:
    """Adapter for 国家医保局 pages whose list records are embedded as XML CDATA."""
    list_url = source.get("list_url", "")
    try:
        response = requests.get(list_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=settings.timeout)
        response.raise_for_status()
        if not response.encoding or response.encoding.lower() == "iso-8859-1":
            response.encoding = response.apparent_encoding
    except Exception as exc:
        logger.error("国家医保局列表页抓取失败: %s", exc)
        return [failed_article(source, list_url, str(exc))]

    stubs = extract_nhsa_stubs(source, list_url, response.text)
    articles: list[dict[str, Any]] = []
    seen_urls: set[str] = set()

    for stub in stubs:
        keyword_text = f"{stub.get('title', '')} {stub.get('summary', '')}"
        if not matches_keyword_rules(source, keyword_text):
            continue
        url = stub.get("url", "")
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        article = fetch_nhsa_detail(source, stub, settings, logger)
        if article.get("status") == "success":
            articles.append(article)
        if max_articles is not None and len(articles) >= max_articles:
            break

    logger.info("国家医保局抓取成功: %s 篇", len(articles))
    return articles


def extract_nhsa_stubs(source: dict[str, Any], list_url: str, html: str) -> list[dict[str, str]]:
    stubs: list[dict[str, str]] = []
    for record_html in re.findall(r"<record><!\[CDATA\[(.*?)\]\]></record>", html, flags=re.S):
        soup = BeautifulSoup(record_html, "lxml")
        link = soup.select_one("a[href]")
        if not link:
            continue
        url = normalize_url(make_absolute_url(list_url, link.get("href", "")))
        title = clean_text(link.get("title", "") or link.get_text(" ", strip=True))
        date_node = soup.select_one("span")
        stubs.append(
            {
                "source_name": source.get("source_name", ""),
                "category": source.get("category", ""),
                "title": title,
                "publish_date": clean_text(date_node.get_text(" ", strip=True) if date_node else ""),
                "url": url,
                "summary": clean_text(soup.get_text(" ", strip=True)),
            }
        )
    return stubs


def fetch_nhsa_detail(
    source: dict[str, Any],
    stub: dict[str, str],
    settings: ScraperSettings,
    logger: logging.Logger,
) -> dict[str, Any]:
    result = {
        "source_name": source.get("source_name", ""),
        "category": source.get("category", ""),
        "title": stub.get("title", ""),
        "publish_date": stub.get("publish_date", ""),
        "url": stub.get("url", ""),
        "author": "",
        "raw_html": "",
        "body": "",
        "crawl_time": now_iso(),
        "status": "success",
        "error_message": "",
    }

    try:
        response = requests.get(result["url"], headers={"User-Agent": "Mozilla/5.0"}, timeout=settings.timeout)
        response.raise_for_status()
        if not response.encoding or response.encoding.lower() == "iso-8859-1":
            response.encoding = response.apparent_encoding
        soup = BeautifulSoup(response.text, "lxml")
        result["raw_html"] = response.text
        result["title"] = extract_meta_or_title(soup, "ArticleTitle", result["title"])
        result["publish_date"] = extract_meta_or_title(soup, "PubDate", result["publish_date"])
        result["author"] = extract_meta_or_title(soup, "ContentSource", "")

        body_node = soup.select_one((source.get("selectors", {}) or {}).get("body") or "#zoom")
        result["body"] = html_to_text(str(body_node)) if body_node else ""
        if not result["body"]:
            result["status"] = "failed"
            result["error_message"] = "empty body"
        elif not matches_keyword_rules(source, f"{result['title']} {result['body']}"):
            result["status"] = "failed"
            result["error_message"] = "filtered by include/exclude keywords"
    except Exception as exc:
        result["status"] = "failed"
        result["error_message"] = str(exc)
        logger.warning("国家医保局详情页抓取失败: %s | %s", result["url"], exc)

    return result


def extract_meta_or_title(soup: BeautifulSoup, name: str, fallback: str) -> str:
    node = soup.select_one(f"meta[name='{name}']")
    value = clean_text(node.get("content", "") if node else "")
    return value or fallback


def scrape_qixieke(
    source: dict[str, Any],
    max_articles: int | None,
    settings: ScraperSettings,
    logger: logging.Logger,
) -> list[dict[str, Any]]:
    """Adapter for 器械之家 homepage article list."""
    list_url = source.get("list_url", "")
    try:
        response = requests.get(list_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=settings.timeout)
        response.raise_for_status()
        if not response.encoding or response.encoding.lower() == "iso-8859-1":
            response.encoding = response.apparent_encoding
    except Exception as exc:
        logger.error("器械之家列表页抓取失败: %s", exc)
        return [failed_article(source, list_url, str(exc))]

    soup = BeautifulSoup(response.text, "lxml")
    cards = soup.select("ul.main-list li, ul.lists.main-list li")
    if not cards:
        cards = [link.parent for link in soup.select("a[href*='detailPage']") if link.parent]

    articles: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    for card in cards:
        stub = extract_qixieke_stub(source, list_url, card)
        url = stub.get("url", "")
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        article = fetch_qixieke_detail(source, stub, settings, logger)
        if article.get("status") != "success":
            logger.warning("器械之家跳过无可用正文文章: %s | %s", url, article.get("error_message", ""))
            continue
        articles.append(article)
        if max_articles is not None and len(articles) >= max_articles:
            break

    logger.info("器械之家抓取成功: %s 篇", len(articles))
    return articles


def extract_qixieke_stub(source: dict[str, Any], list_url: str, card: Any) -> dict[str, str]:
    link = card.select_one("a[href*='detailPage']")
    if not link:
        return {}

    url = normalize_url(make_absolute_url(list_url, link.get("href", "")))
    title = clean_text(link.get_text(" ", strip=True) or link.get("title", ""))
    card_text = clean_text(card.get_text(" ", strip=True))
    if not title:
        title = clean_text(re.sub(r"\s*(?:其他|市场动态|X线机|IVD|医学影像)\s+20\d{2}-\d{1,2}-\d{1,2}.*$", "", card_text))

    date_match = re.search(r"20\d{2}-\d{1,2}-\d{1,2}", card_text)
    return {
        "source_name": source.get("source_name", ""),
        "category": source.get("category", ""),
        "title": title,
        "publish_date": date_match.group(0) if date_match else "",
        "url": url,
        "summary": clean_qixieke_summary(card_text, title),
    }


def fetch_qixieke_detail(
    source: dict[str, Any],
    stub: dict[str, str],
    settings: ScraperSettings,
    logger: logging.Logger,
) -> dict[str, Any]:
    result = {
        "source_name": source.get("source_name", ""),
        "category": source.get("category", ""),
        "title": stub.get("title", ""),
        "publish_date": stub.get("publish_date", ""),
        "url": stub.get("url", ""),
        "author": "",
        "raw_html": "",
        "body": stub.get("summary", ""),
        "crawl_time": now_iso(),
        "status": "success",
        "error_message": "",
    }

    try:
        response = requests.get(
            result["url"],
            headers={"User-Agent": "Mozilla/5.0", "Referer": source.get("list_url", "")},
            timeout=settings.timeout,
        )
        response.raise_for_status()
        if not response.encoding or response.encoding.lower() == "iso-8859-1":
            response.encoding = response.apparent_encoding
        soup = BeautifulSoup(response.text, "lxml")
        result["raw_html"] = response.text
        result["title"] = extract_qixieke_title(soup, result["title"])
        result["publish_date"] = extract_qixieke_date(soup, result["publish_date"])
        result["author"] = extract_qixieke_author(soup)

        body_node = soup.select_one((source.get("selectors", {}) or {}).get("body") or ".detail")
        body = clean_qixieke_body(html_to_text(str(body_node)) if body_node else "", result["title"])
        result["body"] = body or result["body"]
        if not result["body"]:
            result["status"] = "failed"
            result["error_message"] = "empty body"
        elif len(result["body"]) < 50:
            result["status"] = "failed"
            result["error_message"] = "body too short; likely image-only or non-article page"
    except Exception as exc:
        logger.warning("器械之家详情页抓取失败，保留列表摘要: %s | %s", result["url"], exc)
        result["error_message"] = f"detail fetch failed; used list summary: {exc}"
        if not result["body"]:
            result["status"] = "failed"

    return result


def extract_qixieke_title(soup: BeautifulSoup, fallback: str) -> str:
    for selector in ["h1", ".title"]:
        node = soup.select_one(selector)
        if node:
            title = clean_text(node.get_text(" ", strip=True))
            if title:
                return title
    if soup.title:
        return clean_text(soup.title.get_text(" ", strip=True).replace("-器械之家", ""))
    return fallback


def extract_qixieke_date(soup: BeautifulSoup, fallback: str) -> str:
    match = re.search(r"20\d{2}-\d{1,2}-\d{1,2}", soup.get_text(" ", strip=True))
    return match.group(0) if match else fallback


def extract_qixieke_author(soup: BeautifulSoup) -> str:
    text = soup.get_text(" ", strip=True)
    match = re.search(r"来源[:：]\s*([^\s，,。]{2,30})", text)
    return clean_text(match.group(1)) if match else ""


def clean_qixieke_summary(text: str, title: str) -> str:
    text = clean_text(text)
    if title and text.startswith(title):
        text = text[len(title) :].strip()
    text = re.sub(r"\s*(?:其他|市场动态|X线机|IVD|医学影像)\s+20\d{2}-\d{1,2}-\d{1,2}\s*$", "", text)
    return text.strip()


def clean_qixieke_body(text: str, title: str = "") -> str:
    lines: list[str] = []
    for line in (text or "").splitlines():
        line = clean_text(line)
        if not line:
            continue
        if line == title or line in {"首页", ">", "详情"}:
            continue
        if line in {"其他", "市场动态", "X线机", "IVD", "医学影像", "展览/会议"}:
            continue
        if line in {"新闻", "前沿技术", "市场及融资", "专题", "会议活动", "热词搜索"}:
            continue
        if re.fullmatch(r"20\d{2}-\d{1,2}-\d{1,2}", line):
            continue
        if line.startswith("来源："):
            continue
        if line.startswith(("关于我们", "商业合作", "加入我们", "意见反馈", "标签库")):
            break
        lines.append(line)
    return "\n".join(lines).strip()


def scrape_yaozh_news(
    source: dict[str, Any],
    max_articles: int | None,
    settings: ScraperSettings,
    logger: logging.Logger,
) -> list[dict[str, Any]]:
    """Adapter for 药智新闻, whose list page loads more items through a public JSON endpoint."""
    articles: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    page = 1
    max_pages = 100

    while page <= max_pages:
        try:
            page_items, pageall = fetch_yaozh_list_page(page, settings)
        except Exception as exc:
            logger.error("药智新闻列表接口抓取失败 page=%s: %s", page, exc)
            if not articles:
                return [failed_article(source, source.get("list_url", ""), str(exc))]
            break

        if not page_items:
            break

        for item in page_items:
            article = yaozh_item_to_article(source, item, settings, logger)
            key = article.get("url") or article.get("title")
            if not key or key in seen_urls:
                continue
            seen_urls.add(key)
            articles.append(article)

            if max_articles is not None and len(articles) >= max_articles:
                logger.info("药智新闻抓取成功: %s 篇", len(articles))
                return articles

        if pageall and page >= int(pageall):
            break
        page += 1

    logger.info("药智新闻抓取成功: %s 篇", len(articles))
    return articles


def fetch_yaozh_list_page(page: int, settings: ScraperSettings) -> tuple[list[dict[str, Any]], int]:
    response = requests.get(
        "https://news.yaozh.com/api/Common/getsearcharticle",
        params={
            "user_id": "",
            "search_name": "",
            "page": page,
            "limits": "10",
            "is_index": "false",
            "navid": "24",
            "has_cateid": "61",
            "artid": "",
            "is_headline": 0,
            "uid": "",
        },
        headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/126.0 Safari/537.36",
            "Referer": "https://news.yaozh.com/archivelist/24?has_cateid=61",
        },
        timeout=settings.timeout,
    )
    response.raise_for_status()
    response_data = response.json()
    if response_data.get("code") != 200:
        raise RuntimeError(f"unexpected response: {response_data}")

    decrypted = decrypt_yaozh_response(response_data.get("data", ""))
    payload = json.loads(decrypted)
    return payload.get("article") or [], int(payload.get("pageall") or 0)


def decrypt_yaozh_response(input_text: str, key: str = "yaozh_news2020!") -> str:
    """Mirror the public front-end decoder used by 药智新闻 for its JSON responses."""
    if not input_text:
        return ""

    xor_key = hashlib.md5(key.encode("utf-8")).hexdigest()
    key_index = 0
    pending_utf8: list[int] = []
    output: list[str] = []
    cleaned_input = "".join(ch for ch in input_text if ch.isalnum() or ch in "+/=")

    def decode_xored_byte(value: int) -> str:
        if pending_utf8:
            first = pending_utf8[0]
            if 191 < first < 224:
                pending_utf8.clear()
                return chr(((31 & first) << 6) | (63 & value))
            if len(pending_utf8) == 1:
                pending_utf8.append(value)
                return ""
            second = pending_utf8[1]
            pending_utf8.clear()
            return chr(((15 & first) << 12) | ((63 & second) << 6) | (63 & value))

        if value < 128:
            return chr(value)
        pending_utf8.append(value)
        return ""

    for byte in base64.b64decode(cleaned_input):
        if key_index == 32:
            key_index = 0
        decoded_byte = byte ^ ord(xor_key[key_index])
        key_index += 1
        output.append(decode_xored_byte(decoded_byte))

    return "".join(output)


def yaozh_item_to_article(
    source: dict[str, Any],
    item: dict[str, Any],
    settings: ScraperSettings,
    logger: logging.Logger,
) -> dict[str, Any]:
    title = clean_text(item.get("title", ""))
    summary = html_to_text(item.get("description", ""))
    item_id = item.get("id", "")
    url = f"https://news.yaozh.com/archive/{item_id}.html" if item_id else source.get("list_url", "")

    result = {
        "source_name": source.get("source_name", ""),
        "category": source.get("category", ""),
        "title": title,
        "publish_date": clean_text(item.get("create_time", "")),
        "url": url,
        "author": clean_text(item.get("authorname", "")),
        "raw_html": json.dumps(item, ensure_ascii=False),
        "body": summary or title,
        "tag_name": clean_text(item.get("tag_name", "")),
        "crawl_time": now_iso(),
        "status": "success",
        "error_message": "",
    }

    if item_id:
        try:
            response = requests.get(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36",
                    "Referer": source.get("list_url", ""),
                },
                timeout=settings.timeout,
            )
            response.raise_for_status()
            if not response.encoding or response.encoding.lower() == "iso-8859-1":
                response.encoding = response.apparent_encoding
            soup = BeautifulSoup(response.text, "lxml")
            result["raw_html"] = response.text
            result["title"] = extract_yaozh_title(soup, title)

            body_node = soup.select_one((source.get("selectors", {}) or {}).get("body") or ".detail")
            detail_body = clean_yaozh_body(html_to_text(str(body_node)) if body_node else "", result["title"])
            if detail_body:
                result["body"] = detail_body
            elif not result["body"]:
                result["status"] = "failed"
                result["error_message"] = "empty body"
        except Exception as exc:
            logger.warning("药智新闻详情页抓取失败，保留列表摘要: %s | %s", url, exc)
            result["error_message"] = f"detail fetch failed; used list summary: {exc}"

    if not result["body"]:
        result["status"] = "failed"
        result["error_message"] = result["error_message"] or "empty body"

    return result


def extract_yaozh_title(soup: BeautifulSoup, fallback: str) -> str:
    title_node = soup.select_one(".detail h1, h1")
    if title_node:
        title = clean_text(title_node.get_text(" ", strip=True))
        if title:
            return title
    if soup.title:
        return clean_text(soup.title.get_text(" ", strip=True).replace("_药智新闻", ""))
    return fallback


def clean_yaozh_body(text: str, title: str = "") -> str:
    import re

    lines: list[str] = []
    started = False
    for line in (text or "").splitlines():
        line = clean_text(line)
        if not line:
            continue
        if line == title or line in {"分享", "扫码分享到微信", "A + A -", "A", "+", "-"}:
            continue
        if re.fullmatch(r"\d{1,8}", line):
            continue
        if line.startswith("来源："):
            continue
        if re.fullmatch(r"20\d{2}", line) or re.fullmatch(r"\d{1,2}/\d{1,2}", line):
            continue
        if line.startswith(("延伸阅读", "声明：本文仅作信息传递", "合作、投稿、转载")):
            break
        if line.startswith("导读："):
            started = True
        if not started and len(line) < 30:
            continue
        started = True
        lines.append(line)
    return "\n".join(lines).strip()


def scrape_menet_news(
    source: dict[str, Any],
    max_articles: int | None,
    settings: ScraperSettings,
    logger: logging.Logger,
) -> list[dict[str, Any]]:
    """Small adapter for 米内网, whose list page uses empty anchor text."""
    list_url = source.get("list_url", "")
    selectors = source.get("selectors", {}) or {}

    try:
        response = requests.get(list_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=settings.timeout)
        response.raise_for_status()
        if not response.encoding or response.encoding.lower() == "iso-8859-1":
            response.encoding = response.apparent_encoding
    except Exception as exc:
        logger.error("米内网列表页抓取失败: %s", exc)
        return [failed_article(source, list_url, str(exc))]

    soup = BeautifulSoup(response.text, "lxml")
    card_selector = selectors.get("article_card") or ".itemOut"
    cards = soup.select(card_selector)
    articles: list[dict[str, Any]] = []
    seen_urls: set[str] = set()

    for card in cards:
        link = card.select_one(selectors.get("article_link") or ".item_title a[href]")
        if not link:
            continue
        url = normalize_url(make_absolute_url(list_url, link.get("href", "")))
        if not url or url in seen_urls:
            continue

        title_node = card.select_one(selectors.get("title") or ".item_title")
        title = clean_text(title_node.get_text(" ", strip=True) if title_node else "")
        summary_node = card.select_one(".item_con")
        summary = clean_text(summary_node.get_text(" ", strip=True) if summary_node else "")
        date_node = card.select_one(selectors.get("date") or ".item_time")
        publish_date = clean_text(date_node.get_text(" ", strip=True) if date_node else "")

        if not title:
            continue

        seen_urls.add(url)
        articles.append(fetch_menet_detail(source, url, title, publish_date, summary, settings, logger))

        if max_articles is not None and len(articles) >= max_articles:
            break

    logger.info("米内网抓取成功: %s 篇", len(articles))
    return articles


def fetch_menet_detail(
    source: dict[str, Any],
    url: str,
    title: str,
    publish_date: str,
    summary: str,
    settings: ScraperSettings,
    logger: logging.Logger,
) -> dict[str, Any]:
    result = {
        "source_name": source.get("source_name", ""),
        "category": source.get("category", ""),
        "title": title,
        "publish_date": publish_date,
        "url": url,
        "author": "",
        "raw_html": "",
        "body": summary,
        "crawl_time": now_iso(),
        "status": "success",
        "error_message": "",
    }

    try:
        response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=settings.timeout)
        response.raise_for_status()
        if not response.encoding or response.encoding.lower() == "iso-8859-1":
            response.encoding = response.apparent_encoding
        soup = BeautifulSoup(response.text, "lxml")
        result["raw_html"] = response.text
        result["title"] = extract_menet_title(soup, title)
        result["publish_date"] = extract_menet_date(soup, publish_date)
        result["author"] = extract_menet_author(soup)

        body_node = soup.select_one((source.get("selectors", {}) or {}).get("body") or ".detail")
        body = html_to_text(str(body_node)) if body_node else ""
        result["body"] = body or summary
        if not result["body"]:
            result["status"] = "failed"
            result["error_message"] = "empty body"
    except Exception as exc:
        logger.warning("米内网详情页抓取失败，保留列表摘要: %s | %s", url, exc)
        result["error_message"] = f"detail fetch failed; used list summary: {exc}"
        if not result["body"]:
            result["status"] = "failed"

    return result


def extract_menet_title(soup: BeautifulSoup, fallback: str) -> str:
    title_node = soup.select_one(".info_title, .article_title, h1")
    if title_node:
        title = clean_text(title_node.get_text(" ", strip=True))
        if title:
            return title
    if soup.title:
        return clean_text(soup.title.get_text(" ", strip=True).replace("-米内网", ""))
    return fallback


def extract_menet_date(soup: BeautifulSoup, fallback: str) -> str:
    text = soup.get_text(" ", strip=True)
    import re

    match = re.search(r"20\d{2}-\d{1,2}-\d{1,2}(?:\s+\d{1,2}:\d{2})?", text)
    return match.group(0) if match else fallback


def extract_menet_author(soup: BeautifulSoup) -> str:
    text = soup.get_text(" ", strip=True)
    if "来源：米内网原创" in text:
        return "米内网原创"
    if "来源：米内网" in text:
        return "米内网"
    return ""


def failed_article(source: dict[str, Any], url: str, error_message: str) -> dict[str, Any]:
    return {
        "source_name": source.get("source_name", ""),
        "category": source.get("category", ""),
        "title": "",
        "publish_date": "",
        "url": url,
        "author": "",
        "raw_html": "",
        "body": "",
        "crawl_time": now_iso(),
        "status": "failed",
        "error_message": error_message,
    }


def scrape_vbdata_intel_list(
    source: dict[str, Any],
    max_articles: int | None,
    settings: ScraperSettings,
    logger: logging.Logger,
    project_dir: Path,
) -> list[dict[str, Any]]:
    """Small site adapter for 动脉网 7x24H情报."""
    api_articles = scrape_vbdata_intel_list_api(source, max_articles, settings, logger)
    if api_articles:
        return api_articles

    logger.warning("动脉网 API 抓取未返回数据，回退到 Playwright 动态抓取。")
    scraper = DynamicScraper(settings=settings, logger=logger, project_dir=project_dir)
    return scraper.scrape_source(source, max_articles=max_articles)


def scrape_vbdata_intel_list_api(
    source: dict[str, Any],
    max_articles: int | None,
    settings: ScraperSettings,
    logger: logging.Logger,
) -> list[dict[str, Any]]:
    """Fetch 动脉网 7x24H 情报 through the same public JSON endpoint used by the page."""
    size = max_articles or 20
    payload = {
        "page": 1,
        "size": size,
        "getCount": False,
    }

    try:
        response_data = vbdata_api_post("/api/mi/list", payload, settings)
    except Exception as exc:
        logger.error("动脉网 API list failed: %s", exc)
        return []

    if response_data.get("code") != 0:
        logger.error("动脉网 API list returned error: %s", response_data)
        return []

    items = response_data.get("data") or []
    articles: list[dict[str, Any]] = []
    seen_keys: set[str] = set()

    for item in items:
        article = vbdata_item_to_article(source, item)
        key = article.get("url") or article.get("title")
        if not key or key in seen_keys:
            continue
        seen_keys.add(key)
        articles.append(article)
        if max_articles is not None and len(articles) >= max_articles:
            break

    logger.info("动脉网 API 抓取成功: %s 篇", len(articles))
    return articles


def vbdata_api_post(path: str, payload: dict[str, Any], settings: ScraperSettings) -> dict[str, Any]:
    body = dict(payload)
    body.update({"uUserId": None, "uUid": None})
    timestamp = vbdata_timestamp()
    body_text = json.dumps(body, ensure_ascii=False, separators=(",", ":"))
    sign = hashlib.md5((body_text + str(timestamp)).encode("utf-8")).hexdigest()

    response = requests.post(
        urljoin("https://app.vbdata.cn", path),
        data=body_text.encode("utf-8"),
        headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/126.0 Safari/537.36",
            "Referer": "https://www.vbdata.cn/intelList",
            "Origin": "https://www.vbdata.cn",
            "content-Type": "application/json; charset=UTF-8",
            "timestamp": str(timestamp),
            "sign": sign,
            "platform": "PC",
        },
        timeout=settings.timeout,
    )
    response.raise_for_status()
    return response.json()


def vbdata_timestamp() -> int:
    seconds = int(time.time())
    crc_prefix = str(zlib.crc32(str(seconds).encode("utf-8")) & 0xFFFFFFFF)[:3]
    return int(f"{seconds}{crc_prefix}")


def vbdata_item_to_article(source: dict[str, Any], item: dict[str, Any]) -> dict[str, Any]:
    title = clean_text(item.get("title", ""))
    summary = html_to_text(item.get("summary", ""))
    content = html_to_text(item.get("content", ""))
    body = summary or content or title

    item_id = item.get("appMiId") or item.get("id") or ""
    url = item.get("url") or ""
    if not url and item_id:
        url = f"https://www.vbdata.cn/intelDetail/{item_id}"

    return {
        "source_name": source.get("source_name", ""),
        "category": source.get("category", ""),
        "title": title,
        "publish_date": clean_text(item.get("publishTime", "")),
        "url": url or source.get("list_url", ""),
        "author": clean_text(item.get("authorName", "") or item.get("author", "")),
        "raw_html": json.dumps(item, ensure_ascii=False),
        "body": body,
        "intel_type": clean_text(item.get("showAppItrackTagName", "") or item.get("source", "")),
        "crawl_time": now_iso(),
        "status": "success" if body else "failed",
        "error_message": "" if body else "empty body",
    }


def clean_text(value: Any) -> str:
    return " ".join(str(value or "").split())


def matches_keyword_rules(source: dict[str, Any], text: str) -> bool:
    include_keywords = [str(item).lower() for item in source.get("include_keywords", []) if item]
    exclude_keywords = [str(item).lower() for item in source.get("exclude_keywords", []) if item]
    normalized_text = (text or "").lower()

    if exclude_keywords and any(keyword in normalized_text for keyword in exclude_keywords):
        return False
    if include_keywords and not any(keyword in normalized_text for keyword in include_keywords):
        return False
    return True
