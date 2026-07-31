# Step 4 — Deterministic Rule Filtering

Date: 2026-07-24

## Scope

Step 4 adds a local rule-based first-pass filter over Step 3 normalized articles:

```text
normalized JSON
  -> configured keyword matching
  -> business category classification
  -> device and packaging scoring
  -> URL/title/content duplicate detection
  -> scored JSON + filtered JSON + review CSV
```

It makes no HTTP request, calls no LLM/API, adds no source, and does not touch the existing
WeChat workflow.

## Command

From the project root:

```bash
.venv/bin/python -m southeast_asia_medtech.processors.rule_filter
```

An alternate normalized JSON list can be supplied with:

```bash
.venv/bin/python -m southeast_asia_medtech.processors.rule_filter \
  --input /absolute/path/articles_normalized.json
```

## Outputs

```text
southeast_asia_medtech/data/filtered/
├── articles_scored.json
└── articles_filtered.json
```

- `articles_scored.json` contains every input row, including low-value, failed, and duplicate
  records, with complete reasons.
- `articles_filtered.json` contains every unique article that passes the automatic
  keyword/packaging gate.

There is no manual-review gate. A valid article with a non-negative configured keyword
match is immediately marked `include_in_llm_analysis: true`.

## Added fields

Each scored record preserves the Step 3 fields and adds:

```json
{
  "matched_keywords": [],
  "business_categories": [],
  "device_relevance_score": 0,
  "packaging_relevance_score": 0,
  "priority_level": "",
  "filter_reason": "",
  "include_in_llm_analysis": false,
  "duplicate_of": "",
  "duplicate_reason": ""
}
```

## Keyword matching

The processor reads `config/keywords.yaml`; keyword rules are not duplicated in code.

- Matching is case-insensitive.
- Canonical keywords and their configured synonyms are checked against title + body.
- Single alphanumeric terms use word boundaries, preventing matches such as `CE` inside
  unrelated words.
- Each canonical keyword is recorded at most once.
- Title matches provide an additional device relevance signal.

## Device score: 0–20

Signals include:

- core medical-device/equipment/consumable terminology;
- registration, approval, market authorization, and classification;
- product launch/commercialization;
- procurement, tender, and contract awards;
- factory, production line, local manufacturing, and capacity expansion;
- export/overseas certification;
- financing, acquisition, or BD;
- distributor, channel, or supply-chain cooperation;
- sterile single-use devices;
- specific packaging evidence;
- official Southeast Asian context.

Negative rules subtract points for:

- recruitment/job vacancies;
- training registration and event invitations;
- pure brand promotion;
- patient education;
- pharmaceutical-only news.

A failed scrape or body shorter than 80 characters always receives device score 0 regardless
of title keywords.

Priority:

| Rule | Priority | Automatic LLM flag |
|---|---|---|
| Matched and device 16–20 or packaging 7–10 | `high` | `true` |
| Any other valid non-negative keyword match, or packaging 5+ | `matched` | `true` |
| Failed, short, negative-rule, or unmatched | `excluded` | `false` |
| Duplicate loser | `duplicate` | `false` |

Device and packaging scores remain useful ranking signals for DeepSeek input ordering, but
they no longer create an `optional` manual-review state.

## Packaging score: 0–10

High-specificity terms start at 6 and quickly cap at 10:

- Tyvek, forming film, header bag;
- sterilization/paper-plastic pouches;
- blister/thermoformed/medical-device trays;
- medical-grade paper or coated paper;
- sterile barrier system/integrity;
- seal integrity and packaging validation;
- ISO 11607.

Medium terms add 4–5:

- sterile or medical-device packaging;
- EO/ethylene oxide, radiation, or steam sterilization;
- cleanroom packaging;
- sterilization compatibility.

General materials such as plastic film, lidding, sealing material, and protective packaging
receive only small scores. A phrase combining packaging with sterility/sterility breach
receives packaging score 5 even when the official page categorizes the product differently.

## Business categories

Possible deterministic categories are:

- `regulatory_registration`
- `commercialization_product_launch`
- `procurement_contract_award`
- `manufacturing_capacity`
- `export_market_access`
- `corporate_transaction`
- `distribution_supply_chain`
- `medical_consumables`
- `medical_device_packaging`

An article may have multiple categories.

## Duplicate detection

Detection order:

1. normalized exact URL, ignoring fragments, trailing slashes, and common tracking
   parameters;
2. exact normalized body fingerprint for bodies of at least 80 characters;
3. normalized title equality or `SequenceMatcher` similarity of at least 0.92.

Winner preference is lexicographic:

1. official regulator/government source;
2. successful scrape;
3. more complete body;
4. clearer publication date.

The losing record stays in scored JSON/CSV with `duplicate_of` and `duplicate_reason`, but
is excluded from filtered JSON and automatic analysis.

## Tests

Run:

```bash
.venv/bin/python -m unittest discover -s southeast_asia_medtech/tests -v
```

Step 4 includes 15 dedicated rule cases:

1. registration/approval;
2. procurement/award;
3. factory/capacity expansion;
4. financing/acquisition;
5. high-specificity ISO 11607/Tyvek/tray packaging;
6. medium-high sterilization/cleanroom packaging;
7. general equipment sales with low packaging relevance;
8. training-registration penalty;
9. recruitment penalty;
10. failed scrape exclusion;
11. URL tracking-parameter duplicate;
12. highly similar title duplicate and longer-body preference;
13. official-source preference;
14. packaging-score cap.
15. any ordinary non-negative keyword match enters the LLM queue.

Together with prior configuration/scraper tests, the suite contains 23 tests.

## Actual Step 3 input result

The current normalized input has only 6 articles, so it is not representative of a complete
month. The Step 4 run reports exact counts rather than inflating results:

- input: 6;
- unique: 6;
- duplicates: 0;
- high/matched rows are written directly to the DeepSeek candidate JSON;
- failed, duplicate, unmatched, and explicit negative-rule rows are excluded automatically;
- no human approval is required between Step 4 and the later API stage.

The CSV should be reviewed before changing thresholds. Step 4 stops here and does not invoke
analysis or generate a report.
