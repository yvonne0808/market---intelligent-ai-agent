# SEA MedTech Report Stream Isolation Design

**Date:** 2026-08-11  
**Status:** Approved for implementation planning  
**Scope:** `southeast_asia_medtech`

## Objective

Separate the Southeast Asia MedTech website's `monthly-report` and
`customer-analysis` sections into independent source, collection, analysis,
report-generation, data, and publishing pipelines.

The two sections answer different questions:

- **Monthly Report:** What changed in the Southeast Asia medical-device market?
- **Customer Analysis:** What did named customers and competitors do, and what
  should sales or business development investigate next?

They may share low-level utilities, but neither stream may read the other
stream's sources, prompts, analysis cache, issue data, or website assets.

## Target Architecture

```text
southeast_asia_medtech/
├── monthly_report/
│   ├── config/
│   │   ├── sources.yaml
│   │   └── keywords.yaml
│   ├── prompts/
│   │   ├── article_analysis_prompt.txt
│   │   └── report_generation_prompt.txt
│   ├── scrapers/
│   ├── processors/
│   └── reports/
├── customer_analysis/
│   ├── config/
│   │   └── sources.yaml
│   ├── prompts/
│   │   ├── article_analysis_prompt.txt
│   │   └── report_generation_prompt.txt
│   ├── scrapers/
│   ├── processors/
│   └── reports/
├── shared/
│   ├── http_client.py
│   ├── date_utils.py
│   └── url_utils.py
└── data/
    ├── monthly_report/
    │   ├── raw/
    │   ├── normalized/
    │   ├── filtered/
    │   ├── analyzed/
    │   └── issues/
    └── customer_analysis/
        ├── discovery/
        ├── analyzed/
        ├── master_events.json
        └── issues/
```

Existing module paths may remain temporarily as compatibility wrappers, but
new code and outputs must use the stream-specific paths.

## Source Ownership

### Monthly Report

The Monthly Report owns market, regulatory, investment, channel, and trade
media sources:

- Singapore HSA
- Malaysia MDA
- Thailand FDA
- Indonesia Farmalkes
- Vietnam VIMDA
- Philippines FDA
- Southeast Asia Healthcare Channel Partners
- Malaysia MIDA and AMMI
- MDDI medical-device manufacturing and packaging news

Regulatory source names, search terms, and notes must be changed from
customer-targeted monitoring to market monitoring. Relevant event types include
registration, approval, recall, FSCA, safety alerts, regulatory changes,
procurement, market access, and other concrete medical-device outcomes.

### Customer Analysis

Customer Analysis owns named-company discovery and first-party company sources:

- Google News RSS company-query discovery
- BD official press releases
- Baxter official news
- ResMed official news
- Smith+Nephew official news
- Johnson & Johnson MedTech press releases
- Olympus official news
- Malaysia glove-company investor relations and announcements

Google News must become an explicit configured source rather than an implicit
hard-coded provider. `company_watchlist.yaml` remains the authority for customer
names, aliases, competitors, product segments, and verified Southeast Asia
footprints.

Each source has exactly one owning stream. Cross-stream evidence import is out
of scope unless a later workflow adds an explicit, human-approved import step.

## Collection and Processing Flows

### Monthly Report

```text
monthly_report/config/sources.yaml
→ monthly collection
→ monthly keyword and rule filtering
→ monthly article analysis
→ monthly evidence ledger
→ monthly report generation
→ monthly website assets
```

### Customer Analysis

```text
customer_analysis/config/sources.yaml + company_watchlist.yaml
→ customer and competitor discovery
→ customer article analysis
→ customer evidence ledger
→ customer report generation
→ customer-analysis website assets
```

Shared code is limited to technical capabilities such as HTTP behavior, date
parsing, canonical URL handling, atomic file writes, and generic validation
helpers. Business selection, scoring, schemas, and prompts are stream-owned.

## Article Analysis Prompts

### Monthly Report Prompt

`monthly_report/prompts/article_analysis_prompt.txt` determines whether an
article represents a material Southeast Asia medical-device market event.

It evaluates:

- medical-device or consumables relevance;
- explicit Southeast Asia geography;
- event country and event status;
- regulatory, procurement, commercialization, manufacturing, investment,
  channel, supply-chain, partnership, or packaging significance;
- market, supply-chain, and packaging implications;
- evidence quality and uncertainty; and
- inclusion in the Monthly Report.

Its primary categories are:

1. Regulatory, registration and safety
2. Procurement and contract awards
3. Product commercialization
4. Manufacturing, localization and capacity
5. Channels and supply chain
6. Financing, M&A and partnerships
7. Medical-device packaging
8. Market and policy
9. Other

It must not contain TOP 20 customer priority rules or require customer and
competitor relationship fields.

### Customer Analysis Prompt

`customer_analysis/prompts/article_analysis_prompt.txt` determines what a named
customer or competitor did and whether the evidence merits commercial follow-up.

It evaluates:

- matched customers and competitors;
- the concrete company event;
- effects on capacity, product mix, market access, channels, sales, supply, or
  competitive position;
- supported customer-competitor relationships;
- supported packaging signals;
- commercial implications and cautious follow-up actions; and
- inclusion in Customer Analysis.

It must not use `include_in_monthly_report`, fill country sections, or retain
general market and policy news without named-company value.

## Article Schemas and Cache Identity

Monthly analysis uses market-oriented fields such as:

- `include_in_monthly_report`
- `market_relevance_score`
- `primary_category`
- `report_countries`
- `event_status`
- `market_implication_cn`
- `supply_chain_implication_cn`
- `packaging_relevance_score`

Customer analysis uses company-oriented fields such as:

- `include_in_customer_analysis`
- `customer_relevance`
- `matched_customers`
- `competitor_companies`
- `related_customer_groups`
- `competitive_relationship`
- `customer_impact_cn`
- `commercial_implication_cn`
- `recommended_follow_up_cn`

The cache identity must include `article_id`, `stream`, and `prompt_version`.
The initial versions are:

- `monthly-report-article-v1`
- `monthly-report-generation-v1`
- `customer-analysis-article-v1`
- `customer-analysis-generation-v3`

One stream must never reuse another stream's cached analysis, even when both
have seen the same canonical URL.

## Final Report Generation

### Monthly Report

The Monthly Report generation prompt consumes only validated monthly analysis
and produces structured JSON covering:

- Executive Summary;
- priority market signals;
- country and regional developments;
- regulation and safety;
- procurement and commercialization;
- manufacturing, localization, capacity, channels, and investment;
- packaging signals; and
- coverage limitations and uncertainty.

Issue outputs live under:

```text
data/monthly_report/issues/<YYYY-MM>/
├── evidence.json
├── draft.json
├── approved.json
└── manifest.json
```

### Customer Analysis

The Customer Analysis generation prompt consumes only the customer evidence
ledger and produces the existing action-first report, including the executive
summary, ten priority actions, company explorer data, evidence links, and
commercial follow-up steps.

Issue outputs live under:

```text
data/customer_analysis/issues/<YYYY-MM>/
├── evidence.json
├── prompt_evidence.json
├── draft.json
├── approved.json
└── source_manifest.json
```

In both streams, model output is a draft. An approved file takes precedence for
publication. If no approved version exists, the website must label the content
as draft. A failed generation must not overwrite an existing approved report.

## Website Assets

The website consumes separate asset roots:

```text
public/monthly-report/report.json
public/monthly-report/events.json

public/customer-analysis/report.json
public/customer-analysis/events.json
```

The ambiguous root `public/report-data.json` may remain during a compatibility
period, but new generation code must not write to it. The Monthly Report page
and Customer Analysis route must each load only their own assets.

## Migration

Migration is non-destructive:

- `data/raw/<month>` → `data/monthly_report/raw/<month>`
- `data/normalized/<month>` → `data/monthly_report/normalized/<month>`
- `data/filtered/<month>` → `data/monthly_report/filtered/<month>`
- `data/customer_discovery` → `data/customer_analysis/discovery`
- `data/analyzed/customer_discovery_*` → `data/customer_analysis/analyzed/`
- existing customer issue data remains under the new customer-owned structure

Existing `data/analyzed/2026-07` results were produced by a customer-priority
prompt. They must not be relabeled as new Monthly Report analysis. They may be
preserved as legacy evidence until a separately authorized reanalysis occurs.

Old paths remain for one compatibility cycle. No old files are deleted by this
change. Migration must verify record counts and canonical URLs before and after
copying or moving data.

## Failure Handling

The pipeline fails closed rather than borrowing another stream's resources when:

- its prompt is missing;
- a source belongs to the wrong stream;
- input data lacks a valid stream identity;
- the prompt version does not match;
- an output path points into the other stream; or
- input does not satisfy the stream-specific schema.

A single article failure is recorded and does not stop unrelated articles in
the batch. Final report failure leaves the previously approved report and
published assets unchanged.

## Testing and Acceptance Criteria

Tests must demonstrate that:

1. each source configuration loads independently;
2. Monthly collection cannot load customer-owned sources;
3. Customer collection cannot load market-owned sources;
4. prompt paths and versions differ by stream;
5. both article schemas validate independently;
6. output paths cannot cross stream boundaries;
7. draft output cannot silently replace approved output;
8. no-API test mode performs no provider call;
9. both website pages load only their own assets;
10. website build and page tests pass; and
11. migration preserves expected record counts and canonical URLs.

## Implementation Boundaries

Implementation includes structure, configuration split, prompt split, code
wiring, safe data migration, compatibility wrappers where needed, and automated
tests.

Implementation does not authorize:

- collecting new articles;
- calling DeepSeek or another LLM;
- regenerating an official report;
- publishing the website;
- deleting legacy files; or
- changing the separate China WeChat workflow.

