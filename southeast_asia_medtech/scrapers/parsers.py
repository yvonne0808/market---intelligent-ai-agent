from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any
from urllib.parse import urljoin, urlparse, urlunparse

from bs4 import BeautifulSoup


ENGLISH_DATE = re.compile(
    r"\b(\d{1,2})\s+"
    r"(January|February|March|April|May|June|July|August|September|October|November|December)"
    r"\s+(20\d{2})\b",
    flags=re.IGNORECASE,
)


@dataclass(frozen=True)
class ArticleStub:
    title: str
    published_date: str
    url: str
    list_text: str = ""


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def normalize_url(base_url: str, href: str) -> str:
    absolute = urljoin(base_url, (href or "").strip())
    parsed = urlparse(absolute)
    path = re.sub(r"/{2,}", "/", parsed.path)
    return urlunparse(
        (
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            path,
            "",
            parsed.query,
            "",
        )
    )


def parse_english_date(value: str) -> date | None:
    match = ENGLISH_DATE.search(value or "")
    if not match:
        return None
    return datetime.strptime(match.group(0), "%d %B %Y").date()


def date_in_range(value: str, start_date: date, end_date: date) -> bool:
    parsed = parse_english_date(value)
    return parsed is not None and start_date <= parsed <= end_date


def parse_hsa_list(html: str, source: dict[str, Any]) -> list[ArticleStub]:
    soup = BeautifulSoup(html or "", "lxml")
    output: list[ArticleStub] = []
    seen: set[str] = set()

    for link in soup.select('a[href^="/announcements/"]'):
        href = str(link.get("href", ""))
        url = normalize_url(source["base_url"], href)
        if href.rstrip("/") == "/announcements" or url in seen:
            continue
        title_node = link.select_one("h3 [title], h3")
        date_node = link.select_one("p")
        title = clean_text(
            str(title_node.get("title", "")) if title_node and title_node.get("title") else
            title_node.get_text(" ", strip=True) if title_node else ""
        )
        published = clean_text(date_node.get_text(" ", strip=True) if date_node else "")
        list_text = clean_text(link.get_text(" ", strip=True))
        if not title or not parse_english_date(published):
            continue
        seen.add(url)
        output.append(ArticleStub(title, published, url, list_text))

    return output


def parse_hsa_embedded_list(html: str, source: dict[str, Any]) -> list[ArticleStub]:
    """Parse all HSA announcement records embedded in the Next.js flight payload."""
    marker = r'\"id\":\"/announcements/'
    starts = [match.start() for match in re.finditer(re.escape(marker), html or "")]
    output: list[ArticleStub] = []
    seen: set[str] = set()
    for index, start in enumerate(starts):
        end = starts[index + 1] if index + 1 < len(starts) else min(len(html), start + 12000)
        chunk = html[start:end]
        if (
            r'\"category\":\"Product type\",\"selected\":[\"Medical devices\"]'
            not in chunk
        ):
            continue
        identity = re.search(r'\\"id\\":\\"([^"]+)\\"', chunk)
        date_match = re.search(r'\\"formattedDate\\":\\"([^"]+)\\"', chunk)
        if date_match is None:
            date_match = re.search(r'\\"date\\":\\"\$D(\d{4}-\d{2}-\d{2})', chunk)
        title_match = re.search(r'\\"title\\":\\"(.*?)\\",\\"', chunk)
        if not identity or not date_match or not title_match:
            continue
        url = normalize_url(source["base_url"], identity.group(1))
        if url in seen:
            continue
        title = bytes(title_match.group(1), "utf-8").decode("unicode_escape")
        try:
            title = title.encode("latin1").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            pass
        published = date_match.group(1)
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", published):
            published = datetime.strptime(published, "%Y-%m-%d").strftime("%d %B %Y")
        seen.add(url)
        output.append(ArticleStub(clean_text(title), published, url, "Medical devices"))
    return output


def parse_mda_list(html: str, source: dict[str, Any]) -> list[ArticleStub]:
    soup = BeautifulSoup(html or "", "lxml")
    output: list[ArticleStub] = []
    seen: set[str] = set()

    for link in soup.select("th.list-title a[href]"):
        row = link.find_parent("tr")
        date_node = row.select_one("td.list-date") if row else None
        title = clean_text(link.get_text(" ", strip=True))
        published = clean_text(date_node.get_text(" ", strip=True) if date_node else "")
        url = normalize_url(source["base_url"], str(link.get("href", "")))
        if not title or not parse_english_date(published) or url in seen:
            continue
        seen.add(url)
        output.append(ArticleStub(title, published, url, clean_text(row.get_text(" ", strip=True))))

    return output


