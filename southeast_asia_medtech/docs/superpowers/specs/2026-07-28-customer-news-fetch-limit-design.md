# Customer News Fetch Limit and Medical-Context Filter

## Goal

Improve customer-news discovery in two ways:

1. Increase the default number of candidates selected for full-text retrieval
   from 30 to 60, without removing the operator's ability to override it.
2. Prevent ambiguous company names, such as the medical-device company
   Hollister, from matching unrelated fashion or consumer-brand news.

## Design

- Change the `--fetch-top` default in
  `southeast_asia_medtech/scrapers/run_customer_news_discovery.py` to `60`.
- Keep the existing `--fetch-top` CLI option and positive-value validation.
- Include the configured `fetch_top` value in the JSON run summary so the
  effective limit is visible after each run.
- Do not modify historical candidate or article JSON files. A future discovery
  run will use the new default.
- Add a medical-context block to each Google News query. It will combine general
  terms (`medical`, `healthcare`, and `medtech`) with the entity's configured
  `product_segments`, converting underscores to spaces.
- Use the positive medical terms in the Google News query, where matching can
  use the full indexed page context instead of requiring the exact phrase in
  the displayed headline.
- Reject returned titles containing clear non-medical same-name signals such as
  `fashion`, `clothing`, `festival`, `retail collection`, or `apparel`.

## Behavior

The script will sort all accepted candidates by event score and company name,
then attempt full-text retrieval for at most the first 60 candidates. If fewer
than 60 candidates exist, it will attempt all of them. Records that fail
full-text retrieval will still be retained with their failure status, as they
are today.

An explicit command such as `--fetch-top 25` or `--fetch-top 80` will override
the default.

The medical filter is entity-aware. For Hollister, for example, the query will
include terms such as `ostomy care`, `continence care`, and `wound care`.
Therefore a medical headline does not need to contain the literal word
`medical` to qualify.

## Testing

- Verify the CLI parser defaults `fetch_top` to 60.
- Verify an explicit `--fetch-top` value overrides the default.
- Verify medical query terms are generated from configured product segments.
- Verify a Hollister ostomy headline passes.
- Verify Hollister fashion and festival headlines are rejected.
- Run the complete Southeast Asia MedTech unit-test suite.
