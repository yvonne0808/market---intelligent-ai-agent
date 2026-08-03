# China WeChat Monthly Report Workflow Documentation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add one durable, user-facing workflow handbook for the China WeChat Medical Device and Pharma monthly-report process.

**Architecture:** Create one standalone Markdown file in the root project's `docs/` directory. It summarizes the recurring business workflow and links to existing technical design documents instead of duplicating implementation details. It explicitly separates local review from public deployment.

**Tech Stack:** Markdown and Git only.

## Global Constraints

- Cover only `china-wechat-med-phar/`; do not document `southeast_asia_medtech/`.
- Do not run crawlers, invoke an LLM, regenerate reports, edit data, or publish a website update.
- Keep the handbook in the root checkout, not under `.worktrees/`.
- Do not alter existing reports, prompts, scripts, or `public_share/`.

---

### Task 1: Create the recurring monthly-report handbook

**Files:**
- Create: `docs/china-wechat-monthly-report-workflow.md`

**Interfaces:**
- Consumes: Existing directory conventions, monthly-report prompt decisions, and local-review workflow records.
- Produces: A single Markdown handbook future agents can read before beginning recurring China WeChat report work.

- [x] **Step 1: Create the handbook with stable operational sections**

Include these sections, in this order:

```markdown
# China WeChat Monthly Report Workflow

## Purpose and scope
## Before starting
## Standard monthly workflow
## Report content decisions
## Output map
## Review and publication rules
## Handoff checklist for future runs
## Related technical records
```

The workflow must describe Medical Device and Pharma as separate report streams,
state that DeepSeek analysis resumes from saved article IDs and skips duplicates,
and state that public publication requires an explicit user instruction.

- [x] **Step 2: Add exact project-relative paths and commands**

Document the recurring locations without hard-coding a user home directory:

```text
china-wechat-med-phar/data/raw/
china-wechat-med-phar/data/filtered/
china-wechat-med-phar/data/analyzed/
china-wechat-med-phar/public_share/reports/
china-wechat-med-phar/public_share/
china-wechat-med-phar/scripts/
```

Include the standard China entry-point form:

```bash
.venv/bin/python china-wechat-med-phar/scripts/main.py
```

- [x] **Step 3: Record current editorial decisions exactly**

State that monthly reports should retain Executive Summary and supporting
article evidence, rank Top Opportunities, use linked weekly news lists, lower
the priority of regulation-only news, and distinguish source-confirmed facts
from inference. State that a concise PDF is local review-only unless the user
explicitly approves publication.

- [x] **Step 4: Review the document for scope and accuracy**

Run:

```bash
rg -n 'southeast_asia_medtech|publish|DeepSeek|Executive Summary|regulation|public_share' \
  docs/china-wechat-monthly-report-workflow.md
```

Expected: China-only scope is explicit; the publication gate, saved-analysis
resume behavior, editorial choices, and production checkout are all present.

- [x] **Step 5: Commit only the handbook and its plan**

```bash
git add docs/china-wechat-monthly-report-workflow.md \
  docs/superpowers/plans/2026-08-03-china-wechat-monthly-report-workflow.md
git commit -m "docs: add China WeChat monthly report workflow"
```
