from __future__ import annotations

import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from analyze_articles import (
    PROJECT_DIR,
    call_deepseek,
    filter_articles,
    get_article_text,
    load_deepseek_config,
    load_json_list,
    load_source_priorities,
    prioritize_articles,
    save_json_list,
)


INPUT_PATH = PROJECT_DIR / "data" / "llm_ready" / "Medical Device" / "articles_llm_ready_2026_07.json"
OUTPUT_PATH = PROJECT_DIR / "data" / "analyzed" / "Medical Device" / "articles_analyzed_2026_07.json"
PROMPT_PATH = PROJECT_DIR / "prompts" / "Medical Device" / "medical_device_article_analysis_prompt.txt"
AMCOR_CONTEXT_PATH = PROJECT_DIR / "prompts" / "amcor_apac_context.txt"

ANALYSIS_FIELDS = [
    "article_id", "title", "source_name", "published", "link",
    "include_in_weekly_report", "relevance_score", "importance_level",
    "primary_category", "secondary_categories", "summary_cn", "key_points",
    "companies", "medical_devices", "medical_consumables", "device_categories",
    "regulatory_approvals", "clinical_or_regulatory_stage",
    "tender_or_procurement_events", "deal_amounts", "production_capacity_events",
    "overseas_expansion_events", "market_implication_cn", "amcor_relevance_score",
    "amcor_relevance_reason", "packaging_relevance", "packaging_forms",
    "packaging_materials", "sterilization_methods", "packaging_related_keywords",
    "risks_or_uncertainties", "source_confidence", "why_it_matters",
    "one_sentence_takeaway",
]

LIST_FIELDS = {
    "secondary_categories", "key_points", "companies", "medical_devices",
    "medical_consumables", "device_categories", "regulatory_approvals",
    "tender_or_procurement_events", "deal_amounts", "production_capacity_events",
    "overseas_expansion_events", "packaging_forms", "packaging_materials",
    "sterilization_methods", "packaging_related_keywords", "risks_or_uncertainties",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze Medical Device articles with DeepSeek.")
    parser.add_argument("--input", type=Path, default=INPUT_PATH, help="LLM-ready input JSON.")
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH, help="Analyzed output JSON.")
    parser.add_argument("--limit", type=int, default=10, help="Maximum new articles to analyze.")
    parser.add_argument("--start", default="2026-07-01", help="Start date YYYY-MM-DD.")
    parser.add_argument("--end", default="2026-07-31", help="End date YYYY-MM-DD.")
    parser.add_argument("--include-ocr", action="store_true", help="Include OCR text.")
    parser.add_argument("--force", action="store_true", help="Re-analyze existing article IDs.")
    parser.add_argument("--sleep", type=float, default=0.5, help="Delay between API calls.")
    parser.add_argument("--workers", type=int, default=1, help="Concurrent API workers.")
    return parser.parse_args()


def load_prompt() -> str:
    prompt = PROMPT_PATH.read_text(encoding="utf-8")
    context = AMCOR_CONTEXT_PATH.read_text(encoding="utf-8") if AMCOR_CONTEXT_PATH.exists() else ""
    return prompt.replace("{amcor_context}", context.strip())


def bounded_int(value: Any, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value or 0)
    except (TypeError, ValueError):
        parsed = 0
    return max(minimum, min(maximum, parsed))


def coerce_analysis(raw: dict[str, Any], article: dict[str, Any]) -> dict[str, Any]:
    result = {field: raw.get(field) for field in ANALYSIS_FIELDS}
    for field in ("article_id", "title", "source_name", "published", "link"):
        result[field] = str(article.get(field, "") or result.get(field) or "")

    result["include_in_weekly_report"] = bool(result.get("include_in_weekly_report"))
    result["relevance_score"] = bounded_int(result.get("relevance_score"), 0, 20)
    result["amcor_relevance_score"] = bounded_int(result.get("amcor_relevance_score"), 0, 5)

    importance = str(result.get("importance_level") or "low").lower()
    result["importance_level"] = importance if importance in {"high", "medium", "low"} else "low"
    packaging = str(result.get("packaging_relevance") or "none").lower()
    result["packaging_relevance"] = packaging if packaging in {"high", "medium", "low", "none"} else "none"

    for field in LIST_FIELDS:
        result[field] = result.get(field) if isinstance(result.get(field), list) else []
    for field in ANALYSIS_FIELDS:
        if result.get(field) is None:
            result[field] = [] if field in LIST_FIELDS else ""

    if (
        result["relevance_score"] < 10
        or result["importance_level"] == "low"
        or result["amcor_relevance_score"] == 0
    ):
        minimize_low_value(result)

    result["_analyzed_at"] = datetime.now(timezone.utc).isoformat()
    return result


