# Market Intelligence
## Mentor 操作手册

**适用环境：** Mac + Codex Desktop  
**适用对象：** 不需要编程经验的操作人员  
**流程版本：** 2026 年 8 月示例

> 这份手册的核心规则：一次只做一个 Step。看到本 Step 的“成功标志”后，停止并记录结果，不要让 Codex 自动进入下一步。

---

## 这套系统在做什么

这套 Market Intelligence 系统把微信公众号文章整理成两类月报：

1. **Pharma（医药）**：药品、药企、临床、审批、授权交易、并购和市场变化。
2. **Medical Device（医疗器械）**：器械企业、产品、采购、注册、临床、产能和行业政策。

五个工具各自负责不同事情：

| 工具 | 用简单的话说 | 你需要做什么 |
|---|---|---|
| GitHub | 保存项目代码的远程仓库 | 让 Codex 拉取最新代码 |
| Codex Desktop | 负责看文件、执行命令、报告结果的助手 | 复制本手册的指令给它 |
| WeWe RSS | 把微信公众号文章变成 RSS 文章列表 | 启动、打开、微信扫码、刷新 |
| DeepSeek | 对文章进行逐篇分析并协助生成月报 | 确认可以调用 API，观察进度 |
| 本地项目 | 保存文章、分析结果和月报文件的文件夹 | 让 Codex 在正确项目内工作 |

本手册从以下状态开始：项目已经 clone 到 mentor 的 Mac；软件已经安装；WeWe RSS 中已经有公众号源；项目的 `.env` 已配置 DeepSeek API key。

### 三条安全规则

- 不要把 `.env`、DeepSeek API key、WeWe RSS 的 `wewe-rss.db` 或本地原始数据复制到聊天或 GitHub。
- 不要直接修改 WeWe RSS 数据库。让 WeWe RSS 正常刷新，项目只读取它输出的 RSS。
- 不要为了“试试看”使用 `--force`。它可能让同一篇文章重复调用 DeepSeek，增加时间和费用。

### 每月先填写这两个日期

本手册示例使用：

```text
START_DATE = 2026-08-01
END_DATE   = 2026-08-31
```

日期格式必须是 `YYYY-MM-DD`。开始日和结束日都包含，例如 8 月 31 日发布的文章会被保留。

---

# Step 1｜从 GitHub 更新项目

## 目的

确保 mentor 使用的是 GitHub 上最新的脚本、提示词和修复，而不是 Mac 上旧的文件。

## 开始前检查

- Codex Desktop 已打开。
- Codex 当前打开的是 `monthly-report-library` 项目，而不是父文件夹或其他项目。
- 当前项目已经 clone 好，里面能看到 `china-wechat-med-phar` 文件夹。

## 复制给 Codex 的指令

```text
请先确认当前工作区是 monthly-report-library 项目，不要修改任何文件。

1. 运行 git status -sb，告诉我当前分支和是否有未提交修改。
2. 如果当前分支不是 main，请先停下来告诉我，不要自行切换。
3. 如果有未提交修改，也先停下来，列出文件并询问我，不要覆盖它们。
4. 如果工作区干净，运行 git pull --ff-only。
5. 运行 git log -1 --oneline，告诉我更新后的最新 commit。
完成以上检查后停止，不要进入 WeWe RSS、采集或分析步骤。
```

## Codex 会做什么

Codex 会读取当前状态，从 GitHub 拉取最新 `main` 分支，并显示最新 commit。`--ff-only` 的含义是：如果远端和本地无法安全直线合并，就停止，不擅自解决冲突。

## 成功标志

终端应显示：

- `git pull` 成功完成，或显示 `Already up to date`。
- 没有 merge conflict。
- `git status -sb` 没有意外的未提交修改。
- Codex 报告了最新 commit。

请记录：

```text
Step 1 完成日期：__________
最新 commit：______________
```

> **停止点：** Step 1 完成后停止。回复 Codex“Step 1 完成”，不要让它继续启动 WeWe RSS。

## 如果出错，复制给 Codex

