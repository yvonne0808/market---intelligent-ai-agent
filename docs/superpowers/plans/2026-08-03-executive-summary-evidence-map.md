# Executive Summary Evidence Map Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Require both monthly-report prompts to cite two to five analyzed source articles under every Executive Summary conclusion.

**Architecture:** Add the same compact `Evidence / Supporting articles` contract immediately after each prompt's Executive Summary instructions. The contract relies on existing analyzed article fields and does not change scripts, schemas, or current reports.

**Tech Stack:** Plain-text prompts, Python standard-library text assertions.

## Global Constraints

- Modify only the Pharma and Medical Device monthly-report prompts.
- Preserve existing report structure, article JSON schema, rankings, and business logic.
- Each Executive Summary bullet cites two to five current-input articles.
- Each citation includes `article_id`, title, source, publication date, and original link.
- Do not invent source fields; label inference-only support as indirect.

---

### Task 1: Add the shared evidence-map contract

**Files:**
- Modify: `china-wechat-med-phar/prompts/Medical Device/monthly_report_prompt.txt`
- Modify: `china-wechat-med-phar/prompts/Pharma/monthly_report_prompt.txt`

**Interfaces:**
- Consumes: existing input article fields `article_id`, `title`, `source_name`, `published`, and `link`.
- Produces: an `Evidence / Supporting articles` block below every Executive Summary bullet.

- [ ] **Step 1: Write a failing text assertion**

```python
required = (
    "Evidence / Supporting articles",
    "2–5",
    "article_id",
    "source_name",
    "published",
    "link",
    "indirect",
)
for prompt_path in prompt_paths:
    prompt = prompt_path.read_text(encoding="utf-8")
    for term in required:
        assert term in prompt, (prompt_path, term)
```

- [ ] **Step 2: Run the assertion and verify it fails**

Run the Step 1 Python script against both prompt paths. Expected: failure because the existing Executive Summary instructions do not yet define the evidence-map contract.

- [ ] **Step 3: Add identical requirements after each Executive Summary section**

Insert this contract in both prompts:

```text
### Evidence / Supporting articles
For every Executive Summary bullet, add 2–5 supporting articles from the current input:
- [article_id] Title — source_name, published — link
Use only supplied article fields. Never invent an article_id, title, source_name, published date, or link.
If the conclusion is an inference rather than directly disclosed by an article, label the relationship as indirect.
```

- [ ] **Step 4: Run the assertion and verify it passes**

Run the same Step 1 Python script. Expected: every required term appears in both prompts.

- [ ] **Step 5: Check diff scope and commit**

Run `git diff --check` and `git diff --` for only the two prompt files. Commit exactly those files:

```bash
git add "china-wechat-med-phar/prompts/Medical Device/monthly_report_prompt.txt" \
  china-wechat-med-phar/prompts/Pharma/monthly_report_prompt.txt
git commit -m "feat: require executive summary source evidence"
```
