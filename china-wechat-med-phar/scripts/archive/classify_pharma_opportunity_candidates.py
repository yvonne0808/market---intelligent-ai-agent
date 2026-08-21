from __future__ import annotations

import argparse
import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import requests


PROJECT_DIR = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = PROJECT_DIR.parent
PROMPT_PATH = PROJECT_DIR / "prompts/Pharma/opportunity_candidate_classification_prompt.txt"
DEFAULT_INPUT = PROJECT_DIR / "data/llm_ready/Pharma/july_pharma_hybrid_candidates_v1.json"
DEFAULT_OUTPUT = PROJECT_DIR / "data/analyzed/Pharma/july_pharma_opportunity_light_classification_v1.json"
ALLOWED_CATEGORIES = {"市场与商业化", "产能与资本投入", "重点产品与剂型", "包装与供应链机会"}
ALLOWED_CONFIDENCE = {"high", "medium", "low"}


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def load_config() -> dict[str, str]:
    load_env_file(REPOSITORY_ROOT / ".env")
    api_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if not api_key or api_key == "your_deepseek_api_key_here":
        raise RuntimeError("Missing DEEPSEEK_API_KEY in the repository .env file.")
    return {
        "api_key": api_key,
        "base_url": os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/"),
        "model": os.environ.get("DEEPSEEK_MODEL", "deepseek-chat"),
    }


def article_excerpt(article: dict[str, Any], length: int) -> str:
    text = str(article.get("llm_input_text", "") or article.get("main_text", "") or "")
    return re.sub(r"\s+", " ", text).strip()[:length]


def build_batch_input(articles: list[dict[str, Any]], excerpt_chars: int) -> list[dict[str, str]]:
    return [
        {
            "article_id": str(article.get("article_id", "")),
            "title": str(article.get("title", "")),
            "source_name": str(article.get("source_name", "")),
            "published": str(article.get("published", "")),
            "excerpt": article_excerpt(article, excerpt_chars),
        }
        for article in articles
    ]


def chunked(items: list[dict[str, Any]], size: int) -> list[list[dict[str, Any]]]:
    return [items[offset : offset + size] for offset in range(0, len(items), size)]


def limit_batches(batches: list[list[dict[str, Any]]], maximum: int) -> list[list[dict[str, Any]]]:
    return batches if maximum <= 0 else batches[:maximum]


def extract_json_array(content: str) -> list[dict[str, Any]]:
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", content.strip())
    match = re.search(r"\[.*\]", text, flags=re.S)
    if not match:
        raise ValueError("DeepSeek response does not contain a JSON array.")
    parsed = json.loads(match.group(0))
    if not isinstance(parsed, list) or not all(isinstance(item, dict) for item in parsed):
        raise ValueError("DeepSeek response must be a JSON array of objects.")
    return parsed


def normalize_results(raw: list[dict[str, Any]], expected_ids: set[str]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    received_ids: set[str] = set()
    for item in raw:
        article_id = str(item.get("article_id", ""))
        if article_id not in expected_ids or article_id in received_ids:
            raise ValueError("Response article_id does not match this batch.")
        received_ids.add(article_id)
        is_top = item.get("is_top_opportunity")
        if not isinstance(is_top, bool):
            raise ValueError("is_top_opportunity must be a boolean.")
        category = str(item.get("new_category", "")).strip()
        if is_top and category not in ALLOWED_CATEGORIES:
            raise ValueError("new_category must be one of the four current opportunity categories.")
        if not is_top:
            category = ""
        confidence = str(item.get("confidence", "")).strip().lower()
        if confidence not in ALLOWED_CONFIDENCE:
            raise ValueError("confidence must be high, medium, or low.")
        normalized.append(
            {
                "article_id": article_id,
                "is_top_opportunity": is_top,
                "new_category": category,
                "confidence": confidence,
            }
        )
    if received_ids != expected_ids:
        raise ValueError("Response did not classify every article in this batch.")
    return normalized


def classify_batch(config: dict[str, str], prompt: str, items: list[dict[str, str]], retries: int) -> list[dict[str, Any]]:
    payload = {
        "model": config["model"],
        "temperature": 0,
        "messages": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": json.dumps(items, ensure_ascii=False)},
        ],
    }
    headers = {"Authorization": f"Bearer {config['api_key']}", "Content-Type": "application/json"}
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            response = requests.post(f"{config['base_url']}/chat/completions", headers=headers, json=payload, timeout=120)
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            return normalize_results(extract_json_array(content), {item["article_id"] for item in items})
        except Exception as exc:  # preserve completed batches if an API request fails
            last_error = exc
            if attempt < retries:
                time.sleep(2**attempt)
    raise RuntimeError(f"DeepSeek batch failed after {retries} attempts: {last_error}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Lightweight DeepSeek classifier for Pharma opportunity candidates.")
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--batch-size", type=int, default=20)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument(
        "--max-batches",
        type=int,
        default=0,
        help="Process at most this many batches, then exit cleanly. 0 processes all pending batches.",
    )
    parser.add_argument("--excerpt-chars", type=int, default=600)
    parser.add_argument("--retries", type=int, default=3)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    articles = json.loads(Path(args.input).read_text(encoding="utf-8"))
    if not isinstance(articles, list):
        raise ValueError("Input must be a JSON list.")
    prompt = PROMPT_PATH.read_text(encoding="utf-8")
    config = load_config()
    output_path = Path(args.output)
    completed: list[dict[str, Any]] = []
    if output_path.exists():
        prior = json.loads(output_path.read_text(encoding="utf-8"))
        if isinstance(prior, list):
            completed = normalize_results(prior, {str(item.get("article_id", "")) for item in prior})
    completed_ids = {item["article_id"] for item in completed}
    pending = [item for item in articles if str(item.get("article_id", "")) not in completed_ids]
    batches = limit_batches(chunked(pending, args.batch_size), args.max_batches)
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        futures = {
            executor.submit(
                classify_batch,
                config,
                prompt,
                build_batch_input(batch, args.excerpt_chars),
                args.retries,
            ): batch
            for batch in batches
        }
        for future in as_completed(futures):
            completed.extend(future.result())
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(json.dumps(completed, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"Saved {len(completed)}/{len(articles)} classifications", flush=True)


if __name__ == "__main__":
    main()