```text
刚才的 GitHub 更新没有成功。请只做诊断，不要修改文件、不使用 git reset、不删除任何内容。
请告诉我：当前目录、当前分支、git status -sb 的完整结果、远端地址，以及错误的中文解释。
完成诊断后停止。
```

---

# Step 2｜登录 WeWe RSS

## 目的

让本机 WeWe RSS 服务正常运行，并确认 mentor 可以用微信扫码进入已有账号。

## 开始前检查

- Docker Desktop 已打开。
- mentor 手边有已经绑定 WeWe RSS 的微信。
- 不需要重新添加公众号源；本手册假设源已经存在。

## 复制给 Codex 的指令

```text
现在只检查和启动 WeWe RSS，不要抓取文章，也不要调用 DeepSeek。

1. 确认同级目录 wewe-rss-local 是否存在，以及是否有 docker-compose.yml 或 compose 文件。
2. 检查 Docker 是否正在运行；如果 Docker Desktop 没启动，请告诉我需要先打开它并停止。
3. 如果服务未运行，使用现有 compose 配置启动 WeWe RSS；不要修改数据库和 compose 文件。
4. 检查 http://localhost:8001 是否可以访问。
5. 如果可以访问，请打开或提示我在浏览器中打开这个地址，然后停止，等待我完成微信扫码。
不要进入文章刷新、采集、分析或报告步骤。
```

## 需要 mentor 亲自操作

1. 在浏览器打开 `http://localhost:8001`。
2. 如果出现登录二维码，用微信扫描。
3. 在手机上确认登录。
4. 回到浏览器，确认能看到 WeWe RSS 页面和已有公众号源。

Codex 不能替你完成微信扫码，也不应该索要微信密码或二维码内容。

## 成功标志

- 浏览器打开 `http://localhost:8001`。
- 登录成功后能看到已有的公众号源。
- 没有修改 `wewe-rss.db`。

记录：

```text
WeWe RSS 页面可访问：□
微信扫码完成：□
已有公众号源可见：□
```

> **停止点：** 登录和源列表确认后停止。回复 Codex“Step 2 完成”，不要让它自动刷新文章。

## 如果 localhost 打不开

```text
请只诊断 WeWe RSS，不要修改数据库。
请检查：Docker 是否运行、compose 容器状态、8001 端口是否有服务、http://localhost:8001 的 HTTP 状态。
解释每个结果，并告诉我下一步需要我点击什么。完成诊断后停止。
```

---

# Step 3｜刷新到最新文章日期

## 目的

让已有公众号源从 WeWe RSS 更新到本次运行需要的最新文章日期。

## 需要 mentor 亲自操作

1. 在 WeWe RSS 页面找到已有公众号源。
2. 点击页面中的刷新、同步或更新按钮（按钮名称以当前页面为准）。
3. 等待刷新结束，不要关闭浏览器或 Docker。
4. 查看文章列表，记下每个重点源的最新文章日期。

## 复制给 Codex 的指令

```text
现在只验证 WeWe RSS 刷新结果，不要运行采集脚本，不要调用 DeepSeek。

请检查 http://localhost:8001 是否仍可访问，并指导我核对已有公众号源和文章列表。
请让我记录：重点源名称、刷新后的最新文章日期、页面是否显示刷新成功。
如果页面没有更新、没有文章或出现错误，请先解释原因和建议，不要进入下一步。
完成验证后停止。
```

## 成功标志

- 重点公众号源仍然存在。
- 文章列表可以打开。
- 最新文章日期已经达到本次目标日期，或 mentor 已明确知道哪些源没有新文章。
- 没有修改 WeWe RSS 数据库文件。

记录：

| 公众号源 | 刷新后的最新日期 | 是否达到目标 |
|---|---|---|
| 例：源 A | 2026-08-31 | □ |
| 例：源 B | 2026-08-30 | □ |
| 例：源 C | __________ | □ |

> **停止点：** 只有在日期已记录后才结束 Step 3。回复 Codex“Step 3 完成”，不要自动拉取文章。

## 如果日期不变

```text
WeWe RSS 页面可以打开，但刷新后的最新文章日期没有变化。
请只诊断：刷新按钮是否真正完成、容器日志是否有错误、目标 feed 是否存在、RSS feed 是否返回文章。
不要修改数据库，不要调用 DeepSeek，不要进入采集步骤。
```

