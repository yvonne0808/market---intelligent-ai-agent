# SEA MedTech Monthly Source Expansion Design

**Date:** 2026-08-11  
**Status:** Approved for implementation planning  
**Scope:** Monthly Report sources only

## Objective

Evaluate and add six candidate Monthly Report sources and supplement the
existing MIDA source without affecting Customer Analysis, calling an LLM, or
running an unrestricted monthly crawl.

## Candidate Sources

### Krungsri Medical Devices Research

- Registry action: add a new research source.
- Listing: `https://www.krungsri.com/en/research/industry/industry-outlook/other-industries/medical-devices/io`
- Role: dated Thailand medical-device industry outlooks and periodic research.
- Frequency: annual or periodic, not daily news.
- Keep concrete device demand, production, exports, investment, consumables,
  manufacturing, and supply-chain evidence.

### Asian Hospital & Healthcare Management

- Registry action: add a new industry-news source.
- Start from the site's News/Press Releases content, not interviews or events.
- Keep concrete equipment/device launches, approvals, manufacturing,
  commercialization, capacity, transactions, and regional supply-chain events.
- Exclude hospital promotion, thought leadership without an event, awards,
  conferences, podcasts, and advertising.

### Thailand Medical News

- Registry action: add a new Thailand device-news source.
- Listing: `https://www.thailandmedical.news/articles/medical-devices`
- Do not crawl the general homepage or pharma/disease categories.
- Keep concrete medical-device events and apply the Monthly Prompt's Southeast
  Asia boundary.

### Healthcare Asia

- Registry action: add a new regional healthcare-news source.
- Do not use the submitted Advertising page as the listing.
- Use the site's daily news content and filter aggressively for devices,
  consumables, manufacturing, investment, procurement, commercialization,
  channels, supply chain, and direct packaging relevance.
- Exclude awards, event promotion, hospital profiles, general administration,
  and advertorial material without a concrete industrial event.

### LabMedica

- Registry action: add a new IVD/laboratory-device source.
- Listing: `https://www.labmedica.com/industry-news/`
- Keep diagnostics instruments, laboratory automation, IVD commercialization,
  manufacturing, approvals, company transactions, and supply-chain events.
- Exclude general clinical research and biomarker articles without an actual
  product or industrial event.

### BioSpectrum Asia

- Registry action: add a new MedTech source.
- Listing: `https://www.biospectrumasia.com/category/med-tech/medical-devices`
- Do not crawl the Pharma or general homepage feed.
- Keep concrete device, diagnostics, manufacturing, commercialization,
  financing, transaction, and Southeast Asia market events.

### MIDA Healthcare Services

- Registry action: update the existing `my_mida_ammi` source; do not create a
  duplicate source ID.
- Existing MIDA Media Releases remain the recurring news entrypoint.
- Add `https://www.mida.gov.my/industries/services/healthcare-services/` only as
  a supplemental industry/discovery page. An undated static page must not be
  emitted as a monthly article.

## Test Method

Test sources individually at low frequency with a maximum of five candidates
per source. Do not call an LLM.

For every candidate validate:

- title;
- publication date;
- canonical article URL;
- extracted article body;
- medical-device/consumables relevance;
- Southeast Asia or direct packaging relevance; and
- acquisition status and errors.

Use the existing `run_phase1_sources` path where its generic parser contract is
sufficient. Add focused parser tests before adding custom logic for a site.

## Enablement Rules

- Stable valid article extraction: `enabled: true`.
- Static/undated page or no article listing: retain configuration with
  `enabled: false` and an explicit note.
- Access blocked, timed out, challenged, or JavaScript-only: record the exact
  status; do not represent it as success.
- HTTP 200 is not success unless title, date, URL, and usable article body pass
  validation.
- A source with no current relevant article is not necessarily broken; report
  `no_relevant_sample` separately from access or parsing failure.

## Outputs

Produce a source-by-source test report containing:

- tested URL;
- parser/acquisition strategy;
- access result;
- candidate count;
- valid article count;
- up to five sample titles/dates/URLs;
- final enabled state; and
- any required follow-up.

Do not run the full monthly collector, analyze articles, generate a report,
modify website assets, push, or publish.

