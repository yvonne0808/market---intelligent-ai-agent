from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from southeast_asia_medtech.config.config_loader import load_keywords


MODULE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = MODULE_DIR / "data" / "normalized" / "articles_normalized.json"
OUTPUT_DIR = MODULE_DIR / "data" / "filtered"
SCORED_OUTPUT = OUTPUT_DIR / "articles_scored.json"
FILTERED_OUTPUT = OUTPUT_DIR / "articles_filtered.json"

TRACKING_PARAMETERS = {
    "fbclid",
    "gclid",
    "mc_cid",
    "mc_eid",
    "ref",
    "source",
    "utm_campaign",
    "utm_content",
    "utm_medium",
    "utm_source",
    "utm_term",
}

BUSINESS_CATEGORY_RULES: dict[str, set[str]] = {
    "regulatory_registration": {
        "registration",
        "approval",
        "market authorization",
        "overseas registration",
        "FDA",
        "CE",
        "MDR",
        "clinical trial",
    },
    "commercialization_product_launch": {"commercialization"},
    "procurement_contract_award": {"procurement", "tender", "contract award"},
    "manufacturing_capacity": {
        "localization",
        "local manufacturing",
        "production line",
        "capacity expansion",
        "manufacturing facility",
    },
    "export_market_access": {"export", "overseas registration", "FDA", "CE", "MDR"},
    "corporate_transaction": {"financing", "acquisition", "BD cooperation"},
    "distribution_supply_chain": {"distributor", "channel partnership", "supply chain"},
    "medical_consumables": {
        "medical consumables",
        "disposable medical products",
        "high-value medical consumables",
        "low-value medical consumables",
    },
}

HIGH_VALUE_GROUPS: list[tuple[str, tuple[str, ...], int]] = [
    (
        "registration_or_approval",
        (
            "registration",
            "re-registration",
            "approval",
            "market authorization",
            "product classification",
            "regulatory update",
        ),
        5,
    ),
    (
        "new_product_launch",
        ("new product", "product launch", "market launch", "launched", "commercialization"),
        4,
    ),
    (
        "procurement_or_award",
        ("procurement", "tender", "contract award", "successful bidder", "awarded contract"),
        5,
    ),
    (
        "factory_or_expansion",
        (
            "new factory",
            "new plant",
            "manufacturing facility",
            "production line",
            "capacity expansion",
            "local manufacturing",
        ),
        5,
    ),
    (
        "export_or_overseas_certification",
        ("export", "overseas registration", "foreign registration", "ce mark", "fda clearance"),
        4,
    ),
    (
        "transaction_or_bd",
        ("acquisition", "financing", "funding", "bd cooperation", "strategic cooperation"),
        4,
    ),
    (
        "channel_or_supply_chain",
        ("distributor", "channel partnership", "distribution partnership", "supply chain"),
        4,
    ),
    (
        "sterile_single_use_device",
        (
            "single-use medical",
            "single use medical",
            "disposable medical",
            "sterile medical device",
            "sterile medical consumable",
        ),
        5,
    ),
]

NEGATIVE_RULES: list[tuple[str, tuple[str, ...], int]] = [
    ("recruitment", ("job vacancy", "career opportunity", "recruitment", "jawatan kosong"), 12),
    (
        "training_or_event",
        (
            "training calendar",
            "register here",
            "registration open until",
            "training on",
            "workshop invitation",
            "conference invitation",
            "webinar invitation",
        ),
        8,
    ),
    ("brand_only", ("brand campaign", "brand ambassador", "celebrating our brand"), 6),
    (
        "patient_education",
        ("patient education", "consumer safety article", "for patients", "health tips"),
        7,
    ),
    (
        "pharma_only",
        ("therapeutic product", "pharmaceutical", "medicine recall", "drug approval"),
        8,
    ),
]

