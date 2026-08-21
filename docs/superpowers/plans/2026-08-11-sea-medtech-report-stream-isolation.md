# SEA MedTech Report Stream Isolation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** Build independent Monthly Report and Customer Analysis source, prompt, processing, data, and website-asset pipelines without collecting articles, calling an LLM, publishing, or deleting legacy data.

**Architecture:** Add explicit stream contracts, give each stream its own source registry, prompts, schemas, cache versions, output roots, and website assets, and share only low-level utilities. Preserve old paths through compatibility reads and a dry-run-first migration tool.

**Tech Stack:** Python 3, PyYAML, unittest, JSON, Next.js 16, React 19, TypeScript, Node test runner, GitHub Pages static export.

## Global Constraints

- A source has exactly one owning stream.
- Monthly Report does not use TOP 20 customer admission rules.
- Customer Analysis does not use include_in_monthly_report.
- Cache identity contains article_id, stream, and prompt_version.
- Approved output takes precedence over draft output.
- Invalid stream resources fail closed; no cross-stream fallback is allowed.
- Existing files are preserved; no legacy file is deleted.
- Do not collect articles, call an LLM, regenerate an official report, push, publish, or change the China WeChat workflow.
- Run Python tests with .venv/bin/python from /Users/yvonne/Desktop/forecasting/monthly-report-library.

---

### Task 1: Stream Contracts and Path Guards

**Files:**
- Create: southeast_asia_medtech/shared/__init__.py
- Create: southeast_asia_medtech/shared/stream_contracts.py
- Test: southeast_asia_medtech/tests/test_stream_contracts.py

**Interfaces:**
- Produces: ReportStream, StreamContract, contract_for(stream), ensure_stream_path(path, contract).

- [ ] **Step 1: Write failing tests**

    class StreamContractTests(unittest.TestCase):
        def test_resources_are_distinct(self):
            monthly = contract_for(ReportStream.MONTHLY_REPORT)
            customer = contract_for(ReportStream.CUSTOMER_ANALYSIS)
            self.assertNotEqual(monthly.source_path, customer.source_path)
            self.assertNotEqual(monthly.article_prompt_path, customer.article_prompt_path)
            self.assertNotEqual(monthly.data_root, customer.data_root)

        def test_cross_stream_path_is_rejected(self):
            monthly = contract_for(ReportStream.MONTHLY_REPORT)
            with self.assertRaisesRegex(ValueError, "outside monthly_report data root"):
                ensure_stream_path(
                    Path("southeast_asia_medtech/data/customer_analysis/x.json"),
                    monthly,
                )

- [ ] **Step 2: Verify failure**

Run: .venv/bin/python -m unittest southeast_asia_medtech.tests.test_stream_contracts -v

Expected: ModuleNotFoundError for shared.stream_contracts.

- [ ] **Step 3: Implement the contract**

Define ReportStream values monthly_report and customer_analysis. Define an immutable StreamContract with source_path, article_prompt_path, report_prompt_path, data_root, article_prompt_version, and report_prompt_version. Use versions monthly-report-article-v1, monthly-report-generation-v1, customer-analysis-article-v1, and customer-analysis-generation-v3. Implement ensure_stream_path using resolved-path containment.

- [ ] **Step 4: Verify and commit**

Run the Step 2 command; expect two passing tests.

Commit only the three Task 1 files with message: feat: define SEA MedTech report stream contracts

---

### Task 2: Split Source Registries

**Files:**
- Create: southeast_asia_medtech/monthly_report/config/sources.yaml
- Create: southeast_asia_medtech/monthly_report/config/keywords.yaml
- Create: southeast_asia_medtech/customer_analysis/config/sources.yaml
- Modify: southeast_asia_medtech/config/config_loader.py
- Test: southeast_asia_medtech/tests/test_stream_sources.py

**Interfaces:**
- Consumes: Task 1 contracts.
- Produces: load_stream_sources(stream, data=None) -> dict[str, Any].

