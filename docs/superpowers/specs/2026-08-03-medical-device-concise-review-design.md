# July 2026 Medical Device Concise Review PDF

## Purpose

Create a local, review-only concise companion PDF for the July Medical Device
monthly report. The existing full report and public website remain unchanged
until the user explicitly approves publication.

## Source of truth

Use the existing July report artifacts only:

- `public_share/reports/medical-device/monthly/2026-07/report.json`
- `public_share/reports/medical-device/monthly/2026-07/report.md`

No crawler, LLM call, report regeneration, or source expansion is in scope.

## Content structure

The PDF is concise but has no fixed page limit. The target is roughly five to
six readable Letter pages.

1. **Executive Summary 月度核心总结**
   - Preserve the existing seven monthly-summary points verbatim.
   - This replaces the former `Five Key Takeaways` section.

2. **Top Opportunities**
   - Preserve the ten ranked opportunities from `Monthly Amcor Relevance
     Ranking`, in the existing order.
   - Each entry shows its rank, title, concise opportunity rationale, source
     and publication date, and a clickable original-article link.

3. **Weekly Overview — July at a Glance**
   - Combine the existing Week 1 through Week 5 `本周概览` text into one
     self-contained module.
   - Retain a separate compact card for each week so the progression across the
     month remains clear.

4. **July Integrated Signals**
   - Consolidate original report sections 7.1–7.4 into one module with four
     labelled subsections: commercialization/volume, capacity and supply
     chain, packaging/sterilization evidence, and follow-up opportunities.

5. **Reference note**
   - Include the original report's necessary caution that packaging conclusions
     are inferences unless an article explicitly confirms them.
   - Do not reproduce the full appendix or full article digest.

## Presentation

- Reuse the existing clean blue card visual language.
- Ensure Chinese text and clickable links render correctly in the final PDF.
- The artifact stays outside `public_share/` in a clearly named local review
  output path until the user approves deployment.

## Verification

- Validate expected section headings and counts (7 Executive Summary bullets,
  10 opportunities, 5 weekly summaries, 4 integrated-signal subsections).
- Render the final PDF to PNG page images and inspect every page for clipping,
  overflow, or blank/spurious pages.
- Confirm no tracked file in `public_share/` changes and no network publication
  command runs.
