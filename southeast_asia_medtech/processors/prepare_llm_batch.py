from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


MODULE_DIR = Path(__file__).resolve().parents[1]
PROMPT_PATH = MODULE_DIR / "prompts" / "website_article_analysis_prompt.txt"
PROMPT_VERSION = "sea-medtech-website-v4-global-customer-priority"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare filtered website articles for later LLM analysis.")
    parser.add_argument("--month", required=True, help="Month in YYYY-MM format.")
    parser.add_argument("--input", type=Path)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_path = args.input or (
        MODULE_DIR / "data" / "filtered" / args.month / "articles_filtered.json"
    )
    output_path = args.output or (
        MODULE_DIR / "data" / "filtered" / args.month / "articles_llm_ready.json"
    )
    articles = json.loads(input_path.read_text(encoding="utf-8"))
    if not isinstance(articles, list):
        raise ValueError("Filtered input must be a JSON list.")
    prompt_text = PROMPT_PATH.read_text(encoding="utf-8")
    jobs: list[dict[str, Any]] = []
    for article in articles:
        jobs.append(
            {
                "job_id": f"{args.month}:{article['article_id']}",
                "prompt_version": PROMPT_VERSION,
                "system_prompt_path": str(PROMPT_PATH),
                "article": article,
                "analysis_status": "pending",
                "analysis_result": None,
                "analysis_error": "",
            }
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(jobs, ensure_ascii=False, indent=2), encoding="utf-8")
    manifest = {
        "month": args.month,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "prompt_version": PROMPT_VERSION,
        "prompt_characters": len(prompt_text),
        "articles_ready": len(jobs),
        "api_called": False,
        "input": str(input_path.resolve()),
        "output": str(output_path.resolve()),
    }
    manifest_path = output_path.with_name("llm_batch_manifest.json")
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
