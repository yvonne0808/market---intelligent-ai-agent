# Mentor Market Intelligence 操作手册设计说明

## 目标

为一位不熟悉计算机的 mentor 制作一份中文、可照做的操作手册，指导其在 Mac 的 Codex 桌面版中运行现有 Market Intelligence 项目。手册从项目已经 clone 到本地、软件已经安装、WeWe RSS 已配置公众号源、DeepSeek API key 已配置的状态开始。

## 用户与边界

- 读者：不具备编程背景的 mentor。
- 操作环境：macOS、Codex 桌面版、Terminal、浏览器、已安装并配置好的 WeWe RSS。
- 项目范围：中国微信公众号医药（Pharma）与医疗器械（Medical Device）月报工作流。
- 每月输入：明确的起止日期；结束日期包含在筛选范围内，手册用 `2026-08-01` 至 `2026-08-31` 作为示例。
- 安全边界：不把 `.env`、API key、WeWe RSS SQLite 数据库或本地原始数据上传 GitHub；不直接修改 WeWe RSS 数据库。
- 操作边界：每个 Step 完成后停止，等待 mentor 确认再进入下一步；采集、分析、报告生成和发布不自动串联。

## 内容结构

1. 开始前：用简单语言解释 GitHub、WeWe RSS、Codex、DeepSeek 和本地报告项目的关系。
2. 六个独立步骤：
   - Step 1：在 Codex 打开已 clone 项目并从 GitHub pull 最新代码。
   - Step 2：启动 WeWe RSS，打开 `http://localhost:8001`，微信扫码登录。
   - Step 3：刷新已有公众号源，确认服务中显示的文章已更新到最新日期。
   - Step 4：运行采集和日期筛选，保留指定区间内的全部文章，并分别检查 Pharma 与 Medical Device 数据量。
   - Step 5：先确认候选数量，再分别运行医疗器械和医药分析；说明 DeepSeek API 调用、增量保存、跳过已分析文章和失败记录。
   - Step 6：在分析完整后，分别生成 Pharma 与 Medical Device monthly report，并检查 Markdown、JSON、HTML/PDF 输出。
3. 每月快速清单：一页复用版。
4. 常见故障：Codex 找不到项目、localhost 无法访问、扫码后日期没更新、日期筛选为空、API key 或网络错误、分析中断、报告不完整。
5. 附录：日期填写模板、常用术语、可选首次安装说明和安全提醒。

## 每个 Step 的固定模板

每个步骤按同一顺序呈现：

1. 这一步的目的。
2. 开始前检查。
3. mentor 需要亲自点击、扫码或确认的动作。
4. 可整段复制给 Codex 的指令。
5. Codex 将执行的命令和产生的文件（用项目相对路径）。
6. 成功标志及应记录的数量、日期或文件名。
7. 常见错误及给 Codex 的诊断指令。
8. 勾选式停止点：完成后停止，不自动进入下一步。

## 技术事实依据

手册中的命令和路径以仓库现有文档与脚本为准，重点使用：

- `china-wechat-med-phar/MENTOR_SETUP.md`
- `china-wechat-med-phar/README.md`
- `docs/china-wechat-monthly-report-workflow.md`
- `china-wechat-med-phar/scripts/main.py`
- `china-wechat-med-phar/scripts/archive/collect_july_pharma_articles.py`
- `china-wechat-med-phar/scripts/analyze_pharma_articles.py`
- `china-wechat-med-phar/scripts/analyze_medical_device_articles.py`
- `china-wechat-med-phar/scripts/generate_pharma_monthly_report.py`
- `china-wechat-med-phar/scripts/generate_medical_device_monthly_report.py`

手册会把日期示例写成变量形式，避免把某一个月误当成永久配置。对于当前代码中不同报告流使用不同脚本的情况，手册会明确列出 Pharma 与 Medical Device 两条命令，不用一个模糊命令代替。

## 视觉设计

选择 `compact_reference_guide` 预设，采用 `editorial_cover` 首页模式：

- US Letter 纵向，四边 1 英寸页边距，正文 Calibri 11 pt，1.25 倍行距。
- 一级标题 16 pt `#2E74B5`，二级标题 13 pt `#2E74B5`，三级标题 12 pt `#1F4D78`。
- 指令使用浅灰蓝色固定宽度代码框；警告使用浅红色提示框；成功标志使用浅绿色提示框。
- 每个 Step 从新页开始，页眉显示 “Market Intelligence · Mentor Guide”，页脚显示页码。
- 使用真实编号列表、固定 DXA 表格宽度和明确单元格边距，不用手工输入的假项目符号。

## 交付与验证

- 交付文件：可编辑 `.docx` 与可直接转发 `.pdf`。
- 使用文档技能的 `render_docx.py` 渲染 DOCX，检查所有页面 PNG 是否有截断、重叠、表格溢出、字体异常或大面积空白。
- 运行结构检查，扫描 `TODO`、`TBD`、未替换占位符和错误路径。
- 若 PDF/Word 渲染工具不可用，保留结构化验证结果，并在交付说明中明确视觉 QA 的限制。
