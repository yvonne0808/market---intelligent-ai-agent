# SEA MedTech Monthly Source Expansion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** Add and validate six Monthly Report source families and supplement the existing MIDA source using strict five-record sampling.

**Architecture:** Extend only the Monthly source registry, use the existing generic listing/detail pipeline where it produces valid records, and add source-specific candidate adapters only when a fixture proves the generic path cannot represent the site's listing. Run each source separately, preserve exact access/parsing failures, and enable only sources with stable valid extraction.

**Tech Stack:** Python 3, requests, BeautifulSoup, PyYAML, unittest, existing PoliteHttpClient and run_phase1_sources sampler.

## Global Constraints

- Monthly Report only; do not modify Customer Analysis.
- Maximum five requested records per source.
- No LLM/API analysis, full monthly crawl, report generation, website update, push, or publication.
- HTTP 200 is not success without title, publication date, canonical detail URL, relevant body, and valid record.
- Do not bypass authentication, CAPTCHA, paywall, robots rules, or access controls.
- MIDA remains one source ID.
- Run Python with /Users/yvonne/Desktop/forecasting/monthly-report-library/.venv/bin/python.

---

### Task 1: Register Candidate Sources as Disabled

**Files:**
- Modify: southeast_asia_medtech/monthly_report/config/sources.yaml
- Modify: southeast_asia_medtech/config/sources.yaml
- Modify: southeast_asia_medtech/tests/test_config_loading.py

**Interfaces:**
- Produces source IDs: th_krungsri_medical_devices, apac_asian_hhm_devices, th_thailand_medical_news_devices, apac_healthcare_asia_medtech, global_labmedica_industry, apac_biospectrum_medical_devices.
- Updates source ID: my_mida_ammi.

- [ ] Step 1: Write failing registry tests

Assert all six IDs exist in both compatibility and owned registries, begin with enabled=false, have unique IDs, use the approved list URLs, contain required selectors/search terms/article URL patterns, and the two registry files remain byte-identical. Assert my_mida_ammi contains the Healthcare Services URL exactly once and no second MIDA source exists.

- [ ] Step 2: Verify RED

Run:
    .venv/bin/python -m unittest southeast_asia_medtech.tests.test_config_loading -v

Expected: assertions fail because candidate IDs are absent.

- [ ] Step 3: Add the six disabled rows

Use workflows research_insight, news_listing, packaging_news, investment_news, competitor_news, or channel_news only after adding any missing workflow to allowed_workflows. Preserve schema-required fields. Configure:

- Krungsri list URL: https://www.krungsri.com/en/research/industry/industry-outlook/other-industries/medical-devices/io
- Asian HHM list URL: https://www.asianhhm.com/
- Thailand Medical News list URL: https://www.thailandmedical.news/articles/medical-devices
- Healthcare Asia list URL: https://healthcareasiamagazine.com/
- LabMedica list URL: https://www.labmedica.com/industry-news/
- BioSpectrum list URL: https://www.biospectrumasia.com/category/med-tech/medical-devices

Start all new rows disabled so the ordinary monthly collector cannot use unverified sources.

- [ ] Step 4: Supplement MIDA

Add the submitted Healthcare Services URL as a secondary discovery/reference endpoint. Keep Media Releases first and document that undated industry pages are not monthly records.

- [ ] Step 5: Verify GREEN and commit

Run config tests and YAML parsing. Commit config/test changes with message:
    feat: register SEA MedTech monthly source candidates

---

### Task 2: Make Explicit Disabled Sources Testable

**Files:**
- Modify: southeast_asia_medtech/scrapers/run_phase1_sources.py
- Modify: southeast_asia_medtech/tests/test_scraper_parsers.py

**Interfaces:**
- Produces: select_sources(config, requested_ids) -> list[dict].
- Contract: explicit --source IDs may be sampled while disabled; an unfiltered run still uses enabled sources only.

- [ ] Step 1: Write failing selection tests

    def test_explicit_source_can_sample_disabled_candidate(self):
        config = {"sources": [
            {"source_id": "candidate", "enabled": False},
            {"source_id": "live", "enabled": True},
        ]}
        self.assertEqual(
            [row["source_id"] for row in select_sources(config, {"candidate"})],
            ["candidate"],
        )

    def test_unfiltered_selection_keeps_enabled_only(self):
        config = {"sources": [
            {"source_id": "candidate", "enabled": False},
            {"source_id": "live", "enabled": True},
        ]}
        self.assertEqual(
            [row["source_id"] for row in select_sources(config, set())],
            ["live"],
        )

- [ ] Step 2: Verify RED

Run the focused parser tests. Expected: select_sources is missing.

- [ ] Step 3: Implement minimal selection

    def select_sources(config, requested_ids):
        rows = config["sources"]
        if requested_ids:
            selected = [row for row in rows if row["source_id"] in requested_ids]
            missing = requested_ids - {row["source_id"] for row in selected}
            if missing:
                raise ValueError(f"Unknown source_id(s): {sorted(missing)}")
            return selected
        return [row for row in rows if row.get("enabled") is True]

Use this helper in run(). This enables safe candidate testing without activating candidates in normal runs.

- [ ] Step 4: Verify and commit

Run focused and full scraper tests. Commit with message:
    feat: support explicit sampling of disabled sources

---

### Task 3: Add Fixture-Driven Candidate Extraction Tests

