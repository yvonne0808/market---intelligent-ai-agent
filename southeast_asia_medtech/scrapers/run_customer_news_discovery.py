from __future__ import annotations

import argparse
import json
import re
from datetime import date, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import quote_plus

import feedparser
import requests
from bs4 import BeautifulSoup
from googlenewsdecoder import new_decoderv1

from southeast_asia_medtech.config.config_loader import load_company_watchlist


MODULE_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = MODULE_DIR / "data" / "customer_discovery"
EVENT_TERMS = {
    "launch": 4, "introduces": 4, "approval": 5, "authorization": 5,
    "recall": 5, "safety": 3, "acquire": 5, "acquisition": 5, "sell": 4,
    "investment": 4, "factory": 5, "facility": 5, "manufacturing": 5,
    "production": 4, "capacity": 4, "expansion": 4, "export": 4,
    "distribution": 4, "partnership": 4, "agreement": 3,
    "commercial": 3, "sales": 2, "revenue": 2, "market access": 5,
}
EXCLUDE_TERMS = {
    "stock trades": 6, "price target": 6, "class action": 8, "law firm": 8,
    "shareholder alert": 8, "dividend": 5, "earnings call": 5,
    "conference call": 5, "to report results": 5, "appoints": 3,
    "appointed": 3, "retires": 3, "award": 2, " shares": 8,
    "stock a buy": 8, "investment case": 8, "how investors": 8,
    "cheap after": 8, "acquisitions by": 8, "obituary": 10,
    "independent director": 8, "head of investment": 8,
    "wealth management": 8, "fund management": 8,
    "employee stock purchase": 8, "regional performance": 5,
    "alcon silver": 10, "baxter fluorspar": 10, "martin ansell": 10,
    "fair value": 7, "investment story": 7,
}
GENERAL_MEDICAL_TERMS = ("medical", "healthcare", "medtech")
NON_MEDICAL_TERMS = (
    "fashion",
    "clothing",
    "festival",
    "retail collection",
    "apparel",
)
BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/138.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


def args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Discover monthly customer news.")
    parser.add_argument("--start-date", required=True)
    parser.add_argument("--end-date", required=True)
    parser.add_argument("--target-min", type=int, default=40)
    parser.add_argument("--target-max", type=int, default=400)
    parser.add_argument("--per-customer", type=int, default=10)
    parser.add_argument("--per-competitor", type=int, default=6)
    parser.add_argument("--fetch-top", type=int, default=60)
    parser.add_argument("--timeout", type=int, default=20)
    parser.add_argument(
        "--no-date-filter",
        action="store_true",
        help="Do not add date clauses or filter RSS entries by publication date.",
    )
    return parser.parse_args()


def score(title: str) -> int:
    lowered = title.casefold()
    return sum(weight for term, weight in EVENT_TERMS.items() if term in lowered) - sum(
        weight for term, weight in EXCLUDE_TERMS.items() if term in lowered
    )


def clean_title(title: str) -> tuple[str, str]:
    parts = [part.strip() for part in title.rsplit(" - ", 1)]
    return (parts[0], parts[1] if len(parts) == 2 else "")


def medical_terms_for(entity: dict) -> list[str]:
    terms = [
        *GENERAL_MEDICAL_TERMS,
        *(
            str(segment).replace("_", " ").strip()
            for segment in entity.get("product_segments", [])
        ),
    ]
    return list(dict.fromkeys(term for term in terms if term))


def has_medical_context(title: str, entity: dict) -> bool:
    # Positive medical context is enforced by the Google query, which can
    # match indexed page text that does not appear in the displayed headline.
    folded = title.casefold()
    return not any(term in folded for term in NON_MEDICAL_TERMS)


def build_news_query(
    entity: dict, start: date | None = None, end: date | None = None
) -> str:
    medical_query = " OR ".join(
        f'"{term}"' if " " in term else term for term in medical_terms_for(entity)
    )
    event_query = (
        "(launch OR approval OR authorization OR recall OR acquisition OR "
        "manufacturing OR facility OR distribution OR partnership OR expansion)"
    )
    query = f'"{entity["canonical_name"]}" ({medical_query}) {event_query}'
    if start is not None and end is not None:
        query += f" after:{start.isoformat()} before:{end.isoformat()}"
    return query


def published_in_range(published: str, start: date, end: date) -> bool:
    try:
        published_date = parsedate_to_datetime(published).date()
    except (TypeError, ValueError, OverflowError):
        return False
    return start <= published_date < end


def candidate_limit_for(entity: dict, options: argparse.Namespace) -> int:
    if entity.get("entity_type") == "customer":
        return options.per_customer
    return options.per_competitor


def configure_session(session: requests.Session) -> None:
    session.headers.update(BROWSER_HEADERS)


def extract_body(html: str) -> tuple[str, str]:
    soup = BeautifulSoup(html or "", "lxml")
    for node in soup.select("script, style, noscript, nav, footer, header, aside"):
        node.decompose()
    title_node = soup.select_one("main h1, article h1, h1")
    title = " ".join(title_node.get_text(" ", strip=True).split()) if title_node else ""
    container = soup.select_one(
        "article, main, .evergreen-news-body, .module_body, .article-content, "
        ".entry-content, .content, .field--name-body, .release-body, #content"
    )
    body = " ".join(container.get_text(" ", strip=True).split()) if container else ""
    return title, body


