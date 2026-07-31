from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Any


MODULE_DIR = Path(__file__).resolve().parents[1]
FILTERED_DIR = MODULE_DIR / "data" / "filtered"
FILTERED_INPUT = FILTERED_DIR / "articles_filtered.json"
SCORED_INPUT = FILTERED_DIR / "articles_scored.json"
REPORTS_DIR = MODULE_DIR / "reports"
BUILDER_PATH = Path(__file__).resolve().with_name("build_excel.mjs")

EMPTY_SECTION = "No material updates identified during this reporting period."

SECTION_ORDER = [
    ("regulatory", "2. Regulatory and Approval Updates"),
    ("market", "3. Medical Device and Consumables Market Updates"),
    ("procurement", "4. Procurement and Commercialization"),
    ("manufacturing", "5. Manufacturing, Capacity and Supply Chain"),
    ("transactions", "6. Financing, M&A and Partnerships"),
    ("packaging", "7. Medical Device Packaging Signals"),
]

EVENT_PRIORITY = {
    "regulatory_registration": 0,
    "procurement_contract_award": 1,
    "manufacturing_capacity": 2,
    "export_market_access": 3,
    "distribution_supply_chain": 4,
    "corporate_transaction": 5,
    "commercialization_product_launch": 6,
    "medical_consumables": 7,
    "medical_device_packaging": 8,
}

SECTION_CATEGORY_MAP = {
    "regulatory": {"regulatory_registration", "export_market_access"},
    "market": {"medical_consumables", "commercialization_product_launch"},
    "procurement": {"procurement_contract_award"},
    "manufacturing": {"manufacturing_capacity", "distribution_supply_chain"},
    "transactions": {"corporate_transaction"},
    "packaging": {"medical_device_packaging"},
}

COUNTRY_NAMES = {"SG": "Singapore", "MY": "Malaysia"}
CORPORATE_PATTERNS = (
    re.compile(
        r"\b((?:[A-Z][A-Z0-9&.'()-]*\s+){1,6}"
        r"(?:SDN\.?\s+BHD\.?|PTE\.?\s+LTD\.?|LIMITED|LTD\.?|INC\.?|CORP\.?))\b"
    ),
    re.compile(
        r"\b((?:[A-Z][A-Za-z0-9&.'()-]*\s+){1,6}"
        r"(?:Pte\.?\s+Ltd\.?|Sdn\.?\s+Bhd\.?|Limited|Ltd\.?|Inc\.?|Corp\.?))\b"
    ),
)
LABELED_COMPANY_PATTERN = re.compile(
    r"(?:Local Company|Manufacturer|Company)\s*:\s*([^.;\n]{2,100})",
    flags=re.IGNORECASE,
)

PACKAGING_MATERIALS = {
    "Tyvek": ("tyvek",),
    "forming film": ("forming film", "thermoforming film"),
    "medical-grade coated paper": ("medical-grade coated paper", "medical grade coated paper"),
    "medical-grade paper": ("medical-grade paper", "medical grade paper"),
    "dialysis paper": ("dialysis paper",),
    "plastic film": ("plastic film",),
    "lidding material": ("lidding material", "lidding film", "lidding paper"),
    "sealing material": ("sealing material",),
}
PACKAGING_FORMATS = {
    "header bag": ("header bag",),
    "paper-plastic pouch": ("paper-plastic pouch", "paper plastic pouch"),
    "sterilization pouch": ("sterilization pouch", "sterilisation pouch"),
    "tubing bag": ("tubing bag",),
    "clean bag": ("clean bag",),
    "blister tray": ("blister tray",),
    "thermoformed tray": ("thermoformed tray",),
    "medical device tray": ("medical device tray",),
}
STERILIZATION_METHODS = {
    "EO sterilization": ("eo sterilization", "eto sterilization", "ethylene oxide sterilization"),
    "radiation sterilization": ("radiation sterilization", "gamma sterilization", "e-beam sterilization"),
    "steam sterilization": ("steam sterilization", "autoclave sterilization"),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate deterministic SEA MedTech monthly Markdown, JSON, and Excel."
    )
    parser.add_argument("--month", required=True, help="Reporting month in YYYY-MM.")
    parser.add_argument("--input", type=Path, default=FILTERED_INPUT)
    parser.add_argument("--scored-input", type=Path, default=SCORED_INPUT)
    return parser.parse_args()


