from __future__ import annotations

import re
from typing import Any

from bs4 import BeautifulSoup


NOISE_PATTERNS = [
    r"分享到.*",
    r"分享至.*",
    r"扫一扫.*",
    r"首页\s*>.*详情",
    r"上一篇[:：].*",
    r"下一篇[:：].*",
    r"相关推荐.*",
    r"延伸阅读.*",
    r"相关新闻.*",
    r"相关阅读.*",
    r"声明：本文仅作信息传递.*",
    r"合作、投稿、转载.*",
    r"发布时间[:：]?.*",
    r"点击数[:：]?.*",
    r"打印本页.*",
    r"关闭窗口.*",
    r"返回列表.*",
    r"版权.*所有.*",
    r"Copyright.*",
]


def normalize_chinese_text(text: str) -> str:
    """Normalize spaces and common punctuation without changing article meaning."""
    text = text or ""
    replacements = {
        "\u3000": " ",
        "， ": "，",
        "。 ": "。",
        "； ": "；",
        "： ": "：",
        "（ ": "（",
        " ）": "）",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)

    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def remove_noise_lines(text: str) -> str:
    lines = [line.strip() for line in (text or "").splitlines()]
    cleaned_lines: list[str] = []

    for line in lines:
        if not line:
            cleaned_lines.append("")
            continue
        if any(re.fullmatch(pattern, line, flags=re.IGNORECASE) for pattern in NOISE_PATTERNS):
            continue
        # Very short button-like lines are usually not part of the article body.
        if line in {"分享", "微信", "微博", "打印", "关闭", "返回", "首页"}:
            continue
        cleaned_lines.append(line)

    return normalize_chinese_text("\n".join(cleaned_lines))


def html_to_text(html: str) -> str:
    if not html:
        return ""

    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "noscript", "nav", "footer", "header", "form"]):
        tag.decompose()

    text = soup.get_text("\n", strip=True)
    return remove_noise_lines(text)


def clean_body(body: str, raw_html: str = "") -> tuple[str, int]:
    """Return cleaned article body and its character length."""
    text = body or html_to_text(raw_html)
    text = remove_noise_lines(text)
    return text, len(text)


def to_clean_article(raw_article: dict[str, Any]) -> dict[str, Any]:
    body, body_length = clean_body(
        raw_article.get("body", ""),
        raw_article.get("raw_html", ""),
    )
    title = str(raw_article.get("title", "")).strip()
    body = remove_leading_title(body, title)
    body_length = len(body)

    status = raw_article.get("status", "success")
    error_message = raw_article.get("error_message", "")
    if status == "success" and body_length == 0:
        status = "failed"
        error_message = error_message or "empty body after cleaning"

    return {
        "source_type": "website",
        "source_name": raw_article.get("source_name", ""),
        "category": raw_article.get("category", ""),
        "title": raw_article.get("title", ""),
        "publish_date": raw_article.get("publish_date", ""),
        "url": raw_article.get("url", ""),
        "author": raw_article.get("author", ""),
        "body": body,
        "body_length": body_length,
        "crawl_time": raw_article.get("crawl_time", ""),
        "status": status,
        "error_message": error_message,
    }


def remove_leading_title(body: str, title: str) -> str:
    if not body or not title:
        return body
    lines = body.splitlines()
    while len(lines) > 1 and lines[0].strip() == title:
        lines.pop(0)
    return normalize_chinese_text("\n".join(lines))
