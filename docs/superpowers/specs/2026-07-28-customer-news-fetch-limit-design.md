# Customer News Full-Text Fetch Limit

## Goal

Increase the default number of customer-discovery candidates selected for
full-text retrieval from 30 to 60, without removing the operator's ability to
override the limit for a specific run.

## Design

- Change the `--fetch-top` default in
  `southeast_asia_medtech/scrapers/run_customer_news_discovery.py` to `60`.
- Keep the existing `--fetch-top` CLI option and positive-value validation.
- Include the configured `fetch_top` value in the JSON run summary so the
  effective limit is visible after each run.
- Do not modify historical candidate or article JSON files. A future discovery
  run will use the new default.

## Behavior

The script will sort all accepted candidates by event score and company name,
then attempt full-text retrieval for at most the first 60 candidates. If fewer
than 60 candidates exist, it will attempt all of them. Records that fail
full-text retrieval will still be retained with their failure status, as they
are today.

An explicit command such as `--fetch-top 25` or `--fetch-top 80` will override
the default.

## Testing

- Verify the CLI parser defaults `fetch_top` to 60.
- Verify an explicit `--fetch-top` value overrides the default.
- Run the complete Southeast Asia MedTech unit-test suite.

