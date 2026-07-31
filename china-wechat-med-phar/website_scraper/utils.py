from __future__ import annotations

import hashlib
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse, urlunparse


def setup_logger(log_path: Path) -> logging.Logger:
    """Create a logger that writes both to file and to the terminal."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("website_scraper")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    logger.propagate = False

    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    return logger


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def make_absolute_url(base_url: str, href: str) -> str:
    if not href:
        return ""
    return urljoin(base_url, href.strip())


def normalize_url(url: str) -> str:
    """Remove fragments and normalize repeated whitespace."""
    url = (url or "").strip()
    if not url:
        return ""
    parsed = urlparse(url)
    return urlunparse(parsed._replace(fragment=""))


def stable_id(value: str) -> str:
    return hashlib.sha1((value or "").encode("utf-8")).hexdigest()[:16]


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)


def read_text_sample(text: str, limit: int = 1000) -> str:
    text = text or ""
    if len(text) <= limit:
        return text
    return text[:limit] + "\n...[truncated]"
