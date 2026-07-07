# WeChat RSS Data Collector

这个项目用于读取 WeWe RSS 生成的微信公众号 RSS Feed，并把文章元数据和正文内容保存成结构化文件，然后交给 LLM 做医药行业和 Amcor 包装业务相关性分析，最后生成 weekly / monthly report。

当前流程包括：

1. 抓取公众号 RSS 文章和正文。
2. 清洗成 LLM-ready 数据。
3. 使用 DeepSeek API 分析文章价值、Amcor 相关性和包装机会。
4. 生成 Markdown / JSON 月报。
5. 可选转换成 PDF 或更适合阅读的 HTML report。

## 和 WeWe RSS 的关系

WeWe RSS 负责把微信公众号文章转换成 RSS Feed URL。

本项目负责读取这些 RSS Feed，解析文章列表，尝试抓取正文，并保存为 CSV、JSON 和 Excel。

你的 WeWe RSS 项目目录是：

```text
/Users/yvonne/Desktop/forecasting/wewe-rss-local
```

你的采集项目目录是：

```text
/Users/yvonne/Desktop/forecasting/wechat-rss-data-collector
```

两个项目是分开的。本项目不会修改 WeWe RSS 的 `docker-compose.yml`，也不会直接操作 WeWe RSS 的 SQLite 数据库。

## 为什么不要修改 WeWe RSS 的数据库

WeWe RSS 的数据库位于：

```text
/Users/yvonne/Desktop/forecasting/wewe-rss-local/data/wewe-rss.db
```

这个数据库是 WeWe RSS 自己使用的内部数据，包括账号、公众号源、文章记录等。直接改数据库容易造成 WeWe RSS 后台异常、数据损坏、登录状态丢失或后续升级失败。

正确做法是：让 WeWe RSS 正常输出 RSS Feed，本项目只读取 RSS URL。

## 如何创建项目目录

项目目录为：

```text
/Users/yvonne/Desktop/forecasting/wechat-rss-data-collector
```

目录结构：

```text
wechat-rss-data-collector/
  main.py
  config.yaml
  requirements.txt
  seen_articles.json
  README.md
  data/
    raw/
    logs/
```

## 如何安装依赖

打开 Terminal，进入项目目录：

```bash
cd /Users/yvonne/Desktop/forecasting/wechat-rss-data-collector
```

建议先创建虚拟环境：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

如果系统提示找不到 `python3` 或 `pip`，说明 Mac 上还没有安装 Python，需要先安装 Python。

## 如何配置 DeepSeek API

复制环境变量模板：

```bash
cp .env.example .env
```

然后在 `.env` 里填写：

```text
DEEPSEEK_API_KEY=your_deepseek_api_key_here
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
```

`.env` 不会上传到 GitHub。

## 如何运行

确保 WeWe RSS 已经在本地运行，并且浏览器可以打开：

```text
http://localhost:8001
```

然后在项目目录运行：

```bash
cd /Users/yvonne/Desktop/forecasting/wechat-rss-data-collector
.venv/bin/python main.py
```

运行结束后，终端会输出本次读取了多少篇文章、新增了多少篇、正文抓取成功和失败数量，以及输出文件位置。

## config.yaml 字段说明

当前配置文件保存所有公众号 Feed URL，例如：

```yaml
feeds:
  - name: "丁香园 Insight 数据库"
    url: "http://localhost:8001/feeds/MP_WXS_3975077766.atom?limit=100"
    category: "新药研发"
    tags: ["创新药", "药企动态", "NMPA", "临床试验", "新药上市", "药企出海"]
    priority: "high"
```

字段含义：

`name`：公众号名称，用于标记文章来源。

`url`：WeWe RSS 生成的 RSS Feed URL。

`category`：你给这个公众号设置的业务分类。

`tags`：你给这个公众号设置的标签，后续 LLM 分析时可以作为上下文。

`priority`：公众号优先级，例如 `high`、`medium`、`low`。

`collector.output_dir`：文章数据保存目录，当前是 `data/raw`。

`collector.log_dir`：运行日志保存目录，当前是 `data/logs`。

`collector.sleep_seconds_min` 和 `collector.sleep_seconds_max`：抓取微信原文页面之间的随机等待时间，避免请求太密集。

`collector.extract_images`：是否从文章 HTML 中提取图片链接和图片说明。