def parse_month(value: str) -> tuple[int, int]:
    match = re.fullmatch(r"(20\d{2})-(0[1-9]|1[0-2])", value or "")
    if not match:
        raise ValueError("--month must use YYYY-MM")
    return int(match.group(1)), int(match.group(2))


def parse_article_date(value: str) -> date | None:
    value = (value or "").strip()
    for pattern in ("%Y-%m-%d", "%d %B %Y", "%d %b %Y"):
        try:
            return datetime.strptime(value, pattern).date()
        except ValueError:
            pass
    return None


def load_json_list(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"Expected JSON list: {path}")
    return [item for item in data if isinstance(item, dict)]


def filter_month(rows: list[dict[str, Any]], year: int, month: int) -> list[dict[str, Any]]:
    output = []
    for row in rows:
        published = parse_article_date(str(row.get("published_date", "")))
        if published and (published.year, published.month) == (year, month):
            output.append(row)
    return output


def article_sort_key(article: dict[str, Any]) -> tuple[int, int, int, int]:
    categories = effective_categories(article)
    event_rank = min(
        (EVENT_PRIORITY[category] for category in categories if category in EVENT_PRIORITY),
        default=99,
    )
    published = parse_article_date(str(article.get("published_date", "")))
    date_rank = -(published.toordinal() if published else 0)
    return (
        event_rank,
        -int(article.get("device_relevance_score", 0) or 0),
        -int(article.get("packaging_relevance_score", 0) or 0),
        date_rank,
    )


def extractive_placeholder(article: dict[str, Any], limit: int = 260) -> str:
    body = re.sub(r"\s+", " ", str(article.get("body", ""))).strip()
    if not body:
        return ""
    if len(body) <= limit:
        return body
    cut = body[:limit].rsplit(" ", 1)[0]
    return cut.rstrip(" ,;:") + "..."


def sections_for_article(article: dict[str, Any]) -> list[str]:
    categories = effective_categories(article)
    sections = [
        section
        for section, mapped_categories in SECTION_CATEGORY_MAP.items()
        if categories & mapped_categories
    ]
    if not sections:
        sections.append("market")
    return sections


def effective_categories(article: dict[str, Any]) -> set[str]:
    categories = set(article.get("business_categories", []))
    text = f"{article.get('title', '')} {article.get('body', '')}".casefold()
    if (
        "sebut harga" in text
        and ("yang berjaya" in text or "harga setuju terima" in text)
    ):
        categories.add("procurement_contract_award")
    return categories


def find_values(text: str, mapping: dict[str, tuple[str, ...]]) -> list[str]:
    lower = text.casefold()
    return [
        label
        for label, variants in mapping.items()
        if any(variant.casefold() in lower for variant in variants)
    ]


def packaging_details(article: dict[str, Any]) -> dict[str, str]:
    text = f"{article.get('title', '')} {article.get('body', '')}"
    lower = text.casefold()
    material = "; ".join(find_values(text, PACKAGING_MATERIALS))
    packaging_format = "; ".join(find_values(text, PACKAGING_FORMATS))
    sterilization = "; ".join(find_values(text, STERILIZATION_METHODS))
    sterile_barrier = ""
    if "sterile barrier system" in lower:
        sterile_barrier = "Sterile barrier system explicitly mentioned"
    elif "sterile barrier integrity" in lower:
        sterile_barrier = "Sterile barrier integrity explicitly mentioned"
    elif ("sterility" in lower or "sterile" in lower) and (
        "packaging" in lower or "package" in lower
    ):
        sterile_barrier = "Packaging sterility issue explicitly mentioned"
    iso_relevance = "ISO 11607 explicitly mentioned" if "iso 11607" in lower else ""
    return {
        "packaging_material": material,
        "packaging_format": packaging_format,
        "sterilization_method": sterilization,
        "sterile_barrier_relevance": sterile_barrier,
        "ISO_11607_relevance": iso_relevance,
        "possible_business_implication": "",
    }


