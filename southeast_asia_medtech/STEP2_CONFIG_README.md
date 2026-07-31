# Step 2 — Source and Keyword Configuration

Date: 2026-07-24

## Delivered scope

Step 2 adds configuration and validation only. It does not implement or run a production
scraper and does not call an LLM.

Created files:

```text
southeast_asia_medtech/
├── __init__.py
├── STEP2_CONFIG_README.md
├── config/
│   ├── __init__.py
│   ├── config_loader.py
│   ├── sources.yaml
│   ├── keywords.yaml
│   └── data_schema.md
└── tests/
    ├── __init__.py
    └── test_config_loading.py
```

## Phase-one sources

Exactly two official organizations are configured:

1. **Singapore Health Sciences Authority (HSA)**  
   Primary monitor: `https://www.hsa.gov.sg/announcements/`  
   The public listing provides filters including Medical devices, Regulatory Updates,
   Safety Alerts, Field Safety Notices, Product Recalls, Public Consultations, HSA Updates,
   and Press Releases.

2. **Malaysia Medical Device Authority (MDA)**  
   Primary monitor: `https://www.mda.gov.my/announcement/`  
   Related public safety sections are recorded as monitoring metadata for recalls and field
   safety corrective actions. They do not count as additional source organizations.

Authenticated transaction/product databases such as HSA SHARE and MDA MeDC@St are explicitly
excluded.

## Why `custom_parser` is configured

Both official sites have public pages suitable for long-term monitoring, but Step 2 does
not yet store representative HTML fixtures or test selectors:

- HSA uses a shared faceted announcement listing rather than a stable medical-device-only
  URL.
- MDA uses a paginated/bilingual publishing layout, multiple public domains, and PDF-heavy
  safety notices.

Fixed CSS selectors are therefore left blank deliberately. A later bounded discovery step
should save legal public fixtures, identify stable semantic hooks or public JSON endpoints,
and only then decide whether each source remains `custom_parser` or can become
`static_html`/`api_json`. This avoids encoding guessed selectors.

`requires_javascript: false` means neither source currently requires Playwright for the
public content observed during configuration research. This is a configuration assumption
to verify with fixtures, not authorization to crawl.

## Configuration contracts

`sources.yaml` contains:

- allowed strategies and shared request defaults;
- stable source IDs, organization/country metadata, primary URLs, priority, language,
  frequency, strategy, JavaScript flag, selectors, monitoring sections, exclusions, and
  parsing notes;
- exactly two enabled phase-one source records.

`keywords.yaml` contains two weighted categories:

- `medical_device_business`
- `medical_device_packaging`

Every canonical term has `synonyms`, `weight`, and `language`. Synonyms inherit their
canonical term's metadata. Matching rules are declared at the top of the file; no matching
engine is implemented in this step.

`data_schema.md` defines the future normalized article contract, attachment provenance,
identity/deduplication order, date rules, and the boundary between deterministic normalized
data and future LLM-derived analysis.

## Reading and testing the configuration

From the project root:

```bash
.venv/bin/python -m unittest southeast_asia_medtech.tests.test_config_loading -v
```

The project virtual environment is used because PyYAML is a project dependency; the host
system Python may not include it.

The test:

- parses both YAML files through the side-effect-free loader;
- asserts that exactly two source records exist;
- validates required source and selector fields;
- validates strategy, country, language, HTTPS URLs, and unique IDs;
- verifies keyword metadata and representative required terms.

The loader only reads YAML. It performs no HTTP request, browser operation, scraping,
file-state mutation, or LLM call.

## Official pages checked for configuration

- HSA Announcements: <https://www.hsa.gov.sg/announcements/>
- HSA Medical Devices overview: <https://www.hsa.gov.sg/medical-devices/>
- HSA Medical Device guidance documents:
  <https://www.hsa.gov.sg/medical-devices/guidance-documents/>
- MDA Announcements: <https://www.mda.gov.my/announcement/>
- MDA public Alert list: <https://www.mda.gov.my/index.php/alert>
- MDA public Safety Information:
  <https://portal.mda.gov.my/index.php/ms/profesional/safety-alert>

URLs and page behavior are time-sensitive and must be revalidated before Step 3 implements
any bounded collection.

## Stop point

Step 2 is complete after the local configuration test passes. No full scraping workflow,
additional country/source, LLM analysis, or existing WeChat configuration change belongs in
this step.
