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


def article_sort_key(
    article: dict[str, Any], report_type: str = "Pharma"
) -> tuple[int, int, int, str]:
    packaging_rank = {"high": 3, "medium": 2, "low": 1, "none": 0}
    if report_type.lower() == "pharma":
        return (
            int(article.get("relevance_score", 0) or 0),
            int(article.get("amcor_relevance_score", 0) or 0),
            packaging_rank.get(str(article.get("packaging_relevance", "")).lower(), 0),
            str(article.get("published", "")),
        )
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
    category = article.get("primary_category", "")
    badges = [
        f'<span class="badge category">{esc(category)}</span>',
        f'<span class="badge relevance">Relevance {relevance}</span>',
        f'<span class="badge {score_class(amcor)}">Amcor {amcor}</span>',
    ]
    if "packaging_relevance" in article:
        packaging = str(article.get("packaging_relevance", "none") or "none")
        badges.append(
            f'<span class="badge {packaging_class(packaging)}">Packaging {esc(packaging)}</span>'
        )
    return '<div class="badges">' + "".join(badges) + "</div>"


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


def split_week_articles(
    articles: list[dict[str, Any]], report_type: str = "Pharma"
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    ordered = sorted(articles, key=lambda item: article_sort_key(item, report_type), reverse=True)
    return ordered[:4], ordered[4:]


def render_week(
    week: dict[str, Any],
    overview_html: str = "",
    report_type: str = "Pharma",
) -> str:
    direct, other = split_week_articles(week.get("articles", []), report_type)
    article_count = len(direct) + len(other)
    direct_html = (
        "".join(render_article_card(article) for article in direct[:4])
        if direct
        else '<p class="empty-note">本周暂无直接包装相关强信号。</p>'
    )
    other_html = "".join(render_compact_article(article) for article in other[:8])
    overview_block = (
        f'<div class="week-overview"><h3>本周概览</h3>{overview_html}</div>'
        if overview_html
        else ""
    )
    return f"""
      <section class="week-section" id="{esc(week.get('week', '').replace(' ', '-').lower())}">
        <div class="week-header">
          <div>
            <div class="eyebrow">{esc(week.get("week", ""))}</div>
            <h2>{esc(week.get("start_date", ""))} 至 {esc(week.get("end_date", ""))}</h2>
          </div>
          <span class="week-count">{article_count} articles</span>
        </div>
        {overview_block}
        <h3 class="subhead">Most Relevant to Amcor / Packaging</h3>
        <div class="card-grid">{direct_html}</div>
        <details class="other-news" open>
          <summary>Other Important {esc(report_type)} News</summary>
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


def extract_markdown_section(markdown: str, heading_pattern: str, next_heading_pattern: str) -> str:
    """Extract one Markdown section between two headings."""
    match = re.search(heading_pattern, markdown, flags=re.M)
    if not match:
        return ""
    section = markdown[match.end() :]
    next_match = re.search(next_heading_pattern, section, flags=re.M)
    if next_match:
        section = section[: next_match.start()]
    return section.strip()


def simple_markdown_to_html(markdown: str) -> str:
    """Render the small Markdown subset used in report narrative sections."""
    html_lines = []
    list_type = ""

    def close_list() -> None:
        nonlocal list_type
        if list_type:
            html_lines.append(f"</{list_type}>")
            list_type = ""

    def is_table_separator(value: str) -> bool:
        cleaned = value.strip().strip("|").replace(":", "").replace("-", "").replace("|", "").strip()
        return cleaned == ""

    def split_table_row(value: str) -> list[str]:
        return [cell.strip() for cell in value.strip().strip("|").split("|")]

    lines = markdown.splitlines()
    i = 0
    while i < len(lines):
        raw = lines[i]
        line = raw.strip()
        if not line or line == "---":
            close_list()
            i += 1
            continue
        if (
            line.startswith("|")
            and i + 1 < len(lines)
            and lines[i + 1].strip().startswith("|")
            and is_table_separator(lines[i + 1])
        ):
            close_list()
            headers = split_table_row(line)
            rows = []
            i += 2
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append(split_table_row(lines[i].strip()))
                i += 1
            html_lines.append('<div class="markdown-table-wrap"><table class="markdown-table">')
            html_lines.append(
                "<thead><tr>"
                + "".join(f"<th>{linkify_markdown(cell)}</th>" for cell in headers)
                + "</tr></thead>"
            )
            html_lines.append("<tbody>")
            for row in rows:
                padded = row + [""] * max(0, len(headers) - len(row))
                html_lines.append(
                    "<tr>"
                    + "".join(f"<td>{linkify_markdown(cell)}</td>" for cell in padded[: len(headers)])
                    + "</tr>"
                )
            html_lines.append("</tbody></table></div>")
            continue
        if line.startswith("#"):
            close_list()
            text = line.lstrip("#").strip()
            level = min(line.count("#"), 3)
            html_lines.append(f"<h{level}>{linkify_markdown(text)}</h{level}>")
            i += 1
            continue

        numbered = re.match(r"^\d+\.\s+(.*)$", line)
        if numbered:
            if list_type != "ol":
                close_list()
                html_lines.append("<ol>")
                list_type = "ol"
            html_lines.append(f"<li>{linkify_markdown(numbered.group(1))}</li>")
            i += 1
            continue

        if line.startswith("- "):
            if list_type != "ul":
                close_list()
                html_lines.append("<ul>")
                list_type = "ul"
            html_lines.append(f"<li>{linkify_markdown(line[2:])}</li>")
            i += 1
            continue

        close_list()
        html_lines.append(f"<p>{linkify_markdown(line)}</p>")
        i += 1

    close_list()
    return "\n".join(html_lines)


def render_executive_summary(markdown: str) -> str:
    section = extract_markdown_section(
        markdown,
        r"^##\s+1\.\s+Executive Summary.*$",
        r"^##\s+2\.",
    )
    if not section:
        return ""
    return f"""
    <section id="executive-summary" class="narrative">
      <div class="section-title"><h2>Executive Summary 月度核心总结</h2></div>
      {simple_markdown_to_html(section)}
    </section>
    """


def render_watchlists_and_implications(markdown: str) -> str:
    """Render report sections 5-7 that are generated by the monthly prompt."""
    section = extract_markdown_section(
        markdown,
        r"^##\s+5\.\s+Company Watchlist.*$",
        r"^##\s+8\.",
    )
    if not section:
        return ""
    return f"""
    <section id="watchlists" class="narrative">
      <div class="section-title"><h2>Watchlists & Amcor Implications</h2></div>
      {simple_markdown_to_html("## 5. Company Watchlist\n\n" + section)}
    </section>
    """


def render_appendix(weeks: list[dict[str, Any]], articles: list[dict[str, Any]]) -> str:
    """Render the complete traceability list grouped by report week."""
    groups = []
    if weeks:
        groups = [(str(week.get("week", "")), week.get("articles", [])) for week in weeks]
    elif articles:
        groups = [("Articles Reviewed", articles)]
    rendered = []
    for label, week_articles in groups:
        items = []
        for article in week_articles:
            title = esc(article.get("title", ""))
            link = esc(article.get("link", ""))
            linked_title = (
                f'<a href="{link}" target="_blank" rel="noopener">{title}</a>'
                if link
                else title
            )
            items.append(
                f'<li>{esc(text_date(article.get("published", "")))} · '
                f'{linked_title} · {esc(article.get("source_name", ""))}</li>'
            )
        rendered.append(
            f'<div class="appendix-week"><h3>{esc(label)}</h3>'
            f'<ul class="appendix-list">{"".join(items)}</ul></div>'
        )
    return "".join(rendered)


def extract_week_overview(markdown: str, week_label: str) -> str:
    week_match = re.search(rf"^###\s+{re.escape(week_label)}:.*$", markdown, flags=re.M)
    if not week_match:
        return ""
    week_text = markdown[week_match.end() :]
    next_week = re.search(r"^###\s+Week\s+\d+:", week_text, flags=re.M)
    if next_week:
        week_text = week_text[: next_week.start()]
    else:
        next_section = re.search(r"^##\s+", week_text, flags=re.M)
        if next_section:
            week_text = week_text[: next_section.start()]

    overview_match = re.search(r"^####\s+3\.\d+\.1\s+本周概览\s*$", week_text, flags=re.M)
    if not overview_match:
        return week_text.strip()
    overview = week_text[overview_match.end() :]
    next_subsection = re.search(r"^####\s+3\.\d+\.\d+", overview, flags=re.M)
    if next_subsection:
        overview = overview[: next_subsection.start()]
    return overview.strip()


def build_html(report: dict[str, Any]) -> str:
    report_type = str(report.get("report_type", "Pharma") or "Pharma")
    report_title = (
        "Monthly Medical Device News Report"
        if report_type.lower() == "medical device"
        else "Monthly Pharma News Report"
    )
    articles = sorted(
        report.get("articles", []),
        key=lambda item: article_sort_key(item, report_type),
        reverse=True,
    )
    weeks = report.get("weeks", [])
    start = report.get("start_date", "")
    end = report.get("end_date", "")
    generated = report.get("generated_at", "")
    top_articles = report.get("top_opportunity_articles") or articles[:10]
    amcor_high = sum(1 for article in articles if int(article.get("amcor_relevance_score", 0) or 0) >= 4)
    packaging_high = sum(1 for article in articles if str(article.get("packaging_relevance", "")).lower() == "high")
    category_counts = Counter(article.get("primary_category", "其他") for article in articles)
    source_counts = Counter(article.get("source_name", "") for article in articles)
    markdown_report = report.get("markdown_report", "")
    executive_summary_html = render_executive_summary(markdown_report)
    watchlists_html = render_watchlists_and_implications(markdown_report)
    week_overviews = {
        week.get("week", ""): simple_markdown_to_html(extract_week_overview(markdown_report, week.get("week", "")))
        for week in weeks
    }
    appendix_html = render_appendix(weeks, articles)

    top_html = "".join(render_article_card(article, i + 1) for i, article in enumerate(top_articles))
    week_html = "".join(
        render_week(
            week,
            week_overviews.get(week.get("week", ""), ""),
            report_type,
        )
        for week in weeks
    )
    category_html = "".join(
        f'<span class="pill">{esc(name)} <b>{count}</b></span>'
        for name, count in category_counts.most_common()
    )
    source_html = "".join(
        f'<span class="pill pill-muted">{esc(name)} <b>{count}</b></span>'
        for name, count in source_counts.most_common()
    )
    risks_html = render_markdown_summary(markdown_report)

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{esc(report_title)}</title>
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
    .narrative {{
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fbfcfe;
      padding: 18px 20px;
    }}
    .narrative p {{ margin: 8px 0 12px; color: #34465a; }}
    .narrative ol, .narrative ul {{ margin: 8px 0 0; padding-left: 22px; }}
    .narrative li {{ margin: 9px 0; }}
    .markdown-table-wrap {{ overflow-x: auto; margin: 14px 0 18px; border: 1px solid var(--line); border-radius: 8px; }}
    .markdown-table {{ width: 100%; min-width: 900px; border-collapse: collapse; font-size: 13px; background: #fff; }}
    .markdown-table th, .markdown-table td {{ border-bottom: 1px solid #e3e9f0; padding: 9px 10px; text-align: left; vertical-align: top; }}
    .markdown-table th {{ background: #f2f5f9; color: #31465b; font-weight: 720; }}
    .markdown-table tr:last-child td {{ border-bottom: 0; }}
    .week-overview {{
      border-left: 4px solid var(--teal);
      background: #f5fbfc;
      padding: 12px 14px;
      margin: 12px 0 16px;
      border-radius: 0 8px 8px 0;
      color: #31485a;
    }}
    .week-overview h3 {{ font-size: 15px; color: var(--teal); margin-bottom: 4px; }}
    .week-overview p {{ margin: 4px 0; }}
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
    .appendix-week {{ margin: 22px 0 28px; }}
    .appendix-week h3 {{ margin: 0 0 8px; color: #1c3654; }}
    .appendix-list {{ margin: 0; padding-left: 24px; }}
    .appendix-list li {{ margin: 6px 0; }}
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
        <h1>{esc(report_title)}</h1>
        <p>{esc(start)} 至 {esc(end)} · Generated {esc(generated)}</p>
        <div class="nav">
          <a href="#top-opportunities">Top Opportunities</a>
          <a href="#executive-summary">Executive Summary</a>
          <a href="#weeks">Week-by-Week</a>
          <a href="#categories">Categories</a>
          <a href="#watchlists">Watchlists</a>
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

    {executive_summary_html}

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

    {watchlists_html}

    <section id="risks" class="risks">
      {risks_html}
    </section>

    <section id="appendix">
      <div class="section-title"><h2>Appendix: Articles Reviewed</h2></div>
      <div class="appendix-wrap">{appendix_html}</div>
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
