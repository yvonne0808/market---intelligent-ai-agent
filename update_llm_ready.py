from __future__ import annotations

import json
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_DIR = Path(__file__).resolve().parent
LLM_READY_DIR = PROJECT_DIR / "data/llm_ready"
INPUT_JSON_PATH = LLM_READY_DIR / "articles_llm_ready.json"
OUTPUT_JSON_PATH = LLM_READY_DIR / "articles_llm_ready.json"
OUTPUT_MD_PATH = LLM_READY_DIR / "articles_llm_ready.md"
BACKUP_DIR = LLM_READY_DIR / "backup"

IMAGE_OCR_QUALITY_NOTE = (
    "图片 OCR 仅供参考，可能存在识别错误，尤其是图表、表格、坐标轴和数字。"
    "核心分析应优先基于 main_text。"
)

FINAL_FIELDS = [
    "title",
    "source_name",
    "source_category",
    "source_tags",
    "source_priority",
    "link",
    "published",
    "article_id",
    "scraped_at",
    "fetch_status",
    "fetch_error",
    "content_source",
    "image_count",
    "image_urls",
    "image_ocr_text",
    "image_fetch_status",
    "image_fetch_error",
    "image_ocr_quality_note",
    "main_text",
    "main_text_preview",
    "text_length",
    "word_count",
    "has_full_text",
    "has_image_ocr",
    "data_quality_score",
    "data_quality_note",
    "llm_input_text",
    "llm_input_text_with_ocr",
]