PACKAGING_HIGH = {
    "header bag",
    "forming film",
    "medical-grade coated paper",
    "Tyvek",
    "medical-grade paper",
    "dialysis paper",
    "paper-plastic pouch",
    "sterilization pouch",
    "blister tray",
    "thermoformed tray",
    "medical device tray",
    "sterile barrier system",
    "packaging seal integrity",
    "sterile barrier integrity",
    "packaging validation",
    "ISO 11607",
}
PACKAGING_MEDIUM = {
    "tubing bag",
    "clean bag",
    "sterile packaging",
    "medical device packaging",
    "EO sterilization",
    "ethylene oxide sterilization",
    "radiation sterilization",
    "steam sterilization",
    "sterilization compatibility",
    "cleanroom packaging",
}
PACKAGING_LOW = {
    "coated paper",
    "plastic film",
    "lidding material",
    "sealing material",
    "protective packaging",
}

REGION_TERMS = {
    "singapore",
    "malaysia",
    "southeast asia",
    "south east asia",
    "asean",
    "indonesia",
    "thailand",
    "vietnam",
    "philippines",
}


@dataclass(frozen=True)
class KeywordDefinition:
    keyword: str
    synonyms: tuple[str, ...]
    weight: int
    language: str
    category: str


def normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def normalized_title(value: str) -> str:
    value = normalize_space(value).casefold()
    value = re.sub(r"[^\w\s]", " ", value, flags=re.UNICODE)
    return normalize_space(value)


def normalized_url(value: str) -> str:
    parsed = urlparse((value or "").strip())
    query = [
        (key, item)
        for key, item in parse_qsl(parsed.query, keep_blank_values=True)
        if key.casefold() not in TRACKING_PARAMETERS
    ]
    path = re.sub(r"/{2,}", "/", parsed.path).rstrip("/") or "/"
    return urlunparse(
        (
            parsed.scheme.casefold(),
            parsed.netloc.casefold(),
            path,
            "",
            urlencode(sorted(query)),
            "",
        )
    )


def normalized_content(value: str) -> str:
    value = normalize_space(value).casefold()
    return re.sub(r"[^\w\s]", "", value, flags=re.UNICODE)


def content_fingerprint(value: str) -> str:
    normalized = normalized_content(value)
    if len(normalized) < 80:
        return ""
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def load_keyword_definitions() -> list[KeywordDefinition]:
    config = load_keywords()
    definitions: list[KeywordDefinition] = []
    for category in config["categories"]:
        category_name = str(category["category"])
        for entry in category["keywords"]:
            definitions.append(
                KeywordDefinition(
                    keyword=str(entry["keyword"]),
                    synonyms=tuple(str(item) for item in entry.get("synonyms", [])),
                    weight=int(entry["weight"]),
                    language=str(entry["language"]),
                    category=category_name,
                )
            )
    return definitions


def phrase_present(text: str, phrase: str) -> bool:
    phrase = normalize_space(phrase).casefold()
    if not phrase:
        return False
    if re.fullmatch(r"[a-z0-9]+", phrase):
        return re.search(rf"\b{re.escape(phrase)}\b", text) is not None
    return phrase in text


def match_keywords(
    article: dict[str, Any],
    definitions: list[KeywordDefinition],
) -> tuple[list[str], set[str], set[str]]:
    title = normalize_space(str(article.get("title", ""))).casefold()
    body = normalize_space(str(article.get("body", ""))).casefold()
    combined = f"{title} {body}"
    matched: list[str] = []
    matched_in_title: set[str] = set()
    keyword_categories: set[str] = set()
    for definition in definitions:
        variants = (definition.keyword, *definition.synonyms)
        if any(phrase_present(combined, variant) for variant in variants):
            matched.append(definition.keyword)
            keyword_categories.add(definition.category)
            if any(phrase_present(title, variant) for variant in variants):
                matched_in_title.add(definition.keyword)
    return matched, matched_in_title, keyword_categories


def calculate_packaging_score(matched_keywords: list[str], text: str) -> int:
    matched = set(matched_keywords)
    score = 0
    high_count = len(matched & PACKAGING_HIGH)
    medium_count = len(matched & PACKAGING_MEDIUM)
    low_count = len(matched & PACKAGING_LOW)
    if high_count:
        score += 6 + min(2, high_count - 1) * 2
    if medium_count:
        score += 4 + min(1, medium_count - 1)
    if low_count:
        score += min(2, low_count)
    if (
        "sterility" in text
        and ("packaging" in text or "package" in text)
        and score < 5
    ):
        score = 5
    return min(10, score)


