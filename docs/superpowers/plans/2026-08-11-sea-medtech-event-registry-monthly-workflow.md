# SEA MedTech Event Registry Monthly Workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Collect high-volume Southeast Asia medical-device industry events from Event Registry, classify them into eight Monthly Report categories, deduplicate by `eventUri`, and prepare 30–60 high-value unique events without Customer or Competitor watchlists.

**Architecture:** Event Registry is the unified discovery source. The Monthly Report collector builds category-and-geography queries for one calendar month, preserves raw provider evidence, normalizes and deduplicates records, then prepares an LLM batch. The final selector keeps 30–60 unique, relevant events and reports a shortfall instead of padding with irrelevant content.

**Tech Stack:** Python 3, PyYAML, `requests`, `unittest`, Event Registry REST API, JSON artifacts, existing SEA MedTech configuration and LLM conventions.

## Global Constraints

- All new workflow code belongs to `southeast_asia_medtech/monthly_report/`.
- Never load Customer Analysis company or competitor watchlists.
- Do not modify Customer Analysis prompts, configuration, scripts, or output.
- Keep both keyword registries byte-identical.
- Read `EVENT_REGISTRY_API_KEY` only from the environment; never store or print it.
- Mock all provider and LLM calls in tests.
- A live pilot requires explicit user approval and one bounded month.
- Deduplicate before calculating the target of 30–60 report events.

## Category Contract

| Category ID | Included events |
|---|---|
| `product_approval_launch` | Important device/consumables approval, registration, clearance, certification, or launch |
| `clinical_registration_progress` | Successful/pivotal clinical trials, registration clinical progress, submission, or application |
| `overseas_market_access` | Export/overseas expansion and FDA, CE, EU MDR, or other market-access milestones |
| `commercialization_channels` | Commercial launch, sales rollout, market expansion, distributor or channel cooperation |
| `financing_ma_strategic_cooperation` | Financing, M&A, strategic investment, licensing, BD, JV, or material cooperation |
| `manufacturing_capacity_supply_chain` | Production base/line, commissioning, capacity expansion, manufacturing investment, or supply-chain change |
| `sales_scale_market_size` | Disclosed revenue, sales volume, commercial ramp-up, shipment growth, or quantified market size |
| `packaging_sterile_supply_opportunity` | Device packaging, sterile packaging/barrier, sterilization compatibility, or concrete packaging demand |

Geographies are Singapore, Malaysia, Thailand, Indonesia, Vietnam, Philippines, Southeast Asia, and ASEAN. Company is an extracted output field, never a query input.

---

### Task 1: Replace Broad Keywords with Eight Monthly Categories

**Files:**
- Modify: `southeast_asia_medtech/monthly_report/config/keywords.yaml`
- Modify: `southeast_asia_medtech/config/keywords.yaml`
- Modify: `southeast_asia_medtech/tests/test_config_loading.py`

**Interfaces:**
- Consumes: `load_keywords(path: Path | None = None) -> dict[str, Any]`.
- Produces: the eight Category Contract IDs; every keyword keeps `keyword`, `synonyms`, `weight`, `language`.

- [ ] **Step 1: Write the failing category test**

```python
MONTHLY_CATEGORY_IDS = {
    "product_approval_launch", "clinical_registration_progress",
    "overseas_market_access", "commercialization_channels",
    "financing_ma_strategic_cooperation",
    "manufacturing_capacity_supply_chain", "sales_scale_market_size",
    "packaging_sterile_supply_opportunity",
}

def test_monthly_keywords_use_approved_event_categories(self):
    config = load_keywords()
    self.assertEqual({row["category"] for row in config["categories"]}, MONTHLY_CATEGORY_IDS)
    terms = {e["keyword"] for row in config["categories"] for e in row["keywords"]}
    self.assertTrue({
        "medical device approval", "pivotal clinical trial",
        "medical device FDA clearance", "medical device commercialization",
        "medical device acquisition", "medical consumables production line",
        "medical device sales growth", "medical device packaging",
    }.issubset(terms))
    self.assertTrue({"FDA", "CE", "factory", "investment"}.isdisjoint(terms))
```

