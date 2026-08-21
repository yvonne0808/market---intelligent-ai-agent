from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests

try:
    import yaml
except ImportError:  # pragma: no cover - script can still run without priority sorting.
    yaml = None


PROJECT_DIR = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = PROJECT_DIR.parent
INPUT_PATH = PROJECT_DIR / "data/llm_ready/articles_llm_ready.json"
OUTPUT_PATH = PROJECT_DIR / "data/analyzed/articles_analyzed.json"
PROMPT_PATH = PROJECT_DIR / "prompts/Pharma/article_analysis_prompt.txt"
AMCOR_CONTEXT_PATH = PROJECT_DIR / "prompts/amcor_apac_context.txt"
CONFIG_PATH = PROJECT_DIR / "config.yaml"

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
    load_env_file(REPOSITORY_ROOT / ".env")
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
    parser.add_argument("--input", default=str(INPUT_PATH), help="Input LLM-ready JSON file.")
    parser.add_argument("--output", default=str(OUTPUT_PATH), help="Output analyzed JSON file.")
    parser.add_argument(
        "--selected-output",
        default="",
        help=(
            "Optional clean output containing only analyzed articles from this input/date selection. "
            "Useful for month-specific report files."
        ),
    )
    parser.add_argument("--start", default=default_start.isoformat(), help="Start date YYYY-MM-DD")
    parser.add_argument("--end", default=today.isoformat(), help="End date YYYY-MM-DD")
    parser.add_argument("--include-ocr", action="store_true", help="Use llm_input_text_with_ocr")
    parser.add_argument("--force", action="store_true", help="Re-analyze existing article IDs")
    parser.add_argument("--limit", type=int, default=0, help="Optional max articles for testing")
    parser.add_argument("--sleep", type=float, default=0.5, help="Sleep seconds between API calls")
    parser.add_argument(
        "--only-sources",
        default="",
        help="Optional comma-separated source names to analyze. Default analyzes all sources in date range.",
    )
    parser.add_argument(
        "--smart-new-only",
        action="store_true",
        help=(
            "Analyze only not-yet-analyzed articles, skip empty text, and prioritize important sources first."
        ),
    )
    parser.add_argument(
        "--skip-empty-text",
        action="store_true",
        help="Skip articles whose LLM input text is empty or too short.",
    )
    parser.add_argument(
        "--min-text-length",
        type=int,
        default=1,
        help="Minimum article text length when --skip-empty-text or --smart-new-only is used.",
    )
    parser.add_argument(
        "--priority-sources",
        default="",
        help="Optional comma-separated source names to place before other sources.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Number of concurrent API workers. Keep small to avoid rate limits.",
    )
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


def load_source_priorities(config_path: Path = CONFIG_PATH) -> dict[str, str]:
    if yaml is None or not config_path.exists():
        return {}
    data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    feeds = data.get("feeds", [])
    priorities: dict[str, str] = {}
    if isinstance(feeds, list):
        for feed in feeds:
            if not isinstance(feed, dict):
                continue
            name = str(feed.get("name", "")).strip()
            priority = str(feed.get("priority", "")).strip().lower()
            if name:
                priorities[name] = priority
    return priorities


