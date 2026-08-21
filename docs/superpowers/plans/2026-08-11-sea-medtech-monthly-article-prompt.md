# SEA MedTech Monthly Article Prompt Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create the Southeast Asia Monthly Report single-article analysis Prompt without changing Customer Analysis or running analysis.

**Architecture:** Add one section-owned Prompt under `monthly_report/prompts/` and validate its geography, five-category taxonomy, scoring fields, strict JSON contract, and isolation from Customer Analysis with a focused unit test.

**Tech Stack:** Plain-text Prompt, Python `unittest`.

## Global Constraints

- Preserve the approved China Prompt business focus.
- Use only five primary categories: 产品与商业化、制造与产能、渠道与供应链、融资并购与合作、其他.
- Specific product approval/registration/certification/recall belongs to 产品与商业化.
- General regulation and macro policy belongs to 其他 and is normally excluded.
- Do not edit Customer Analysis, collect articles, call an LLM, migrate data, or publish.

### Task 1: Monthly Article Analysis Prompt

**Files:**
- Create: `southeast_asia_medtech/monthly_report/prompts/article_analysis_prompt.txt`
- Modify: `southeast_asia_medtech/tests/test_prompts.py`

**Interfaces:**
- Produces: one strict JSON analysis contract consumed by a future Monthly analyzer.

- [ ] **Step 1: Write failing tests**

Assert the file exists; contains Southeast Asia geography, `include_in_monthly_report`, `packaging_relevance_score`, and all required JSON fields; defines exactly the five approved primary categories; assigns concrete approvals/recalls to 产品与商业化; assigns general policy to 其他; and contains no TOP 20/customer-analysis rules.

- [ ] **Step 2: Verify RED**

Run `.venv/bin/python -m unittest southeast_asia_medtech.tests.test_prompts -v` and confirm failure because the file does not exist.

- [ ] **Step 3: Write the Prompt**

Adapt the complete supplied China Prompt section-by-section, replacing China/weekly/WeChat assumptions with the approved Southeast Asia/monthly/website-source rules while retaining device, consumables, commercialization, manufacturing, transactions, channels, supply chain, and packaging detail.

- [ ] **Step 4: Verify GREEN**

Run the focused Prompt tests, then the complete SEA MedTech test suite. Confirm no API or collection command runs.

- [ ] **Step 5: Commit and stop**

Commit the Prompt and tests locally. Do not push, publish, or run analysis.