---

# Step 4｜拉取文章并筛选日期

## 目的

先把 WeWe RSS 中的全部已配置文章读取到本地，再保留指定日期区间内的文章。此时只采集和清洗，不做 AI 分析。

## 本次日期

请先替换下面两个值：

```text
START_DATE = 2026-08-01
END_DATE   = 2026-08-31
```

## 复制给 Codex 的指令

```text
现在执行 Step 4，只做文章采集和日期筛选，不调用 DeepSeek，不做文章分析，不生成月报。

日期范围（开始和结束都包含）是：
START_DATE = 2026-08-01
END_DATE = 2026-08-31

请按以下顺序执行：
1. 先确认当前目录是 monthly-report-library，且 http://localhost:8001 可访问。
2. 运行 .venv/bin/python china-wechat-med-phar/scripts/main.py，读取全部已配置 feed。
3. 运行 prepare_llm_data.py，使用 --start 2026-08-01 --end 2026-08-31，并保留 source_category 为“医药”和“医疗器械”的文章。
4. 检查输出 JSON 中每篇文章的 published 日期，确认没有超出日期范围。
5. 分别统计 Pharma/医药和 Medical Device/医疗器械的文章数量，并告诉我输出文件路径。
完成后停止，不要运行任何 Article Analysis 或 Monthly Analysis 脚本。
```

## Codex 执行的核心命令

```bash
.venv/bin/python china-wechat-med-phar/scripts/main.py
.venv/bin/python china-wechat-med-phar/scripts/prepare_llm_data.py \
  --start 2026-08-01 --end 2026-08-31 \
  --source-category 医药 \
  --source-category 医疗器械
```

## 主要输出

原始采集文件：

```text
china-wechat-med-phar/data/raw/articles.json
china-wechat-med-phar/data/raw/articles.csv
china-wechat-med-phar/data/raw/articles.xlsx
```

8 月清洗文件：

```text
china-wechat-med-phar/data/llm_ready/articles_llm_ready_2026_08.json
china-wechat-med-phar/data/llm_ready/articles_llm_ready_2026_08.md
```

## 成功标志

- 终端显示采集完成和新增数量。
- `articles_llm_ready_2026_08.json` 存在且可以打开。
- 没有超出 `2026-08-01` 至 `2026-08-31` 的文章。
- 已分别记录医药和医疗器械数量。

记录：

```text
医药文章数：__________
医疗器械文章数：______
日期范围检查：通过 □
```

> **停止点：** Step 4 完成后停止。不要因为文章已经准备好就自动调用 DeepSeek；API 分析必须从 Step 5 单独开始。

## 如果日期筛选结果是 0

```text
Step 4 的日期筛选结果是 0。请只诊断，不调用 DeepSeek，也不要修改原始数据。
请检查：raw articles.json 是否存在、published 字段的实际日期格式、WeWe RSS 最新日期、START_DATE/END_DATE 是否写反或写错。
列出证据和建议修改的日期，然后停止。
```

---

# Step 5｜分别分析医药和医疗器械

## 目的

把日期范围内的文章交给 DeepSeek 做逐篇结构化分析。医药和医疗器械必须使用独立的输入、提示词和输出文件。

## 重要提醒

- 这是会调用 DeepSeek API 的步骤，可能需要较长时间并产生 API 用量。
- Codex 应该增量保存；中断后可以继续，不要从头强制重跑。
- 先看数量和配置，再开始分析。不要在没有确认范围时直接调用 API。

## 5A：先确认候选数量

复制给 Codex：

```text
现在进入 Step 5，但先不要调用 DeepSeek。
请读取 Step 4 生成的日期范围 JSON，分别统计医药和医疗器械的候选文章数、空正文数、已有分析数（如果有），并检查输出目录是否可写。
告诉我两个分析命令会使用的输入、输出和日期范围。
等我确认后再调用 API。
```

如果数量和日期都正确，再回复 Codex“开始分析”。

## 5B：分析 Pharma（医药）

