# Mentor 手册命令与输出映射

## 固定项目位置

在 Codex 中打开的项目根目录应是：

```text
monthly-report-library/
```

所有命令使用项目根目录中的 `.venv/bin/python`。不要使用系统 Python，也不要把 `.env` 内容复制到聊天中。

## Step 1：同步 GitHub 项目

Codex 执行：

```bash
git status -sb
git pull --ff-only
git log -1 --oneline
```

外部网络动作：GitHub pull。成功标志：pull 完成、没有冲突，终端显示最新 commit。

## Step 2：确认 WeWe RSS

WeWe RSS 是同级独立项目 `/Users/yvonne/Desktop/forecasting/wewe-rss-local`，默认服务地址 `http://localhost:8001`。Codex 先检查服务和 Docker 状态，mentor 在浏览器中完成微信扫码。不要直接修改 `wewe-rss.db`。

## Step 3：刷新到最新文章日期

mentor 在 WeWe RSS 页面点击刷新/同步，Codex 再用浏览器或 HTTP 检查页面可访问。成功标志：目标公众号源仍存在，并且文章列表的最新日期已更新到预期日期。此步不调用 DeepSeek。

## Step 4：采集和日期筛选

先抓取全部已配置 feed：

```bash
.venv/bin/python china-wechat-med-phar/scripts/main.py
```

主要输出：

```text
china-wechat-med-phar/data/raw/articles.json
china-wechat-med-phar/data/raw/articles.csv
china-wechat-med-phar/data/raw/articles.xlsx
```

按包含起止日期准备 LLM 输入，例如：

```bash
.venv/bin/python china-wechat-med-phar/scripts/prepare_llm_data.py \
  --start 2026-08-01 --end 2026-08-31 \
  --source-category 医药 \
  --source-category 医疗器械
```

日期规则：文章日期小于开始日期或大于结束日期会被排除，因此开始日和结束日都包含。主要输出：

```text
china-wechat-med-phar/data/llm_ready/articles_llm_ready_2026_08.json
china-wechat-med-phar/data/llm_ready/articles_llm_ready_2026_08.md
```

成功标志：终端显示抓取统计；JSON 存在；日期检查没有超出指定区间；医药和医疗器械数量均已记录。

## Step 5：分别分析两条业务线

### Pharma

```bash
.venv/bin/python china-wechat-med-phar/scripts/analyze_pharma_articles.py \
  --input china-wechat-med-phar/data/llm_ready/articles_llm_ready_2026_08.json \
  --output china-wechat-med-phar/data/analyzed/articles_analyzed.json \
  --selected-output china-wechat-med-phar/data/analyzed/Pharma/articles_analyzed_2026_08.json \
  --start 2026-08-01 --end 2026-08-31 \
  --smart-new-only --skip-empty-text --workers 1
```

该脚本调用 DeepSeek，按 `article_id` 增量保存，默认跳过已分析文章，并记录 processed/skipped/failed 数量。

### Medical Device

```bash
.venv/bin/python china-wechat-med-phar/scripts/analyze_medical_device_articles.py \
  --input china-wechat-med-phar/data/llm_ready/articles_llm_ready_2026_08.json \
  --output "china-wechat-med-phar/data/analyzed/Medical Device/articles_analyzed_2026_08.json" \
  --start 2026-08-01 --end 2026-08-31 --workers 1
```

该脚本调用 DeepSeek，跳过目标输出中已有的 article ID，并在每篇完成后写回 JSON。不要随意使用 `--force`，因为它会重复调用 API。

成功标志：两条线分别显示选中、已分析、失败数量；输出 JSON 存在；失败数量为 0，或已记录失败标题和原因。此步完成后停止。

## Step 6：生成月报

只有 mentor 确认 Step 5 分析完成后才运行。

### Pharma monthly report

```bash
.venv/bin/python china-wechat-med-phar/scripts/generate_pharma_monthly_report.py \
  --input china-wechat-med-phar/data/analyzed/articles_analyzed.json \
  --start 2026-08-01 --end 2026-08-31
```

生成 `china-wechat-med-phar/reports/Pharma/monthly_report_20260801_20260831.md` 和 `.json`。此生成器会再次调用 DeepSeek 形成月报文本。

### Medical Device monthly report

```bash
.venv/bin/python china-wechat-med-phar/scripts/generate_medical_device_monthly_report.py \
  --input "china-wechat-med-phar/data/analyzed/Medical Device/articles_analyzed_2026_08.json" \
  --start 2026-08-01 --end 2026-08-31
```

生成 `china-wechat-med-phar/reports/Medical Device/monthly_report_20260801_20260831.md` 和 `.json`。

成功标志：两条线的 Markdown/JSON 文件都存在；报告日期正确；周度文章链接、Executive Summary 和 Top Opportunities（如适用）有内容；没有把 Pharma 文章放入 Medical Device，反之亦然。PDF/HTML 是可选本地阅读产物，不能替代 Markdown/JSON 主报告。
