from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any

import requests

from southeast_asia_medtech.config.config_loader import load_company_watchlist


MODULE_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = MODULE_DIR.parent
PROMPT_PATH = MODULE_DIR / "prompts" / "website_article_analysis_prompt.txt"
PROMPT_VERSION = "sea-medtech-website-v4-global-customer-priority"
DEFAULT_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-chat"

REQUIRED_FIELDS = {
    "article_id", "title", "source_name", "country", "source_country_tag",
    "report_countries", "organization", "source_type", "published_date", "url",
    "language", "include_in_monthly_report", "relevance_score", "importance_level",
    "primary_category", "secondary_categories", "summary_cn", "key_points",
    "companies", "medical_devices", "medical_consumables", "device_categories",
    "regulatory_events", "procurement_events", "manufacturing_events",
    "export_and_market_access_events", "financing_and_ma_events",
    "partnership_events", "market_implication_cn", "packaging_relevance_score",
    "packaging_relevance", "packaging_relevance_reason", "packaging_forms",
    "packaging_materials", "sterilization_methods", "packaging_signals",
    "risks_or_uncertainties", "source_confidence", "why_it_matters",
    "one_sentence_takeaway",
    "customer_relevance", "matched_customers", "related_customer_groups",
    "competitor_companies", "competitive_relationship", "customer_impact_cn",
}
ARRAY_FIELDS = {
    "report_countries", "secondary_categories", "key_points", "companies",
    "medical_devices", "medical_consumables", "device_categories",
    "regulatory_events", "procurement_events", "manufacturing_events",
    "export_and_market_access_events", "financing_and_ma_events",
    "partnership_events", "packaging_forms", "packaging_materials",
    "sterilization_methods", "packaging_signals", "risks_or_uncertainties",
    "matched_customers", "related_customer_groups", "competitor_companies",
}
COUNTRIES = {"Singapore", "Malaysia", "Thailand", "Indonesia", "Vietnam", "Philippines"}
CUSTOMER_RELEVANCE_VALUES = {
    "direct_customer", "competitor", "potential_customer_or_partner",
    "industry_only", "none",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze SEA MedTech website articles with DeepSeek.")
    parser.add_argument("--month", required=True, help="Month in YYYY-MM format.")
    parser.add_argument("--input", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--errors", type=Path)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--sleep", type=float, default=0.25)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def load_env() -> None:
    path = PROJECT_DIR / ".env"
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def config() -> dict[str, str]:
    load_env()
    key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if not key or key == "your_deepseek_api_key_here":
        raise RuntimeError("DEEPSEEK_API_KEY is not configured.")
    return {
        "api_key": key,
        "base_url": os.environ.get("DEEPSEEK_BASE_URL", DEFAULT_BASE_URL).rstrip("/"),
        "model": os.environ.get("DEEPSEEK_MODEL", DEFAULT_MODEL).strip(),
    }


def read_list(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    value = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(value, dict) and isinstance(value.get("records"), list):
        value = value["records"]
    if not isinstance(value, list):
        raise ValueError(f"{path} must contain a JSON list or a records array")
    return [item for item in value if isinstance(item, dict)]


def normalize_article(article: dict[str, Any]) -> dict[str, Any]:
    """Fill stable source metadata for customer-discovery records."""
    normalized = dict(article)
    url = str(normalized.get("url") or normalized.get("discovery_url") or "")
    if not normalized.get("article_id"):
        digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:20]
        normalized["article_id"] = f"customer_discovery_{digest}"
    company = str(
        normalized.get("company_name") or normalized.get("organization") or ""
    )
    normalized.setdefault(
        "source_name",
        normalized.get("publisher") or normalized.get("organization")
        or "Customer news discovery",
    )
    normalized.setdefault("country", "GLOBAL")
    normalized.setdefault("source_country_tag", normalized["country"])
    normalized.setdefault("organization", company)
    normalized.setdefault("source_type", "customer_competitor_news_discovery")
    normalized.setdefault("language", "en")
    normalized.setdefault("body", "")
    normalized.setdefault("url", url)
    return normalized


def save(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def extract_json(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.removeprefix("```json").removeprefix("```").strip()
        cleaned = cleaned.removesuffix("```").strip()
    value = json.loads(cleaned)
    if not isinstance(value, dict):
        raise ValueError("DeepSeek response must be a JSON object")
    return value


def validate(
    result: dict[str, Any],
    article: dict[str, Any],
    canonical_customers: set[str],
) -> dict[str, Any]:
    missing = sorted(REQUIRED_FIELDS - result.keys())
    if missing:
        raise ValueError(f"Missing response fields: {', '.join(missing)}")
    if not isinstance(result["relevance_score"], int) or not 0 <= result["relevance_score"] <= 20:
        raise ValueError("relevance_score must be an integer from 0 to 20")
    if not isinstance(result["packaging_relevance_score"], int) or not 0 <= result["packaging_relevance_score"] <= 5:
        raise ValueError("packaging_relevance_score must be an integer from 0 to 5")
    if not isinstance(result["include_in_monthly_report"], bool):
        raise ValueError("include_in_monthly_report must be boolean")
    if result["importance_level"] not in {"high", "medium", "low"}:
        raise ValueError("Invalid importance_level")
    if result["packaging_relevance"] not in {"high", "medium", "low", "none"}:
        raise ValueError("Invalid packaging_relevance")
    if result["source_confidence"] not in {"high", "medium", "low"}:
        raise ValueError("Invalid source_confidence")
    if result["customer_relevance"] not in CUSTOMER_RELEVANCE_VALUES:
        raise ValueError("Invalid customer_relevance")
    for field in ARRAY_FIELDS:
        if not isinstance(result[field], list):
            raise ValueError(f"{field} must be an array")
    result["report_countries"] = [
        country for country in result["report_countries"] if country in COUNTRIES
    ]
    for field in ("matched_customers", "related_customer_groups"):
        invalid = set(result[field]) - canonical_customers
        if invalid:
            raise ValueError(
                f"{field} contains non-canonical customer names: {sorted(invalid)}"
            )
    for field in (
        "article_id", "title", "source_name", "country", "organization",
        "source_type", "published_date", "url", "language",
    ):
        result[field] = article.get(field, result.get(field, ""))
    result["source_country_tag"] = article.get("country", "")
    result["_analysis_meta"] = {
        "provider": "deepseek",
        "prompt_version": PROMPT_VERSION,
        "analyzed_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    return result


def call_api(
    cfg: dict[str, str],
    prompt: str,
    article: dict[str, Any],
    retries: int,
    canonical_customers: set[str],
) -> dict[str, Any]:
    payload = {
        "model": cfg["model"],
        "messages": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": json.dumps(article, ensure_ascii=False)},
        ],
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
    }
    headers = {"Authorization": f"Bearer {cfg['api_key']}", "Content-Type": "application/json"}
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            response = requests.post(
                f"{cfg['base_url']}/chat/completions",
                headers=headers,
                json=payload,
                timeout=120,
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            return validate(extract_json(content), article, canonical_customers)
        except Exception as exc:  # keep the rest of the paid batch resumable
            last_error = exc
            if attempt < retries:
                time.sleep(2**attempt)
    raise RuntimeError(f"DeepSeek failed after {retries} attempts: {last_error}")


def main() -> int:
    args = parse_args()
    input_path = args.input or MODULE_DIR / "data" / "filtered" / args.month / "articles_llm_ready.json"
    output_path = args.output or MODULE_DIR / "data" / "analyzed" / args.month / "articles_analyzed.json"
    errors_path = args.errors or MODULE_DIR / "data" / "analyzed" / args.month / "analysis_errors.json"
    jobs = read_list(input_path)
    articles = [job.get("article", job) for job in jobs]
    articles = [
        normalize_article(article)
        for article in articles
        if isinstance(article, dict)
    ]
    existing = read_list(output_path)
    completed = {
        item.get("article_id"): item for item in existing
        if item.get("article_id") and item.get("_analysis_meta", {}).get("prompt_version") == PROMPT_VERSION
    }
    pending = [
        article for article in articles
        if args.force or article.get("article_id") not in completed
    ]
    if args.limit:
        pending = pending[:args.limit]
    cfg = config()
    prompt = PROMPT_PATH.read_text(encoding="utf-8")
    watchlist = load_company_watchlist()
    canonical_customers = {
        customer["canonical_name"] for customer in watchlist["customers"]
    }
    prompt = (
        f"{prompt}\n\n十一、运行时客户与竞争对手配置\n"
        "以下 YAML 配置是本次分析允许使用的客户别名、产品线和竞争关系依据。"
        "若配置与文章事实冲突，以文章事实为准；没有共享竞争维度时不得标记 competitor。\n\n"
        f"{json.dumps(watchlist, ensure_ascii=False, separators=(',', ':'))}"
    )
    errors = read_list(errors_path)
    print(f"DeepSeek SEA MedTech analysis: pending={len(pending)} cached={len(completed)} model={cfg['model']}", flush=True)
    failed = 0
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        future_map = {}
        for article in pending:
            future_map[
                executor.submit(
                    call_api,
                    cfg,
                    prompt,
                    article,
                    args.retries,
                    canonical_customers,
                )
            ] = article
            if args.sleep:
                time.sleep(args.sleep)
        for index, future in enumerate(as_completed(future_map), 1):
            article = future_map[future]
            article_id = article.get("article_id", "")
            try:
                result = future.result()
                completed[article_id] = result
                save(output_path, sorted(completed.values(), key=lambda x: x.get("published_date", ""), reverse=True))
                print(f"[{index}/{len(pending)}] saved {article_id} score={result['relevance_score']}", flush=True)
            except Exception as exc:
                failed += 1
                errors.append({
                    "article_id": article_id,
                    "title": article.get("title", ""),
                    "error": str(exc),
                    "failed_at": datetime.now().astimezone().isoformat(timespec="seconds"),
                })
                save(errors_path, errors)
                print(f"[{index}/{len(pending)}] failed {article_id}: {exc}", file=sys.stderr, flush=True)
    manifest = {
        "month": args.month,
        "prompt_version": PROMPT_VERSION,
        "watchlist_schema_version": watchlist.get("schema_version", ""),
        "model": cfg["model"],
        "input_articles": len(articles),
        "analyzed_articles": len(completed),
        "failed_this_run": failed,
        "api_called": bool(pending),
        "updated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    save(output_path.with_name("analysis_manifest.json"), manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2), flush=True)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
