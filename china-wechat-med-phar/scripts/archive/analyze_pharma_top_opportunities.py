from __future__ import annotations

import argparse
import json
import os
import re
import time
from pathlib import Path
from typing import Any

import requests


PROJECT_DIR = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = PROJECT_DIR.parent
PROMPT_PATH = PROJECT_DIR / "prompts/Pharma/top_opportunity_analysis_prompt.txt"
DEFAULT_INPUT = PROJECT_DIR / "data/llm_ready/Pharma/july_pharma_top_opportunity_full_analysis_input_v1.json"
DEFAULT_OUTPUT = PROJECT_DIR / "data/analyzed/Pharma/july_pharma_top_opportunity_ranking_analysis_v1.json"
CATEGORIES = {"市场与商业化", "产能与资本投入", "重点产品与剂型", "包装与供应链机会", "其他"}


def load_env_file(path: Path) -> None:
    for line in path.read_text(encoding="utf-8").splitlines() if path.exists() else []:
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def normalize_analysis(raw: dict[str, Any], article: dict[str, Any]) -> dict[str, Any]:
    category = str(raw.get("primary_category", "其他")).strip()
    if category not in CATEGORIES:
        category = "其他"
    return {
        "article_id": str(article.get("article_id", "")),
        "title": str(article.get("title", "")),
        "source_name": str(article.get("source_name", "")),
        "published": str(article.get("published", "")),
        "link": str(article.get("link", "")),
        "primary_category": category,
        "relevance_score": max(0, min(20, int(raw.get("relevance_score", 0) or 0))),
        "amcor_relevance_score": max(0, min(5, int(raw.get("amcor_relevance_score", 0) or 0))),
        "amcor_relevance_reason": str(raw.get("amcor_relevance_reason", "")).strip(),
        "summary_cn": str(raw.get("summary_cn", "")).strip(),
    }


def extract_json(content: str) -> dict[str, Any]:
    match = re.search(r"\{.*\}", content, flags=re.S)
    if not match:
        raise ValueError("DeepSeek response does not contain a JSON object.")
    value = json.loads(match.group(0))
    if not isinstance(value, dict):
        raise ValueError("DeepSeek response must be a JSON object.")
    return value


def main() -> None:
    parser = argparse.ArgumentParser(description="Lean Top Opportunity analysis for Pharma.")
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()
    load_env_file(REPOSITORY_ROOT / ".env")
    key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if not key:
        raise RuntimeError("Missing DEEPSEEK_API_KEY.")
    articles = json.loads(Path(args.input).read_text(encoding="utf-8"))
    output_path = Path(args.output)
    existing = json.loads(output_path.read_text(encoding="utf-8")) if output_path.exists() else []
    by_id = {str(item.get("article_id", "")): item for item in existing}
    pending = [article for article in articles if str(article.get("article_id", "")) not in by_id]
    if args.limit > 0:
        pending = pending[: args.limit]
    prompt = PROMPT_PATH.read_text(encoding="utf-8")
    base_url = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
    model = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    for article in pending:
        payload = {"model": model, "temperature": 0.1, "messages": [{"role": "system", "content": prompt}, {"role": "user", "content": json.dumps({"article_id": article.get("article_id", ""), "title": article.get("title", ""), "source_name": article.get("source_name", ""), "published": article.get("published", ""), "article_text": str(article.get("llm_input_text", ""))}, ensure_ascii=False)}]}
        response = requests.post(f"{base_url}/chat/completions", headers=headers, json=payload, timeout=120)
        response.raise_for_status()
        by_id[str(article.get("article_id", ""))] = normalize_analysis(extract_json(response.json()["choices"][0]["message"]["content"]), article)
        saved = list(by_id.values())
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(saved, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved {len(saved)}/{len(articles)}", flush=True)
        time.sleep(0.1)


if __name__ == "__main__":
    main()