- [ ] **Step 2: Verify RED**

Run: `.venv/bin/python -m unittest southeast_asia_medtech.tests.test_config_loading -v`

Expected: FAIL because broad categories and standalone weak terms remain.

- [ ] **Step 3: Implement the eight categories**

Use specific event phrases such as:

```yaml
- category: product_approval_launch
  description: Important device and consumables approvals and launches
  keywords:
    - keyword: medical device approval
      synonyms: [medical device approved, device regulatory approval, medical device clearance]
      weight: 6
      language: en
```

Repeat this exact schema for all Category Contract groups. Remove weak standalone `FDA`, `CE`, `factory`, `investment`, `market growth`, and `clinical study`. Copy the completed file verbatim to the compatibility path.

- [ ] **Step 4: Verify GREEN and compatibility**

```bash
.venv/bin/python -m unittest southeast_asia_medtech.tests.test_config_loading -v
cmp -s southeast_asia_medtech/monthly_report/config/keywords.yaml southeast_asia_medtech/config/keywords.yaml
```

- [ ] **Step 5: Commit**

```bash
git add southeast_asia_medtech/monthly_report/config/keywords.yaml southeast_asia_medtech/config/keywords.yaml southeast_asia_medtech/tests/test_config_loading.py
git commit -m "feat: focus SEA monthly report event keywords"
```

---

### Task 2: Build Category, Geography, and Month Queries

**Files:**
- Create: `southeast_asia_medtech/monthly_report/config/event_registry.yaml`
- Create: `southeast_asia_medtech/monthly_report/event_registry/__init__.py`
- Create: `southeast_asia_medtech/monthly_report/event_registry/query_builder.py`
- Create: `southeast_asia_medtech/tests/test_event_registry_query_builder.py`

**Interfaces:**
- Produces: `build_queries(month: str, keywords: dict, settings: dict) -> list[dict]`.
- Each query contains `category_id`, `date_start`, `date_end`, `keywords`, `locations`, `languages`, `max_items`.

- [ ] **Step 1: Write failing query tests**

```python
def test_queries_cover_categories_geographies_and_exact_month(self):
    queries = build_queries("2026-07", keyword_config(), settings())
    self.assertEqual({q["category_id"] for q in queries}, MONTHLY_CATEGORY_IDS)
    self.assertEqual({q["date_start"] for q in queries}, {"2026-07-01"})
    self.assertEqual({q["date_end"] for q in queries}, {"2026-07-31"})
    self.assertEqual(set(queries[0]["locations"]), {
        "Singapore", "Malaysia", "Thailand", "Indonesia", "Vietnam",
        "Philippines", "Southeast Asia", "ASEAN",
    })
    self.assertNotIn("watchlist", json.dumps(queries).lower())
```

- [ ] **Step 2: Verify RED**

Run: `.venv/bin/python -m unittest southeast_asia_medtech.tests.test_event_registry_query_builder -v`

- [ ] **Step 3: Add deterministic settings**

```yaml
provider: event_registry
api_base_url: https://eventregistry.org/api/v1
geographies: [Singapore, Malaysia, Thailand, Indonesia, Vietnam, Philippines, Southeast Asia, ASEAN]
languages: [eng, ind]
max_candidates_per_category: 250
target_report_events: {min: 30, max: 60}
request_timeout_seconds: 30
max_retries: 2
```

Evaluate Thai, Vietnamese, and Malay support during the live pilot before adding provider language codes.

- [ ] **Step 4: Implement month validation and one query per category**

Reject any month not matching `^20\d{2}-(0[1-9]|1[0-2])$`. Flatten each category's canonical phrases and synonyms into its query, and compute inclusive first/last calendar dates.

- [ ] **Step 5: Verify and commit**

```bash
.venv/bin/python -m unittest southeast_asia_medtech.tests.test_event_registry_query_builder -v
git add southeast_asia_medtech/monthly_report/config/event_registry.yaml southeast_asia_medtech/monthly_report/event_registry southeast_asia_medtech/tests/test_event_registry_query_builder.py
git commit -m "feat: build Event Registry monthly queries"
```

