from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests


PROJECT_DIR = Path(__file__).resolve().parent
INPUT_PATH = PROJECT_DIR / "data/llm_ready/articles_llm_ready.json"
OUTPUT_PATH = PROJECT_DIR / "data/analyzed/articles_analyzed.json"
PROMPT_PATH = PROJECT_DIR / "prompts/article_analysis_prompt.txt"
AMCOR_CONTEXT_PATH = PROJECT_DIR / "prompts/amcor_apac_context.txt"

DEFAULT_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-chat"

ANALYSIS_FIELDS = [
    "article_id",
    "title",
    "source_name",
    "published",
    "link",
    "include_in_weekly_report",
    "relevance_score",
    "importance_level",
    "primary_category",
    "secondary_categories",
    "summary_cn",
    "key_points",
    "companies",
    "drugs",
    "targets_or_mechanisms",
    "indications",
    "clinical_or_regulatory_stage",
    "deal_amounts",
    "market_implication_cn",
    "amcor_relevance_score",
    "amcor_relevance_reason",
    "packaging_relevance",
    "packaging_related_keywords",
    "risks_or_uncertainties",
    "source_confidence",
    "why_it_matters",
    "one_sentence_takeaway",
]


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def load_deepseek_config() -> dict[str, str]:
    load_env_file(PROJECT_DIR / ".env")
    api_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if not api_key or api_key == "your_deepseek_api_key_here":
        raise RuntimeError(
            "Missing DEEPSEEK_API_KEY. Create .env from .env.example and add your key."
        )
    return {
        "api_key": api_key,
        "base_url": os.environ.get("DEEPSEEK_BASE_URL", DEFAULT_BASE_URL).rstrip("/"),
        "model": os.environ.get("DEEPSEEK_MODEL", DEFAULT_MODEL),
    }


def parse_args() -> argparse.Namespace:
    today = date.today()
    default_start = today - timedelta(days=7)
    parser = argparse.ArgumentParser(description="Analyze LLM-ready articles with DeepSeek.")
    parser.add_argument("--start", default=default_start.isoformat(), help="Start date YYYY-MM-DD")
    parser.add_argument("--end", default=today.isoformat(), help="End date YYYY-MM-DD")
    parser.add_argument("--include-ocr", action="store_true", help="Use llm_input_text_with_ocr")
    parser.add_argument("--force", action="store_true", help="Re-analyze existing article IDs")
    parser.add_argument("--limit", type=int, default=0, help="Optional max articles for testing")
    parser.add_argument("--sleep", type=float, default=0.5, help="Sleep seconds between API calls")
    return parser.parse_args()


def parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def parse_published_date(value: str) -> date | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized).date()
    except ValueError:
        try:
            return datetime.strptime(value[:10], "%Y-%m-%d").date()
        except ValueError:
            return None


def load_json_list(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"{path} must contain a JSON list.")
    return [item for item in data if isinstance(item, dict)]


def load_prompt_with_context() -> str:
    prompt_template = PROMPT_PATH.read_text(encoding="utf-8")
    amcor_context = ""
    if AMCOR_CONTEXT_PATH.exists():
        amcor_context = AMCOR_CONTEXT_PATH.read_text(encoding="utf-8").strip()
    return prompt_template.replace("{amcor_context}", amcor_context)