- [ ] **Step 1: Write ownership tests**

    def test_monthly_sources_exclude_customer_sites(self):
        rows = load_stream_sources(ReportStream.MONTHLY_REPORT)["sources"]
        ids = {row["source_id"] for row in rows if row["enabled"]}
        self.assertIn("sg_hsa_announcements", ids)
        self.assertNotIn("customer_bd_news", ids)
        self.assertTrue(all(row["stream"] == "monthly_report" for row in rows))

    def test_customer_sources_include_google_news(self):
        rows = load_stream_sources(ReportStream.CUSTOMER_ANALYSIS)["sources"]
        ids = {row["source_id"] for row in rows if row["enabled"]}
        self.assertIn("google_news_customer_discovery", ids)
        self.assertIn("customer_bd_news", ids)
        self.assertNotIn("sg_hsa_announcements", ids)

    def test_mismatched_declaration_fails(self):
        with self.assertRaisesRegex(ValueError, "source stream mismatch"):
            load_stream_sources(
                ReportStream.MONTHLY_REPORT,
                data={"sources": [{"source_id": "bad", "enabled": True,
                                   "stream": "customer_analysis"}]},
            )

- [ ] **Step 2: Verify failure**

Run the new source test module. Expected: import failure for load_stream_sources.

- [ ] **Step 3: Create Monthly sources**

Copy HSA, MDA, Thai FDA, Farmalkes, VIMDA, Philippines FDA, Healthcare Channel Partners, MIDA/AMMI, and MDDI rows without inventing selectors or endpoints. Add stream: monthly_report. Rename customer-targeted labels and notes to market scopes. Copy the keyword taxonomy unchanged.

- [ ] **Step 4: Create Customer sources**

Copy BD, Baxter, ResMed, Smith+Nephew, J&J MedTech, Olympus, and Malaysia glove IR rows with stream: customer_analysis. Add one enabled google_news_customer_discovery row with workflow customer_discovery and feed_url https://news.google.com/rss/search.

- [ ] **Step 5: Implement strict loading**

    def load_stream_sources(stream, *, data=None):
        expected = ReportStream(stream)
        loaded = data if data is not None else _load_yaml(
            contract_for(expected).source_path
        )
        rows = loaded.get("sources")
        if not isinstance(rows, list):
            raise ValueError("sources must be a list")
        for row in rows:
            if row.get("stream") != expected.value:
                raise ValueError(
                    f"source stream mismatch: {row.get('source_id')}"
                )
        return loaded

Retain load_sources only as a documented legacy loader.

- [ ] **Step 6: Verify and commit**

Run test_stream_sources and test_config_loading. Commit Task 2 files with message: feat: split SEA MedTech source registries

---

### Task 3: Stream-Owned Collectors

**Files:**
- Modify: southeast_asia_medtech/scrapers/collect_monthly_articles.py
- Modify: southeast_asia_medtech/scrapers/run_customer_news_discovery.py
- Test: southeast_asia_medtech/tests/test_customer_news_discovery.py
- Test: southeast_asia_medtech/tests/test_scraper_parsers.py

**Interfaces:**
- Consumes: Tasks 1-2.
- Produces: load_collection_sources() and load_discovery_source().

- [ ] **Step 1: Add no-network tests**

    def test_monthly_collection_sources_are_monthly_only(self):
        rows = monthly_collector.load_collection_sources()
        self.assertTrue(all(row["stream"] == "monthly_report" for row in rows))
        self.assertNotIn("customer_bd_news",
                         {row["source_id"] for row in rows})

    def test_discovery_provider_comes_from_customer_config(self):
        source = customer_discovery.load_discovery_source()
        self.assertEqual(source["source_id"],
                         "google_news_customer_discovery")

- [ ] **Step 2: Verify failure**

Run both affected test modules. Expect missing helper failures and no live request.

- [ ] **Step 3: Implement Monthly ownership**

Load only load_stream_sources(MONTHLY_REPORT). Build raw, normalized, and collection summary paths from the Monthly contract data root. Guard every output path before writing.

- [ ] **Step 4: Implement Customer ownership**

Load exactly one enabled source with workflow customer_discovery. Use its feed_url instead of a hard-coded Google URL. Write only beneath data/customer_analysis/discovery and guard paths.

- [ ] **Step 5: Verify and commit**

Run both test modules. Commit scraper and test changes with message: refactor: isolate SEA MedTech collection streams

---

### Task 4: Split Article Prompts and Analysis Schemas