---

### Task 3: Add the Event Registry Client and Raw Collector

**Files:**
- Create: `southeast_asia_medtech/monthly_report/event_registry/client.py`
- Create: `southeast_asia_medtech/monthly_report/event_registry/collect.py`
- Create: `southeast_asia_medtech/monthly_report/scripts/collect_event_registry.py`
- Create: `southeast_asia_medtech/tests/test_event_registry_client.py`
- Create: `southeast_asia_medtech/tests/test_event_registry_collection.py`

**Interfaces:**
- Produces: `EventRegistryClient.search(query: dict) -> list[dict]`.
- Produces: `collect_month(month: str, client, output_root: Path) -> dict`.
- Writes: `data/raw/<YYYY-MM>/event_registry_articles.json` and `event_registry_manifest.json`.

- [ ] **Step 1: Write failing client tests**

```python
def test_search_requests_full_body_and_event_uri(self):
    session = FakeSession({"articles": {"results": []}})
    EventRegistryClient("secret", session=session).search(sample_query())
    self.assertEqual(session.last_json["articleBodyLen"], -1)
    self.assertTrue(session.last_json["includeArticleBody"])
    self.assertTrue(session.last_json["includeArticleEventUri"])

def test_missing_key_fails_before_network(self):
    with self.assertRaisesRegex(ValueError, "EVENT_REGISTRY_API_KEY"):
        EventRegistryClient("")
```

- [ ] **Step 2: Verify RED**

Run: `.venv/bin/python -m unittest southeast_asia_medtech.tests.test_event_registry_client -v`

- [ ] **Step 3: Implement bounded paginated POST requests**

POST to `/article/getArticles`; request full body, source, concepts, location, publication date, URL, language, and `eventUri`; sort by date and stop at `max_items`. Raise `EventRegistryError` for non-200, malformed JSON, provider errors, or exhausted retries. Never include the API key in error messages.

- [ ] **Step 4: Add mocked artifact tests**

```python
self.assertEqual(manifest["month"], "2026-07")
self.assertEqual(manifest["provider"], "event_registry")
self.assertEqual(manifest["category_count"], 8)
self.assertNotIn("apiKey", json.dumps(manifest))
```

- [ ] **Step 5: Add the CLI without a live call**

```text
python -m southeast_asia_medtech.monthly_report.scripts.collect_event_registry --month 2026-07 --max-candidates-per-category 250
```

Read `EVENT_REGISTRY_API_KEY` from the environment and print only counts and artifact paths.

- [ ] **Step 6: Verify and commit**

```bash
.venv/bin/python -m unittest southeast_asia_medtech.tests.test_event_registry_client southeast_asia_medtech.tests.test_event_registry_collection -v
git add southeast_asia_medtech/monthly_report/event_registry southeast_asia_medtech/monthly_report/scripts southeast_asia_medtech/tests/test_event_registry_client.py southeast_asia_medtech/tests/test_event_registry_collection.py
git commit -m "feat: collect Event Registry monthly candidates"
```

---

### Task 4: Normalize and Deduplicate by Event

**Files:**
- Create: `southeast_asia_medtech/monthly_report/event_registry/normalize.py`
- Create: `southeast_asia_medtech/monthly_report/event_registry/deduplicate.py`
- Create: `southeast_asia_medtech/tests/test_event_registry_normalization.py`
- Create: `southeast_asia_medtech/tests/test_event_registry_deduplication.py`

**Interfaces:**
- Produces: `normalize_article(raw: dict, matched_category: str, month: str) -> dict`.
- Produces: `deduplicate_events(records: list[dict]) -> list[dict]`.
- Fields: `article_id`, `event_uri`, `title`, `body`, `published_date`, `url`, `source_name`, `source_country`, `event_country`, `language`, `primary_category`, `matched_categories`, `company`, `provider`.

- [ ] **Step 1: Write failing normalization tests**

Require a specific title, body length at least 80, ISO date inside the requested month, HTTP(S) URL, source, category, and `provider == "event_registry"`.

- [ ] **Step 2: Write failing deduplication tests**

