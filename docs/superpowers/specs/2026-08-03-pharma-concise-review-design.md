# July 2026 Pharma Concise Review PDF

## Purpose

Create a local, review-only concise companion PDF for the July Pharma monthly
report. The existing full report and public website remain unchanged until
Yvonne explicitly approves publication.

## Source of truth

Use only the existing July Pharma report artifacts:

- `china-wechat-med-phar/public_share/reports/pharma/monthly/2026-07/report.json`
- `china-wechat-med-phar/public_share/reports/pharma/monthly/2026-07/report.md`

No crawler, DeepSeek call, report regeneration, or source expansion is in
scope.

## Content structure

The PDF has no fixed page limit. It should be more concise and readable than
the full report while retaining these six requested modules.

1. **Executive Summary 月度核心总结**
   - Preserve the full report's monthly-summary bullets.
   - Keep the associated evidence / supporting-article references when they
     are present in the source report.

2. **Top Amcor Opportunities**
   - Preserve the ranked entries from the existing `Monthly Amcor Relevance
     Ranking` in their existing order.
   - Each entry shows its rank, title, short rationale, source/date, and an
     original-article link.

3. **Week-by-Week Digest — summary edition**
   - Combine the five weekly `本周概览` sections into one compact module.
   - Present one short card per week; do not reproduce every individual news
     item from the full digest.

4. **Drug / Target / Technology Watchlist**
   - Preserve the structured watchlist from section 6 in a compact, readable
     format without adding new claims.

5. **Packaging & Commercialization Implications for Amcor**
   - Retain the full report's section 7 themes in concise cards and bullets.
   - Clearly distinguish original-source-confirmed packaging facts from
     commercial or packaging-demand inferences that require verification.

6. **Appendix: Articles Reviewed**
   - Retain every report article in a compact week-grouped list:
     `date · linked title · source`.
   - Do not repeat scores, categories, or long article summaries.

## Presentation

- Reuse the Medical Device concise review's blue card and bullet visual system.
- Use short bullets instead of dense paragraphs.
- Preserve Chinese text and clickable original-source links in the PDF.
- Write the HTML and PDF to a local review output directory outside
  `public_share/`.

## Verification

- Check the expected number of Executive Summary bullets, ranked opportunities,
  weekly cards, watchlist groups, packaging sections, and appendix articles
  against the source report.
- Render the complete PDF to page images and visually inspect every page for
  clipping, overlap, unreadable text, and unwanted blank pages.
- Confirm no tracked file inside `public_share/` changes and no website
  publication command runs.
