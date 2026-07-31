# Phase 1 Source Access and Content Audit

Generated: 2026-07-24

## Result

- 17 configured source families.
- 16 source families have five unique, normalized records.
- 80 records have non-empty content of at least 80 characters.
- 80 unique `article_id` values.
- Vietnam VNEPS remains the only source without five saved tender records.

## Acquisition modes

- Live HTTP content: ASEAN AMDC, Singapore HSA, Thailand FDA, Indonesia
  Farmalkes, Vietnam VIMDA, Singapore GeBIZ, Philippines PhilGEPS,
  APACMed, MIDA/AMMI, MDDI, DuPont Tyvek and Sterile Barrier Association.
- Official public-index fallback: Malaysia MDA, Philippines FDA and Malaysia
  MOH procurement.
- Public search-index fallback: Healthcare Packaging.

Fallback records are explicitly marked
`success_from_official_index_snapshot` or
`success_from_official_index_snapshot`; they are not represented as live HTTP
successes.

## Vietnam VNEPS limitation

The VNEPS public homepage is accessible in a browser and the tender search UI
loads. Python/OpenSSL access fails with `DH_KEY_TOO_SMALL`, while the public
search is JavaScript/API driven. The browser search control accepted the
medical-device keyword but did not return a result route that can yet be
replayed by the command-line scraper. No unrelated VIMDA or third-party tender
content was substituted.

## Re-run

```bash
.venv/bin/python -m southeast_asia_medtech.scrapers.run_phase1_sources \
  --max-items 5
```

Outputs:

- `data/phase1_samples/source_samples.json`
- `data/phase1_samples/source_sampling_summary.json`
- `logs/phase1_sources.log`
