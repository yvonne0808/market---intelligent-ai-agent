# July PDF Homepage Links Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add homepage PDF download buttons for the July Medical Device and Pharma reports.

**Architecture:** Reuse the existing action-button markup in the two July cards. Each new link points to the corresponding already-published `report.pdf` file.

**Tech Stack:** Static HTML, Git, GitHub Pages.

## Global Constraints

- Change only `china-wechat-med-phar/public_share/index.html` in the production checkout.
- Do not stage temporary, cache, or unrelated files.
- Publish to `market-insights/market-insights.github.io` branch `main`.

---

### Task 1: Add and publish July PDF links

**Files:**
- Modify: `china-wechat-med-phar/public_share/index.html:91-124`

**Interfaces:**
- Produces two `<a class="button">PDF</a>` links to the existing Medical Device and Pharma July PDF paths.

- [ ] **Step 1: Add the Medical Device PDF action**

Insert `<a class="button" href="reports/medical-device/monthly/2026-07/report.pdf">PDF</a>` after the July Medical Device View report link.

- [ ] **Step 2: Add the Pharma PDF action**

Insert `<a class="button" href="reports/pharma/monthly/2026-07/report.pdf">PDF</a>` after the July Pharma View report link.

- [ ] **Step 3: Verify exact paths**

Run `rg -n 'medical-device/monthly/2026-07/report.pdf|pharma/monthly/2026-07/report.pdf' index.html` in the nested checkout. Expected: two PDF link lines.

- [ ] **Step 4: Commit and push only index.html**

Run `git add index.html`, `git commit -m "Add July report PDF links"`, and `git push origin main` from the nested checkout.

- [ ] **Step 5: Verify production homepage**

Fetch `https://market-insights.github.io/` and require both PDF paths in the HTML.