def discover_company(
    session: requests.Session,
    customer: dict,
    start: date,
    end: date,
    per_company: int,
    timeout: int,
    date_filter: bool = True,
) -> list[dict]:
    name = customer["canonical_name"]
    query = build_news_query(customer, start, end) if date_filter else build_news_query(customer)
    url = (
        "https://news.google.com/rss/search?q="
        f"{quote_plus(query)}&hl=en-US&gl=US&ceid=US:en"
    )
    feed = feedparser.parse(session.get(url, timeout=timeout).content)
    company_terms = [name, *customer.get("aliases", [])]
    candidates = []
    seen_titles: set[str] = set()
    for entry in feed.entries:
        published = str(entry.get("published", ""))
        if date_filter and not published_in_range(published, start, end):
            continue
        title, publisher = clean_title(str(entry.get("title", "")))
        folded = title.casefold()
        if title in seen_titles or not any(term.casefold() in folded for term in company_terms):
            continue
        if not has_medical_context(title, customer):
            continue
        event_score = score(title)
        if event_score <= 0:
            continue
        seen_titles.add(title)
        candidates.append(
            {
                "customer_id": customer.get("customer_id", ""),
                "competitor_id": customer.get("competitor_id", ""),
                "entity_type": customer.get("entity_type", "customer"),
                "company_name": name,
                "product_segments": customer.get("product_segments", []),
                "title": title,
                "publisher": publisher or entry.get("source", {}).get("title", ""),
                "published_date": published,
                "discovery_url": entry.get("link", ""),
                "event_score": event_score,
                "discovery_method": "google_news_rss_company_query",
            }
        )
    candidates.sort(key=lambda item: (-item["event_score"], item["published_date"]))
    return candidates[:per_company]


def main() -> int:
    options = args()
    start = date.fromisoformat(options.start_date)
    end = date.fromisoformat(options.end_date)
    valid_limits = (
        1 <= options.target_min <= options.target_max <= 1000
        and options.per_customer > 0
        and options.per_competitor > 0
        and options.fetch_top >= 0
    )
    if start > end or not valid_limits:
        raise ValueError("Invalid date range or candidate target")
    watchlist = load_company_watchlist()
    customers = [
        {**item, "entity_type": "customer"} for item in watchlist["customers"]
    ]
    approved_competitor_ids = {
        competitor["company_id"]
        for customer in watchlist["customers"]
        for competitor in customer.get("competitors", [])
        if competitor["company_id"] in watchlist["competitor_companies"]
    }
    customer_ids = {customer["customer_id"] for customer in watchlist["customers"]}
    approved_competitor_ids -= customer_ids
    competitors = [
        {
            "competitor_id": competitor_id,
            "canonical_name": watchlist["competitor_companies"][competitor_id][
                "canonical_name"
            ],
            "aliases": watchlist["competitor_companies"][competitor_id].get(
                "aliases", []
            ),
            "product_segments": [],
            "entity_type": "competitor",
        }
        for competitor_id in sorted(approved_competitor_ids)
    ]
    entities = customers + competitors
    session = requests.Session()
    configure_session(session)
    candidates: list[dict] = []
    for entity in entities:
        candidates.extend(
            discover_company(
                session,
                entity,
                start,
                end,
                candidate_limit_for(entity, options),
                options.timeout,
                date_filter=not options.no_date_filter,
            )
        )
    candidates.sort(key=lambda item: (-item["event_score"], item["company_name"]))
    candidates = candidates[: options.target_max]

    articles = []
    for item in candidates[: options.fetch_top]:
        record = dict(item)
        try:
            decoded = new_decoderv1(item["discovery_url"])
            if not decoded.get("status"):
                raise ValueError(str(decoded))
            original_url = decoded["decoded_url"]
            response = session.get(original_url, timeout=options.timeout)
            response.raise_for_status()
            extracted_title, body = extract_body(response.text)
            record.update(
                {
                    "url": response.url,
                    "title": extracted_title or item["title"],
                    "body": body,
                    "raw_text_length": len(body),
                    "scrape_status": "success" if len(body) >= 120 else "body_too_short",
                }
            )
        except Exception as exc:
            record.update(
                {
                    "url": "",
                    "body": "",
                    "raw_text_length": 0,
                    "scrape_status": "failed",
                    "error_message": f"{type(exc).__name__}: {exc}",
                }
            )
        articles.append(record)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = f"{start.isoformat()}_{end.isoformat()}"
    candidate_path = OUTPUT_DIR / f"candidates_{stamp}.json"
    article_path = OUTPUT_DIR / f"articles_{stamp}.json"
    candidate_path.write_text(
        json.dumps(candidates, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    article_path.write_text(
        json.dumps(articles, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    result = {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "candidate_count": len(candidates),
        "target_min": options.target_min,
        "target_max": options.target_max,
        "per_customer": options.per_customer,
        "per_competitor": options.per_competitor,
        "fetch_top": options.fetch_top,
        "date_filter": not options.no_date_filter,
        "full_text_attempts": len(articles),
        "full_text_success": sum(
            item.get("scrape_status") == "success" for item in articles
        ),
        "candidate_output": str(candidate_path),
        "article_output": str(article_path),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
