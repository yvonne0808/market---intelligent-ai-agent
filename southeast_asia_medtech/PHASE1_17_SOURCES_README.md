# Phase 1 — 17 Source Configuration and Sampling Audit

Date: 2026-07-24

## Scope

The independent Southeast Asia module now configures the requested 17 source families.
MIDA and AMMI are represented as one source family, matching the user's stated total of 17,
but both public websites are listed as endpoints.

No LLM API was called. No WeChat configuration or analysis output was read or modified.

## Commands

Try all enabled public sources, at most five valid records each:

```bash
.venv/bin/python -m southeast_asia_medtech.scrapers.run_phase1_sources \
  --max-items 5
```

Try one source:

```bash
.venv/bin/python -m southeast_asia_medtech.scrapers.run_phase1_sources \
  --source sg_hsa_announcements \
  --max-items 5
```

The original HSA/MDA dated scraper remains available and deliberately ignores the other
15 source definitions:

```bash
.venv/bin/python -m southeast_asia_medtech.scrapers.run_scraper \
  --start-date 2026-07-01 \
  --end-date 2026-07-31 \
  --max-articles 5
```

## Valid-record gate

A sample is only saved when it has:

- a specific, non-navigation title;
- an explicit publication date;
- at least 80 characters of extracted body;
- a configured source-specific term in the title, URL or body;
- a public detail URL.

Static product pages, home pages, generic registry landing pages, category pages, empty
JavaScript shells and undated technical pages are not counted as successful information.

## Actual first run

All 17 source families were attempted. The strict final output contains 14 valid records.
Only the MIDA/AMMI source family reached five records. HSA, Farmalkes, VIMDA, APACMed and SBA
returned one to three strict records. Other sources returned zero in the static/public
attempt.

This is intentionally not reported as 85/85. The current limitations are:

- GeBIZ, MyProcurement and VNEPS require JavaScript search interactions and source-specific
  result parsers.
- PhilGEPS exposes public bid abstracts, but the category/search navigation needs a dedicated
  ASP.NET parser.
- Philippines FDA and Healthcare Packaging returned HTTP 403 to the polite requests client.
- Malaysia MDA timed out during this run; its existing dedicated parser remains in place.
- Thailand FDA returned usable list links but its detail body is rendered outside the generic
  HTML container and needs a dedicated parser.
- ASEAN AMDC has no stable standalone feed; the ASEAN search page produced no reliable cards.
- MDDI's old `/packaging` path is no longer valid. The config now monitors the main site and
  requires a packaging-specific discovery parser.
- DuPont's public healthcare page produced product/navigation links but no dated records under
  the strict monthly-news gate.

## Outputs

- `config/sources.yaml`: 17 source families, workflows, strategies, languages, priorities,
  endpoints, search terms and source-specific fields.
- `config/keywords.yaml`: business, packaging, device type, safety, procurement and
  Indonesian/Malay/Vietnamese/Thai discovery terms.
- `data/phase1_samples/source_samples.json`: strict successful samples only.
- `data/phase1_samples/source_sampling_summary.json`: per-source result and exact error.
- `logs/phase1_sources.log`: request and parser log.

## Next implementation boundary

The configuration is complete, but the sampling audit shows that one generic parser cannot
reliably collect all 17 sources. The next work should implement dedicated adapters in this
order:

1. PhilGEPS and the three JavaScript procurement searches;
2. Thailand FDA, Philippines FDA and ASEAN search;
3. MDDI, Healthcare Packaging and DuPont dated-news discovery;
4. targeted registry query inputs for company, device category, product keyword and known
   registration number.

No login, CAPTCHA bypass or full registration-database download should be added.
