from __future__ import annotations

import argparse
import html
import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def text_date(value: str) -> str:
    if not value:
        return ""
    return value[:10]


def score_class(score: int) -> str:
    if score >= 5:
        return "score-max"
    if score >= 4:
        return "score-high"
    if score >= 3:
        return "score-mid"
    if score >= 1:
        return "score-low"
    return "score-none"


def packaging_class(value: str) -> str:
    value = (value or "none").lower()
    if value in {"high", "medium", "low", "none"}:
        return f"pack-{value}"
    return "pack-none"


def article_sort_key(article: dict[str, Any]) -> tuple[int, int, int, str]:
    packaging_rank = {"high": 3, "medium": 2, "low": 1, "none": 0}
    return (
        int(article.get("amcor_relevance_score", 0) or 0),
        packaging_rank.get(str(article.get("packaging_relevance", "")).lower(), 0),
        int(article.get("relevance_score", 0) or 0),
        str(article.get("published", "")),
    )


def linkify_markdown(text: str) -> str:
    text = esc(text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(
        r"\[([^\]]+)\]\((https?://[^)]+)\)",
        r'<a href="\2" target="_blank" rel="noopener">\1</a>',
        text,
    )
    return text


def first_present(*values: Any) -> str:
    for value in values:
        if isinstance(value, list) and value:
            return "、".join(str(item) for item in value[:8])
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def render_badges(article: dict[str, Any]) -> str:
    relevance = int(article.get("relevance_score", 0) or 0)
    amcor = int(article.get("amcor_relevance_score", 0) or 0)
    packaging = str(article.get("packaging_relevance", "none") or "none")
    category = article.get("primary_category", "")
    return f"""
      <div class="badges">
        <span class="badge category">{esc(category)}</span>
        <span class="badge relevance">Relevance {relevance}</span>
        <span class="badge {score_class(amcor)}">Amcor {amcor}</span>
        <span class="badge {packaging_class(packaging)}">Packaging {esc(packaging)}</span>
      </div>
    """


def render_article_card(article: dict[str, Any], rank: int | None = None) -> str:
    title = article.get("title", "")
    source = article.get("source_name", "")
    published = text_date(article.get("published", ""))
    takeaway = first_present(article.get("one_sentence_takeaway", ""), article.get("summary_cn", ""))
    amcor_reason = article.get("amcor_relevance_reason", "")
    keywords = article.get("packaging_related_keywords", [])
    companies = article.get("companies", [])
    link = article.get("link", "")
    rank_html = f'<div class="rank">{rank}</div>' if rank is not None else ""
    chips = []
    for item in list(companies)[:4]:
        chips.append(f'<span class="chip">{esc(item)}</span>')
    for item in list(keywords)[:4]:
        chips.append(f'<span class="chip chip-soft">{esc(item)}</span>')
    chip_html = f'<div class="chips">{"".join(chips)}</div>' if chips else ""
    return f"""
      <article class="article-card">
        {rank_html}
        <div class="article-main">
          <div class="article-meta">{esc(source)} · {esc(published)}</div>
          <h3>{esc(title)}</h3>
          {render_badges(article)}
          <p class="takeaway">{esc(takeaway)}</p>
          {f'<p class="reason">{esc(amcor_reason)}</p>' if amcor_reason else ''}
          {chip_html}
          {f'<a class="read-link" href="{esc(link)}" target="_blank" rel="noopener">Open original</a>' if link else ''}
        </div>
      </article>
    """


def render_compact_article(article: dict[str, Any]) -> str:
    title = article.get("title", "")
    source = article.get("source_name", "")
    published = text_date(article.get("published", ""))
    link = article.get("link", "")
    takeaway = first_present(article.get("one_sentence_takeaway", ""), article.get("summary_cn", ""))
    amcor = int(article.get("amcor_relevance_score", 0) or 0)
    relevance = int(article.get("relevance_score", 0) or 0)
    return f"""
      <li class="compact-article">
        <div>
          <a href="{esc(link)}" target="_blank" rel="noopener">{esc(title)}</a>
          <div class="compact-meta">{esc(source)} · {esc(published)} · relevance {relevance} · amcor {amcor}</div>
          <p>{esc(takeaway)}</p>
        </div>
      </li>
    """


def render_week(week: dict[str, Any]) -> str:
    articles = sorted(week.get("articles", []), key=article_sort_key, reverse=True)
    direct = [
        article
        for article in articles
        if int(article.get("amcor_relevance_score", 0) or 0) >= 4
        or str(article.get("packaging_relevance", "")).lower() in {"high", "medium"}
    ]
    other = [article for article in articles if article not in direct]
    direct_html = (
        "".join(render_article_card(article) for article in direct[:4])
        if direct
        else '<p class="empty-note">本周暂无直接包装相关强信号。</p>'
    )
    other_html = "".join(render_compact_article(article) for article in other[:8])
    return f"""
      <section class="week-section" id="{esc(week.get('week', '').replace(' ', '-').lower())}">
        <div class="week-header">
          <div>
            <div class="eyebrow">{esc(week.get("week", ""))}</div>
            <h2>{esc(week.get("start_date", ""))} 至 {esc(week.get("end_date", ""))}</h2>
          </div>
          <span class="week-count">{len(articles)} articles</span>
        </div>
        <h3 class="subhead">Most Relevant to Amcor / Packaging</h3>
        <div class="card-grid">{direct_html}</div>
        <details class="other-news" open>
          <summary>Other Important Pharma News</summary>
          <ul>{other_html}</ul>
        </details>
      </section>
    """


def render_markdown_summary(markdown: str) -> str:
    marker = "## 8. Risks and Uncertainties"
    if marker not in markdown:
        return ""
    section = markdown[markdown.index(marker) :]
    next_marker = "\n## 9."
    if next_marker in section:
        section = section[: section.index(next_marker)]
    lines = []
    for raw in section.splitlines():
        line = raw.strip()
        if not line or line == "---":
            continue
        if line.startswith("## "):
            lines.append(f"<h2>{esc(line[3:])}</h2>")
        elif line.startswith("- "):
            lines.append(f"<li>{linkify_markdown(line[2:])}</li>")
        else:
            lines.append(f"<p>{linkify_markdown(line)}</p>")
    html_lines = []
    in_list = False
    for line in lines:
        if line.startswith("<li>") and not in_list:
            html_lines.append("<ul>")
            in_list = True
        if not line.startswith("<li>") and in_list:
            html_lines.append("</ul>")
            in_list = False
        html_lines.append(line)
    if in_list:
        html_lines.append("</ul>")
    return "\n".join(html_lines)


def build_html(report: dict[str, Any]) -> str:
    articles = sorted(report.get("articles", []), key=article_sort_key, reverse=True)
    weeks = report.get("weeks", [])
    start = report.get("start_date", "")
    end = report.get("end_date", "")
    generated = report.get("generated_at", "")
    top_articles = articles[:10]
    amcor_high = sum(1 for article in articles if int(article.get("amcor_relevance_score", 0) or 0) >= 4)
    packaging_high = sum(1 for article in articles if str(article.get("packaging_relevance", "")).lower() == "high")
    category_counts = Counter(article.get("primary_category", "其他") for article in articles)
    source_counts = Counter(article.get("source_name", "") for article in articles)

    top_html = "".join(render_article_card(article, i + 1) for i, article in enumerate(top_articles))
    week_html = "".join(render_week(week) for week in weeks)
    category_html = "".join(
        f'<span class="pill">{esc(name)} <b>{count}</b></span>'
        for name, count in category_counts.most_common()
    )
    source_html = "".join(
        f'<span class="pill pill-muted">{esc(name)} <b>{count}</b></span>'
        for name, count in source_counts.most_common()
    )
    risks_html = render_markdown_summary(report.get("markdown_report", ""))

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Monthly Pharma News Report</title>
  <style>
    :root {{
      --ink: #15202b;
      --muted: #647184;
      --line: #d9e1ec;
      --panel: #f7f9fc;
      --blue: #174a7c;
      --teal: #087f8c;
      --green: #1d7f4b;
      --amber: #a56400;
      --red: #a23b36;
      --bg: #ffffff;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", Arial, sans-serif;
      color: var(--ink);
      background: var(--bg);
      line-height: 1.58;
    }}
    a {{ color: #145a9e; text-decoration-thickness: 1px; text-underline-offset: 3px; }}
    .shell {{ max-width: 1180px; margin: 0 auto; padding: 28px 28px 56px; }}
    .hero {{
      border-bottom: 1px solid var(--line);
      padding: 22px 0 24px;
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 24px;
      align-items: end;
    }}
    .hero h1 {{ margin: 0 0 10px; font-size: 34px; letter-spacing: 0; color: #11345b; }}
    .hero p {{ margin: 0; color: var(--muted); }}
    .nav {{ display: flex; flex-wrap: wrap; gap: 8px; margin-top: 18px; }}
    .nav a {{
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 6px 11px;
      background: #fff;
      font-size: 13px;
      text-decoration: none;
      color: #27445f;
    }}
    .kpis {{ display: grid; grid-template-columns: repeat(4, minmax(130px, 1fr)); gap: 12px; margin: 22px 0; }}
    .kpi {{ border: 1px solid var(--line); border-radius: 8px; padding: 14px; background: var(--panel); }}
    .kpi .value {{ font-size: 28px; font-weight: 720; color: var(--blue); }}
    .kpi .label {{ color: var(--muted); font-size: 13px; }}
    section {{ margin: 28px 0; }}
    .section-title {{ display: flex; justify-content: space-between; align-items: end; gap: 16px; margin-bottom: 14px; }}
    h2 {{ color: #123b66; font-size: 24px; margin: 0; }}
    h3 {{ color: #294961; margin: 0 0 8px; font-size: 17px; }}
    .pills {{ display: flex; flex-wrap: wrap; gap: 8px; }}
    .pill {{
      display: inline-flex;
      gap: 6px;
      align-items: center;
      border: 1px solid #cdd8e4;
      background: #f9fbfd;
      border-radius: 999px;
      padding: 6px 10px;
      font-size: 13px;
      color: #33475b;
    }}
    .pill-muted {{ background: #fff; }}
    .card-grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; }}
    .article-card {{
      display: grid;
      grid-template-columns: auto 1fr;
      gap: 12px;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 14px;
      background: #fff;
      box-shadow: 0 1px 2px rgba(17, 52, 91, 0.05);
    }}
    .rank {{
      width: 30px;
      height: 30px;
      border-radius: 50%;
      background: #123b66;
      color: #fff;
      display: grid;
      place-items: center;
      font-weight: 700;
      margin-top: 2px;
    }}
    .article-card h3 {{ font-size: 16px; line-height: 1.42; margin: 2px 0 8px; color: #14283b; }}
    .article-meta, .compact-meta {{ color: var(--muted); font-size: 12.5px; }}
    .badges {{ display: flex; flex-wrap: wrap; gap: 6px; margin: 8px 0; }}
    .badge {{ display: inline-flex; border-radius: 999px; padding: 3px 8px; font-size: 12px; background: #eef3f8; color: #2b4055; }}
    .category {{ background: #e7f0f8; color: #164b77; }}
    .relevance {{ background: #eef2f7; }}
    .score-max, .pack-high {{ background: #dff3e7; color: #176a3c; }}
    .score-high, .pack-medium {{ background: #e4f2f4; color: #096f78; }}
    .score-mid, .pack-low {{ background: #fff3dc; color: #8a5600; }}
    .score-low {{ background: #f5eee8; color: #8a5600; }}
    .score-none, .pack-none {{ background: #f1f1f1; color: #606a76; }}
    .takeaway {{ margin: 8px 0; font-weight: 620; }}
    .reason {{ color: #435161; margin: 8px 0; font-size: 14px; }}
    .chips {{ display: flex; flex-wrap: wrap; gap: 6px; margin-top: 10px; }}
    .chip {{ font-size: 12px; padding: 3px 7px; border-radius: 5px; background: #edf5ff; color: #24557f; }}
    .chip-soft {{ background: #f1f8f3; color: #2b6c40; }}
    .read-link {{ display: inline-block; margin-top: 10px; font-size: 13px; }}
    .week-section {{ border-top: 1px solid var(--line); padding-top: 22px; }}
    .week-header {{ display: flex; justify-content: space-between; gap: 16px; align-items: start; margin-bottom: 12px; }}
    .eyebrow {{ color: var(--teal); text-transform: uppercase; letter-spacing: 0.02em; font-size: 12px; font-weight: 700; }}
    .week-count {{ background: #eef3f8; color: #405368; border-radius: 999px; padding: 5px 10px; font-size: 12px; white-space: nowrap; }}
    .subhead {{ margin: 12px 0; color: #123b66; }}
    .other-news {{ margin-top: 14px; border: 1px solid var(--line); border-radius: 8px; padding: 12px 14px; background: #fbfcfe; }}
    .other-news summary {{ cursor: pointer; font-weight: 700; color: #234560; }}
    .other-news ul {{ padding-left: 18px; }}
    .compact-article {{ margin: 10px 0; }}
    .compact-article p {{ margin: 3px 0 0; color: #3f4c59; }}
    .empty-note {{ color: var(--muted); background: var(--panel); border: 1px dashed #cbd6e2; border-radius: 8px; padding: 14px; }}
    .risks {{ border: 1px solid var(--line); border-radius: 8px; padding: 18px; background: #fff; }}
    .appendix-table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
    .appendix-wrap {{ overflow-x: auto; border: 1px solid var(--line); border-radius: 8px; }}
    .appendix-table th, .appendix-table td {{ border-bottom: 1px solid #e3e9f0; padding: 8px 10px; text-align: left; vertical-align: top; }}
    .appendix-table th {{ background: #f2f5f9; color: #31465b; position: sticky; top: 0; }}
    footer {{ color: var(--muted); font-size: 12px; border-top: 1px solid var(--line); margin-top: 36px; padding-top: 14px; }}
    @media (max-width: 820px) {{
      .shell {{ padding: 18px 16px 40px; }}
      .hero {{ grid-template-columns: 1fr; }}
      .kpis {{ grid-template-columns: repeat(2, 1fr); }}
      .card-grid {{ grid-template-columns: 1fr; }}
      .hero h1 {{ font-size: 28px; }}
    }}
    @media print {{
      .nav {{ display: none; }}
      .article-card, .other-news, .risks {{ break-inside: avoid; }}
      body {{ background: #fff; }}
    }}
  </style>
</head>
<body>
  <main class="shell">
    <header class="hero">
      <div>
        <h1>Monthly Pharma News Report</h1>
        <p>{esc(start)} 至 {esc(end)} · Generated {esc(generated)}</p>
        <div class="nav">
          <a href="#top-opportunities">Top Opportunities</a>
          <a href="#weeks">Week-by-Week</a>
          <a href="#categories">Categories</a>
          <a href="#risks">Risks</a>
          <a href="#appendix">Appendix</a>
        </div>
      </div>
    </header>

    <section class="kpis">
      <div class="kpi"><div class="value">{len(articles)}</div><div class="label">Articles included</div></div>
      <div class="kpi"><div class="value">{len(weeks)}</div><div class="label">Weekly sections</div></div>
      <div class="kpi"><div class="value">{amcor_high}</div><div class="label">Amcor score >= 4</div></div>
      <div class="kpi"><div class="value">{packaging_high}</div><div class="label">High packaging relevance</div></div>
    </section>

    <section id="top-opportunities">
      <div class="section-title">
        <h2>Top Amcor Opportunities</h2>
      </div>
      <div class="card-grid">{top_html}</div>
    </section>

    <section id="weeks">
      <div class="section-title">
        <h2>Week-by-Week Digest</h2>
      </div>
      {week_html}
    </section>

    <section id="categories">
      <div class="section-title"><h2>Category Summary</h2></div>
      <div class="pills">{category_html}</div>
      <div class="section-title" style="margin-top:18px"><h2>Sources</h2></div>
      <div class="pills">{source_html}</div>
    </section>

    <section id="risks" class="risks">
      {risks_html}
    </section>

    <section id="appendix">
      <div class="section-title"><h2>Appendix: Articles Reviewed</h2></div>
      <div class="appendix-wrap">
        <table class="appendix-table">
          <thead>
            <tr>
              <th>Date</th><th>Title</th><th>Source</th><th>Category</th><th>Rel.</th><th>Amcor</th><th>Packaging</th>
            </tr>
          </thead>
          <tbody>
            {''.join(f"<tr><td>{esc(text_date(a.get('published','')))}</td><td><a href='{esc(a.get('link',''))}' target='_blank' rel='noopener'>{esc(a.get('title',''))}</a></td><td>{esc(a.get('source_name',''))}</td><td>{esc(a.get('primary_category',''))}</td><td>{esc(a.get('relevance_score',''))}</td><td>{esc(a.get('amcor_relevance_score',''))}</td><td>{esc(a.get('packaging_relevance',''))}</td></tr>" for a in articles)}
          </tbody>
        </table>
      </div>
    </section>

    <footer>
      Generated from structured monthly report JSON. Original links point to source WeChat articles.
    </footer>
  </main>
</body>
</html>"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a readable HTML monthly report from monthly report JSON.")
    parser.add_argument("input_json", type=Path)
    parser.add_argument("output_html", type=Path)
    args = parser.parse_args()

    report = json.loads(args.input_json.read_text(encoding="utf-8"))
    html_text = build_html(report)
    args.output_html.parent.mkdir(parents=True, exist_ok=True)
    args.output_html.write_text(html_text, encoding="utf-8")
    print(args.output_html)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