def save_json_list(path: Path, data: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def save_selected_analysis(
    path: Path | None,
    analyzed_by_id: dict[str, dict[str, Any]],
    selected_articles: list[dict[str, Any]],
) -> None:
    if path is None:
        return
    selected_ids = {
        str(article.get("article_id", "") or article.get("link", ""))
        for article in selected_articles
    }
    selected_analyzed = [
        analyzed_by_id[article_id]
        for article_id in selected_ids
        if article_id in analyzed_by_id
    ]
    selected_analyzed.sort(key=lambda item: item.get("published", ""), reverse=True)
    save_json_list(path, selected_analyzed)


def filter_articles(
    articles: list[dict[str, Any]],
    start_date: date,
    end_date: date,
    limit: int = 0,
    source_names: set[str] | None = None,
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for article in articles:
        if source_names and article.get("source_name", "") not in source_names:
            continue
        published_date = parse_published_date(article.get("published", ""))
        if not published_date:
            continue
        if start_date <= published_date <= end_date:
            selected.append(article)
    selected.sort(key=lambda item: item.get("published", ""), reverse=True)
    if limit > 0:
        return selected[:limit]
    return selected


def get_article_text(article: dict[str, Any], include_ocr: bool = False) -> str:
    text_key = "llm_input_text_with_ocr" if include_ocr else "llm_input_text"
    return str(article.get(text_key, "") or article.get("llm_input_text", "") or "")


def prioritize_articles(
    articles: list[dict[str, Any]],
    source_priorities: dict[str, str],
    priority_sources: set[str],
) -> list[dict[str, Any]]:
    priority_rank = {"high": 0, "medium": 1, "low": 2}

    def sort_key(article: dict[str, Any]) -> tuple[int, int, str]:
        source_name = str(article.get("source_name", "")).strip()
        manual_rank = 0 if source_name in priority_sources else 1
        source_rank = priority_rank.get(source_priorities.get(source_name, ""), 3)
        # YYYY-MM-DD strings sort naturally; reversing the string order keeps newer items first
        # while preserving the simpler priority ranking above.
        published = str(article.get("published", ""))
        newer_first = "".join(chr(255 - ord(char)) for char in published)
        return (manual_rank, source_rank, newer_first)

    return sorted(articles, key=sort_key, reverse=False)


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

    # Enforce the Pharma report score bands after the model response.
    if result["relevance_score"] >= 18:
        result["include_in_weekly_report"] = True
    elif result["relevance_score"] <= 11:
        result["include_in_weekly_report"] = False

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

    if should_minimize_low_value_analysis(result):
        minimize_low_value_analysis(result)

    result["_analyzed_at"] = datetime.now(timezone.utc).isoformat()
    return result


def should_minimize_low_value_analysis(analysis: dict[str, Any]) -> bool:
    return int(analysis.get("relevance_score", 0) or 0) < 10


def minimize_low_value_analysis(analysis: dict[str, Any]) -> None:
    analysis["include_in_weekly_report"] = False
    analysis["key_points"] = []
    analysis["companies"] = []
    analysis["drugs"] = []
    analysis["targets_or_mechanisms"] = []
    analysis["indications"] = []
    analysis["clinical_or_regulatory_stage"] = ""
    analysis["deal_amounts"] = []
    analysis["market_implication_cn"] = ""
    analysis["packaging_related_keywords"] = []
    analysis["risks_or_uncertainties"] = []
    analysis["source_confidence"] = analysis.get("source_confidence") or "high"
    if not analysis.get("amcor_relevance_reason"):
        analysis["amcor_relevance_reason"] = (
            "文章未提及具体包装技术、剂型、产能或商业化相关内容，"
            "与 Amcor 业务无直接关联。"
        )
    if not analysis.get("why_it_matters"):
        analysis["why_it_matters"] = "本文缺乏实质医药行业动态或商业信息，对周报无参考价值。"
    if not analysis.get("one_sentence_takeaway"):
        analysis["one_sentence_takeaway"] = "本文信息量较低，不应纳入周报。"


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


def analyze_one_article(
    config: dict[str, str],
    system_prompt: str,
    article: dict[str, Any],
    include_ocr: bool = False,
) -> tuple[str, dict[str, Any]]:
    article_id = str(article.get("article_id", "") or article.get("link", ""))
    article_text = get_article_text(article, include_ocr)
    raw_analysis = call_deepseek(config, system_prompt, article, article_text)
    return article_id, coerce_analysis(raw_analysis, article)


def main() -> int:
    args = parse_args()
    start_date = parse_date(args.start)
    end_date = parse_date(args.end)
    if start_date > end_date:
        raise ValueError("--start must be earlier than or equal to --end")
    source_names = {name.strip() for name in args.only_sources.split(",") if name.strip()}
    priority_sources = {
        name.strip() for name in args.priority_sources.split(",") if name.strip()
    }

    config = load_deepseek_config()
    system_prompt = load_prompt_with_context()
    input_path = Path(args.input)
    output_path = Path(args.output)
    selected_output_path = Path(args.selected_output) if args.selected_output else None
    articles = load_json_list(input_path)
    selected_articles = filter_articles(articles, start_date, end_date, 0, source_names)
    analyzed = load_json_list(output_path)
    analyzed_by_id = {
        str(item.get("article_id", "")): item
        for item in analyzed
        if item.get("article_id")
    }
    source_priorities = load_source_priorities()

    prefilter_skipped_done = 0
    prefilter_skipped_empty = 0
    if args.smart_new_only:
        remaining_articles: list[dict[str, Any]] = []
        for article in selected_articles:
            article_id = str(article.get("article_id", "") or article.get("link", ""))
            if article_id and article_id in analyzed_by_id and not args.force:
                prefilter_skipped_done += 1
                continue
            article_text = get_article_text(article, args.include_ocr).strip()
            if len(article_text) < args.min_text_length:
                prefilter_skipped_empty += 1
                continue
            remaining_articles.append(article)
        selected_articles = prioritize_articles(
            remaining_articles,
            source_priorities,
            priority_sources,
        )
    elif args.skip_empty_text:
        selected_articles = [
            article
            for article in selected_articles
            if len(get_article_text(article, args.include_ocr).strip()) >= args.min_text_length
        ]

    if args.limit > 0:
        selected_articles = selected_articles[: args.limit]

    print("DeepSeek article analysis", flush=True)
    print(f"- Date range: {start_date} to {end_date}", flush=True)
    print(f"- Articles selected for this run: {len(selected_articles)}", flush=True)
    print(f"- Input: {input_path}", flush=True)
    if selected_output_path:
        print(f"- Selected output: {selected_output_path}", flush=True)
    if source_names:
        print(f"- Sources: {', '.join(sorted(source_names))}", flush=True)
    if priority_sources:
        print(f"- Priority sources first: {', '.join(sorted(priority_sources))}", flush=True)
    print(f"- Include OCR: {args.include_ocr}", flush=True)
    print(f"- Force re-analyze: {args.force}", flush=True)
    print(f"- Smart new-only mode: {args.smart_new_only}", flush=True)
    print(f"- API workers: {max(1, args.workers)}", flush=True)
    if args.smart_new_only:
        print(f"- Pre-skipped already analyzed: {prefilter_skipped_done}", flush=True)
        print(f"- Pre-skipped empty text: {prefilter_skipped_empty}", flush=True)

    processed = 0
    skipped = 0
    failed = 0

    if args.workers > 1:
        ready_articles: list[dict[str, Any]] = []
        for index, article in enumerate(selected_articles, start=1):
            article_id = str(article.get("article_id", "") or article.get("link", ""))
            title = article.get("title", "")
            if not article_id:
                print(f"[{index}/{len(selected_articles)}] Skip article without article_id: {title}", flush=True)
                skipped += 1
                continue
            if article_id in analyzed_by_id and not args.force:
                print(f"[{index}/{len(selected_articles)}] Skip already analyzed: {title}", flush=True)
                skipped += 1
                continue
            article_text = get_article_text(article, args.include_ocr)
            if (args.skip_empty_text or args.smart_new_only) and len(article_text.strip()) < args.min_text_length:
                print(f"[{index}/{len(selected_articles)}] Skip empty text: {title}", flush=True)
                skipped += 1
                continue
            ready_articles.append(article)

        print(f"- Ready for concurrent analysis: {len(ready_articles)}", flush=True)
        future_to_article: dict[Any, dict[str, Any]] = {}
        with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
            for article in ready_articles:
                future = executor.submit(analyze_one_article, config, system_prompt, article, args.include_ocr)
                future_to_article[future] = article
                if args.sleep > 0:
                    time.sleep(args.sleep)

            total_ready = len(ready_articles)
            for completed_index, future in enumerate(as_completed(future_to_article), start=1):
                article = future_to_article[future]
                title = article.get("title", "")
                try:
                    article_id, analysis = future.result()
                    analyzed_by_id[article_id] = analysis
                    analyzed = list(analyzed_by_id.values())
                    analyzed.sort(key=lambda item: item.get("published", ""), reverse=True)
                    save_json_list(output_path, analyzed)
                    save_selected_analysis(selected_output_path, analyzed_by_id, selected_articles)
                    processed += 1
                    print(
                        f"[{completed_index}/{total_ready}] Saved: {title} "
                        f"relevance={analysis['relevance_score']}, "
                        f"amcor={analysis['amcor_relevance_score']}",
                        flush=True,
                    )
                except Exception as exc:  # noqa: BLE001 - continue batch after one failed article.
                    failed += 1
                    print(f"[{completed_index}/{total_ready}] Failed: {title} | {exc}", file=sys.stderr, flush=True)

        print("Analysis run finished", flush=True)
        print(f"- Processed: {processed}", flush=True)
        print(f"- Skipped: {skipped}", flush=True)
        print(f"- Failed: {failed}", flush=True)
        print(f"- Output: {output_path}", flush=True)
        if selected_output_path:
            save_selected_analysis(selected_output_path, analyzed_by_id, selected_articles)
            print(f"- Selected output: {selected_output_path}", flush=True)
        return 0 if failed == 0 else 1

    for index, article in enumerate(selected_articles, start=1):
        article_id = str(article.get("article_id", "") or article.get("link", ""))
        title = article.get("title", "")
        if not article_id:
            print(f"[{index}/{len(selected_articles)}] Skip article without article_id: {title}", flush=True)
            skipped += 1
            continue

        if article_id in analyzed_by_id and not args.force:
            print(f"[{index}/{len(selected_articles)}] Skip already analyzed: {title}", flush=True)
            skipped += 1
            continue

        article_text = get_article_text(article, args.include_ocr)
        if (args.skip_empty_text or args.smart_new_only) and len(article_text.strip()) < args.min_text_length:
            print(f"[{index}/{len(selected_articles)}] Skip empty text: {title}", flush=True)
            skipped += 1
            continue

        print(f"[{index}/{len(selected_articles)}] Analyzing: {title}", flush=True)

        try:
            raw_analysis = call_deepseek(config, system_prompt, article, article_text)
            analysis = coerce_analysis(raw_analysis, article)
            analyzed_by_id[article_id] = analysis
            analyzed = list(analyzed_by_id.values())
            analyzed.sort(key=lambda item: item.get("published", ""), reverse=True)
            save_json_list(output_path, analyzed)
            save_selected_analysis(selected_output_path, analyzed_by_id, selected_articles)
            processed += 1
            print(
                f"  Saved. relevance={analysis['relevance_score']}, "
                f"amcor={analysis['amcor_relevance_score']}",
                flush=True,
            )
            time.sleep(args.sleep)
        except Exception as exc:  # noqa: BLE001 - continue batch after one failed article.
            failed += 1
            print(f"  Failed: {exc}", file=sys.stderr, flush=True)

    print("Analysis run finished", flush=True)
    print(f"- Processed: {processed}", flush=True)
    print(f"- Skipped: {skipped}", flush=True)
    print(f"- Failed: {failed}", flush=True)
    print(f"- Output: {output_path}", flush=True)
    if selected_output_path:
        save_selected_analysis(selected_output_path, analyzed_by_id, selected_articles)
        print(f"- Selected output: {selected_output_path}", flush=True)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
