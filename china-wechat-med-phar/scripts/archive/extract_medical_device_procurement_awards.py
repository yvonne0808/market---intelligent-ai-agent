from __future__ import annotations

import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from analyze_pharma_articles import (
    PROJECT_DIR,
    call_deepseek,
    get_article_text,
    load_deepseek_config,
    load_json_list,
    save_json_list,
)


INPUT_PATH = (
    PROJECT_DIR
    / "data"
    / "filtered"
    / "Medical Device"
    / "consumable_procurement_articles_2026_06_2026_07.json"
)
OUTPUT_PATH = (
    PROJECT_DIR
    / "data"
    / "extracted"
    / "Medical Device"
    / "procurement_awards_2026_06_2026_07.json"
)
PROMPT_PATH = (
    PROJECT_DIR
    / "prompts"
    / "Medical Device"
    / "medical_device_procurement_award_extraction_prompt.txt"
)

AWARD_FIELDS = [
    "category_product",
    "product_name",
    "specification_model",
    "company_name",
    "applicant_company",
    "registrant_name",
    "manufacturer_name",
    "registration_certificate_no",
    "bidding_unit",
    "procurement_group",
    "region",
    "award_status",
    "award_price",
    "currency",
    "price_unit",
    "award_price_text",
    "procurement_volume",
    "volume_unit",
    "procurement_volume_text",
    "price_reduction",
    "price_reduction_text",
    "contract_amount",
    "contract_amount_currency",
    "contract_amount_text",
    "execution_period",
    "evidence_text",
]
ALLOWED_STATUSES = {
    "拟中选",
    "中选",
    "中标",
    "入围",
    "备选",
    "采购结果",
    "执行结果",
    "其他明确结果",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract structured Medical Device procurement award records."
    )
    parser.add_argument("--input", type=Path, default=INPUT_PATH)
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--sleep", type=float, default=0.5)
    parser.add_argument("--include-ocr", action="store_true")
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def text(value: Any) -> str:
    return str(value or "").strip()


def number_or_none(value: Any) -> int | float | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value
    try:
        return float(str(value).replace(",", "").strip())
    except ValueError:
        return None


def coerce_result(raw: dict[str, Any], article: dict[str, Any]) -> dict[str, Any]:
    result = {
        "article_id": text(article.get("article_id") or article.get("link")),
        "title": text(article.get("title")),
        "source_name": text(article.get("source_name")),
        "published": text(article.get("published")),
        "link": text(article.get("link")),
        "is_valid_award_notice": bool(raw.get("is_valid_award_notice")),
        "notice_scope": text(raw.get("notice_scope")),
        "procurement_project_name": text(raw.get("procurement_project_name")),
        "procurement_level": text(raw.get("procurement_level")),
        "announcement_date": text(raw.get("announcement_date")),
        "regions": raw.get("regions") if isinstance(raw.get("regions"), list) else [],
        "invalid_reason": text(raw.get("invalid_reason")),
        "summary_cn": text(raw.get("summary_cn")),
        "awards": [],
        "risks_or_uncertainties": (
            raw.get("risks_or_uncertainties")
            if isinstance(raw.get("risks_or_uncertainties"), list)
            else []
        ),
        "source_confidence": text(raw.get("source_confidence")).lower(),
        "_filter_source_period": text(article.get("_filter_source_period")),
        "_extracted_at": datetime.now(timezone.utc).isoformat(),
    }
    if result["source_confidence"] not in {"high", "medium", "low"}:
        result["source_confidence"] = "low"

    raw_awards = raw.get("awards") if isinstance(raw.get("awards"), list) else []
    for raw_award in raw_awards:
        if not isinstance(raw_award, dict):
            continue
        award = {field: raw_award.get(field) for field in AWARD_FIELDS}
        for field in AWARD_FIELDS:
            if field in {
                "award_price",
                "procurement_volume",
                "price_reduction",
                "contract_amount",
            }:
                award[field] = number_or_none(award.get(field))
            else:
                award[field] = text(award.get(field))
        if award["award_status"] not in ALLOWED_STATUSES:
            award["award_status"] = "其他明确结果" if award["award_status"] else ""
        award["evidence_text"] = award["evidence_text"][:80]
        if award["company_name"]:
            result["awards"].append(award)

    if not result["is_valid_award_notice"] or not result["awards"]:
        result["is_valid_award_notice"] = False
        result["awards"] = []
        if not result["invalid_reason"]:
            result["invalid_reason"] = "未识别到包含明确中选企业的有效中标记录。"
    else:
        result["invalid_reason"] = ""
    return result


def main() -> int:
    args = parse_args()
    articles = load_json_list(args.input)
    existing = load_json_list(args.output)
    existing_by_id = {
        text(item.get("article_id") or item.get("link")): item for item in existing
    }
    remaining = [
        article
        for article in articles
        if text(article.get("main_text"))
        and (
            args.force
            or text(article.get("article_id") or article.get("link"))
            not in existing_by_id
        )
    ]
    selected = remaining[: args.limit] if args.limit > 0 else remaining
    prompt = PROMPT_PATH.read_text(encoding="utf-8")
    config = load_deepseek_config()

    print("Medical Device procurement award extraction", flush=True)
    print(f"- Candidate articles: {len(articles)}", flush=True)
    print(f"- Already extracted: {len(existing_by_id)}", flush=True)
    print(f"- Selected: {len(selected)}", flush=True)
    print(f"- Prompt: {PROMPT_PATH}", flush=True)
    print(f"- Output: {args.output}", flush=True)

    processed = 0
    failed = 0

    def extract_one(article: dict[str, Any]) -> dict[str, Any]:
        raw = call_deepseek(
            config,
            prompt,
            article,
            get_article_text(article, args.include_ocr),
        )
        return coerce_result(raw, article)

    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        future_map = {}
        for article in selected:
            future_map[executor.submit(extract_one, article)] = article
            if args.sleep > 0:
                time.sleep(args.sleep)

        for index, future in enumerate(as_completed(future_map), start=1):
            article = future_map[future]
            article_id = text(article.get("article_id") or article.get("link"))
            try:
                result = future.result()
                existing_by_id[article_id] = result
                output = sorted(
                    existing_by_id.values(),
                    key=lambda item: text(item.get("published")),
                    reverse=True,
                )
                save_json_list(args.output, output)
                processed += 1
                print(
                    f"[{index}/{len(selected)}] Saved: {result['title']} | "
                    f"valid={result['is_valid_award_notice']} | "
                    f"awards={len(result['awards'])}",
                    flush=True,
                )
            except Exception as exc:  # noqa: BLE001
                failed += 1
                print(
                    f"[{index}/{len(selected)}] Failed: {article.get('title', '')} | {exc}",
                    flush=True,
                )

    print("Procurement award extraction finished", flush=True)
    print(f"- Processed: {processed}", flush=True)
    print(f"- Failed: {failed}", flush=True)
    print(f"- Total output: {len(existing_by_id)}", flush=True)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
