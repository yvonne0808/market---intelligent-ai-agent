from __future__ import annotations

import argparse
import json
from datetime import date, datetime
from pathlib import Path
from typing import Any


PROJECT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = PROJECT_DIR / "data/analyzed/Pharma/july_pharma_top_opportunity_ranking_analysis_v1.json"
DEFAULT_OUTPUT = PROJECT_DIR / "data/analyzed/Pharma/july_pharma_top10_opportunities_v1.json"
EXPLICIT_TERMS = (
    "药包材", "医药包装", "包装材料", "包装形式", "包装供应链", "铝塑", "铝铝", "药用铝箔", "冷铝",
    "生产基地", "生产线", "产线", "投产", "扩产", "产能",
    "集采中标", "集采中选", "中标", "中选", "带量采购", "采购量", "销量增长", "销售放量",
    "国产化", "国产替代", "进口替代",
)


def opportunity_bonus(article: dict[str, Any]) -> int:
    text = " ".join(str(article.get(field, "") or "") for field in ("title", "summary_cn", "amcor_relevance_reason"))
    return int(any(term in text for term in EXPLICIT_TERMS))


def rank_key(article: dict[str, Any]) -> tuple[int, int, int, str]:
    return (
        int(article.get("relevance_score", 0) or 0),
        int(article.get("amcor_relevance_score", 0) or 0),
        opportunity_bonus(article),
        str(article.get("published", "")),
    )


def week_label(published: str) -> str:
    day = datetime.fromisoformat(published.replace("Z", "+00:00")).date() if "T" in published else date.fromisoformat(published[:10])
    if day <= date(2026, 7, 4):
        return "7.1–7.4"
    start = ((day.day - 5) // 7) * 7 + 5
    end = min(start + 6, 31)
    return f"7.{start}–7.{end}"


def select_top(articles: list[dict[str, Any]], limit: int = 10) -> list[dict[str, Any]]:
    ordered = sorted(articles, key=rank_key, reverse=True)[:limit]
    return [{**article, "rank": rank, "week": week_label(str(article.get("published", "")))} for rank, article in enumerate(ordered, start=1)]


def main() -> None:
    parser = argparse.ArgumentParser(description="Select July Pharma Top 10 opportunities.")
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()
    selected = select_top(json.loads(Path(args.input).read_text(encoding="utf-8")))
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(selected, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Selected {len(selected)} Top Opportunities: {output_path}")


if __name__ == "__main__":
    main()