**Files:**
- Create: southeast_asia_medtech/tests/fixtures/monthly_source_candidates/krungsri.html
- Create: southeast_asia_medtech/tests/fixtures/monthly_source_candidates/asian_hhm.html
- Create: southeast_asia_medtech/tests/fixtures/monthly_source_candidates/thailand_medical_news.html
- Create: southeast_asia_medtech/tests/fixtures/monthly_source_candidates/healthcare_asia.html
- Create: southeast_asia_medtech/tests/fixtures/monthly_source_candidates/labmedica.html
- Create: southeast_asia_medtech/tests/fixtures/monthly_source_candidates/biospectrum.html
- Create: southeast_asia_medtech/tests/test_monthly_source_candidates.py
- Modify: southeast_asia_medtech/scrapers/run_phase1_sources.py

**Interfaces:**
- Produces: candidate extraction through existing generic_candidates or focused functions named <source_id>_candidates.

- [ ] Step 1: Capture minimal public listing fixtures

Save only the HTML fragments needed to represent two article cards per source: detail link, specific title, and publication date. Do not store full pages, ads, navigation, or unrelated content.

- [ ] Step 2: Write failing extraction tests

For each source assert:
- two unique canonical detail URLs;
- specific non-navigation titles;
- publication dates retained;
- category/listing URLs rejected as detail URLs;
- ads/events/interviews/hospital awards excluded for Asian HHM and Healthcare Asia;
- disease/pharma content excluded for Thailand Medical News;
- general clinical research excluded for LabMedica;
- Pharma/Biotech content excluded for BioSpectrum.

- [ ] Step 3: Verify RED

Run:
    .venv/bin/python -m unittest southeast_asia_medtech.tests.test_monthly_source_candidates -v

Expected: one or more sources fail under generic extraction.

- [ ] Step 4: Implement the smallest adapters

Prefer selector and article_url_patterns configuration. Add a named adapter only for a source whose fixture cannot pass with the generic parser. Route by source_id in listing_candidates(). Reuse generic_detail and record validation.

- [ ] Step 5: Verify and commit

Run focused and all scraper tests. Commit with message:
    feat: parse SEA MedTech monthly source listings

---

### Task 4: Live Five-Record Sampling

**Files:**
- Modify only when a reproduced live failure requires a fixture-backed parser correction.
- Output: southeast_asia_medtech/data/phase1_samples/source_samples.json
- Output: southeast_asia_medtech/data/phase1_samples/source_sampling_summary.json
- Output: southeast_asia_medtech/logs/phase1_sources.log

**Interfaces:**
- Consumes the six candidate IDs and existing my_mida_ammi.
- Produces strict source summaries and at most five records per source.

- [ ] Step 1: Test sources individually

Run one command per source:
    .venv/bin/python -m southeast_asia_medtech.scrapers.run_phase1_sources --source <source_id> --max-items 5

Use timeout/retry defaults and polite delay. Do not combine sources until individual results are understood.

- [ ] Step 2: Record first-pass evidence

For every source capture candidates_found, valid_records, endpoint_errors, detail failures, acquisition mode, titles, dates, and URLs.

- [ ] Step 3: Diagnose failures systematically

Classify each failure as access_failed, listing_parse_failed, detail_parse_failed, no_relevant_sample, undated_static_reference, or success/partial. For parsing failures, add the smallest sanitized fixture reproducing the live HTML and return to Task 3's RED-GREEN cycle. Do not change selectors by guessing.

- [ ] Step 4: Re-run corrected sources

Re-run only the affected source ID. Stop after at most five valid records. Do not run the full monthly collector.

- [ ] Step 5: Validate output records

Programmatically assert source ID, specific title, parseable date, HTTP(S) canonical detail URL, body length >= 80, relevant medical-device text, and no duplicate URLs.

---

### Task 5: Final Enablement Decisions

**Files:**
- Modify: southeast_asia_medtech/monthly_report/config/sources.yaml
- Modify: southeast_asia_medtech/config/sources.yaml
- Modify: southeast_asia_medtech/tests/test_config_loading.py
- Create: southeast_asia_medtech/docs/2026-08-11-monthly-source-sampling-results.md

**Interfaces:**
- Consumes Task 4 evidence.
- Produces final enabled flags and a source-by-source report.

- [ ] Step 1: Write failing decision tests

Encode the evidence-backed expected enabled state for all six candidates. Assert both source registries remain byte-identical and MIDA remains one source.

- [ ] Step 2: Set final flags and notes

Set enabled=true only for stable valid extraction. Keep enabled=false for blocked, static/undated, or unreliable sources. Add exact limitation notes without presenting failures as success.

- [ ] Step 3: Write the sampling report

For each submitted source report submitted URL, actual list URL, parser strategy, access result, candidate count, valid count, up to five sample titles/dates/URLs, enabled state, and follow-up.

- [ ] Step 4: Full verification

Run:
    .venv/bin/python -m compileall -q southeast_asia_medtech
    .venv/bin/python -m unittest discover -s southeast_asia_medtech/tests -p test_*.py
    git diff --check
    git status --short

Verify no Customer Analysis, analyzed data, report, website, or publishing files changed.

- [ ] Step 5: Commit and stop

Commit configuration, parser, tests, sample outputs, and result report with message:
    feat: validate SEA MedTech monthly source expansion

Report results. Do not run LLM analysis, monthly collection, push, or publish.

