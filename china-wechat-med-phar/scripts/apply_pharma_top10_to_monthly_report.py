from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_TOP10 = PROJECT_DIR / "data/analyzed/Pharma/july_pharma_top10_opportunities_v1.json"
DEFAULT_REPORT_DIR = PROJECT_DIR / "public_share/reports/pharma/monthly/2026-07"


def ranking_table(top10: list[dict]) -> str:
    rows = [
        "| 排名 | 标题 | 周次 | 来源与发布时间 | relevance_score / amcor_relevance_score | 与 Amcor 业务的关系 | 原文链接 |",
        "|---|---|---|---|---|---|---|",
    ]
    for article in top10:
        rows.append(
            f"| {article['rank']} | {article['title']} | {article['week']} | "
            f"{article['source_name']}，{str(article['published'])[:10]} | "
            f"{article['relevance_score']} / {article['amcor_relevance_score']} | "
            f"{article['amcor_relevance_reason']} | [链接]({article['link']}) |"
        )
    return "\n".join(rows)


def replace_ranking(markdown: str, table: str) -> str:
    pattern = r"(## 2\. Monthly Amcor Relevance Ranking\n\n).*?(?=\n---\n\n## 3\. Week-by-Week News Digest)"
    updated, count = re.subn(pattern, r"\1" + table + "\n", markdown, flags=re.S)
    if count != 1:
        raise ValueError("Could not find exactly one Monthly Amcor Relevance Ranking section.")
    return updated


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply the approved Pharma Top 10 to July report sources.")
    parser.add_argument("--top10", type=Path, default=DEFAULT_TOP10)
    parser.add_argument("--report-dir", type=Path, default=DEFAULT_REPORT_DIR)
    args = parser.parse_args()
    top10 = json.loads(args.top10.read_text(encoding="utf-8"))
    if len(top10) != 10:
        raise ValueError("Top 10 input must contain exactly 10 articles.")
    report_json_path = args.report_dir / "report.json"
    report_md_path = args.report_dir / "report.md"
    report = json.loads(report_json_path.read_text(encoding="utf-8"))
    table = ranking_table(top10)
    markdown = replace_ranking(report_md_path.read_text(encoding="utf-8"), table)
    report["top_opportunity_articles"] = top10
    report["markdown_report"] = replace_ranking(str(report.get("markdown_report", "")), table)
    report_json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    report_md_path.write_text(markdown, encoding="utf-8")
    print(f"Applied {len(top10)} Top Opportunities to {args.report_dir}")


if __name__ == "__main__":
    main()