`collector.backfill_existing_images`：是否给已经抓过的旧文章补充图片信息。

`collector.ocr_images`：是否尝试识别图片里的文字。默认是 `false`，因为需要本机额外安装 OCR 工具。

`collector.ocr_language`：OCR 语言，中文和英文可用 `chi_sim+eng`。

`collector.image_dir`：如果开启 OCR，下载的图片会保存到这个目录。

## 抓取后的文章保存在哪里

抓取结果会保存到：

```text
/Users/yvonne/Desktop/forecasting/wechat-rss-data-collector/data/raw/articles.csv
/Users/yvonne/Desktop/forecasting/wechat-rss-data-collector/data/raw/articles.json
/Users/yvonne/Desktop/forecasting/wechat-rss-data-collector/data/raw/articles.xlsx
```

文件用途：

`articles.csv`：适合 Excel、Numbers 或 pandas 快速查看。

`articles.json`：保留完整结构化字段，推荐下一步 LLM 分析优先读取。

`articles.xlsx`：适合人工检查和筛选。

图片相关字段：

`image_count`：文章中发现的图片数量。

`image_urls`：文章图片链接列表。

`image_ocr_text`：如果开启 OCR，这里保存图片识别出的文字。

`image_fetch_status`：图片信息处理状态。

`image_fetch_error`：图片信息处理失败原因。

程序会把图片链接、alt、title 等信息追加到 `content_text` 末尾的 `[图片信息]` 区域。如果开启 OCR，图片识别文字会追加到 `[图片OCR文字]` 区域。

去重记录保存在：

```text
/Users/yvonne/Desktop/forecasting/wechat-rss-data-collector/seen_articles.json
```

## 下一步 LLM 分析优先读取哪个文件

推荐优先读取：

```text
data/raw/articles.json
```

原因是 JSON 能保留完整字段结构，包括标题、链接、发布时间、来源标签、正文、抓取状态和失败原因。

如果已经运行过 LLM 数据清洗脚本，则更推荐优先读取：

```text
data/llm_ready/articles_llm_ready.json
```

这个文件会移除过长的 `content_html`，清理正文里重复混入的图片信息块，并把正文主体和图片 OCR 内容分开保存，更适合直接交给 DeepSeek、GPT 或其他 LLM 做分析。

## 如何生成 LLM-ready 数据

原始抓取文件是：

```text
data/raw/articles.json
```

这个文件保留了完整抓取结果，包括 `content_html`、`content_text`、`image_urls`、`image_ocr_text` 等字段。它适合做原始备份，但不适合直接全部塞给 LLM，因为 HTML 很长，图片 OCR 也可能比较乱。

运行清洗脚本：

```bash
cd /Users/yvonne/Desktop/forecasting/wechat-rss-data-collector
.venv/bin/python prepare_llm_data.py
```

清洗后会生成：

```text
data/llm_ready/articles_llm_ready.json
data/llm_ready/articles_llm_ready.md
```

如果只想处理某个月，例如 2026 年 6 月：

```bash
.venv/bin/python prepare_llm_data.py --start 2026-06-01 --end 2026-06-30
```

## 如何分析文章

```bash
.venv/bin/python analyze_articles.py --start 2026-06-01 --end 2026-06-30 --force
```

分析结果会保存到：

```text
data/analyzed/articles_analyzed.json
```

## 如何生成月报

```bash
.venv/bin/python generate_monthly_report.py --start 2026-06-01 --end 2026-06-30
```

输出会保存到：

```text
reports/monthly_report_20260601_20260630.md
reports/monthly_report_20260601_20260630.json
```

## 如何生成更适合阅读的版本

把月报 Markdown 转成 PDF：

```bash
.venv/bin/python scripts/convert_monthly_markdown_to_pdf.py reports/monthly_report_20260601_20260630.md reports/monthly_report_20260601_20260630.pdf
```

把月报 JSON 转成浏览器可读的 HTML dashboard：

```bash
.venv/bin/python scripts/generate_readable_monthly_html.py reports/monthly_report_20260601_20260630.json reports/monthly_report_20260601_20260630.html
```

## Amcor 上下文

Amcor APAC 的重点区域、重点客户、重点产品和新闻优先级信号保存在：

```text
prompts/amcor_apac_context.txt
```

文章分析和 monthly / weekly report 生成都会读取这份上下文。

`articles_llm_ready.json` 是下一步程序化 LLM 分析推荐读取的文件。

