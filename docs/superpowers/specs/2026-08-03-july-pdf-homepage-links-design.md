# July PDF Homepage Links Design

## Goal

Expose the existing July Medical Device and July Pharma PDFs directly from the report-library homepage.

## Design

Add one `PDF` action button to each July monthly-report card in the nested
`public_share/index.html` checkout. Each button follows the existing June PDF
button styling and links to its same-report `report.pdf` path.

No report files, routes, cards, site layout, or non-July links change. The
production commit contains only `index.html`; temporary files remain untracked.

## Validation

Confirm both PDF `href` paths are present in the static homepage, then push
the single-file production change and verify the public homepage contains both
links.