def clean_company_name(value: str) -> str:
    value = re.sub(r"\s+", " ", value).strip(" ,.;:-")
    value = re.sub(
        r"^(?:PIHAK BERKUASA PERANTI PERUBATAN\s+)+",
        "",
        value,
        flags=re.IGNORECASE,
    )
    value = re.sub(r"\s+(?:Product Category|Batch No|Description of Issue).*$", "", value, flags=re.I)
    return value[:120]


def extract_companies(article: dict[str, Any]) -> list[str]:
    text = f"{article.get('title', '')}\n{article.get('body', '')}"
    names: list[str] = []
    for match in LABELED_COMPANY_PATTERN.finditer(text):
        names.append(clean_company_name(match.group(1)))
    for pattern in CORPORATE_PATTERNS:
        for match in pattern.finditer(text):
            names.append(clean_company_name(match.group(1)))
    excluded = {
        str(article.get("organization", "")).casefold(),
        "medical device authority",
        "health sciences authority",
    }
    return list(
        dict.fromkeys(
            name for name in names if name and name.casefold() not in excluded
        )
    )


def event_type(article: dict[str, Any]) -> str:
    categories = effective_categories(article)
    for category in EVENT_PRIORITY:
        if category in categories:
            return category
    return "general_market_update"


def build_company_rows(articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for article in articles:
        for company in extract_companies(article):
            key = (company.casefold(), str(article.get("country", "")))
            published = parse_article_date(str(article.get("published_date", "")))
            current = grouped.setdefault(
                key,
                {
                    "company_name": company,
                    "country": article.get("country", ""),
                    "event_types": set(),
                    "articles": [],
                    "packaging_relevance": 0,
                    "latest_update_date": "",
                    "_latest": None,
                },
            )
            current["event_types"].add(event_type(article))
            current["articles"].append(str(article.get("title", "")))
            current["packaging_relevance"] = max(
                current["packaging_relevance"],
                int(article.get("packaging_relevance_score", 0) or 0),
            )
            if published and (current["_latest"] is None or published > current["_latest"]):
                current["_latest"] = published
                current["latest_update_date"] = published.isoformat()

    output = []
    for value in grouped.values():
        output.append(
            {
                "company_name": value["company_name"],
                "country": value["country"],
                "event_type": "; ".join(sorted(value["event_types"])),
                "number_of_mentions": len(value["articles"]),
                "related_articles": " | ".join(dict.fromkeys(value["articles"])),
                "packaging_relevance": value["packaging_relevance"],
                "latest_update_date": value["latest_update_date"],
            }
        )
    return sorted(output, key=lambda item: (-item["number_of_mentions"], item["company_name"]))


def build_source_rows(scored_articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for article in scored_articles:
        key = (str(article.get("source_name", "")), str(article.get("country", "")))
        current = grouped.setdefault(
            key,
            {
                "source_name": article.get("source_name", ""),
                "country": article.get("country", ""),
                "organization": article.get("organization", ""),
                "number_of_articles": 0,
                "successful_scrapes": 0,
                "failed_scrapes": 0,
                "latest_article_date": "",
                "_latest": None,
            },
        )
        current["number_of_articles"] += 1
        if article.get("scrape_status") == "success":
            current["successful_scrapes"] += 1
        else:
            current["failed_scrapes"] += 1
        published = parse_article_date(str(article.get("published_date", "")))
        if published and (current["_latest"] is None or published > current["_latest"]):
            current["_latest"] = published
            current["latest_article_date"] = published.isoformat()
    output = []
    for value in grouped.values():
        value.pop("_latest", None)
        output.append(value)
    return sorted(output, key=lambda item: (item["country"], item["source_name"]))


def article_markdown(article: dict[str, Any]) -> str:
    categories = ", ".join(sorted(effective_categories(article))) or "general update"
    keywords = ", ".join(article.get("matched_keywords", [])) or "packaging rule match"
    placeholder = extractive_placeholder(article)
    lines = [
        f"- **[{article.get('title', '')}]({article.get('url', '')})**",
        (
            f"  - {article.get('published_date', '')} | {article.get('source_name', '')} | "
            f"Device score {article.get('device_relevance_score', 0)}/20 | "
            f"Packaging score {article.get('packaging_relevance_score', 0)}/10"
        ),
        f"  - Categories: {categories}. Matched signals: {keywords}.",
    ]
    if placeholder:
        lines.append(f"  - Source extract: {placeholder}")
    return "\n".join(lines)


def render_country_subsections(articles: list[dict[str, Any]]) -> list[str]:
    lines: list[str] = []
    for country_code in ("SG", "MY"):
        lines.append(f"### {COUNTRY_NAMES[country_code]}")
        country_articles = [item for item in articles if item.get("country") == country_code]
        if not country_articles:
            lines.append(EMPTY_SECTION)
        else:
            lines.extend(article_markdown(item) for item in sorted(country_articles, key=article_sort_key))
        lines.append("")
    return lines


def generate_markdown(
    month_value: str,
    articles: list[dict[str, Any]],
    companies: list[dict[str, Any]],
    sources: list[dict[str, Any]],
) -> str:
    section_articles: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for article in articles:
        for section in sections_for_article(article):
            section_articles[section].append(article)

    country_counts = {
        country: sum(item.get("country") == country for item in articles)
        for country in ("SG", "MY")
    }
    packaging_count = sum(
        int(item.get("packaging_relevance_score", 0) or 0) >= 5 for item in articles
    )
    lines = [
        "# Southeast Asia Medical Device Monthly Report",
        "",
        f"Reporting period: {month_value}",
        "",
        "## 1. Executive Summary",
        "",
        (
            f"This rule-based MVP includes {len(articles)} matched official-source articles: "
            f"{country_counts['SG']} from Singapore and {country_counts['MY']} from Malaysia. "
            f"{packaging_count} article(s) reached the packaging relevance threshold of 5."
        ),
        "",
        (
            "The report uses deterministic categories and source extracts only. "
            "No LLM-generated summary or inferred fact is included."
        ),
        "",
    ]

    for section, heading in SECTION_ORDER:
        lines.append(f"## {heading}")
        lines.append("")
        items = sorted(section_articles.get(section, []), key=article_sort_key)
        if section == "regulatory":
            lines.extend(render_country_subsections(items))
        elif not items:
            lines.extend([EMPTY_SECTION, ""])
        else:
            lines.extend(article_markdown(item) for item in items)
            lines.append("")

    lines.extend(["## 8. Key Companies to Watch", ""])
    if not companies:
        lines.extend([EMPTY_SECTION, ""])
    else:
        for company in companies:
            lines.append(
                f"- **{company['company_name']}** ({COUNTRY_NAMES.get(company['country'], company['country'])}) "
                f"— {company['event_type']}; {company['number_of_mentions']} article(s); "
                f"packaging relevance {company['packaging_relevance']}/10."
            )
        lines.append("")

    lines.extend(["## 9. Source List", ""])
    if not sources:
        lines.append(EMPTY_SECTION)
    else:
        for source in sources:
            lines.append(
                f"- {source['source_name']} ({COUNTRY_NAMES.get(source['country'], source['country'])}) "
                f"— {source['organization']}; {source['number_of_articles']} observed article(s), "
                f"{source['successful_scrapes']} successful and {source['failed_scrapes']} failed scrape(s)."
            )
    lines.append("")
    return "\n".join(lines)


def build_all_article_rows(month_value: str, articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output = []
    for article in sorted(articles, key=article_sort_key):
        output.append(
            {
                "month": month_value,
                "country": article.get("country", ""),
                "title": article.get("title", ""),
                "source": article.get("source_name", ""),
                "published_date": (
                    parse_article_date(str(article.get("published_date", ""))).isoformat()
                    if parse_article_date(str(article.get("published_date", "")))
                    else ""
                ),
                "business_categories": "; ".join(sorted(effective_categories(article))),
                "device_relevance_score": article.get("device_relevance_score", 0),
                "packaging_relevance_score": article.get("packaging_relevance_score", 0),
                "priority_level": article.get("priority_level", ""),
                "matched_keywords": "; ".join(article.get("matched_keywords", [])),
                "summary_placeholder": extractive_placeholder(article),
                "url": article.get("url", ""),
            }
        )
    return output


def build_packaging_rows(month_value: str, articles: list[dict[str, Any]], threshold: int) -> list[dict[str, Any]]:
    output = []
    for article in sorted(articles, key=article_sort_key):
        if int(article.get("packaging_relevance_score", 0) or 0) < threshold:
            continue
        row = build_all_article_rows(month_value, [article])[0]
        row.update(packaging_details(article))
        output.append(row)
    return output


def run_excel_builder(payload_path: Path, xlsx_path: Path, qa_dir: Path) -> None:
    node_executable = Path(
        os.environ.get(
            "CODEX_NODE_EXECUTABLE",
            str(Path.home() / ".cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node"),
        )
    )
    node_modules = Path(
        os.environ.get(
            "CODEX_NODE_MODULES",
            str(Path.home() / ".cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules"),
        )
    )
    if not node_executable.exists() or not node_modules.exists():
        raise RuntimeError(
            "Bundled artifact-tool runtime not found. Set CODEX_NODE_EXECUTABLE and "
            "CODEX_NODE_MODULES to the workspace dependency paths."
        )

    runtime_dir = MODULE_DIR / "tmp" / "step5_artifact_runtime"
    if runtime_dir.exists():
        shutil.rmtree(runtime_dir)
    runtime_dir.mkdir(parents=True)
    shutil.copy2(BUILDER_PATH, runtime_dir / "build_excel.mjs")
    (runtime_dir / "node_modules").symlink_to(node_modules, target_is_directory=True)
    try:
        subprocess.run(
            [
                str(node_executable),
                str(runtime_dir / "build_excel.mjs"),
                str(payload_path),
                str(xlsx_path),
                str(qa_dir),
            ],
            cwd=runtime_dir,
            check=True,
        )
        xlsx_path.with_suffix(xlsx_path.suffix + ".inspect.ndjson").unlink(missing_ok=True)
    finally:
        shutil.rmtree(runtime_dir, ignore_errors=True)


def run(month_value: str, input_path: Path, scored_path: Path) -> dict[str, Any]:
    year, month = parse_month(month_value)
    articles = filter_month(load_json_list(input_path), year, month)
    scored = filter_month(load_json_list(scored_path), year, month)
    articles.sort(key=article_sort_key)
    companies = build_company_rows(articles)
    sources = build_source_rows(scored)
    packaging_threshold = 5
    packaging_rows = build_packaging_rows(month_value, articles, packaging_threshold)

    output_dir = REPORTS_DIR / month_value
    output_dir.mkdir(parents=True, exist_ok=True)
    markdown_path = output_dir / "southeast_asia_medtech_monthly_report.md"
    xlsx_path = output_dir / "southeast_asia_medtech_articles.xlsx"
    summary_path = output_dir / "report_summary.json"
    payload_path = MODULE_DIR / "tmp" / f"step5_workbook_payload_{month_value}.json"
    qa_dir = MODULE_DIR / "tmp" / f"step5_qa_{month_value}"
    payload_path.parent.mkdir(parents=True, exist_ok=True)
    qa_dir.mkdir(parents=True, exist_ok=True)

    markdown = generate_markdown(month_value, articles, companies, sources)
    markdown_path.write_text(markdown, encoding="utf-8")
    summary = {
        "report_type": "Southeast Asia Medical Device Monthly Report MVP",
        "month": month_value,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "llm_used": False,
        "packaging_threshold": packaging_threshold,
        "article_count": len(articles),
        "packaging_relevant_count": len(packaging_rows),
        "company_count": len(companies),
        "source_count": len(sources),
        "country_counts": {
            code: sum(item.get("country") == code for item in articles)
            for code in ("SG", "MY")
        },
        "section_counts": {
            section: sum(section in sections_for_article(item) for item in articles)
            for section, _heading in SECTION_ORDER
        },
        "outputs": {
            "markdown": str(markdown_path),
            "excel": str(xlsx_path),
            "summary_json": str(summary_path),
        },
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    payload = {
        "month": month_value,
        "packaging_threshold": packaging_threshold,
        "all_articles": build_all_article_rows(month_value, articles),
        "packaging_articles": packaging_rows,
        "companies": companies,
        "sources": sources,
    }
    payload_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        run_excel_builder(payload_path, xlsx_path, qa_dir)
    finally:
        payload_path.unlink(missing_ok=True)
    return {**summary, "qa_dir": str(qa_dir)}


def main() -> int:
    args = parse_args()
    summary = run(
        args.month,
        args.input.expanduser().resolve(),
        args.scored_input.expanduser().resolve(),
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