**Files:**
- Create: southeast_asia_medtech/monthly_report/prompts/article_analysis_prompt.txt
- Create: southeast_asia_medtech/customer_analysis/prompts/article_analysis_prompt.txt
- Create: southeast_asia_medtech/monthly_report/processors/analyze.py
- Create: southeast_asia_medtech/customer_analysis/processors/analyze.py
- Modify: southeast_asia_medtech/processors/prepare_llm_batch.py
- Modify: southeast_asia_medtech/processors/analyze_with_deepseek.py
- Test: southeast_asia_medtech/tests/test_stream_prompts.py
- Modify: southeast_asia_medtech/tests/test_prompts.py

**Interfaces:**
- Produces: prepare_jobs(stream, articles), validate_monthly_result, validate_customer_result.

- [ ] **Step 1: Write prompt boundary tests**

    def test_monthly_prompt_has_no_customer_contract(self):
        text = contract_for(
            ReportStream.MONTHLY_REPORT
        ).article_prompt_path.read_text()
        self.assertIn('"include_in_monthly_report"', text)
        self.assertIn('"market_relevance_score"', text)
        self.assertNotIn('"matched_customers"', text)
        self.assertNotIn("TOP 20", text)

    def test_customer_prompt_has_no_monthly_admission_field(self):
        text = contract_for(
            ReportStream.CUSTOMER_ANALYSIS
        ).article_prompt_path.read_text()
        self.assertIn('"include_in_customer_analysis"', text)
        self.assertIn('"matched_customers"', text)
        self.assertNotIn('"include_in_monthly_report"', text)

- [ ] **Step 2: Verify failure**

Run test_stream_prompts. Expected: missing prompt files/functions.

- [ ] **Step 3: Write the Monthly article prompt**

Require strict JSON with stream=monthly_report, article_id, include_in_monthly_report, market_relevance_score, importance, category fields, report countries, event status/type, companies/products, Chinese summary and market/supply-chain implications, packaging score/reason, uncertainty, confidence, and takeaway. Require explicit Southeast Asia evidence and accurate proposed/completed status. Do not include TOP 20 rules.

- [ ] **Step 4: Write the Customer article prompt**

Adapt the existing customer-priority prompt to require stream=customer_analysis, include_in_customer_analysis, customer relevance, matched customers, competitors, related groups, event type, competitive relationship, customer impact, commercial implication, packaging evidence, follow-up, uncertainty, confidence, and takeaway. Remove monthly admission fields.

- [ ] **Step 5: Parameterize preparation and analysis**

    def prepare_jobs(stream, articles):
        contract = contract_for(stream)
        return [{
            "job_id": f"{contract.stream.value}:{a['article_id']}",
            "stream": contract.stream.value,
            "prompt_version": contract.article_prompt_version,
            "cache_key": (
                f"{contract.stream.value}:{a['article_id']}:"
                f"{contract.article_prompt_version}"
            ),
            "system_prompt_path": str(contract.article_prompt_path),
            "article": a,
            "analysis_status": "pending",
            "analysis_result": None,
            "analysis_error": "",
        } for a in articles]

Require explicit --stream in the compatibility analyzer or use stream-owned wrappers. Select prompt, validator, cache, input, and output from the contract; never fall back to the shared prompt. Keep provider calls injectable.

- [ ] **Step 6: Implement validators**

Monthly rejects Customer-only admission fields and invalid market categories, countries, statuses, and score ranges. Customer rejects monthly admission fields, unknown watchlist names, invalid relevance values, and wrong stream identity.

- [ ] **Step 7: Verify and commit**

Run test_stream_prompts and test_prompts. Commit Task 4 files with message: feat: split SEA MedTech article analysis prompts

---

### Task 5: Approval-Aware Monthly Report Workflow

**Files:**
- Create: southeast_asia_medtech/monthly_report/prompts/report_generation_prompt.txt
- Create: southeast_asia_medtech/monthly_report/reports/workflow.py
- Test: southeast_asia_medtech/tests/test_monthly_report_workflow.py

**Interfaces:**
- Produces: prepare_monthly_issue, validate_monthly_report, select_publishable_report, export_monthly_assets.

- [ ] **Step 1: Write evidence and approval tests**

    def test_only_included_monthly_evidence_is_retained(self):
        ledger = prepare_monthly_issue([
            {"stream": "monthly_report", "article_id": "keep",
             "url": "https://e/1", "include_in_monthly_report": True},
            {"stream": "monthly_report", "article_id": "drop",
             "url": "https://e/2", "include_in_monthly_report": False},
        ], issue="2026-07")
        self.assertEqual(
            [row["article_id"] for row in ledger["events"]],
            ["keep"],
        )

    def test_approved_precedes_draft(self):
        write_json(issue_dir / "draft.json", {"status": "draft"})
        write_json(issue_dir / "approved.json", {"status": "approved"})
        report = select_publishable_report(issue_dir)
        self.assertEqual(report["publication_status"], "approved")