def normalize_text(text: str) -> str:
    text = str(text or "")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\u00a0", " ")
    text = re.sub(r"[\u200b\u200c\u200d\ufeff]", "", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def strip_html(text: str) -> str:
    text = re.sub(r"<script\b[^>]*>.*?</script>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<style\b[^>]*>.*?</style>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    return text


def remove_image_noise(text: str) -> str:
    if not text:
        return ""

    text = strip_html(text)
    text = re.sub(r"\s*\[图片OCR文字\]\s*.*$", "", text, flags=re.S)
    text = re.sub(r"\s*\[图片信息\]\s*.*?(?=\n\n\S|$)", "\n\n", text, flags=re.S)
    text = re.sub(r"\s*\[图片信息\]\s*.*$", "", text, flags=re.S)

    cleaned_lines: list[str] = []
    seen_image_lines: set[str] = set()
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            cleaned_lines.append("")
            continue

        if re.search(r"https?://mmbiz\.qpic\.cn/\S+", stripped):
            continue
        if re.fullmatch(r"https?://\S+", stripped):
            continue
        if re.fullmatch(r"图片\d+:\s*https?://\S+.*", stripped):
            if stripped in seen_image_lines:
                continue
            seen_image_lines.add(stripped)
            continue

        cleaned_lines.append(line)

    text = "\n".join(cleaned_lines)
    text = re.sub(r"https?://mmbiz\.qpic\.cn/\S+", "", text)
    return fix_abnormal_spacing(normalize_text(text))


def fix_abnormal_spacing(text: str) -> str:
    replacements = {
        "糖尿 病": "糖尿病",
        "贫 血": "贫血",
        "皮 炎": "皮炎",
        "抑 制 剂": "抑制剂",
        "C FB": "CFB",
        "1 0 款": "10 款",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)

    text = re.sub(r"\b([A-Z])\s+([A-Z]{2,})\b", r"\1\2", text)
    text = re.sub(r"\b(\d)\s+(\d)\s+(款|个|项|笔|亿美元|亿元|美元|元)\b", r"\1\2 \3", text)
    return normalize_text(text)


def normalize_tags(tags: Any) -> list[str]:
    if isinstance(tags, list):
        return [str(tag).strip() for tag in tags if str(tag).strip()]
    if isinstance(tags, str):
        return [tag.strip() for tag in re.split(r"[,，、]", tags) if tag.strip()]
    return []


def dedupe_list(items: Any) -> list[str]:
    if not isinstance(items, list):
        return []
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        value = str(item).strip()
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def calculate_quality_score(article: dict[str, Any]) -> int:
    score = 0
    main_text = article.get("main_text", "") or ""
    text_length = len(main_text)

    if article.get("fetch_status") == "success":
        score += 40

    if text_length > 1000:
        score += 40
    elif 500 <= text_length <= 1000:
        score += 25

    if article.get("image_ocr_text"):
        score += 10

    if article.get("image_urls"):
        score += 5

    score = min(score, 100)
    if not main_text:
        score = min(score, 30)
    return score


def build_quality_note(article: dict[str, Any]) -> str:
    main_text = article.get("main_text", "") or ""
    has_ocr = bool(article.get("image_ocr_text"))

    if not main_text:
        return "正文为空，仅有标题和链接，不适合深度分析。"
    if len(main_text) < 500:
        return "正文较短，LLM 分析时需要谨慎。"
    if has_ocr:
        return "正文抓取完整，适合 LLM 分析；图片 OCR 可作为辅助参考。"
    return "正文可用，适合基于正文进行分析。"


def build_llm_input_text(article: dict[str, Any]) -> str:
    tags_text = "、".join(article.get("source_tags", []))
    return normalize_text(
        f"""标题：{article.get("title", "")}
来源：{article.get("source_name", "")}
发布时间：{article.get("published", "")}
分类：{article.get("source_category", "")}
标签：{tags_text}
原文链接：{article.get("link", "")}

正文：
{article.get("main_text", "")}

数据质量说明：
{article.get("data_quality_note", "")}"""
    )


def build_llm_input_text_with_ocr(article: dict[str, Any]) -> str:
    base_text = build_llm_input_text(article)
    return normalize_text(
        f"""{base_text}

图片 OCR 补充信息：
{article.get("image_ocr_text", "")}

注意：图片 OCR 仅供参考，可能存在识别错误。核心分析应优先基于正文 main_text。"""
    )


def clean_article(raw: dict[str, Any]) -> dict[str, Any]:
    main_text_source = raw.get("main_text")
    if main_text_source is None:
        main_text_source = raw.get("content_text", "")
    main_text = remove_image_noise(str(main_text_source or ""))

    image_urls = dedupe_list(raw.get("image_urls", []))
    image_ocr_text = fix_abnormal_spacing(normalize_text(raw.get("image_ocr_text", "") or ""))

    content_source = raw.get("content_source", "") or ""
    fetch_status = raw.get("fetch_status", "") or ""
    if fetch_status == "success" and main_text and not content_source:
        content_source = "wechat_page"

    article = {
        "title": raw.get("title", "") or "",
        "source_name": raw.get("source_name", "") or "",
        "source_category": raw.get("source_category", "") or "",
        "source_tags": normalize_tags(raw.get("source_tags", [])),
        "source_priority": raw.get("source_priority", "") or "",
        "link": raw.get("link", "") or "",
        "published": raw.get("published", "") or "",
        "article_id": raw.get("article_id", "") or raw.get("link", "") or "",
        "scraped_at": raw.get("scraped_at", "") or "",
        "fetch_status": fetch_status,
        "fetch_error": raw.get("fetch_error", "") or "",
        "content_source": content_source,
        "image_count": int(raw.get("image_count", 0) or len(image_urls)),
        "image_urls": image_urls,
        "image_ocr_text": image_ocr_text,
        "image_fetch_status": raw.get("image_fetch_status", "") or "",
        "image_fetch_error": raw.get("image_fetch_error", "") or "",
        "image_ocr_quality_note": IMAGE_OCR_QUALITY_NOTE,
        "main_text": main_text,
        "main_text_preview": main_text[:1000],
        "text_length": len(main_text),
        "word_count": len(main_text),
        "has_full_text": len(main_text) > 500,
        "has_image_ocr": bool(image_ocr_text),
    }
    article["data_quality_score"] = calculate_quality_score(article)
    article["data_quality_note"] = build_quality_note(article)
    article["llm_input_text"] = build_llm_input_text(article)
    article["llm_input_text_with_ocr"] = build_llm_input_text_with_ocr(article)

    return {field: article.get(field) for field in FINAL_FIELDS}


def backup_input_file() -> Path:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = BACKUP_DIR / f"articles_llm_ready_backup_{timestamp}.json"
    shutil.copy2(INPUT_JSON_PATH, backup_path)
    return backup_path


def load_articles() -> list[dict[str, Any]]:
    if not INPUT_JSON_PATH.exists():
        raise FileNotFoundError(f"Input file not found: {INPUT_JSON_PATH}")
    data = json.loads(INPUT_JSON_PATH.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("articles_llm_ready.json must be a list of dicts.")
    return [item for item in data if isinstance(item, dict)]


def save_json(articles: list[dict[str, Any]]) -> None:
    OUTPUT_JSON_PATH.write_text(
        json.dumps(articles, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def save_markdown(articles: list[dict[str, Any]]) -> None:
    parts: list[str] = []
    for article in articles:
        tags_text = "、".join(article.get("source_tags", []))
        parts.extend(
            [
                f"# {article.get('title', '') or 'Untitled'}",
                "",
                f"来源：{article.get('source_name', '')}  ",
                f"发布时间：{article.get('published', '')}  ",
                f"分类：{article.get('source_category', '')}  ",
                f"标签：{tags_text}  ",
                f"原文链接：{article.get('link', '')}  ",
                f"数据质量分：{article.get('data_quality_score', 0)}  ",
                f"数据质量说明：{article.get('data_quality_note', '')}  ",
                "",
                "## 正文",
                "",
                article.get("main_text", "") or "无",
                "",
                "## 图片 OCR 补充信息",
                "",
                article.get("image_ocr_text", "") or "无",
                "",
                "---",
                "",
            ]
        )
    OUTPUT_MD_PATH.write_text("\n".join(parts), encoding="utf-8")


def main() -> int:
    raw_articles = load_articles()
    backup_path = backup_input_file()
    cleaned_articles = [clean_article(article) for article in raw_articles]

    save_json(cleaned_articles)
    save_markdown(cleaned_articles)

    full_text_count = sum(1 for article in cleaned_articles if article["has_full_text"])
    empty_text_count = sum(1 for article in cleaned_articles if not article["main_text"])
    image_ocr_count = sum(1 for article in cleaned_articles if article["has_image_ocr"])

    print("现有 LLM-ready 文件二次清洗完成")
    print(f"- 总共读取多少篇文章: {len(raw_articles)}")
    print(f"- 成功更新多少篇文章: {len(cleaned_articles)}")
    print(f"- 有完整正文多少篇: {full_text_count}")
    print(f"- 正文为空多少篇: {empty_text_count}")
    print(f"- 有图片 OCR 多少篇: {image_ocr_count}")
    print(f"- 已备份到: {backup_path}")
    print(f"- 更新后的 JSON 保存到: {OUTPUT_JSON_PATH}")
    print(f"- Markdown 保存到: {OUTPUT_MD_PATH}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
