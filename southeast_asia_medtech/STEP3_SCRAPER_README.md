# Step 3 — Unified HSA and MDA Scraper

Test date: 2026-07-24  
Test period: 2026-07-01 through 2026-07-31

## Delivered

The Step 3 implementation is isolated under `southeast_asia_medtech/` and supports exactly
the two configured official organizations:

- Singapore Health Sciences Authority (HSA)
- Malaysia Medical Device Authority (MDA)

Files added:

```text
southeast_asia_medtech/
├── scrapers/
│   ├── __init__.py
│   ├── http_client.py
│   ├── parsers.py
│   └── run_scraper.py
├── data/
│   ├── raw/articles_raw.json
│   └── normalized/articles_normalized.json
├── logs/scraper.log
├── tests/test_scraper_parsers.py
└── STEP3_SCRAPER_README.md
```

No LLM, report generation, additional country, Playwright session, or existing
WeChat/RSS code/configuration is used.

## Unified command

Run from the existing project root:

```bash
.venv/bin/python -m southeast_asia_medtech.scrapers.run_scraper \
  --start-date 2026-07-01 \
  --end-date 2026-07-31 \
  --max-articles 5
```

Optional arguments:

```text
--source sg_hsa_announcements
--source my_mda_announcements
--timeout 20
--retries 3
--sleep-min 1.5
--sleep-max 3.0
```

`--source` can be repeated. Step 3 hard-caps `--max-articles` at 5 per source even if a
larger value is supplied.

## Processing flow

```text
sources.yaml
  -> enabled source loop
  -> requests Session with retry/timeout/User-Agent
  -> source list parser
  -> inclusive date filter
  -> fixed first-N test window
  -> persistent known-URL check
  -> detail parser
  -> minimum body-quality check
  -> raw and normalized JSON merge
  -> per-source/run logging
```

All relative links are resolved against `base_url`. Fragments are removed, scheme/host are
normalized, and `article_id` is a stable SHA-256-derived ID of `source_id + canonical URL`.
Writes use a temporary file followed by an atomic replace.

An error in one source is caught in `scrape_one_source`; the outer source loop continues.
Detail failures are saved with `scrape_status: failed` and a specific error.

## Source parsing

### HSA

The public announcement page returns current list cards in static HTML. The parser reads:

- title from `h3`/its titled span;
- date from the card's date paragraph;
- relative announcement URL from the card link;
- detail title from `main h1`;
- detail text from the centered article content container.

The shared HSA page contains many non-device products. Step 3 retains cards explicitly
marked Medical devices or containing a narrow device/safety relevance marker. This captured
the packaging-sterility recall in the test period.

Important limitation: HSA page-number buttons are client-side controls and `?page=N` did not
change server-rendered HTML during investigation. The requests-only Step 3 implementation
therefore claims coverage only for the current static first page. It logs this limitation
on every HSA run. It does not silently claim historical pagination and does not introduce
Playwright merely to expand this five-article test.

### MDA

MDA exposes a server-rendered Joomla list. The parser reads:

- article links from `th.list-title a`;
- dates from `td.list-date`;
- detail title/body from `.article-details`.

Some MDA notices consist only of a heading and a public document link. The scraper follows
same-domain `/documents/.../file` links, validates the PDF response signature/type, and
extracts its text layer with `pypdf`. If the PDF has no usable text layer, it optionally
runs local English Tesseract OCR on substantial embedded page images. A final body under
80 characters is explicitly marked failed rather than accepted as successful.

## Normalized output contract

Every stored normalized record contains:

```json
{
  "article_id": "",
  "title": "",
  "source_name": "",
  "country": "",
  "organization": "",
  "source_type": "",
  "published_date": "",
  "collected_at": "",
  "url": "",
  "language": "",
  "body": "",
  "raw_text_length": 0,
  "scrape_status": "",
  "error_message": ""
}
```

Outputs:

- `data/raw/articles_raw.json`: list/detail provenance and extracted raw text
- `data/normalized/articles_normalized.json`: stable normalized contract
- `logs/scraper.log`: requests, limitations, failures, source totals, and run totals

Existing normalized URLs form the persistent deduplication set. Failed records are also
preserved and not repeatedly added during the same fixed Step 3 test window.

## Live test results

Initial run before MDA document-link support:

| Source | List items seen | In-range relevant items | Saved | Successful | Failed |
|---|---:|---:|---:|---:|---:|
| HSA | 10 | 1 | 1 | 1 | 0 |
| MDA | 10 | 8 | 5 | 1 | 4 |

The four MDA failures are honest extraction outcomes:

- two pages returned no body text;
- two pages returned only title-like text below the 80-character quality threshold.

The one successful MDA record is the product-classification online-process announcement
with 1,495 extracted characters. The successful HSA packaging-sterility recall has 2,621
extracted characters.

MDA document-link repair run:

| MDA result after repair | Count |
|---|---:|
| Successful | 4 |
| Failed | 1 |

Three of the four original failures were recovered from their public linked PDFs (477,
2,120, and 275 extracted characters). The remaining training PDF has no text layer.
Local embedded-image Tesseract OCR fallback has been added for this case, but the subsequent
live verification attempt was interrupted by repeated MDA TLS/list-page timeouts. The
existing failed record remains intact and is eligible for a later retry; it is not reported
as a false success.

Second identical run:

| Source | Duplicate URLs skipped | New records |
|---|---:|---:|
| HSA | 1 | 0 |
| MDA | 5 | 0 |

Total normalized records remained 6, demonstrating persistent URL deduplication. The second
run fetched only the two list pages and did not refetch known detail pages.

## Automated checks

Run:

```bash
.venv/bin/python -m unittest discover -s southeast_asia_medtech/tests -v
```

The suite covers:

- Step 2 source and keyword configuration;
- HSA fixture list/detail parsing;
- MDA fixture list/detail parsing;
- short-body failure classification;
- source-level exception isolation without propagation.

Live-output validation also checks required fields, HTTPS URLs, unique URLs/article IDs,
parseable dates, successful-body non-emptiness, and stored text lengths.

## Known next-step issues

- HSA historical pagination needs a separately approved investigation of the client data
  endpoint or a narrowly scoped Playwright fallback.
- MDA image/PDF-only notices need an attachment processor if they are required as body
  content. Text-layer PDF extraction and embedded-image OCR are now implemented; complex
  scanned documents may still require a future full-page rendering/OCR fallback.
- Step 3 reads only the configured primary MDA announcement list; related safety sections
  recorded in Step 2 are not additional crawls in this limited test.
- Failed records need an explicit retry/version policy before production scheduling.

Step 3 stops here. It does not generate a monthly report.
