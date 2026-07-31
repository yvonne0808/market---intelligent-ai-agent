# Southeast Asia MedTech Data Schema

Schema version: `2.0`

This contract describes normalized article records for the independent Southeast Asia
module. It does not replace or modify the existing WeChat/RSS article schema.

## Normalized article fields

| Field | Type | Required | Meaning |
|---|---|---:|---|
| `schema_version` | string | yes | Record contract version, initially `1.0` |
| `article_id` | string | yes | Stable module-local ID |
| `source_id` | string | yes | ID from `config/sources.yaml` |
| `source_name` | string | yes | Human-readable source name |
| `organization` | string | yes | Publishing authority |
| `source_type` | enum | yes | For phase one, `regulator` |
| `country` | string | yes | ISO alpha-2 where applicable; `ASEAN`, `APAC`, or `GLOBAL` for regional sources |
| `language` | ISO 639-1 | yes | Primary article language |
| `category` | string | yes | High-level configured source category |
| `title` | string | yes | Clean article/notice title |
| `url` | URI | yes | Discovered article URL |
| `canonical_url` | URI | yes | Normalized URL used for primary dedupe |
| `published_at` | ISO 8601 string/null | yes | Parsed publication time/date |
| `published_date_raw` | string | yes | Original date text, including Malay labels |
| `published_date_precision` | enum | yes | `datetime`, `date`, `month`, `unknown` |
| `timezone` | IANA name | yes | Source timezone used for parsing |
| `discovered_at` | ISO 8601 string | yes | First observed time |
| `fetched_at` | ISO 8601 string | yes | Detail retrieval time |
| `author` | string | no | Author/byline when present |
| `body_text` | string | yes | Extracted normalized text |
| `body_length` | integer | yes | Unicode character count |
| `content_hash` | string | yes | SHA-256 of normalized body text |
| `topics` | array[string] | yes | Matched business/regulatory/packaging topics |
| `keyword_matches` | array[object] | yes | Matched category, keyword, weight, language |
| `keyword_score` | number | yes | Sum of unique matched keyword weights |
| `attachments` | array[object] | yes | Public linked PDF/document metadata |
| `retrieval_status` | enum | yes | `success`, `partial`, `failed`, `skipped` |
| `http_status` | integer/null | yes | HTTP result when a request occurred |
| `error_message` | string | yes | Empty on success |
| `raw_snapshot_path` | string | yes | Module-relative immutable raw snapshot |
| `parser_name` | string | yes | Parser/strategy identifier |
| `parser_version` | string | yes | Version used to produce the record |

## Attachment object

```yaml
title: ""
url: ""
media_type: "application/pdf"
file_hash: ""
local_path: ""
retrieval_status: "skipped"
```

Authenticated files, CAPTCHA-protected content, and complete registration databases are
outside phase-one scope.

## Source workflow types

- `news_listing`: dated articles, announcements and regulatory updates.
- `registry_targeted`: public notices plus company/product/registration-number queries; never a full registry dump.
- `procurement_search`: keyword/category queries for tenders and awards, normally run weekly.
- `packaging_news`: dated medical-device packaging, sterile-barrier and validation updates.

Procurement records additionally reserve:

`procurement_agency`, `tender_title`, `device_category`, `consumable_type`, `quantity`,
`tender_value`, `currency`, `winner`, `manufacturer`, `distributor`, `closing_date`,
`award_date`, `packaging_relevance`, and `source_url`.

## Identity and deduplication

1. Use normalized `canonical_url` as the primary key candidate.
2. Use an official source-provided notice ID when available.
3. Otherwise derive `article_id` from `source_id`, normalized title, and publication date.
4. Use `content_hash` to flag cross-URL or cross-source duplicates.
5. Keep aliases/provenance; do not silently erase duplicate notices.

## Date rules

- Singapore HSA timezone: `Asia/Singapore`.
- Malaysia MDA timezone: `Asia/Kuala_Lumpur`.
- Preserve the exact displayed date in `published_date_raw`.
- Parsers must support English and Malay month labels.
- An ambiguous or absent date becomes `null` with precision `unknown`; it must not be
  replaced with crawl time.

## Keyword-match object

```yaml
category: medical_device_packaging
keyword: sterile barrier system
matched_term: sterile barrier
weight: 6
language: en
```

Synonyms inherit their parent keyword's category, weight, and language. Matching is
case-insensitive and each canonical keyword contributes its weight at most once per
article.

## Future analyzed record boundary

LLM-derived summaries and classifications must live in a separate analyzed record keyed by
`article_id`, `content_hash`, prompt version, and model. They must not be written into raw
snapshots, and existing WeChat analysis files must never be used as state for this module.