```text
开始分析 Pharma/医药文章，日期是 2026-08-01 至 2026-08-31（含首尾）。
只运行医药分析，不运行医疗器械分析和月报生成。

使用：
.venv/bin/python china-wechat-med-phar/scripts/analyze_pharma_articles.py \
  --input china-wechat-med-phar/data/llm_ready/articles_llm_ready_2026_08.json \
  --output china-wechat-med-phar/data/analyzed/articles_analyzed.json \
  --selected-output china-wechat-med-phar/data/analyzed/Pharma/articles_analyzed_2026_08.json \
  --start 2026-08-01 --end 2026-08-31 \
  --smart-new-only --skip-empty-text --workers 1

请保留增量保存和已有 article_id 跳过逻辑，不要使用 --force。每隔一段报告 processed、skipped、failed 和已保存数量；如果中断，告诉我已保存数量和剩余范围，然后停止。
```

核心输出：

```text
china-wechat-med-phar/data/analyzed/articles_analyzed.json
china-wechat-med-phar/data/analyzed/Pharma/articles_analyzed_2026_08.json
```

## 5C：分析 Medical Device（医疗器械）

```text
开始分析 Medical Device/医疗器械文章，日期是 2026-08-01 至 2026-08-31（含首尾）。
只运行医疗器械分析，不运行 Pharma 分析和月报生成。

使用：
.venv/bin/python china-wechat-med-phar/scripts/analyze_medical_device_articles.py \
  --input china-wechat-med-phar/data/llm_ready/articles_llm_ready_2026_08.json \
  --output "china-wechat-med-phar/data/analyzed/Medical Device/articles_analyzed_2026_08.json" \
  --start 2026-08-01 --end 2026-08-31 --workers 1

请保留已有 article ID 跳过逻辑和逐篇保存。每隔一段报告 processed、failed 和已保存数量；如果中断，告诉我已保存数量和剩余范围，然后停止。
```

## 成功标志

两条线分别检查：

- 输出 JSON 存在。
- Codex 报告 selected、processed、skipped、failed 数量。
- `failed = 0`，或已经保存失败文章标题、原因和剩余范围。
- 分析结果中的日期没有超出本次区间。
- 医药输出没有混入医疗器械文章，反之亦然。

记录：

| 分析线 | 已处理 | 跳过 | 失败 | 输出文件 |
|---|---:|---:|---:|---|
| Pharma | ____ | ____ | ____ | `data/analyzed/Pharma/...json` |
| Medical Device | ____ | ____ | ____ | `data/analyzed/Medical Device/...json` |

> **停止点：** 两条线都完成并记录后停止。不要直接生成月报；先确认分析完整性。

## 如果分析中断或 API 报错

```text
分析过程中出现错误。请不要使用 --force，不要删除已有 JSON，不要从头重跑。
请检查最近一次保存的输出文件、已保存 article_id 数量、最后一个错误、剩余未分析数量和 API HTTP 状态。
告诉我是否可以从已有结果安全继续。完成诊断后停止。
```

---

# Step 6｜生成 Pharma 和 Medical Device 月报

## 开始条件

只有在以下条件满足时才开始：

- Step 5 两条分析线已经结束。
- 已保存的数量与预期数量一致，或 mentor 明确接受部分覆盖。
- 失败文章已经记录，不是假装全部完成。

## 复制给 Codex 的指令

```text
我确认 Step 5 的医药和医疗器械分析已经完成，现在进入 Step 6。
请只生成 2026-08-01 至 2026-08-31 的两类 monthly report，不要发布到 GitHub，不要修改 WeWe RSS，不要重新抓取文章。

先检查两条分析 JSON 存在、日期范围正确、两条业务线没有混用；然后分别运行 Pharma 和 Medical Device 的 monthly report 生成脚本。
完成后检查 Markdown 和 JSON 文件都存在，报告日期正确，Executive Summary、周度文章链接和 Top Opportunities（如适用）不为空。
列出所有输出路径和检查结果，然后停止。
```

## Pharma 月报命令

```bash
.venv/bin/python china-wechat-med-phar/scripts/generate_pharma_monthly_report.py \
  --input china-wechat-med-phar/data/analyzed/articles_analyzed.json \
  --start 2026-08-01 --end 2026-08-31
```