- [ ] **Step 2: Verify failure**

Run the new workflow test module. Expect missing functions.

- [ ] **Step 3: Write the final Monthly prompt**

Require strict JSON sections for metadata, executive summary, priority signals, country developments, regulation/safety, procurement/commercialization, manufacturing/supply chain, financing/partnerships/channels, packaging signals, and coverage limitations. Every material statement cites evidence article IDs.

- [ ] **Step 4: Implement workflow**

Reject non-Monthly rows; retain only admitted evidence; canonical-URL deduplicate; sort by market relevance, packaging relevance, and date. Write evidence.json and manifest.json under data/monthly_report/issues/YYYY-MM. Validate cited IDs before writing draft.json.

- [ ] **Step 5: Implement safe publication selection**

Choose approved.json when present, otherwise draft.json and label it draft. Validate report and events before atomic asset replacement. Generation/export failure leaves old approved data and assets unchanged.

- [ ] **Step 6: Verify and commit**

Run test_monthly_report_workflow. Commit Task 5 files with message: feat: add approval-aware monthly report workflow

---

### Task 6: Align Customer Analysis with Its Contract

**Files:**
- Rename: southeast_asia_medtech/customer_analysis/prompts/customer_analysis_report_prompt.txt to report_generation_prompt.txt
- Modify: southeast_asia_medtech/customer_analysis/report_generator.py
- Modify: southeast_asia_medtech/customer_analysis/workflow.py
- Modify: southeast_asia_medtech/customer_analysis/run.py
- Test: southeast_asia_medtech/tests/test_customer_analysis.py

**Interfaces:**
- Consumes: Customer contract and Customer article schema.

- [ ] **Step 1: Add isolation tests**

    def test_customer_ledger_rejects_monthly_rows(self):
        with self.assertRaisesRegex(ValueError, "customer_analysis"):
            build_event_ledger([
                {"stream": "monthly_report", "article_id": "wrong",
                 "url": "https://e"}
            ], source_label="test")

    def test_generation_version_is_isolated(self):
        self.assertEqual(
            PROMPT_VERSION,
            "customer-analysis-generation-v3",
        )

- [ ] **Step 2: Verify failure**

Run test_customer_analysis.

- [ ] **Step 3: Wire Customer prompt and schema**

Load the Customer report prompt/version from its contract. Require stream=customer_analysis plus include_in_customer_analysis=True for evidence admission.

- [ ] **Step 4: Guard paths and approval behavior**

Move defaults beneath the Customer data root and guard caller-provided outputs. Retain approved.json precedence. Test that generation failure does not change exported assets.

- [ ] **Step 5: Verify and commit**

Run test_customer_analysis. Commit Task 6 files with message: refactor: isolate SEA MedTech customer analysis workflow

---

### Task 7: Non-Destructive Data Migration

**Files:**
- Create: southeast_asia_medtech/tools/__init__.py
- Create: southeast_asia_medtech/tools/migrate_report_stream_data.py
- Test: southeast_asia_medtech/tests/test_stream_migration.py

**Interfaces:**
- Produces: build_migration_plan, verify_copy, CLI --dry-run and --copy.

- [ ] **Step 1: Write safety tests**

    def test_plan_copies_only_and_excludes_legacy_july_analysis(self):
        plan = build_migration_plan(Path("southeast_asia_medtech"))
        self.assertTrue(all(item["operation"] == "copy" for item in plan))
        self.assertFalse(any(
            "data/analyzed/2026-07" in str(item["source"])
            for item in plan
        ))

    def test_verify_copy_checks_urls(self):
        payload = [{"url": "https://example.com/a?utm_source=x"}]
        source.write_text(json.dumps(payload))
        target.write_text(json.dumps(payload))
        self.assertEqual(verify_copy(source, target)["records"], 1)

- [ ] **Step 2: Verify failure**

Run test_stream_migration. Expected: missing module.

- [ ] **Step 3: Implement allowlisted copies**