def save_json_list(path: Path, data: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def filter_articles(
    articles: list[dict[str, Any]],
    start_date: date,
    end_date: date,
    limit: int = 0,
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for article in articles:
        published_date = parse_published_date(article.get("published", ""))
        if not published_date:
            continue
        if start_date <= published_date <= end_date:
            selected.append(article)
    selected.sort(key=lambda item: item.get("published", ""), reverse=True)
    if limit > 0:
        return selected[:limit]
    return selected


def extract_json_object(text: str) -> dict[str, Any]:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.S)
        if not match:
            raise
        data = json.loads(match.group(0))
    if not isinstance(data, dict):
        raise ValueError("DeepSeek response JSON is not an object.")
    return data


def coerce_analysis(raw: dict[str, Any], article: dict[str, Any]) -> dict[str, Any]:
    result = {field: raw.get(field) for field in ANALYSIS_FIELDS}
    result["article_id"] = str(result.get("article_id") or article.get("article_id", ""))
    result["title"] = str(result.get("title") or article.get("title", ""))
    result["source_name"] = str(result.get("source_name") or article.get("source_name", ""))
    result["published"] = str(result.get("published") or article.get("published", ""))
    result["link"] = str(result.get("link") or article.get("link", ""))
    result["include_in_weekly_report"] = bool(result.get("include_in_weekly_report"))
    result["relevance_score"] = int(result.get("relevance_score") or 0)
    result["amcor_relevance_score"] = int(result.get("amcor_relevance_score") or 0)

    list_fields = [
        "secondary_categories",
        "key_points",
        "companies",
        "drugs",
        "targets_or_mechanisms",
        "indications",
        "deal_amounts",
        "packaging_related_keywords",
        "risks_or_uncertainties",
    ]
    for field in list_fields:
        value = result.get(field)
        result[field] = value if isinstance(value, list) else []

    for field in ANALYSIS_FIELDS:
        if result.get(field) is None:
            result[field] = "" if field not in list_fields else []

    result["_analyzed_at"] = datetime.now(timezone.utc).isoformat()
    return result


def call_deepseek(
    config: dict[str, str],
    system_prompt: str,
    article: dict[str, Any],
    article_text: str,
    retries: int = 3,
) -> dict[str, Any]:
    url = f"{config['base_url']}/chat/completions"
    payload = {
        "model": config["model"],
        "messages": [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "article_metadata": {
                            "article_id": article.get("article_id", ""),
                            "title": article.get("title", ""),
                            "source_name": article.get("source_name", ""),
                            "published": article.get("published", ""),
                            "link": article.get("link", ""),
                            "data_quality_score": article.get("data_quality_score", 0),
                            "data_quality_note": article.get("data_quality_note", ""),
                        },
                        "article_text": article_text,
                    },
                    ensure_ascii=False,
                ),
            },
        ],
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
    }
    headers = {
        "Authorization": f"Bearer {config['api_key']}",
        "Content-Type": "application/json",
    }

    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=90)
            if response.status_code == 401:
                raise PermissionError(
                    "DeepSeek API returned 401 Authorization Required. "
                    "Please check DEEPSEEK_API_KEY in .env."
                )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            return extract_json_object(content)
        except PermissionError:
            raise
        except Exception as exc:  # noqa: BLE001 - preserve batch progress.
            last_error = exc
            wait_seconds = 2**attempt
            print(f"  API error attempt {attempt}/{retries}: {exc}. Retrying in {wait_seconds}s")
            time.sleep(wait_seconds)
    raise RuntimeError(f"DeepSeek API failed after {retries} retries: {last_error}")


def main() -> int:
    args = parse_args()
    start_date = parse_date(args.start)
    end_date = parse_date(args.end)
    if start_date > end_date:
        raise ValueError("--start must be earlier than or equal to --end")

    config = load_deepseek_config()
    system_prompt = load_prompt_with_context()
    articles = load_json_list(INPUT_PATH)
    selected_articles = filter_articles(articles, start_date, end_date, args.limit)
    analyzed = load_json_list(OUTPUT_PATH)
    analyzed_by_id = {
        str(item.get("article_id", "")): item
        for item in analyzed
        if item.get("article_id")
    }

    print("DeepSeek article analysis")
    print(f"- Date range: {start_date} to {end_date}")
    print(f"- Articles selected: {len(selected_articles)}")
    print(f"- Include OCR: {args.include_ocr}")
    print(f"- Force re-analyze: {args.force}")

    processed = 0
    skipped = 0
    failed = 0

    for index, article in enumerate(selected_articles, start=1):
        article_id = str(article.get("article_id", "") or article.get("link", ""))
        title = article.get("title", "")
        if not article_id:
            print(f"[{index}/{len(selected_articles)}] Skip article without article_id: {title}")
            skipped += 1
            continue

        if article_id in analyzed_by_id and not args.force:
            print(f"[{index}/{len(selected_articles)}] Skip already analyzed: {title}")
            skipped += 1
            continue

        text_key = "llm_input_text_with_ocr" if args.include_ocr else "llm_input_text"
        article_text = article.get(text_key, "") or article.get("llm_input_text", "")
        print(f"[{index}/{len(selected_articles)}] Analyzing: {title}")

        try:
            raw_analysis = call_deepseek(config, system_prompt, article, article_text)
            analysis = coerce_analysis(raw_analysis, article)
            analyzed_by_id[article_id] = analysis
            analyzed = list(analyzed_by_id.values())
            analyzed.sort(key=lambda item: item.get("published", ""), reverse=True)
            save_json_list(OUTPUT_PATH, analyzed)
            processed += 1
            print(
                f"  Saved. relevance={analysis['relevance_score']}, "
                f"amcor={analysis['amcor_relevance_score']}"
            )
            time.sleep(args.sleep)
        except Exception as exc:  # noqa: BLE001 - continue batch after one failed article.
            failed += 1
            print(f"  Failed: {exc}", file=sys.stderr)

    print("Analysis run finished")
    print(f"- Processed: {processed}")
    print(f"- Skipped: {skipped}")
    print(f"- Failed: {failed}")
    print(f"- Output: {OUTPUT_PATH}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