预期输出：

```text
china-wechat-med-phar/reports/Pharma/monthly_report_20260801_20260831.md
china-wechat-med-phar/reports/Pharma/monthly_report_20260801_20260831.json
```

## Medical Device 月报命令

```bash
.venv/bin/python china-wechat-med-phar/scripts/generate_medical_device_monthly_report.py \
  --input "china-wechat-med-phar/data/analyzed/Medical Device/articles_analyzed_2026_08.json" \
  --start 2026-08-01 --end 2026-08-31
```

预期输出：

```text
china-wechat-med-phar/reports/Medical Device/monthly_report_20260801_20260831.md
china-wechat-med-phar/reports/Medical Device/monthly_report_20260801_20260831.json
```

## 本地检查

让 Codex 检查：

```text
请只做本地月报质量检查，不要发布、push 或修改源数据。
检查两类报告：文件是否存在、JSON 是否可解析、报告日期是否为 2026-08-01 至 2026-08-31、文章原始链接是否存在、Executive Summary 是否有内容、周度文章列表是否为空、两条业务线是否混用。
输出一份“通过/需要人工检查”的清单，然后停止。
```

PDF 或 HTML 是可选的本地阅读产物。它们不能替代 Markdown/JSON 主报告，也不会因为生成了文件就自动发布。

> **停止点：** 月报本地检查完成后停止。发布到 GitHub 是另一个需要 mentor 明确批准的动作。

---

# 每月快速清单

填写日期：`START_DATE = ____-__-__`，`END_DATE = ____-__-__`。

1. □ Step 1：Codex 检查工作区干净，`git pull --ff-only` 成功。
2. □ Step 2：WeWe RSS 页面可访问，微信扫码成功，公众号源存在。
3. □ Step 3：刷新完成，记录重点源最新文章日期。
4. □ Step 4：运行采集和 `prepare_llm_data.py`，记录医药/医疗器械数量。
5. □ Step 5：先确认数量，再分别运行两条分析线；记录 processed/skipped/failed。
6. □ Step 6：确认分析完整后，分别生成两类月报并检查 Markdown/JSON。
7. □ 每一步完成后已停止，没有自动跳步。
8. □ 没有把 `.env`、API key、数据库或原始数据发给 Codex/GitHub。

---

# 常见问题词典

| 术语 | 含义 |
|---|---|
| feed | WeWe RSS 中一个公众号的文章订阅入口 |
| raw | 从 RSS 读取后保存的原始文章数据 |
| LLM-ready | 已清洗、适合交给 DeepSeek 分析的数据 |
| analyzed | DeepSeek 已经返回结构化分析的文章 |
| article_id | 用来判断文章是否已经分析过的唯一标识 |
| inclusive | 包含开始日期和结束日期 |
| processed | 本次实际完成分析并保存的文章数 |
| skipped | 因为已有结果或正文为空而跳过的文章数 |
| failed | 本次尝试但失败的文章数 |
| `--force` | 强制重新分析已有文章；通常不要使用 |

## 通用诊断指令

```text
请先总结当前项目状态，再诊断刚才的错误。
只进行读取和检查，不删除文件、不使用 git reset、不修改 .env、不修改 wewe-rss.db、不调用 DeepSeek。
请列出：当前目录、相关文件是否存在、命令的完整错误、最可能原因、下一步需要我亲自点击或确认的动作。
完成诊断后停止。
```

## 什么时候可以发布

本手册只覆盖本地生成。若要把报告发布到 GitHub，必须由 mentor 明确说“发布这份已检查的报告”，再使用单独的发布流程。发布前要再次确认：

- 只发布批准的报告文件。
- 不上传 `.env`、原始采集数据、DeepSeek 返回的本地临时文件或 WeWe RSS 数据库。
- 发布后检查主页卡片和报告直达链接。

---

## 一句话总结

**先更新代码 → 再登录并刷新 WeWe RSS → 拉取文章并按日期筛选 → 分开分析医药和医疗器械 → 确认分析完整 → 分开生成月报；每一步完成后停下。**
