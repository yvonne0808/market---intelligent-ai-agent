from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


USER_AGENT = (
    "Mozilla/5.0 (compatible; SoutheastAsiaMedTechMonitor/0.1; "
    "+local public-source research workflow)"
)


@dataclass(frozen=True)
class HttpSettings:
    timeout: int = 20
    retries: int = 3
    sleep_min: float = 1.5
    sleep_max: float = 3.0


class PoliteHttpClient:
    def __init__(self, settings: HttpSettings, logger: logging.Logger):
        self.settings = settings
        self.logger = logger
        retry = Retry(
            total=settings.retries,
            connect=settings.retries,
            read=settings.retries,
            status=settings.retries,
            backoff_factor=0.8,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset({"GET"}),
            respect_retry_after_header=True,
        )
        adapter = HTTPAdapter(max_retries=retry)
        self.session = requests.Session()
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        self.session.headers.update(
            {
                "User-Agent": USER_AGENT,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-SG,en-MY;q=0.9,en;q=0.8",
            }
        )
        self._request_count = 0

    def _get(self, url: str) -> requests.Response:
        if self._request_count:
            delay = random.uniform(self.settings.sleep_min, self.settings.sleep_max)
            self.logger.debug("Polite delay %.2fs before %s", delay, url)
            time.sleep(delay)
        self._request_count += 1
        self.logger.info("GET %s", url)
        response = self.session.get(url, timeout=self.settings.timeout)
        response.raise_for_status()
        return response

    def get_text(self, url: str) -> tuple[str, int, str]:
        response = self._get(url)
        if not response.encoding or response.encoding.lower() == "iso-8859-1":
            response.encoding = response.apparent_encoding or "utf-8"
        content_type = response.headers.get("Content-Type", "")
        if "html" not in content_type.lower():
            raise ValueError(f"Expected HTML but received Content-Type={content_type!r}")
        return response.text, response.status_code, response.url

    def get_bytes(self, url: str) -> tuple[bytes, int, str, str]:
        response = self._get(url)
        return (
            response.content,
            response.status_code,
            response.url,
            response.headers.get("Content-Type", ""),
        )