`articles_llm_ready.md` 是方便人工快速检查的 Markdown 文件。

清洗后的每篇文章会保留：

```text
title
source_name
source_category
source_tags
source_priority
link
published
article_id
scraped_at
main_text
word_count
main_text_preview
text_length
image_count
image_urls
image_ocr_text
image_ocr_quality_note
fetch_status
llm_input_text
```

其中：

`main_text`：清理后的正文主体，不包含 `content_html`，也会尽量移除 `[图片信息]` 和 `[图片OCR文字]` 这类重复块。

`image_ocr_text`：图片 OCR 结果单独保存，不和正文主体混在一起。

`image_ocr_quality_note`：提醒 LLM 图片 OCR 可能有识别错误，核心分析优先基于正文。

`llm_input_text`：已经拼好的单篇文章 LLM 输入文本，可以直接用于下一步分析。

## 如何清洗现有 LLM-ready 文件

如果已经有这个文件：

```text
data/llm_ready/articles_llm_ready.json
```

并且只是想在它的基础上做二次清洗，不想重新读取 `data/raw/articles.json`，运行：

```bash
cd /Users/yvonne/Desktop/forecasting/wechat-rss-data-collector
.venv/bin/python update_llm_ready.py
```

这个脚本的输入文件是：

```text
data/llm_ready/articles_llm_ready.json
```

运行时会先自动备份旧文件到：

```text
data/llm_ready/backup/articles_llm_ready_backup_YYYYMMDD_HHMMSS.json
```

然后更新同名 JSON 文件：

```text
data/llm_ready/articles_llm_ready.json
```

同时重新生成方便人工检查的 Markdown 文件：

```text
data/llm_ready/articles_llm_ready.md
```

二次清洗会移除不适合 LLM 的字段，例如 `content_html`、`feed_url`、`rss_summary` 和原始 `content_text`，并生成更干净的：

```text
main_text
main_text_preview
text_length
has_full_text
has_image_ocr
data_quality_score
data_quality_note
llm_input_text
```

后续 DeepSeek / GPT 分析应该读取更新后的：

```text
data/llm_ready/articles_llm_ready.json
```

## DeepSeek 文章分析和 Weekly Report

本项目可以在不重新抓取公众号、不修改 WeWe RSS、不修改爬虫的前提下，基于现有 LLM-ready 文件做 DeepSeek 分析，并生成适合 internship weekly report 的周报。

输入文件：

```text
data/llm_ready/articles_llm_ready.json
```

第一版默认使用每篇文章的：

```text
llm_input_text
```

也就是不默认传入图片 OCR。只有显式加 `--include-ocr` 时，才会使用：

```text
llm_input_text_with_ocr
```

### 配置 DeepSeek API Key

先复制环境变量模板：

```bash
cd /Users/yvonne/Desktop/forecasting/wechat-rss-data-collector
cp .env.example .env
```

然后打开 `.env`，填写你的 DeepSeek API key：

```text
DEEPSEEK_API_KEY=your_deepseek_api_key_here
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
```

注意：不要把公司内部敏感信息、客户隐私、未公开项目资料传给外部 API。当前脚本只读取本地公众号文章分析文件。

### 运行单篇文章分析

按日期范围分析文章：

```bash
cd /Users/yvonne/Desktop/forecasting/wechat-rss-data-collector
.venv/bin/python analyze_articles.py --start 2026-06-27 --end 2026-07-03
```

默认会跳过已经分析过的文章，避免重复调用 API。

如果要重新分析同一批文章，使用：

```bash
.venv/bin/python analyze_articles.py --start 2026-06-27 --end 2026-07-03 --force
```

如果某些文章图表很多，需要把 OCR 文本也传给 DeepSeek，使用：

```bash
.venv/bin/python analyze_articles.py --start 2026-06-27 --end 2026-07-03 --include-ocr
```

输出文件：

```text
data/analyzed/articles_analyzed.json
```

脚本会每分析完一篇文章就保存一次，避免中途失败导致结果全部丢失。

### 生成 Weekly Report

在已经完成文章分析后，运行：

```bash
cd /Users/yvonne/Desktop/forecasting/wechat-rss-data-collector
.venv/bin/python generate_weekly_report.py --start 2026-06-27 --end 2026-07-03
```

默认只纳入：

```text
include_in_weekly_report = true
relevance_score >= 12
```