```python
def test_same_event_uri_becomes_one_event(self):
    result = deduplicate_events([
        record("evt-1", "product_approval_launch", "short body" * 20),
        record("evt-1", "overseas_market_access", "long body" * 40),
    ])
    self.assertEqual(len(result), 1)
    self.assertEqual(set(result[0]["matched_categories"]), {
        "product_approval_launch", "overseas_market_access",
    })
```

Also test canonical-URL fallback when `event_uri` is absent.

- [ ] **Step 3: Verify RED**

Run: `.venv/bin/python -m unittest southeast_asia_medtech.tests.test_event_registry_normalization southeast_asia_medtech.tests.test_event_registry_deduplication -v`

- [ ] **Step 4: Implement normalization and merging**

Use `event_uri` as the primary key; otherwise strip fragments and tracking parameters from URL. Keep the longest valid body and merge category IDs. Choose `primary_category` by highest matched keyword weight, then configuration order.

- [ ] **Step 5: Verify and commit**

```bash
.venv/bin/python -m unittest southeast_asia_medtech.tests.test_event_registry_normalization southeast_asia_medtech.tests.test_event_registry_deduplication -v
git add southeast_asia_medtech/monthly_report/event_registry southeast_asia_medtech/tests/test_event_registry_normalization.py southeast_asia_medtech/tests/test_event_registry_deduplication.py
git commit -m "feat: normalize and deduplicate monthly events"
```

---

### Task 5: Prepare the Monthly Report LLM Batch

**Files:**
- Create: `southeast_asia_medtech/monthly_report/processors/__init__.py`
- Create: `southeast_asia_medtech/monthly_report/processors/prepare_analysis_batch.py`
- Create: `southeast_asia_medtech/monthly_report/prompts/article_analysis_prompt.txt` if the approved Monthly Report prompt branch is not integrated first
- Create: `southeast_asia_medtech/tests/test_monthly_analysis_batch.py`
- Modify: `southeast_asia_medtech/tests/test_prompts.py`

**Interfaces:**
- Produces: `prepare_batch(records: list[dict], month: str) -> list[dict]`.
- Writes: `data/filtered/<YYYY-MM>/event_registry_llm_ready.json`.

- [ ] **Step 1: Write failing isolation and evidence tests**

```python
def test_batch_uses_categories_not_watchlists(self):
    item = prepare_batch([normalized_record()], "2026-07")[0]
    self.assertEqual(item["primary_category"], "manufacturing_capacity_supply_chain")
    self.assertNotIn("customer_relevance", item)
    self.assertNotIn("competitor", json.dumps(item).lower())
    self.assertEqual(item["analysis_status"], "pending")
    self.assertEqual(item["event_uri"], "evt-1")
```

- [ ] **Step 2: Verify RED**

Run: `.venv/bin/python -m unittest southeast_asia_medtech.tests.test_monthly_analysis_batch -v`

- [ ] **Step 3: Implement deterministic prefilter and prompt contract**

Require an approved category, in-month date, complete title/body, and Southeast Asia event/source geography. Do not call an LLM in this step. The later analyzer returns:

```json
{
  "is_medical_device_related": true,
  "include_in_monthly_report": true,
  "primary_category": "manufacturing_capacity_supply_chain",
  "event_type": "capacity_expansion",
  "product_segment": "single_use_consumables",
  "country": "Malaysia",
  "company": "Example Medical",
  "business_relevance": "high",
  "packaging_relevance": "medium",
  "reason_cn": "新增一次性导管产线可能增加无菌包装需求"
}
```

The prompt covers all eight category IDs and never references a Customer/Competitor watchlist.

- [ ] **Step 4: Verify and commit**

```bash
.venv/bin/python -m unittest southeast_asia_medtech.tests.test_monthly_analysis_batch southeast_asia_medtech.tests.test_prompts -v
git add southeast_asia_medtech/monthly_report/processors southeast_asia_medtech/monthly_report/prompts/article_analysis_prompt.txt southeast_asia_medtech/tests/test_monthly_analysis_batch.py southeast_asia_medtech/tests/test_prompts.py
git commit -m "feat: prepare monthly industry analysis batch"
```

