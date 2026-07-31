from __future__ import annotations

import logging
import random
import re
import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from website_scraper.article_cleaner import html_to_text
from website_scraper.utils import make_absolute_url, normalize_url, now_iso


USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0 Safari/537.36"
)


@dataclass
class ScraperSettings:
    timeout: int = 20
    retries: int = 3
    sleep_min: float = 1.0
    sleep_max: float = 2.5


class WebsiteScraper:
    def __init__(
        self,
        settings: ScraperSettings | None = None,
        logger: logging.Logger | None = None,
        project_dir: Path | None = None,
    ):
        self.settings = settings or ScraperSettings()
        self.logger = logger or logging.getLogger("website_scraper")
        self.project_dir = project_dir or Path.cwd()
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": USER_AGENT,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.7",
            }
        )

    def scrape_enabled_sources(
        self,
        sources: list[dict[str, Any]],
        max_articles: int | None = 10,
        paginate_static: bool = True,
        max_pages: int = 50,
        target_year: int | None = None,
        target_month: int | None = None,
    ) -> list[dict[str, Any]]:
        """Dispatch each enabled source to the right scraping strategy."""
        raw_articles: list[dict[str, Any]] = []
        seen_keys: set[str] = set()

        for source in sources:
            source_max_articles = self._source_max_articles(source, max_articles)
            source_articles = self.scrape_source(
                source,
                max_articles=source_max_articles,
                paginate_static=paginate_static,
                max_pages=max_pages,
                target_year=target_year,
                target_month=target_month,
            )

            for article in source_articles:
                key = article.get("url") or f"{article.get('source_name', '')}:{article.get('title', '')}"
                if not key or key in seen_keys:
                    continue
                seen_keys.add(key)
                raw_articles.append(article)

        return raw_articles

    def scrape_source(
        self,
        source: dict[str, Any],
        max_articles: int | None = 10,
        paginate_static: bool = True,
        max_pages: int = 50,
        target_year: int | None = None,
        target_month: int | None = None,
    ) -> list[dict[str, Any]]:
        strategy = source.get("parsing_strategy", "static_html")
        source_name = source.get("source_name", "")
        self.logger.info("Scraping source: %s | strategy=%s", source_name, strategy)

        try:
            from website_scraper.site_adapters import scrape_with_adapter

            adapter_result = scrape_with_adapter(
                source=source,
                max_articles=max_articles,
                settings=self.settings,
                logger=self.logger,
                project_dir=self.project_dir,
            )
            if adapter_result is not None:
                return adapter_result

            if strategy == "static_html":
                if paginate_static:
                    return self.scrape_sources_paginated(
                        [source],
                        max_articles_per_page=max_articles,
                        max_pages=max_pages,
                        target_year=target_year,
                        target_month=target_month,
                    )
                return self.scrape_sources([source], max_articles=max_articles)

            if strategy == "dynamic_js":
                from website_scraper.dynamic_scraper import DynamicScraper

                return DynamicScraper(self.settings, self.logger, self.project_dir).scrape_source(
                    source,
                    max_articles=max_articles,
                )

            if strategy == "rss_if_available":
                self.logger.warning("rss_if_available is reserved but not implemented yet: %s", source_name)
                return []

            self.logger.warning("Unknown parsing_strategy=%s. Source skipped: %s", strategy, source_name)
            return []
        except Exception as exc:
            self.logger.error("Source failed but run continues: %s | %s", source_name, exc)
            return [
                {
                    "source_name": source_name,
                    "category": source.get("category", ""),
                    "title": "",
                    "publish_date": "",
                    "url": source.get("list_url", ""),
                    "author": "",
                    "raw_html": "",
                    "body": "",
                    "crawl_time": now_iso(),
                    "status": "failed",
                    "error_message": str(exc),
                }
            ]

    def polite_sleep(self) -> None:
        time.sleep(random.uniform(self.settings.sleep_min, self.settings.sleep_max))

    def fetch_url(self, url: str) -> requests.Response:
        last_error: Exception | None = None
        for attempt in range(1, self.settings.retries + 1):
            try:
                response = self.session.get(url, timeout=self.settings.timeout)
                response.raise_for_status()
                if not response.encoding or response.encoding.lower() == "iso-8859-1":
                    response.encoding = response.apparent_encoding
                return response
            except requests.RequestException as exc:
                last_error = exc
                self.logger.warning("Fetch failed (%s/%s): %s | %s", attempt, self.settings.retries, url, exc)
                if attempt < self.settings.retries:
                    self.polite_sleep()
        raise RuntimeError(str(last_error) if last_error else "unknown fetch error")

    def scrape_list_page(self, source: dict[str, Any], max_articles: int | None = 10) -> list[dict[str, str]]:
        articles, _next_url = self.scrape_list_page_with_next(source, max_articles=max_articles)
        return articles

    def scrape_list_page_with_next(
        self,
        source: dict[str, Any],
        max_articles: int | None = 10,
        list_url_override: str = "",
    ) -> tuple[list[dict[str, str]], str]:
        source_name = source.get("source_name", "")
        list_url = list_url_override or source.get("list_url", "")
        selectors = source.get("selectors", {}) or {}
        self.logger.info("Scraping list page: %s | %s", source_name, list_url)

        try:
            response = self.fetch_url(list_url)
        except Exception as exc:
            self.logger.error("List page failed: %s | %s", list_url, exc)
            return [], ""

        soup = BeautifulSoup(response.text, "lxml")
        link_nodes = self._select_list_links(soup, selectors)
        articles: list[dict[str, str]] = []
        seen_urls: set[str] = set()

        for link_node in link_nodes:
            href = link_node.get("href", "")
            url = normalize_url(make_absolute_url(list_url, href))
            title = self._clean_text(link_node.get_text(" ", strip=True) or link_node.get("title", ""))

            if not self._looks_like_article_url(url, list_url) or not title:
                continue
            keyword_context = " ".join(
                self._clean_text(node.get_text(" ", strip=True))
                for node in [link_node, link_node.parent, getattr(link_node.parent, "parent", None)]
                if node
            )
            if not self._matches_keyword_rules(source, keyword_context or title):
                continue
            if url in seen_urls:
                continue

            seen_urls.add(url)
            articles.append(
                {
                    "title": title,
                    "url": url,
                    "publish_date": self._find_date_near_link(link_node),
                    "source_name": source_name,
                    "category": source.get("category", ""),
                }
            )

            if max_articles is not None and len(articles) >= max_articles:
                break

        next_url = self._find_next_page_url(soup, list_url)
        self.logger.info("List page found %s article links: %s", len(articles), source_name)
        return articles, next_url

    def scrape_article_detail(self, source: dict[str, Any], article_stub: dict[str, str]) -> dict[str, Any]:
        url = article_stub.get("url", "")
        crawl_time = now_iso()
        result: dict[str, Any] = {
            "source_name": source.get("source_name", ""),
            "category": source.get("category", ""),
            "title": article_stub.get("title", ""),
            "publish_date": article_stub.get("publish_date", ""),
            "url": url,
            "author": "",
            "raw_html": "",
            "body": "",
            "crawl_time": crawl_time,
            "status": "success",
            "error_message": "",
        }

        try:
            response = self.fetch_url(url)
            soup = BeautifulSoup(response.text, "lxml")
            result["raw_html"] = response.text
            result["title"] = self._extract_title(soup, source, fallback=result["title"])
            result["publish_date"] = self._extract_publish_date(soup, fallback=result["publish_date"])
            result["author"] = self._extract_author(soup)
            result["body"] = self._extract_body(soup, source)

            if not result["body"]:
                result["status"] = "failed"
                result["error_message"] = "empty body"
            elif not self._matches_keyword_rules(source, f"{result['title']} {result['body']}"):
                result["status"] = "failed"
                result["error_message"] = "filtered by include/exclude keywords"
        except Exception as exc:
            result["status"] = "failed"
            result["error_message"] = str(exc)
            self.logger.error("Article failed: %s | %s", url, exc)

        return result

    def scrape_sources(self, sources: list[dict[str, Any]], max_articles: int | None = 10) -> list[dict[str, Any]]:
        raw_articles: list[dict[str, Any]] = []
        seen_urls: set[str] = set()

        for source in sources:
            try:
                stubs = self.scrape_list_page(source, max_articles=max_articles)
                for stub in stubs:
                    url = stub.get("url", "")
                    if not url or url in seen_urls:
                        continue
                    seen_urls.add(url)
                    self.polite_sleep()
                    raw_articles.append(self.scrape_article_detail(source, stub))
            except Exception as exc:
                self.logger.error("Source failed but run continues: %s | %s", source.get("source_name", ""), exc)

        return raw_articles

    def scrape_sources_paginated(
        self,
        sources: list[dict[str, Any]],
        max_articles_per_page: int | None = None,
        max_pages: int = 50,
        target_year: int | None = None,
        target_month: int | None = None,
    ) -> list[dict[str, Any]]:
        """Scrape list pages until pagination ends or dates are older than the target month."""
        raw_articles: list[dict[str, Any]] = []
        seen_urls: set[str] = set()

        for source in sources:
            current_url = source.get("list_url", "")
            found_target_month = False

            for page_number in range(1, max_pages + 1):
                if not current_url:
                    break

                stubs, next_url = self.scrape_list_page_with_next(
                    source,
                    max_articles=max_articles_per_page,
                    list_url_override=current_url,
                )
                if not stubs:
                    break

                page_articles: list[dict[str, Any]] = []
                for stub in stubs:
                    url = stub.get("url", "")
                    if not url or url in seen_urls:
                        continue
                    seen_urls.add(url)
                    self.polite_sleep()
                    article = self.scrape_article_detail(source, stub)
                    raw_articles.append(article)
                    page_articles.append(article)

                should_stop = self._should_stop_for_target_month(
                    page_articles,
                    target_year=target_year,
                    target_month=target_month,
                    found_target_month=found_target_month,
                )
                if self._page_has_target_month(page_articles, target_year, target_month):
                    found_target_month = True

                if should_stop:
                    self.logger.info(
                        "Stopping pagination for %s at page %s because articles are older than target month.",
                        source.get("source_name", ""),
                        page_number,
                    )
                    break

                if not next_url:
                    self.logger.info("No next page found for %s", source.get("source_name", ""))
                    break

                current_url = next_url

        return raw_articles

    def _select_list_links(self, soup: BeautifulSoup, selectors: dict[str, str]) -> list[Any]:
        selector = selectors.get("article_link", "")
        if selector:
            selected = soup.select(selector)
            if selected:
                return selected

        candidates = []
        for node in soup.select("a[href]"):
            href = node.get("href", "")
            text = self._clean_text(node.get_text(" ", strip=True) or node.get("title", ""))
            if href and len(text) >= 6:
                candidates.append(node)
        return candidates

    def _looks_like_article_url(self, url: str, list_url: str) -> bool:
        if not url:
            return False
        parsed = urlparse(url)
        list_parsed = urlparse(list_url)
        if parsed.scheme not in {"http", "https"}:
            return False
        if parsed.netloc and parsed.netloc != list_parsed.netloc:
            return False
        if any(value in url.lower() for value in ["javascript:", "mailto:", "#"]):
            return False
        if re.search(r"/news/list|/activity/list|/event/list", parsed.path):
            return False
        return bool(re.search(r"/news/|/article/|/content/|/info/|\d", parsed.path))

    def _extract_title(self, soup: BeautifulSoup, source: dict[str, Any], fallback: str = "") -> str:
        selectors = source.get("selectors", {}) or {}
        for selector in [selectors.get("title", ""), "h1", ".title", ".article-title", ".news-title"]:
            if not selector:
                continue
            node = soup.select_one(selector)
            if node:
                title = self._clean_text(node.get_text(" ", strip=True))
                if title:
                    return title
        if soup.title:
            title = self._clean_text(soup.title.get_text(" ", strip=True))
            if " - " in title:
                title = title.split(" - ", 1)[1].strip()
            else:
                title = re.sub(r"[-_].*$", "", title).strip()
            return title or fallback
        return fallback

    def _extract_publish_date(self, soup: BeautifulSoup, fallback: str = "") -> str:
        page_text = soup.get_text(" ", strip=True)
        match = re.search(r"(20\d{2}[-/.年]\d{1,2}[-/.月]\d{1,2}日?)", page_text)
        if match:
            return match.group(1).replace("年", "-").replace("月", "-").replace("日", "")
        return fallback

    def _extract_author(self, soup: BeautifulSoup) -> str:
        text = soup.get_text(" ", strip=True)
        match = re.search(r"(?:作者|来源|发布者)[:：]\s*([^\s｜|]{2,30})", text)
        return match.group(1).strip() if match else ""

    def _extract_body(self, soup: BeautifulSoup, source: dict[str, Any]) -> str:
        selectors = source.get("selectors", {}) or {}
        body_selectors = [
            selectors.get("body", ""),
            ".article-content",
            ".article",
            ".content",
            ".news-content",
            ".detail-content",
            "#content",
            ".TRS_Editor",
        ]

        best_text = ""
        for selector in body_selectors:
            if not selector:
                continue
            node = soup.select_one(selector)
            if not node:
                continue
            text = html_to_text(str(node))
            if len(text) > len(best_text):
                best_text = text

        if best_text:
            return best_text

        # Fallback: choose the text-heavy container. This keeps CAMDI adjustable without hard-coding.
        for tag in soup(["script", "style", "noscript", "nav", "footer", "header", "form"]):
            tag.decompose()
        candidates = soup.find_all(["article", "main", "section", "div", "td"])
        for node in candidates:
            text = html_to_text(str(node))
            if len(text) > len(best_text):
                best_text = text
        return best_text

    def _find_date_near_link(self, link_node: Any) -> str:
        date_pattern = re.compile(r"(20\d{2}[-/.年]\d{1,2}[-/.月]\d{1,2}日?)")
        for node in [link_node, link_node.parent, getattr(link_node.parent, "parent", None)]:
            if not node:
                continue
            text = node.get_text(" ", strip=True)
            match = date_pattern.search(text)
            if match:
                return match.group(1).replace("年", "-").replace("月", "-").replace("日", "")
        return ""

    def _clean_text(self, text: str) -> str:
        return re.sub(r"\s+", " ", text or "").strip()

    def _matches_keyword_rules(self, source: dict[str, Any], text: str) -> bool:
        include_keywords = [str(item).lower() for item in source.get("include_keywords", []) if item]
        exclude_keywords = [str(item).lower() for item in source.get("exclude_keywords", []) if item]
        normalized_text = (text or "").lower()

        if exclude_keywords and any(keyword in normalized_text for keyword in exclude_keywords):
            return False
        if include_keywords and not any(keyword in normalized_text for keyword in include_keywords):
            return False
        return True

    def _source_max_articles(self, source: dict[str, Any], global_max_articles: int | None) -> int | None:
        source_value = source.get("max_articles")
        if source_value in {None, ""}:
            return global_max_articles
        try:
            value = int(source_value)
        except (TypeError, ValueError):
            self.logger.warning("Invalid max_articles for %s: %s", source.get("source_name", ""), source_value)
            return global_max_articles
        source_max_articles = None if value <= 0 else value
        if global_max_articles is None:
            return source_max_articles
        if source_max_articles is None:
            return global_max_articles
        return min(global_max_articles, source_max_articles)

    def _find_next_page_url(self, soup: BeautifulSoup, current_url: str) -> str:
        current_page = self._current_page_number(current_url)
        numeric_next = ""

        for node in soup.select("ul.pagination a[href], .pagination a[href], a[href]"):
            text = self._clean_text(node.get_text(" ", strip=True))
            href = node.get("href", "")
            if not href:
                continue
            absolute_url = normalize_url(make_absolute_url(current_url, href))
            if text in {"»", "下一页", "下页", "Next", "next"}:
                return absolute_url
            if text.isdigit() and int(text) == current_page + 1:
                numeric_next = absolute_url

        return numeric_next

    def _current_page_number(self, url: str) -> int:
        match = re.search(r"/p(\d+)(?:\D*)?$", url or "")
        if match:
            return int(match.group(1))
        return 1

    def _parse_publish_date(self, publish_date: str) -> date | None:
        match = re.search(r"(20\d{2})[-/.年](\d{1,2})[-/.月](\d{1,2})", publish_date or "")
        if not match:
            return None
        return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))

    def _page_has_target_month(
        self,
        page_articles: list[dict[str, Any]],
        target_year: int | None,
        target_month: int | None,
    ) -> bool:
        if target_year is None or target_month is None:
            return False
        for article in page_articles:
            parsed = self._parse_publish_date(article.get("publish_date", ""))
            if parsed and parsed.year == target_year and parsed.month == target_month:
                return True
        return False

    def _should_stop_for_target_month(
        self,
        page_articles: list[dict[str, Any]],
        target_year: int | None,
        target_month: int | None,
        found_target_month: bool,
    ) -> bool:
        if target_year is None or target_month is None:
            return False

        parsed_dates = [
            parsed
            for article in page_articles
            if (parsed := self._parse_publish_date(article.get("publish_date", ""))) is not None
        ]
        if not parsed_dates:
            return False

        target_start = date(target_year, target_month, 1)
        page_has_target = any(item.year == target_year and item.month == target_month for item in parsed_dates)
        page_has_older = any(item < target_start for item in parsed_dates)

        return page_has_older and (found_target_month or page_has_target)
