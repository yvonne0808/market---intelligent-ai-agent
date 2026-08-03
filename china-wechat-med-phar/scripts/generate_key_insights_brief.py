from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from typing import Any


def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def article_index(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        article["article_id"]: article
        for article in report.get("articles", [])
        if isinstance(article, dict) and article.get("article_id")
    }


def article_summary(article: dict[str, Any]) -> str:
    return str(article.get("one_sentence_takeaway") or article.get("summary_cn") or "").strip()


def article_badges(article: dict[str, Any]) -> str:
    return "".join(
        f'<span class="badge">{esc(label)}</span>'
        for label in (
            article.get("primary_category", ""),
            f'Relevance {article.get("relevance_score", "")}',
            f'Amcor {article.get("amcor_relevance_score", "")}',
            f'Packaging {article.get("packaging_relevance", "")}',
        )
        if label
    )


def source_link(article: dict[str, Any]) -> str:
    link = str(article.get("link", "")).strip()
    return f'<a href="{esc(link)}" target="_blank" rel="noopener">Open original source</a>' if link else ""


def render_takeaway(article: dict[str, Any], index: int) -> str:
    return f"""
      <article class="takeaway">
        <span class="number">{index}</span>
        <div><h3>{esc(article.get("title", ""))}</h3><p>{esc(article_summary(article))}</p>{source_link(article)}</div>
      </article>
    """


def render_opportunity(article: dict[str, Any], index: int) -> str:
    companies = " ".join(f'<span class="chip">{esc(company)}</span>' for company in article.get("companies", [])[:4])
    return f"""
      <article class="card">
        <div class="card-top"><span class="number">{index}</span><span>{esc(article.get("source_name", ""))} · {esc(str(article.get("published", ""))[:10])}</span></div>
        <h3>{esc(article.get("title", ""))}</h3>
        <div class="badges">{article_badges(article)}</div>
        <p>{esc(article_summary(article))}</p>
        <div class="chips">{companies}</div>
        {source_link(article)}
      </article>
    """


def build_brief_html(report: dict[str, Any], article_ids: list[str], report_type: str) -> str:
    indexed = article_index(report)
    selected = [indexed[article_id] for article_id in article_ids if article_id in indexed]
    takeaways = selected[:5]
    opportunities = selected[:6]
    references = selected[:12]
    period = f'{report.get("start_date", "")} to {report.get("end_date", "")}'
    takeaway_html = "".join(render_takeaway(article, index) for index, article in enumerate(takeaways, 1))
    opportunity_html = "".join(render_opportunity(article, index) for index, article in enumerate(opportunities, 1))
    reference_html = "".join(
        f'<li><a href="{esc(article.get("link", ""))}" target="_blank" rel="noopener">{esc(article.get("title", ""))}</a><span>{esc(article.get("source_name", ""))} · {esc(str(article.get("published", ""))[:10])}</span></li>'
        for article in references
        if article.get("link")
    )
    watchlist = []
    for article in opportunities:
        for company in article.get("companies", [])[:2]:
            if company and company not in watchlist:
                watchlist.append(company)
    watchlist_html = "".join(f'<span class="watch">{esc(company)}</span>' for company in watchlist[:8]) or '<span class="watch">See opportunity cards</span>'
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>July {esc(report_type)} Key Insights Brief</title>
<style>
@page {{ size: Letter; margin: 12mm; }}
* {{ box-sizing: border-box; }} body {{ margin: 0; background: #eef3f8; color: #172b3d; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif; line-height: 1.45; }}
main {{ width: 816px; margin: 0 auto; background: white; padding: 44px 54px; }} .page {{ min-height: 930px; page-break-after: always; }} .page:last-child {{ page-break-after: auto; }}
.eyebrow {{ color:#3b6f98; font-weight:700; font-size:12px; letter-spacing:.08em; text-transform:uppercase; }} h1 {{ font-size:32px; margin:8px 0; color:#153f6d; }} h2 {{ color:#153f6d; font-size:24px; margin:26px 0 14px; }} h3 {{ margin:0 0 6px; font-size:16px; color:#162f4d; }} .period {{ color:#607286; margin:0 0 28px; }}
.takeaway,.card {{ border:1px solid #d4e0ed; border-radius:11px; background:#fff; box-shadow:0 2px 7px rgba(32,72,112,.08); }} .takeaway {{ display:flex; gap:13px; padding:13px 15px; margin:9px 0; }} .takeaway p,.card p {{ margin:5px 0 8px; font-size:13px; }} .number {{ display:inline-flex; flex:0 0 29px; width:29px; height:29px; align-items:center; justify-content:center; border-radius:50%; background:#174a7c; color:white; font-weight:700; }}
.card {{ padding:15px 17px; margin:12px 0; break-inside:avoid; }} .card-top {{ display:flex; align-items:center; gap:9px; color:#687d91; font-size:12px; }} .badges,.chips {{ display:flex; flex-wrap:wrap; gap:6px; margin:8px 0; }} .badge,.chip,.watch {{ background:#eaf4fb; color:#27618c; padding:4px 8px; border-radius:999px; font-size:11px; }} .chip,.watch {{ background:#edf8f1; color:#347259; }} a {{ color:#1469ac; font-weight:600; text-decoration:underline; font-size:12px; }}
.watchlist {{ display:flex; flex-wrap:wrap; gap:8px; margin:10px 0 24px; }} ul {{ padding-left:20px; }} li {{ margin:11px 0; }} li span {{ display:block; color:#637589; font-size:12px; margin-top:2px; }} .note {{ color:#687b8f; font-size:12px; margin-top:30px; }}
</style></head><body><main>
<section class="page"><div class="eyebrow">July 2026 · Executive Brief</div><h1>{esc(report_type)} Key Insights</h1><p class="period">{esc(period)} · Based on the existing structured July report</p><h2>Five Key Takeaways</h2>{takeaway_html}</section>
<section class="page"><div class="eyebrow">Evidence-led opportunities</div><h2>Top Opportunities</h2>{opportunity_html}</section>
<section class="page"><div class="eyebrow">Follow-up and verification</div><h2>Watchlist &amp; References</h2><div class="watchlist">{watchlist_html}</div><h3>Original sources</h3><ul>{reference_html}</ul><p class="note">This concise brief is derived from the existing July report. It preserves direct source links for verification; the full monthly report remains the complete record.</p></section>
</main></body></html>"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Render a concise July key-insights brief from an existing report JSON.")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report-type", required=True)
    parser.add_argument("--article-ids", required=True, help="Comma-separated article IDs, ordered by priority.")
    args = parser.parse_args()
    report = json.loads(args.input.read_text(encoding="utf-8"))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(build_brief_html(report, args.article_ids.split(","), args.report_type), encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