---

### Task 6: Select 30–60 Unique Monthly Events

**Files:**
- Create: `southeast_asia_medtech/monthly_report/processors/select_report_events.py`
- Create: `southeast_asia_medtech/tests/test_monthly_event_selection.py`

**Interfaces:**
- Produces: `select_report_events(analyzed: list[dict], minimum: int = 30, maximum: int = 60) -> tuple[list[dict], dict]`.
- Writes: `data/analyzed/<YYYY-MM>/monthly_report_events.json` and selection manifest.

- [ ] **Step 1: Write failing selection tests**

Keep only records with both medical-device relevance and Monthly Report inclusion. Enforce unique `event_uri`, maximum 60, and sorting by business relevance, packaging relevance, evidence completeness, then publication date. Assert:

```python
self.assertEqual(manifest["target_min"], 30)
self.assertEqual(manifest["target_max"], 60)
self.assertEqual(manifest["selected_count"], len(selected))
self.assertEqual(manifest["shortfall"], max(0, 30 - len(selected)))
```

- [ ] **Step 2: Verify RED**

Run: `.venv/bin/python -m unittest southeast_asia_medtech.tests.test_monthly_event_selection -v`

- [ ] **Step 3: Implement stable selection**

Map `high`, `medium`, `low` to `3`, `2`, `1`. Prefer explicit packaging evidence over inferred packaging value at equal business relevance. Never manufacture or pad events to reach 30.

- [ ] **Step 4: Verify and commit**

```bash
.venv/bin/python -m unittest southeast_asia_medtech.tests.test_monthly_event_selection -v
git add southeast_asia_medtech/monthly_report/processors/select_report_events.py southeast_asia_medtech/tests/test_monthly_event_selection.py
git commit -m "feat: select unique monthly report events"
```

---

### Task 7: Run a Bounded Live Coverage Pilot

**Files:**
- Create after approved run: `southeast_asia_medtech/data/filtered/<YYYY-MM>/event_registry_coverage_report.json`
- Modify only for reproduced defects: Event Registry modules and matching fixture tests

**Interfaces:**
- Consumes: locally set `EVENT_REGISTRY_API_KEY`, one approved month, eight categories, eight geographies.
- Produces: raw/valid/unique counts, body completeness, deduplication rate, category/geography/language coverage, estimated relevant count, and limitations.

- [ ] **Step 1: Obtain explicit approval and local key availability**

Ask the user to set the environment variable locally. Confirm only whether it exists; never print its value.

- [ ] **Step 2: Run one bounded month**

```bash
.venv/bin/python -m southeast_asia_medtech.monthly_report.scripts.collect_event_registry --month 2026-07 --max-candidates-per-category 250
```

- [ ] **Step 3: Validate outputs**

Assert every record is in-month, has full evidence and an approved category, contains no key, and is unique by `event_uri` after deduplication. Confirm no Customer Analysis config was loaded.

- [ ] **Step 4: Write the coverage report**

```json
{
  "raw_article_count": 0,
  "valid_article_count": 0,
  "unique_event_count": 0,
  "full_body_rate": 0.0,
  "deduplication_rate": 0.0,
  "estimated_relevant_event_count": 0,
  "categories": {},
  "geographies": {},
  "languages": {},
  "limitations": []
}
```

Success means enough complete unique candidates to make 30–60 selected events plausible. If not, report the gap without silently widening keywords.

- [ ] **Step 5: Run full offline verification**

```bash
.venv/bin/python -m unittest discover -s southeast_asia_medtech/tests -v
git diff --check
cmp -s southeast_asia_medtech/monthly_report/config/keywords.yaml southeast_asia_medtech/config/keywords.yaml
```

- [ ] **Step 6: Commit only sanitized evidence and fixture-backed corrections**

Do not commit API keys or raw copyrighted full-text artifacts.

```bash
git add southeast_asia_medtech/monthly_report southeast_asia_medtech/config/keywords.yaml southeast_asia_medtech/tests
git commit -m "test: validate Event Registry monthly coverage"
```
