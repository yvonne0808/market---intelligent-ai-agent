from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


PROJECT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_ARTICLES = PROJECT_DIR / "data/llm_ready/Pharma/july_pharma_hybrid_candidates_v1.json"
DEFAULT_CLASSIFICATIONS = PROJECT_DIR / "data/analyzed/Pharma/july_pharma_opportunity_light_classification_v2.json"
DEFAULT_OUTPUT = PROJECT_DIR / "data/llm_ready/Pharma/july_pharma_top_opportunity_full_analysis_input_v1.json"


def select_articles(articles: list[dict[str, Any]], classifications: list[dict[str, Any]]) -> list[dict[str, Any]]:
    selected_ids = {
        str(item.get("article_id", ""))
        for item in classifications
        if item.get("is_top_opportunity") is True
    }
    return [article for article in articles if str(article.get("article_id", "")) in selected_ids]


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare selected Pharma articles for full DeepSeek analysis.")
    parser.add_argument("--articles", default=str(DEFAULT_ARTICLES))
    parser.add_argument("--classifications", default=str(DEFAULT_CLASSIFICATIONS))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()
    articles = json.loads(Path(args.articles).read_text(encoding="utf-8"))
    classifications = json.loads(Path(args.classifications).read_text(encoding="utf-8"))
    selected = select_articles(articles, classifications)
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(selected, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Prepared {len(selected)} articles: {args.output}")


if __name__ == "__main__":
    main()
