from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


PROJECT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_INPUTS = [
    PROJECT_DIR
    / "data"
    / "llm_ready"
    / "Medical Device"
    / "articles_llm_ready_2026_06.json",
    PROJECT_DIR
    / "data"
    / "llm_ready"
    / "Medical Device"
    / "articles_llm_ready_2026_07.json",
]
DEFAULT_OUTPUT = (
    PROJECT_DIR
    / "data"
    / "filtered"
    / "Medical Device"
    / "consumable_procurement_articles_2026_06_2026_07.json"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Filter Medical Device LLM-ready articles by an exact source_tags value."
        )
    )
    parser.add_argument(
        "--input",
        action="append",
        type=Path,
        dest="inputs",
        help="Input JSON path. Repeat this option for multiple months.",
    )
    parser.add_argument(
        "--tag",
        default="耗材集采",
        help="Exact source_tags value to match (default: 耗材集采).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Combined filtered JSON output path.",
    )
    return parser.parse_args()


def load_articles(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"Input must contain a JSON list: {path}")
    return [article for article in data if isinstance(article, dict)]


def infer_period(path: Path) -> str:
    match = re.search(r"(\d{4}_\d{2})", path.stem)
    return match.group(1) if match else path.stem


def article_identity(article: dict[str, Any]) -> str:
    return str(
        article.get("article_id")
        or article.get("link")
        or f"{article.get('published', '')}|{article.get('title', '')}"
    )


def main() -> int:
    args = parse_args()
    inputs = [path.expanduser().resolve() for path in (args.inputs or DEFAULT_INPUTS)]
    output = args.output.expanduser().resolve()

    selected: list[dict[str, Any]] = []
    seen: set[str] = set()
    input_stats: list[tuple[Path, int, int]] = []

    for path in inputs:
        articles = load_articles(path)
        matched = 0
        period = infer_period(path)
        for article in articles:
            tags = article.get("source_tags") or []
            if not isinstance(tags, list) or args.tag not in tags:
                continue
            matched += 1
            identity = article_identity(article)
            if identity in seen:
                continue
            seen.add(identity)
            enriched = dict(article)
            enriched["_filter_source_period"] = period
            enriched["_matched_source_tag"] = args.tag
            selected.append(enriched)
        input_stats.append((path, len(articles), matched))

    selected.sort(
        key=lambda article: (
            str(article.get("published") or ""),
            str(article.get("title") or ""),
        ),
        reverse=True,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(selected, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print("Medical Device procurement article filtering finished")
    print(f"- Exact source tag: {args.tag}")
    for path, total, matched in input_stats:
        print(f"- {path.name}: {matched}/{total} matched")
    print(f"- Combined unique articles: {len(selected)}")
    print(f"- Output: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
