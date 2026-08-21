# SEA MedTech Monthly Article Analysis Prompt Design

**Date:** 2026-08-11  
**Status:** Approved for implementation planning  
**Target:** `southeast_asia_medtech/monthly_report/prompts/article_analysis_prompt.txt`

## Objective

Adapt the existing China Medical Devices single-article analysis Prompt for the
Southeast Asia Monthly Report while preserving its proven business focus on
medical devices, consumables, commercialization, manufacturing, transactions,
channels, supply chain, and medical-device packaging.

This Prompt belongs only to Monthly Report. It does not contain Customer
Analysis watchlist, customer-priority, or competitor-mapping rules.

## Geographic Boundary

Prioritize events in Singapore, Malaysia, Thailand, Indonesia, Vietnam, and the
Philippines. ASEAN-wide events may be retained as regional evidence.

Global events are eligible only when the article explicitly supports at least
one of these conditions:

- impact on a Southeast Asia market;
- impact on a regional supply chain or market-access route; or
- direct, material medical-device packaging intelligence.

The model must not infer an event country from a company name, source language,
headquarters, or general knowledge. `source_country_tag` describes the source;
`report_countries` describes countries explicitly evidenced by the article.

## Business Scope

Retain the China Prompt's focus on:

- medical devices and medical consumables;
- high-value and low-value consumables;
- single-use medical products;
- product registration, approval, recall, and safety events;
- clinical and regulatory milestones tied to a concrete product;
- government procurement, tenders, awards, and contract results;
- commercialization and sales growth;
- exports, overseas certification, and market access;
- local manufacturing, import substitution, production lines, and capacity;
- supply-chain changes, distribution, channels, and BD partnerships;
- financing, investment, mergers, and acquisitions; and
- sterile packaging materials, formats, sterilization, integrity, validation,
  ISO 11607, and cleanroom packaging.

Deprioritize pharmaceuticals, hospital promotion, individual interviews,
disease education, event promotion, recruiting, advertising, low-information
reposts, and events without a supported Southeast Asia or packaging connection.

## Categories

Use exactly five primary categories:

1. `产品与商业化`
2. `制造与产能`
3. `渠道与供应链`
4. `融资并购与合作`
5. `其他`

Specific product approvals, registrations, overseas certifications, recalls,
and safety actions belong to `产品与商业化` because their value is the product
or commercialization consequence.

General regulations, policy guidance, consultations, industry initiatives, and
macro policy commentary belong to `其他`. They receive low priority and are
normally excluded unless the article demonstrates a concrete effect on a named
product, company, procurement outcome, manufacturing decision, supply chain, or
commercialization event.

Packaging is an independent scoring dimension, not a primary category.

## Scoring and Admission

Keep the China Prompt's 0-20 `relevance_score` structure, localized to Southeast
Asia evidence. Keep a separate 0-5 packaging score, renamed from
`amcor_relevance_score` to the neutral `packaging_relevance_score`.

Rename `include_in_weekly_report` to `include_in_monthly_report`.

High scores require a concrete event, such as product approval, procurement
award, commercialization, capacity, market access, financing/M&A, partnership,
channel change, or direct packaging evidence. Source authority alone does not
justify a high score.

General policy content is normally excluded. A global event without supported
Southeast Asia impact or direct packaging intelligence is excluded.

Retain the low-value fast-exit behavior and short output limits so advertising,
events, recruiting, education, and generic policy articles do not consume deep
extraction tokens.

## Output Contract

Return one strict JSON object with all fields present:

```json
{
  "article_id": "",
  "title": "",
  "source_name": "",
  "source_country_tag": "",
  "report_countries": [],
  "organization": "",
  "source_type": "",
  "published_date": "",
  "url": "",
  "include_in_monthly_report": false,
  "relevance_score": 0,
  "importance_level": "low",
  "primary_category": "其他",
  "secondary_categories": [],
  "summary_cn": "",
  "key_points": [],
  "companies": [],
  "medical_devices": [],
  "medical_consumables": [],
  "device_categories": [],
  "regulatory_events": [],
  "clinical_or_regulatory_stage": "",
  "procurement_events": [],
  "deal_amounts": [],
  "manufacturing_events": [],
  "export_and_market_access_events": [],
  "partnership_events": [],
  "market_implication_cn": "",
  "packaging_relevance_score": 0,
  "packaging_relevance_reason": "",
  "packaging_relevance": "none",
  "packaging_forms": [],
  "packaging_materials": [],
  "sterilization_methods": [],
  "packaging_signals": [],
  "risks_or_uncertainties": [],
  "source_confidence": "high",
  "why_it_matters": "",
  "one_sentence_takeaway": ""
}
```

Use `published_date` and `url` instead of the WeChat fields `published` and
`link`. Use `regulatory_events`, `procurement_events`, and
`manufacturing_events` so event status can be represented explicitly.

## Implementation Boundaries

Implementation creates the new Monthly article analysis Prompt and focused
Prompt-contract tests. It does not modify the Customer Analysis Prompt, source
configuration, collection logic, existing analyzed data, final report Prompt,
website, or published assets. It does not call an LLM or rerun analysis.