输出文件：

```text
reports/weekly_report_YYYYMMDD.md
reports/weekly_report_YYYYMMDD.json
```

Markdown 文件适合人工阅读和提交 internship weekly report。JSON 文件保留本次周报的结构化输入和最终报告文本，方便后续追溯。

### DeepSeek 输出核验注意事项

DeepSeek 输出需要保留 source link，方便人工核验。

图片 OCR 仅供参考，尤其是图表、表格、坐标轴和数字可能有识别错误。

BD 交易金额可能包含 milestone，不等于真实现金收入。

公众号文章本身也需要结合公告、NMPA / CDE、公司新闻稿等官方来源进一步确认。

## 如何重置测试

如果你想让程序重新抓取已经抓过的文章，可以删除：

```text
seen_articles.json
```

或者把它改回：

```json
{
  "updated_at": null,
  "seen_articles": []
}
```

如果你想清空全部抓取结果，可以删除或清空：

```text
data/raw/articles.csv
data/raw/articles.json
data/raw/articles.xlsx
```

然后重新运行：

```bash
python3 main.py
```

## 如何让 WeWe RSS 返回更多文章

在 RSS URL 后面加 `?limit=100` 可以让 WeWe RSS 返回更多文章，例如：

```text
http://localhost:8001/feeds/MP_WXS_3975077766.atom?limit=100
```

当前测试配置已经使用了这个参数。

## 为什么有些微信文章正文可能抓不到

微信文章正文可能抓不到，常见原因包括：

微信有反爬限制。

文章需要特定登录状态或访问权限。

微信页面结构变化，导致 `div#js_content` 不存在。

文章链接失效或被删除。

网络请求被拒绝、超时或返回验证码页面。

程序不会因为单篇正文抓取失败而崩溃。失败原因会记录在 `fetch_error` 字段和日志文件里。

## 如何开启图片 OCR

当前脚本默认会把文章图片链接和图片说明补进 `content_text`，但不会自动识别图片里的文字。

如果你希望识别图片里的表格、截图、海报文字，可以先安装 Tesseract：

```bash
brew install tesseract tesseract-lang
```

然后把 `config.yaml` 里的：

```yaml
ocr_images: false
```

改成：

```yaml
ocr_images: true
```

再次运行：

```bash
python3 main.py
```

注意：OCR 对截图、表格、药品名和中英文混排内容不一定完全准确，但通常比完全忽略图片信息更有用。完整文章分析仍然推荐优先读取 `data/raw/articles.json`。

## 常见错误排查

### localhost:8001 打不开

先确认 WeWe RSS 容器是否还在运行：

```bash
cd /Users/yvonne/Desktop/forecasting/wewe-rss-local
docker compose ps
```

如果没有运行，启动：

```bash
docker compose up -d
```

### RSS URL 打不开

先在浏览器打开：

```text
http://localhost:8001/feeds/MP_WXS_3975077766.atom?limit=100
```

如果浏览器也打不开，说明 WeWe RSS 没有正常返回这个公众号的 Feed。需要回到 WeWe RSS 后台确认公众号源是否已添加成功。

### feedparser 解析不到文章

可能是 RSS URL 不正确、公众号源没有文章、WeWe RSS 返回了错误页面，或者 WeWe RSS 还没有同步到文章。

可以先打开 RSS URL，确认页面里是否有 `<entry>` 或文章标题。

### 微信正文抓取失败

这不一定是程序错误。微信页面可能限制访问，或者页面结构变化。程序会继续保存文章元数据，并把 `fetch_status` 标记为 `failed`。

### 没有新文章

如果终端输出：

```text
没有发现新文章，可能是 seen_articles.json 已经记录过这些文章。
```

说明这些文章之前已经抓过。程序会用 `seen_articles.json` 去重，避免重复保存。

### Excel 文件打不开

先关闭已经打开的 `articles.xlsx`，再重新运行程序。Excel 或 Numbers 打开文件时，可能会锁定文件，导致程序无法写入。

### config.yaml 格式错误

YAML 对缩进敏感。请保持空格缩进，不要用 Tab。列表项前面使用 `-`。

如果运行时报 YAML 解析错误，重点检查引号、冒号和缩进。

### seen_articles.json 导致重复文章不再保存

这是正常去重行为。如果测试时想重新保存所有文章，可以重置 `seen_articles.json`，或者删除它后重新运行。
