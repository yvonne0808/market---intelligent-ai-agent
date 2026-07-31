# Customer News Medical Filter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fetch full text for up to 60 customer-news candidates by default and reject same-name, non-medical news during discovery.

**Architecture:** Keep discovery in `run_customer_news_discovery.py`, but extract small pure functions for query construction and title filtering so behavior is deterministic and unit-testable. Build entity-aware medical terms from general healthcare language plus configured product segments, use them to narrow Google News across its indexed page context, and use the local title gate only to reject explicit non-medical signals.

**Tech Stack:** Python 3, argparse, unittest, Google News RSS, YAML-backed company watchlist

## Global Constraints

- Default `--fetch-top` is `60`, while an explicit CLI value still overrides it.
- General medical terms are `medical`, `healthcare`, and `medtech`.
- Entity product segments are included after replacing underscores with spaces.
- Clear non-medical signals include `fashion`, `clothing`, `festival`, `retail collection`, and `apparel`.
- Historical JSON output files are not rewritten.

---

### Task 1: Raise and expose the full-text fetch limit

**Files:**
- Modify: `southeast_asia_medtech/scrapers/run_customer_news_discovery.py`
- Test: `southeast_asia_medtech/tests/test_customer_news_discovery.py`

**Interfaces:**
- Consumes: `args() -> argparse.Namespace`
- Produces: `options.fetch_top == 60` by default and JSON summary field `"fetch_top"`

- [ ] **Step 1: Write failing parser tests**

Use `unittest.mock.patch` to supply the required dates and test both default and override:

```python
@patch(
    "sys.argv",
    ["news", "--start-date", "2026-07-01", "--end-date", "2026-07-27"],
)
def test_fetch_top_defaults_to_sixty(self) -> None:
    self.assertEqual(args().fetch_top, 60)

@patch(
    "sys.argv",
    [
        "news",
        "--start-date",
        "2026-07-01",
        "--end-date",
        "2026-07-27",
        "--fetch-top",
        "75",
    ],
)
def test_fetch_top_can_be_overridden(self) -> None:
    self.assertEqual(args().fetch_top, 75)
```

- [ ] **Step 2: Run the focused tests and verify the default test fails**

Run:

```bash
PYTHONPATH=. .venv/bin/python -m unittest southeast_asia_medtech.tests.test_customer_news_discovery -v
```

Expected: the default assertion reports `30 != 60`.

- [ ] **Step 3: Change the default and expose it in the run summary**

Change the parser declaration to:

```python
parser.add_argument("--fetch-top", type=int, default=60)
```

Add this field to the final `result` dictionary:

```python
"fetch_top": options.fetch_top,
```

- [ ] **Step 4: Run the focused tests and verify they pass**

Run:

```bash
PYTHONPATH=. .venv/bin/python -m unittest southeast_asia_medtech.tests.test_customer_news_discovery -v
```

Expected: all focused tests pass.

- [ ] **Step 5: Commit only the task files**

```bash
git add southeast_asia_medtech/scrapers/run_customer_news_discovery.py southeast_asia_medtech/tests/test_customer_news_discovery.py
git commit -m "feat: raise customer news fetch limit to 60"
```

### Task 2: Add entity-aware medical query and title filtering

**Files:**
- Modify: `southeast_asia_medtech/scrapers/run_customer_news_discovery.py`
- Test: `southeast_asia_medtech/tests/test_customer_news_discovery.py`

**Interfaces:**
- Produces: `medical_terms_for(entity: dict) -> list[str]`
- Produces: `has_medical_context(title: str, entity: dict) -> bool`
- Produces: `build_news_query(entity: dict, start: date, end: date) -> str`
- Consumes: entity fields `canonical_name: str` and `product_segments: list[str]`

- [ ] **Step 1: Write failing medical-context tests**

Add tests equivalent to:

```python
def test_medical_terms_include_normalized_product_segments(self) -> None:
    entity = {"product_segments": ["ostomy_care", "continence_care"]}
    self.assertEqual(
        medical_terms_for(entity),
        ["medical", "healthcare", "medtech", "ostomy care", "continence care"],
    )

def test_hollister_ostomy_title_passes_medical_filter(self) -> None:
    entity = {
        "canonical_name": "Hollister",
        "product_segments": ["ostomy_care", "continence_care", "wound_care"],
    }
    self.assertTrue(
        has_medical_context("Hollister launches new ostomy care system", entity)
    )

def test_hollister_fashion_title_is_rejected(self) -> None:
    entity = {
        "canonical_name": "Hollister",
        "product_segments": ["ostomy_care", "continence_care", "wound_care"],
    }
    self.assertFalse(
        has_medical_context(
            "Hollister launches festival fashion retail collection", entity
        )
    )
```

Test `build_news_query` with fixed dates and assert it includes `"Hollister"`,
`(medical OR healthcare OR medtech OR "ostomy care" OR "continence care" OR "wound care")`,
and the expected `after:` and `before:` clauses.

- [ ] **Step 2: Run the focused tests and verify imports fail**

Run:

```bash
PYTHONPATH=. .venv/bin/python -m unittest southeast_asia_medtech.tests.test_customer_news_discovery -v
```

Expected: import errors for the new pure functions.

- [ ] **Step 3: Implement medical-term normalization**

Add immutable constants:

```python
GENERAL_MEDICAL_TERMS = ("medical", "healthcare", "medtech")
NON_MEDICAL_TERMS = (
    "fashion",
    "clothing",
    "festival",
    "retail collection",
    "apparel",
)
```

Implement `medical_terms_for` by preserving the general-term order, replacing
underscores in product segments with spaces, and removing duplicates.

- [ ] **Step 4: Implement query construction and local filtering**

Implement `has_medical_context` to case-fold the title and reject any
`NON_MEDICAL_TERMS` match. Do not require an exact medical phrase in the title:
the Google query already supplies the positive medical constraint and can
match page context that is absent from the displayed headline.

Implement `build_news_query` to quote multi-word medical terms and construct:

```text
"canonical name" (medical terms joined by OR) (event terms joined by OR) after:YYYY-MM-DD before:YYYY-MM-DD
```

In `discover_company`, replace the inline query construction with
`build_news_query(customer, start, end)`. Before scoring, skip entries for which
`has_medical_context(title, customer)` is false.

- [ ] **Step 5: Run focused and complete tests**

Run:

```bash
PYTHONPATH=. .venv/bin/python -m unittest southeast_asia_medtech.tests.test_customer_news_discovery -v
PYTHONPATH=. .venv/bin/python -m unittest discover -s southeast_asia_medtech/tests -p 'test_*.py' -v
PYTHONPATH=. .venv/bin/python -m py_compile southeast_asia_medtech/scrapers/run_customer_news_discovery.py
```

Expected: all tests and compilation pass.

- [ ] **Step 6: Commit only the task files**

```bash
git add southeast_asia_medtech/scrapers/run_customer_news_discovery.py southeast_asia_medtech/tests/test_customer_news_discovery.py
git commit -m "feat: filter customer news by medical context"
```