def parse_mda_safety_rows(
    html: str, source: dict[str, Any], page_url: str
) -> list[dict[str, str]]:
    """Parse individual FCA/recall rows instead of treating a monthly page as one item."""
    soup = BeautifulSoup(html or "", "lxml")
    title_node = soup.select_one(".article-details h1, main h1, h1")
    page_title = clean_text(title_node.get_text(" ", strip=True) if title_node else "")
    event_type = "recall" if "recall" in page_title.casefold() else "field_corrective_action"
    output: list[dict[str, str]] = []

    for table in soup.select(".article-details table, main table, table"):
        rows = table.select("tr")
        if not rows:
            continue
        headers = [clean_text(cell.get_text(" ", strip=True)).casefold() for cell in rows[0].select("th, td")]
        if "date received" not in headers:
            continue
        for row in rows[1:]:
            values = [clean_text(cell.get_text(" ", strip=True)) for cell in row.select("th, td")]
            if len(values) != len(headers):
                continue
            item = dict(zip(headers, values))
            date_received = item.get("date received", "")
            if not re.fullmatch(r"\d{1,2}/\d{1,2}/20\d{2}", date_received):
                continue
            if event_type == "recall":
                title = item.get("product name", "")
                detail = item.get("reason of recall", "")
                reference = item.get("reference number", "")
                registration = item.get("product registration number", "")
                establishment = item.get("recalling establishment", "")
                affected_device = title
            else:
                title = item.get("title of fca", "")
                detail = title
                affected_device = item.get("affected medical device", "")
                reference = item.get("mda reference number", "")
                registration = item.get("mda registration number", "")
                establishment = item.get("local establishment contact detail", "")
            if not title:
                continue
            output.append(
                {
                    "title": title,
                    "published_date": datetime.strptime(date_received, "%d/%m/%Y").strftime("%d %B %Y"),
                    "url": f"{page_url}#{reference or len(output) + 1}",
                    "body": clean_text(
                        f"{page_title}. Date received: {date_received}. "
                        f"Affected medical device: {affected_device}. Details: {detail}. "
                        f"MDA reference number: {reference}. MDA registration number: "
                        f"{registration}. Local establishment: {establishment}."
                    ),
                    "safety_event_type": event_type,
                    "reporting_period": page_title,
                    "affected_devices": affected_device,
                    "mda_reference_numbers": reference,
                    "registration_numbers": registration,
                    "local_establishments": establishment,
                }
            )
    return output


def _remove_noise(container: Any) -> None:
    for node in container.select(
        "script, style, noscript, nav, footer, header, form, "
        "[aria-label='Breadcrumb'], .breadcrumb, .breadcrumbs, .article-info"
    ):
        node.decompose()


def parse_hsa_detail(html: str, fallback_title: str) -> tuple[str, str]:
    soup = BeautifulSoup(html or "", "lxml")
    title_node = soup.select_one("main h1") or soup.find("h1")
    title = clean_text(title_node.get_text(" ", strip=True) if title_node else fallback_title)
    main = soup.find("main")
    if main is None:
        return title, ""

    body_container = main.select_one("div.max-w-\\[47\\.8rem\\]") or main
    _remove_noise(body_container)
    if title_node:
        matching_h1 = body_container.find("h1")
        if matching_h1:
            matching_h1.decompose()
    body = clean_text(body_container.get_text("\n", strip=True))
    return title, body


def parse_mda_detail(html: str, fallback_title: str) -> tuple[str, str]:
    soup = BeautifulSoup(html or "", "lxml")
    title_node = soup.select_one(".article-details h1") or soup.find("h1")
    title = clean_text(title_node.get_text(" ", strip=True) if title_node else fallback_title)
    container = soup.select_one(".article-details")
    if container is None:
        return title, ""
    _remove_noise(container)
    heading = container.find("h1")
    if heading:
        heading.decompose()
    body = clean_text(container.get_text("\n", strip=True))
    if body == title:
        body = ""
    return title, body


def parse_thai_fda_detail(html: str, fallback_title: str) -> tuple[str, str, str]:
    """Parse the custom single-news layout used by the Thai FDA English site."""
    soup = BeautifulSoup(html or "", "lxml")
    root = soup.select_one(".single.single-news")
    if root is None:
        return fallback_title, "", ""
    title_node = root.select_one(".single__title")
    content = root.select_one(".single__content.ql-editor, .single__content")
    title = clean_text(title_node.get_text(" ", strip=True) if title_node else fallback_title)
    if content is None:
        return title, "", ""
    _remove_noise(content)
    body = clean_text(content.get_text("\n", strip=True))
    date_match = ENGLISH_DATE.search(
        clean_text(root.get_text(" ", strip=True))
    )
    published = date_match.group(0) if date_match else ""
    return title, body, published


def find_mda_document_url(html: str, base_url: str) -> str:
    """Return the same-domain public document/file URL linked by an MDA notice."""
    soup = BeautifulSoup(html or "", "lxml")
    container = soup.select_one(".article-details")
    if container is None:
        return ""
    allowed_host = urlparse(base_url).netloc.lower()
    for link in container.select('a[href*="/documents/"][href]'):
        url = normalize_url(base_url, str(link.get("href", "")))
        parsed = urlparse(url)
        if parsed.netloc.lower() != allowed_host:
            continue
        if not parsed.path.rstrip("/").endswith("/file"):
            url = url.rstrip("/") + "/file"
        return url
    return ""


LIST_PARSERS = {
    "sg_hsa_announcements": parse_hsa_list,
    "my_mda_announcements": parse_mda_list,
    "my_mda_mmdr": parse_mda_list,
}

DETAIL_PARSERS = {
    "sg_hsa_announcements": parse_hsa_detail,
    "my_mda_announcements": parse_mda_detail,
    "my_mda_mmdr": parse_mda_detail,
}