def normalize_existing_analyses(
    analyzed: list[dict[str, Any]],
    articles: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    by_id = {
        str(article.get("article_id", "") or article.get("link", "")): article
        for article in articles
    }
    by_link = {
        str(article.get("link", "")): article
        for article in articles
        if article.get("link")
    }
    by_identity = {
        (
            str(article.get("title", "")),
            str(article.get("source_name", "")),
            str(article.get("published", "")),
        ): article
        for article in articles
    }

    normalized: dict[str, dict[str, Any]] = {}
    for result in analyzed:
        article = by_id.get(str(result.get("article_id", "")))
        if article is None:
            article = by_link.get(str(result.get("link", "")))
        if article is None:
            article = by_identity.get(
                (
                    str(result.get("title", "")),
                    str(result.get("source_name", "")),
                    str(result.get("published", "")),
                )
            )
        if article is None:
            continue
        article_id = str(article.get("article_id", "") or article.get("link", ""))
        result["article_id"] = article_id
        result["title"] = str(article.get("title", ""))
        result["source_name"] = str(article.get("source_name", ""))
        result["published"] = str(article.get("published", ""))
        result["link"] = str(article.get("link", ""))
        normalized[article_id] = result
    return normalized


def minimize_low_value(result: dict[str, Any]) -> None:
    result["include_in_weekly_report"] = False
    for field in LIST_FIELDS:
        result[field] = []
    result["clinical_or_regulatory_stage"] = ""
    result["market_implication_cn"] = ""
    result["packaging_relevance"] = "none"
    result["source_confidence"] = result.get("source_confidence") or "high"


def main() -> int:
    args = parse_args()
    start_date = datetime.strptime(args.start, "%Y-%m-%d").date()
    end_date = datetime.strptime(args.end, "%Y-%m-%d").date()
    if start_date > end_date:
        raise ValueError("--start must be earlier than or equal to --end")

    config = load_deepseek_config()
    prompt = load_prompt()
    articles = filter_articles(load_json_list(args.input), start_date, end_date)
    analyzed = load_json_list(args.output)
    analyzed_by_id = normalize_existing_analyses(analyzed, articles)

    remaining = []
    for article in articles:
        article_id = str(article.get("article_id", "") or article.get("link", ""))
        if article_id in analyzed_by_id and not args.force:
            continue
        if not str(article.get("main_text", "") or "").strip():
            continue
        remaining.append(article)
    remaining = prioritize_articles(remaining, load_source_priorities(), set())
    selected = remaining[: args.limit] if args.limit > 0 else remaining

    print("DeepSeek Medical Device analysis", flush=True)
    print(f"- Available date-filtered articles: {len(articles)}", flush=True)
    print(f"- Already analyzed: {len(analyzed_by_id)}", flush=True)
    print(f"- Selected for this run: {len(selected)}", flush=True)
    print(f"- Prompt: {PROMPT_PATH}", flush=True)
    print(f"- Input: {args.input}", flush=True)
    print(f"- Output: {args.output}", flush=True)

    processed = 0
    failed = 0
    if args.workers > 1:
        future_to_article: dict[Any, dict[str, Any]] = {}
        with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
            for article in selected:
                future = executor.submit(
                    call_deepseek,
                    config,
                    prompt,
                    article,
                    get_article_text(article, args.include_ocr),
                )
                future_to_article[future] = article
                if args.sleep > 0:
                    time.sleep(args.sleep)

            for index, future in enumerate(as_completed(future_to_article), start=1):
                article = future_to_article[future]
                title = str(article.get("title", ""))
                article_id = str(article.get("article_id", "") or article.get("link", ""))
                try:
                    analysis = coerce_analysis(future.result(), article)
                    analyzed_by_id[article_id] = analysis
                    output = sorted(
                        analyzed_by_id.values(),
                        key=lambda item: item.get("published", ""),
                        reverse=True,
                    )
                    save_json_list(args.output, output)
                    processed += 1
                    print(
                        f"[{index}/{len(selected)}] Saved: {title} "
                        f"relevance={analysis['relevance_score']}, "
                        f"amcor={analysis['amcor_relevance_score']}, "
                        f"weekly={analysis['include_in_weekly_report']}",
                        flush=True,
                    )
                except Exception as exc:  # noqa: BLE001
                    failed += 1
                    print(f"[{index}/{len(selected)}] Failed: {title} | {exc}", flush=True)

        print("Medical Device analysis finished", flush=True)
        print(f"- Processed: {processed}", flush=True)
        print(f"- Failed: {failed}", flush=True)
        print(f"- Total analyzed output: {len(analyzed_by_id)}", flush=True)
        return 0 if failed == 0 else 1

    for index, article in enumerate(selected, start=1):
        title = str(article.get("title", ""))
        article_id = str(article.get("article_id", "") or article.get("link", ""))
        print(f"[{index}/{len(selected)}] Analyzing: {title}", flush=True)
        try:
            raw = call_deepseek(config, prompt, article, get_article_text(article, args.include_ocr))
            analysis = coerce_analysis(raw, article)
            analyzed_by_id[article_id] = analysis
            output = sorted(analyzed_by_id.values(), key=lambda item: item.get("published", ""), reverse=True)
            save_json_list(args.output, output)
            processed += 1
            print(
                f"  Saved. relevance={analysis['relevance_score']}, "
                f"amcor={analysis['amcor_relevance_score']}, "
                f"weekly={analysis['include_in_weekly_report']}",
                flush=True,
            )
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"  Failed: {exc}", flush=True)
        if args.sleep > 0:
            time.sleep(args.sleep)

    print("Medical Device analysis finished", flush=True)
    print(f"- Processed: {processed}", flush=True)
    print(f"- Failed: {failed}", flush=True)
    print(f"- Total analyzed output: {len(analyzed_by_id)}", flush=True)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
