from __future__ import annotations

import argparse
import json
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any


PROJECT_DIR = Path(__file__).resolve().parents[1]
RAW_ARTICLES_PATH = PROJECT_DIR / "data/raw/articles.json"
OUTPUT_DIR = PROJECT_DIR / "data/llm_ready"
OUTPUT_JSON_PATH = OUTPUT_DIR / "articles_llm_ready.json"
OUTPUT_MD_PATH = OUTPUT_DIR / "articles_llm_ready.md"

IMAGE_OCR_QUALITY_NOTE = (
    "图片 OCR 仅供参考，可能存在识别错误。核心分析应优先基于 main_text。"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare WeChat RSS articles for LLM analysis.")
    parser.add_argument("--start", default="", help="Optional start date, YYYY-MM-DD.")
    parser.add_argument("--end", default="", help="Optional end date, YYYY-MM-DD.")
    parser.add_argument(
        "--source-category",
        action="append",
        default=[],
        help=(
            "Optional exact source_category to keep. "
            "Can be used multiple times, for example: "
            "--source-category 医药 --source-category 医药，医疗器械"
        ),
    )
    return parser.parse_args()


def parse_date(value: str) -> date | None:
    value = (value or "").strip()
    if not value:
        return None
    return datetime.strptime(value, "%Y-%m-%d").date()


def article_publish_date(article: dict[str, Any]) -> date | None:
    published = (article.get("published", "") or "").strip()
    if not published:
        return None
    match = re.match(r"(\d{4}-\d{2}-\d{2})", published)
    if not match:
        return None
    return parse_date(match.group(1))


def filter_articles_by_date(
    articles: list[dict[str, Any]],
    start_date: date | None,
    end_date: date | None,
) -> list[dict[str, Any]]:
    if start_date is None and end_date is None:
        return articles

    filtered = []
    for article in articles:
        published_date = article_publish_date(article)
        if published_date is None:
            continue
        if start_date is not None and published_date < start_date:
            continue
        if end_date is not None and published_date > end_date:
            continue
        filtered.append(article)
    return filtered


def filter_articles_by_source_category(
    articles: list[dict[str, Any]],
    source_categories: list[str],
) -> list[dict[str, Any]]:
    allowed_categories = {category.strip() for category in source_categories if category.strip()}
    if not allowed_categories:
        return articles
    return [
        article
        for article in articles
        if str(article.get("source_category", "")).strip() in allowed_categories
    ]


def output_paths(start_date: date | None, end_date: date | None) -> tuple[Path, Path]:
    if start_date is None and end_date is None:
        return OUTPUT_JSON_PATH, OUTPUT_MD_PATH

    if start_date and end_date and start_date.year == end_date.year and start_date.month == end_date.month:
        suffix = f"{start_date.year}_{start_date.month:02d}"
    else:
        start_label = start_date.isoformat() if start_date else "begin"
        end_label = end_date.isoformat() if end_date else "end"
        suffix = f"{start_label}_{end_label}".replace("-", "_")

    return (
        OUTPUT_DIR / f"articles_llm_ready_{suffix}.json",
        OUTPUT_DIR / f"articles_llm_ready_{suffix}.md",
    )


def normalize_text(text: str) -> str:
    text = text or ""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def remove_image_blocks(text: str) -> str:
    if not text:
        return ""

    text = re.sub(r"\s*\[图片OCR文字\]\s*.*$", "", text, flags=re.S)
    text = re.sub(r"\s*\[图片信息\]\s*.*$", "", text, flags=re.S)

    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            lines.append("")
            continue
        if re.fullmatch(r"图片\d+:\s*https?://\S+.*", stripped):
            continue
        if re.fullmatch(r"https?://\S+", stripped):
            continue
        lines.append(line)

    return normalize_text("\n".join(lines))


def normalize_tags(tags: Any) -> list[str]:
    if isinstance(tags, list):
        return [str(tag) for tag in tags if str(tag).strip()]
    if isinstance(tags, str):
        return [tag.strip() for tag in tags.split(",") if tag.strip()]
    return []


def build_llm_input_text(article: dict[str, Any]) -> str:
    tags_text = "、".join(article["source_tags"])
    image_ocr_text = article.get("image_ocr_text", "") or ""

    return normalize_text(
        f"""标题：{article["title"]}
来源：{article["source_name"]}
发布时间：{article["published"]}
分类：{article["source_category"]}
标签：{tags_text}
原文链接：{article["link"]}

正文：
{article["main_text"]}

图片 OCR 补充信息：
{image_ocr_text}

注意：{IMAGE_OCR_QUALITY_NOTE}"""
    )


def prepare_article(raw_article: dict[str, Any]) -> dict[str, Any]:
    main_text = remove_image_blocks(raw_article.get("content_text", "") or "")
    source_tags = normalize_tags(raw_article.get("source_tags", []))
    image_ocr_text = normalize_text(raw_article.get("image_ocr_text", "") or "")
    image_urls = raw_article.get("image_urls", [])
    if not isinstance(image_urls, list):
        image_urls = []

    prepared = {
        "title": raw_article.get("title", "") or "",
        "source_name": raw_article.get("source_name", "") or "",
        "source_category": raw_article.get("source_category", "") or "",
        "source_tags": source_tags,
        "source_priority": raw_article.get("source_priority", "") or "",
        "link": raw_article.get("link", "") or "",
        "published": raw_article.get("published", "") or "",
        "article_id": raw_article.get("article_id", "") or raw_article.get("link", "") or "",
        "scraped_at": raw_article.get("scraped_at", "") or "",
        "main_text": main_text,
        "word_count": len(main_text),
        "main_text_preview": main_text[:1000],
        "text_length": len(main_text),
        "image_count": int(raw_article.get("image_count", 0) or 0),
        "image_urls": image_urls,
        "image_ocr_text": image_ocr_text,
        "image_ocr_quality_note": IMAGE_OCR_QUALITY_NOTE,
        "fetch_status": raw_article.get("fetch_status", "") or "",
    }
    prepared["llm_input_text"] = build_llm_input_text(prepared)
    return prepared


def load_raw_articles() -> list[dict[str, Any]]:
    if not RAW_ARTICLES_PATH.exists():
        raise FileNotFoundError(f"Input file not found: {RAW_ARTICLES_PATH}")
    with RAW_ARTICLES_PATH.open("r", encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, list):
        raise ValueError("data/raw/articles.json must be a list of article dicts.")
    return [item for item in data if isinstance(item, dict)]


def save_json(articles: list[dict[str, Any]], output_path: Path) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as file:
        json.dump(articles, file, ensure_ascii=False, indent=2)


def markdown_escape_title(title: str) -> str:
    return title.replace("\n", " ").strip() or "Untitled"


def save_markdown(articles: list[dict[str, Any]], output_path: Path) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    parts = [
        "# Articles LLM Ready",
        "",
        f"Total articles: {len(articles)}",
        "",
    ]

    for index, article in enumerate(articles, start=1):
        tags_text = "、".join(article.get("source_tags", []))
        parts.extend(
            [
                "---",
                "",
                f"## {index}. {markdown_escape_title(article.get('title', ''))}",
                "",
                f"- 来源：{article.get('source_name', '')}",
                f"- 发布时间：{article.get('published', '')}",
                f"- 分类：{article.get('source_category', '')}",
                f"- 标签：{tags_text}",
                f"- 原文链接：{article.get('link', '')}",
                f"- 正文长度：{article.get('text_length', 0)}",
                f"- 图片数量：{article.get('image_count', 0)}",
                "",
                "### 正文",
                "",
                article.get("main_text", ""),
                "",
                "### 图片 OCR 补充信息",
                "",
                article.get("image_ocr_text", "") or "无",
                "",
                f"> {IMAGE_OCR_QUALITY_NOTE}",
                "",
            ]
        )

    output_path.write_text("\n".join(parts), encoding="utf-8")


def main() -> int:
    args = parse_args()
    start_date = parse_date(args.start)
    end_date = parse_date(args.end)
    if start_date and end_date and start_date > end_date:
        raise ValueError("--start must be earlier than or equal to --end")

    raw_articles = load_raw_articles()
    date_filtered_articles = filter_articles_by_date(raw_articles, start_date, end_date)
    filtered_raw_articles = filter_articles_by_source_category(
        date_filtered_articles,
        args.source_category,
    )
    prepared_articles = [prepare_article(article) for article in filtered_raw_articles]
    empty_main_text_articles = [
        article.get("title", "") or article.get("article_id", "")
        for article in prepared_articles
        if not article.get("main_text")
    ]
    json_path, md_path = output_paths(start_date, end_date)

    save_json(prepared_articles, json_path)
    save_markdown(prepared_articles, md_path)

    print("LLM-ready 数据清洗完成")
    if start_date or end_date:
        print(f"- 日期范围: {start_date or 'begin'} 至 {end_date or 'end'}")
    print(f"- 原始文章总数: {len(raw_articles)}")
    print(f"- 日期过滤后文章数: {len(date_filtered_articles)}")
    if args.source_category:
        print(f"- source_category 过滤: {', '.join(args.source_category)}")
        print(f"- category 过滤后文章数: {len(filtered_raw_articles)}")
    print(f"- 成功生成多少篇 LLM-ready 文章: {len(prepared_articles)}")
    print(f"- 正文为空的文章数量: {len(empty_main_text_articles)}")
    if empty_main_text_articles:
        print("- 正文为空的文章:")
        for title in empty_main_text_articles:
            print(f"  - {title}")
    print(f"- JSON 输出文件: {json_path}")
    print(f"- Markdown 输出文件: {md_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
