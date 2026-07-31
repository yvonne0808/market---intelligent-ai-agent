from __future__ import annotations

import logging
import os
import re
import time
from pathlib import Path
from typing import Any

import requests
from bs4 import BeautifulSoup

from website_scraper.article_cleaner import html_to_text
from website_scraper.utils import make_absolute_url, normalize_url, now_iso
from website_scraper.web_scraper import USER_AGENT, ScraperSettings


class DynamicScraper:
    """Small Playwright wrapper for JavaScript-rendered list pages."""

    def __init__(
        self,
        settings: ScraperSettings,
        logger: logging.Logger,
        project_dir: Path,
    ):
        self.settings = settings
        self.logger = logger
        self.project_dir = project_dir

    def scrape_source(self, source: dict[str, Any], max_articles: int | None = 10) -> list[dict[str, Any]]:
        browser_path = self.project_dir / ".playwright-browsers"
        if browser_path.exists():
            os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(browser_path))

        try:
            from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            self.logger.error("Playwright is not installed. Dynamic source skipped: %s", source.get("source_name", ""))
            self._save_static_debug_html(source)
            return [
                self._failed_article(
                    source,
                    error_message=f"playwright not installed: {exc}",
                    url=source.get("list_url", ""),
                )
            ]

        articles: list[dict[str, Any]] = []
        debug_path = self._debug_path_for_source(source)

        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                page = browser.new_page(
                    user_agent=USER_AGENT,
                    viewport={"width": 1440, "height": 1200},
                    locale="zh-CN",
                )

                try:
                    page.goto(source.get("list_url", ""), wait_until="domcontentloaded", timeout=self.settings.timeout * 1000)
                    try:
                        page.wait_for_load_state("networkidle", timeout=self.settings.timeout * 1000)
                    except PlaywrightTimeoutError:
                        self.logger.warning("Network idle timeout; continuing with current page content.")

                    self._scroll_page(page)
                    html = page.content()
                    article_stubs = self.extract_list_items(source, html)

                    if not article_stubs:
                        self._save_debug_html(debug_path, html)
                        self.logger.warning(
                            "动脉网可能为动态加载页面或 selector 需要调整，已保存 debug HTML。%s",
                            debug_path,
                        )
                        return [
                            self._failed_article(
                                source,
                                error_message="no article cards found; debug HTML saved",
                                url=source.get("list_url", ""),
                                raw_html=html,
                            )
                        ]

                    seen_keys: set[str] = set()
                    for stub in article_stubs:
                        key = stub.get("url") or stub.get("title")
                        if not key or key in seen_keys:
                            continue
                        seen_keys.add(key)
                        articles.append(self._build_article_from_stub(source, page, stub))
                        if max_articles is not None and len(articles) >= max_articles:
                            break
                finally:
                    browser.close()
        except Exception as exc:
            self.logger.error("Dynamic source failed: %s | %s", source.get("source_name", ""), exc)
            self._save_static_debug_html(source)
            articles.append(self._failed_article(source, error_message=str(exc), url=source.get("list_url", "")))

        return articles

    def extract_list_items(self, source: dict[str, Any], html: str) -> list[dict[str, str]]:
        soup = BeautifulSoup(html or "", "lxml")
        selectors = source.get("selectors", {}) or {}
        card_selector = selectors.get("article_card", "")
        cards = soup.select(card_selector) if card_selector else []
        if not cards:
            cards = self._guess_article_cards(soup)

        items: list[dict[str, str]] = []
        for card in cards:
            text = self._clean_text(card.get_text("\n", strip=True))
            if len(text) < 8:
                continue

            title = self._extract_title_from_card(card, selectors)
            body = self._extract_body_from_card(card, title)
            date_text = self._extract_date(text)
            intel_type = self._extract_type(text)
            url = self._extract_url_from_card(card, source.get("list_url", ""), selectors)

            if not title and body:
                title = body[:60]
            if not title:
                continue

            items.append(
                {
                    "title": title,
                    "publish_date": date_text,
                    "url": url,
                    "body": body or title,
                    "intel_type": intel_type,
                }
            )

        return items

    def _build_article_from_stub(self, source: dict[str, Any], page: Any, stub: dict[str, str]) -> dict[str, Any]:
        article = {
            "source_name": source.get("source_name", ""),
            "category": source.get("category", ""),
            "title": stub.get("title", ""),
            "publish_date": stub.get("publish_date", ""),
            "url": stub.get("url", "") or source.get("list_url", ""),
            "author": "",
            "raw_html": "",
            "body": stub.get("body", ""),
            "intel_type": stub.get("intel_type", ""),
            "crawl_time": now_iso(),
            "status": "success",
            "error_message": "",
        }

        detail_url = stub.get("url", "")
        if detail_url and detail_url != source.get("list_url", ""):
            try:
                page.goto(detail_url, wait_until="domcontentloaded", timeout=self.settings.timeout * 1000)
                try:
                    page.wait_for_load_state("networkidle", timeout=self.settings.timeout * 1000)
                except Exception:
                    pass
                detail_html = page.content()
                detail_body = self.extract_detail_body(source, detail_html)
                article["raw_html"] = detail_html
                if detail_body:
                    article["body"] = detail_body
            except Exception as exc:
                self.logger.warning("Detail page failed; keeping list text: %s | %s", detail_url, exc)
                article["error_message"] = f"detail page failed; used list text: {exc}"

        if not article["body"]:
            article["status"] = "failed"
            article["error_message"] = article["error_message"] or "empty body"

        return article

    def extract_detail_body(self, source: dict[str, Any], html: str) -> str:
        soup = BeautifulSoup(html or "", "lxml")
        selectors = source.get("selectors", {}) or {}
        body_selectors = [
            selectors.get("body", ""),
            "article",
            ".article-content",
            ".content",
            ".detail-content",
            ".news-content",
            "main",
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
        return best_text

    def _guess_article_cards(self, soup: BeautifulSoup) -> list[Any]:
        candidates = []
        for selector in [
            "[class*=intel]",
            "[class*=news]",
            "[class*=list] li",
            "[class*=item]",
            "[class*=card]",
            "article",
            "li",
        ]:
            candidates.extend(soup.select(selector))

        unique_cards: list[Any] = []
        seen_texts: set[str] = set()
        for card in candidates:
            text = self._clean_text(card.get_text(" ", strip=True))
            if len(text) < 8 or text in seen_texts:
                continue
            if not self._looks_like_news_text(text):
                continue
            seen_texts.add(text)
            unique_cards.append(card)
        return unique_cards

    def _looks_like_news_text(self, text: str) -> bool:
        keywords = ["医疗", "医药", "器械", "融资", "投资", "获批", "政策", "产品", "企业", "创新", "动态"]
        has_keyword = any(keyword in text for keyword in keywords)
        has_time = bool(re.search(r"\d{4}[-/.年]\d{1,2}[-/.月]\d{1,2}|今天|昨天|\d+分钟前|\d+小时前", text))
        return has_keyword or has_time

    def _extract_title_from_card(self, card: Any, selectors: dict[str, str]) -> str:
        title_selector = selectors.get("title", "")
        for selector in [title_selector, "h1", "h2", "h3", "h4", ".title", "[class*=title]", "a"]:
            if not selector:
                continue
            node = card.select_one(selector)
            if node:
                text = self._clean_text(node.get_text(" ", strip=True))
                if len(text) >= 4:
                    return text

        lines = [line.strip() for line in card.get_text("\n", strip=True).splitlines() if line.strip()]
        return lines[0] if lines else ""

    def _extract_body_from_card(self, card: Any, title: str) -> str:
        text = self._clean_text(card.get_text("\n", strip=True))
        if title and text.startswith(title):
            text = text[len(title) :].strip()
        return text or title

    def _extract_url_from_card(self, card: Any, list_url: str, selectors: dict[str, str]) -> str:
        link_selector = selectors.get("article_link", "")
        link = card.select_one(link_selector) if link_selector else card.select_one("a[href]")
        if not link:
            return ""
        href = link.get("href", "")
        if not href or href.startswith("javascript:"):
            return ""
        return normalize_url(make_absolute_url(list_url, href))

    def _extract_date(self, text: str) -> str:
        patterns = [
            r"20\d{2}[-/.年]\d{1,2}[-/.月]\d{1,2}日?(?:\s+\d{1,2}:\d{2})?",
            r"\d{1,2}[-/.月]\d{1,2}日?(?:\s+\d{1,2}:\d{2})?",
            r"(?:今天|昨天)\s*\d{1,2}:\d{2}",
            r"\d+\s*(?:分钟前|小时前|天前)",
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(0).replace("年", "-").replace("月", "-").replace("日", "")
        return ""

    def _extract_type(self, text: str) -> str:
        for keyword in ["资本动态", "公司动态", "政策动态", "产品动态", "行业动态"]:
            if keyword in text:
                return keyword
        return ""

    def _scroll_page(self, page: Any) -> None:
        for _ in range(3):
            page.mouse.wheel(0, 1200)
            time.sleep(0.8)

    def _debug_path_for_source(self, source: dict[str, Any]) -> Path:
        if source.get("source_name") == "动脉网 7x24H情报":
            return self.project_dir / "data" / "website" / "raw" / "debug_vbdata_intelList.html"
        return self.project_dir / "data" / "website" / "raw" / "debug_dynamic_source.html"

    def _save_debug_html(self, debug_path: Path, html: str) -> None:
        debug_path.parent.mkdir(parents=True, exist_ok=True)
        debug_path.write_text(html or "", encoding="utf-8")

    def _save_static_debug_html(self, source: dict[str, Any]) -> None:
        debug_path = self._debug_path_for_source(source)
        try:
            response = requests.get(
                source.get("list_url", ""),
                headers={"User-Agent": USER_AGENT},
                timeout=self.settings.timeout,
            )
            if not response.encoding or response.encoding.lower() == "iso-8859-1":
                response.encoding = response.apparent_encoding
            self._save_debug_html(debug_path, response.text)
            self.logger.warning(
                "动脉网可能为动态加载页面或 selector 需要调整，已保存 debug HTML。%s",
                debug_path,
            )
        except Exception as exc:
            self.logger.warning("Could not save debug HTML for %s: %s", source.get("source_name", ""), exc)

    def _failed_article(
        self,
        source: dict[str, Any],
        error_message: str,
        url: str = "",
        raw_html: str = "",
    ) -> dict[str, Any]:
        return {
            "source_name": source.get("source_name", ""),
            "category": source.get("category", ""),
            "title": "",
            "publish_date": "",
            "url": url,
            "author": "",
            "raw_html": raw_html,
            "body": "",
            "crawl_time": now_iso(),
            "status": "failed",
            "error_message": error_message,
        }

    def _clean_text(self, text: str) -> str:
        text = re.sub(r"[ \t\r\f\v]+", " ", text or "")
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()
