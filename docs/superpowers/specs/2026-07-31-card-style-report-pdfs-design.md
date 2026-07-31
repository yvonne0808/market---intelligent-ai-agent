# Card-Style July Report PDFs Design

## Goal

Replace the Markdown-flow July PDF exports with PDFs that preserve the report website's card-based layout for both Medical Device and Pharma.

## Scope

- Use each existing July report HTML page as the PDF source.
- Preserve cards, score badges, weekly sections, and expanded Other Important News lists in the exported PDF.
- Use A4 printing with CSS backgrounds enabled.
- Overwrite only the two public `report.pdf` files and publish them at their existing URLs.
- Do not alter report data, LLM output, article selection, or website HTML.

## Design

A dedicated PDF export script will open a supplied local report `index.html` with a headless browser and print it to A4 PDF with background graphics. Before printing, it will set every `details.other-news` element open so all displayed weekly news is included. It will be run separately for the Medical Device and Pharma July pages.

The existing Markdown-to-PDF converter remains available for other reports. The new exporter has one responsibility: render an already-built card-style HTML report to PDF.

## Validation

Verify the output files open as PDFs, retain the expected report titles, render representative first and final pages to PNG, and visually inspect the card layout before publishing only the two PDFs.