def calculate_device_score(
    article: dict[str, Any],
    matched_keywords: list[str],
    matched_in_title: set[str],
    packaging_score: int,
) -> tuple[int, list[str], list[str]]:
    title = normalize_space(str(article.get("title", ""))).casefold()
    body = normalize_space(str(article.get("body", ""))).casefold()
    text = f"{title} {body}"
    reasons: list[str] = []
    high_value_categories: list[str] = []

    score = 0
    core_terms = {
        "medical device",
        "medical equipment",
        "medical consumables",
        "disposable medical products",
        "high-value medical consumables",
        "low-value medical consumables",
    }
    core_hits = core_terms & set(matched_keywords)
    if core_hits:
        score += min(6, 4 + len(core_hits))
        reasons.append("medical-device terminology matched")
    if core_hits & matched_in_title:
        score += 2
        reasons.append("device term appears in title")

    for name, phrases, points in HIGH_VALUE_GROUPS:
        if any(phrase_present(text, phrase) for phrase in phrases):
            score += points
            high_value_categories.append(name)
            reasons.append(name.replace("_", " "))

    if article.get("country") in {"SG", "MY"} or any(term in text for term in REGION_TERMS):
        score += 4
        reasons.append("Southeast Asia official-source context")

    if packaging_score >= 7:
        score += 5
        reasons.append("specific medical packaging evidence")
    elif packaging_score >= 4:
        score += 3
        reasons.append("sterile/packaging evidence")

    for name, phrases, penalty in NEGATIVE_RULES:
        if any(phrase_present(text, phrase) for phrase in phrases):
            score -= penalty
            reasons.append(f"lowered: {name.replace('_', ' ')}")

    if not str(article.get("scrape_status", "")).startswith("success"):
        return 0, reasons + ["excluded: scrape failed or body unavailable"], high_value_categories
    if len(body) < 80:
        return 0, reasons + ["excluded: body too short"], high_value_categories
    return max(0, min(20, score)), reasons, high_value_categories


def business_categories(
    matched_keywords: list[str],
    high_value_categories: list[str],
    packaging_score: int,
) -> list[str]:
    matched = set(matched_keywords)
    output = [
        category
        for category, terms in BUSINESS_CATEGORY_RULES.items()
        if matched & terms
    ]
    if packaging_score:
        output.append("medical_device_packaging")
    if "new_product_launch" in high_value_categories:
        output.append("commercialization_product_launch")
    return sorted(set(output))


def score_article(
    article: dict[str, Any],
    definitions: list[KeywordDefinition],
) -> dict[str, Any]:
    result = dict(article)
    matched, matched_in_title, _keyword_categories = match_keywords(article, definitions)
    text = (
        f"{normalize_space(str(article.get('title', '')))} "
        f"{normalize_space(str(article.get('body', '')))}"
    ).casefold()
    packaging_score = calculate_packaging_score(matched, text)
    device_score, reasons, high_value_categories = calculate_device_score(
        article, matched, matched_in_title, packaging_score
    )
    categories = business_categories(matched, high_value_categories, packaging_score)

    negative_exclusion = any(reason.startswith("lowered:") for reason in reasons)
    valid_body = str(article.get("scrape_status", "")).startswith("success") and len(
        str(article.get("body", ""))
    ) >= 80
    include = valid_body and (
        (bool(matched) and not negative_exclusion) or packaging_score >= 5
    )
    if include and (device_score >= 16 or packaging_score >= 7):
        priority = "high"
    elif include:
        priority = "matched"
    else:
        priority = "excluded"

    if not matched:
        reasons.append("no configured keyword matched")
    result.update(
        {
            "matched_keywords": matched,
            "business_categories": categories,
            "device_relevance_score": device_score,
            "packaging_relevance_score": packaging_score,
            "priority_level": priority,
            "filter_reason": "; ".join(dict.fromkeys(reasons)),
            "include_in_llm_analysis": include,
            "duplicate_of": "",
            "duplicate_reason": "",
        }
    )
    return result