Allow only legacy raw/normalized/filtered months to Monthly roots, customer_discovery to Customer discovery, and analyzed/customer_discovery_* to Customer analyzed. Record data/analyzed/2026-07 as legacy_customer_priority_analysis_not_migrated.

- [ ] **Step 4: Implement dry-run-first verification**

Default to --dry-run; require --copy to write. Refuse non-identical target overwrites. Never delete or move. Compare JSON arrays by record count and canonical URL set and other artifacts by SHA-256. Emit a manifest.

- [ ] **Step 5: Verify and commit**

Run test_stream_migration and the migration CLI with --dry-run. Commit Task 7 files with message: feat: add safe SEA MedTech stream migration tool. Do not run --copy.

---

### Task 8: Split Website Assets

**Files:**
- Create: /Users/yvonne/Desktop/forecasting/sea-medtech-monthly-report/public/monthly-report/report.json
- Create: /Users/yvonne/Desktop/forecasting/sea-medtech-monthly-report/public/monthly-report/events.json
- Modify: /Users/yvonne/Desktop/forecasting/sea-medtech-monthly-report/app/page.tsx
- Modify: /Users/yvonne/Desktop/forecasting/sea-medtech-monthly-report/tests/github-pages.test.mjs
- Modify: /Users/yvonne/Desktop/forecasting/sea-medtech-monthly-report/README.md

**Interfaces:**
- Produces: page-specific static asset fetches.

- [ ] **Step 1: Add failing asset assertions**

    assert.match(monthlySource, /monthly-report\/report\.json/);
    assert.doesNotMatch(monthlySource, /customer-analysis\/report\.json/);
    assert.match(customerSource, /customer-analysis\/report\.json/);
    assert.doesNotMatch(customerSource, /monthly-report\/report\.json/);

- [ ] **Step 2: Verify failure**

In the website repository run node --test tests/github-pages.test.mjs. Expect Monthly path assertions to fail.

- [ ] **Step 3: Seed isolated assets**

Transform existing public/report-data.json into a Monthly events array and metadata object without changing event URLs/content. Retain the root file for compatibility.

- [ ] **Step 4: Change the Monthly loader**

Fetch basePath/monthly-report/report.json and basePath/monthly-report/events.json with Promise.all. Keep Customer fetches under customer-analysis only. Document all four authoritative paths.

- [ ] **Step 5: Build, test, lint, and commit locally**

Run:
1. NEXT_PUBLIC_BASE_PATH=/sea-medtech-monthly-report npm run build:pages
2. node --test tests/github-pages.test.mjs
3. npm run lint

Commit only Task 8 files in the website repository with message: refactor: isolate monthly report website assets. Do not push or publish.

---

### Task 9: Documentation and Full Verification

**Files:**
- Modify: southeast_asia_medtech/prompts/README.md
- Modify: southeast_asia_medtech/customer_analysis/README.md
- Modify: southeast_asia_medtech/JULY_2026_COLLECTION_README.md
- Modify: southeast_asia_medtech/tests/test_config_loading.py

- [ ] **Step 1: Add compatibility tests**

Assert new stream modules do not import the legacy source loader, executable Python does not reference the old shared prompt, and legacy July customer-priority analysis is not treated as Monthly v1.

- [ ] **Step 2: Document operations**

Document two registries, two prompt pairs, explicit-stream no-API preparation, draft/approved behavior, migration dry run, and legacy July exclusion.

- [ ] **Step 3: Run full Python verification**

Run:
1. .venv/bin/python -m compileall -q southeast_asia_medtech
2. .venv/bin/python -m unittest discover -s southeast_asia_medtech/tests -p test_*.py
3. .venv/bin/python -m southeast_asia_medtech.tools.migrate_report_stream_data --dry-run
4. git diff --check
5. git status --short

Expected: compilation/tests pass, dry run lists only allowlisted actions, and unrelated artifacts/mentor_* remain untouched.

- [ ] **Step 4: Re-run website verification**

Run build:pages with the base path, Node tests, lint, and git status in the website repository.

- [ ] **Step 5: Commit documentation**

Commit only Task 9 files with message: docs: document isolated SEA MedTech report streams

- [ ] **Step 6: Stop for explicit authorization**

Report verification evidence, dry-run counts, and both repository commit IDs. Do not run migration --copy, collect, call an LLM, push, or publish.

