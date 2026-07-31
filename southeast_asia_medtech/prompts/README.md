# Southeast Asia Medtech Prompt Layer

本目录只定义 DeepSeek 接入前的 Prompt，不包含 API key、网络请求或模型调用。

## 建议调用顺序

1. `website_article_analysis_prompt.txt`
   - 输入：Step 4 允许分析的单篇官网文章及标准化元数据。
   - 输出：严格 JSON。
   - `include_in_llm_analysis` 只是规则层入口；模型使用 `include_in_monthly_report` 决定是否进入月报。

2. `procurement_award_extraction_prompt.txt`
   - 仅当单篇分析识别出采购/中标候选时使用。
   - 专门排除 MDA/HSA 官网中的 IT、活动、装修等行政采购，区分招标邀请与正式结果。

3. `monthly_report_prompt.txt`
   - 输入：已经分析、校验和去重的文章 JSON。
   - 输出：中文 Markdown 月报。
   - 不直接读取原始网页，也不应使用 Step 4 规则评分代替文章分析。

## 与 WeChat Medical Device Prompt 的关系

保留了原流程的核心设计：

- 单篇文章先输出严格 JSON；
- 行业相关性与包装相关性分别评分；
- 低价值文章快速退出；
- 月报只消费结构化分析结果；
- 强调 Amcor/医疗包装业务相关的材料、形式、灭菌和商业化信号。

官网版本的调整：

- 周报改为月报，字段使用 `include_in_monthly_report`；
- 增加 `country`、`organization`、`source_type`、`url` 等官网溯源字段；
- 增加 `source_country_tag` 与 `report_countries`，将来源归属和事件发生国家分开；
- 使用东南亚监管语境，不套用中国 NMPA/集采结论；
- 强制区分 consultation、guidance、tender 与正式 approval、award；
- 增加安全警示、召回、FSCA 和官网行政采购排除规则；
- 包装相关分数采用 0-5，便于后续与现有 Medical Device 分析流程对齐。

## DeepSeek API 接入

独立的网站文章分析入口：

```bash
.venv/bin/python -m southeast_asia_medtech.processors.analyze_with_deepseek \
  --month 2026-07
```

该入口会：

- 将 Prompt 与单篇网站文章 JSON 组合；
- 校验模型返回为合法 JSON、字段完整且分数在范围内；
- 单篇失败时记录错误并继续处理其他文章；
- 按 `article_id + prompt_version` 断点续跑，避免重复计费；
- 每篇成功后立即原子写入结果；
- 不读取或修改微信公众号文章数据。

2026-07 的首次批次使用 `deepseek-v4-flash` 和
`sea-medtech-website-v2-country-tags`，449 篇全部成功，输出位于
`data/analyzed/2026-07/articles_analyzed.json`。月报应只读取校验通过的
分析结果。