def date_quality(value: str) -> int:
    value = normalize_space(value)
    for pattern, quality in (
        (r"\d{4}-\d{2}-\d{2}", 3),
        (r"\d{1,2}\s+[A-Za-z]+\s+\d{4}", 3),
        (r"[A-Za-z]+\s+\d{4}", 2),
        (r"\d{4}", 1),
    ):
        if re.search(pattern, value):
            return quality
    return 0


def official_source_rank(article: dict[str, Any]) -> int:
    return 1 if article.get("source_type") in {"regulator", "government"} else 0


def preferred_record(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    def rank(article: dict[str, Any]) -> tuple[int, int, int, int]:
        return (
            official_source_rank(article),
            1 if str(article.get("scrape_status", "")).startswith("success") else 0,
            len(str(article.get("body", ""))),
            date_quality(str(article.get("published_date", ""))),
        )

    return right if rank(right) > rank(left) else left


def duplicate_reason(left: dict[str, Any], right: dict[str, Any]) -> str:
    if normalized_url(str(left.get("url", ""))) == normalized_url(str(right.get("url", ""))):
        return "exact_url"
    left_fingerprint = content_fingerprint(str(left.get("body", "")))
    right_fingerprint = content_fingerprint(str(right.get("body", "")))
    if left_fingerprint and left_fingerprint == right_fingerprint:
        return "exact_content"
    left_title = normalized_title(str(left.get("title", "")))
    right_title = normalized_title(str(right.get("title", "")))
    if left_title and right_title:
        similarity = SequenceMatcher(None, left_title, right_title).ratio()
        if left_title == right_title or similarity >= 0.92:
            return f"similar_title:{similarity:.3f}"
    return ""


def deduplicate(
    scored_articles: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    kept: list[dict[str, Any]] = []
    review = [dict(article) for article in scored_articles]

    for article in review:
        match_index = -1
        reason = ""
        for index, candidate in enumerate(kept):
            reason = duplicate_reason(article, candidate)
            if reason:
                match_index = index
                break
        if match_index < 0:
            kept.append(article)
            continue

        candidate = kept[match_index]
        winner = preferred_record(candidate, article)
        loser = article if winner is candidate else candidate
        loser["duplicate_of"] = str(winner.get("article_id", ""))
        loser["duplicate_reason"] = reason
        loser["include_in_llm_analysis"] = False
        loser["priority_level"] = "duplicate"
        loser["filter_reason"] = (
            f"{loser.get('filter_reason', '')}; excluded duplicate: {reason}"
        ).strip("; ")
        if winner is article:
            kept[match_index] = article

    return kept, review


def write_json(path: Path, data: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporary.replace(path)


def load_normalized(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"Input must be a JSON list: {path}")
    return [item for item in data if isinstance(item, dict)]


def run_filter(input_path: Path = DEFAULT_INPUT, output_dir: Path = OUTPUT_DIR) -> dict[str, Any]:
    articles = load_normalized(input_path)
    definitions = load_keyword_definitions()
    scored = [score_article(article, definitions) for article in articles]
    deduplicated, review = deduplicate(scored)
    filtered_articles = [
        article for article in deduplicated if article.get("include_in_llm_analysis") is True
    ]
    scored_output = output_dir / "articles_scored.json"
    filtered_output = output_dir / "articles_filtered.json"
    write_json(scored_output, review)
    write_json(filtered_output, filtered_articles)
    return {
        "input_articles": len(articles),
        "unique_articles": len(deduplicated),
        "duplicates_removed": len(articles) - len(deduplicated),
        "high": sum(item["priority_level"] == "high" for item in deduplicated),
        "matched": sum(item["priority_level"] == "matched" for item in deduplicated),
        "excluded": sum(item["priority_level"] == "excluded" for item in deduplicated),
        "filtered_articles": len(filtered_articles),
        "llm_candidates": len(filtered_articles),
        "scored_output": str(scored_output),
        "filtered_output": str(filtered_output),
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Rule-filter normalized SEA MedTech articles.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = run_filter(
        args.input.expanduser().resolve(),
        args.output_dir.expanduser().resolve(),
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
