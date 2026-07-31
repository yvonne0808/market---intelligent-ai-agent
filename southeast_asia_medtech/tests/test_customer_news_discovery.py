from argparse import Namespace
from datetime import date
import unittest
from unittest.mock import patch

import requests

from southeast_asia_medtech.scrapers.run_customer_news_discovery import (
    args,
    build_news_query,
    candidate_limit_for,
    configure_session,
    extract_body,
    has_medical_context,
    medical_terms_for,
    published_in_range,
)


class CandidateLimitTests(unittest.TestCase):
    def test_customer_and_competitor_use_separate_candidate_limits(self) -> None:
        options = Namespace(per_customer=10, per_competitor=6)

        self.assertEqual(
            candidate_limit_for({"entity_type": "customer"}, options), 10
        )
        self.assertEqual(
            candidate_limit_for({"entity_type": "competitor"}, options), 6
        )

    def test_unknown_entity_type_uses_competitor_limit(self) -> None:
        options = Namespace(per_customer=10, per_competitor=6)

        self.assertEqual(candidate_limit_for({"entity_type": "other"}, options), 6)


class ArgumentTests(unittest.TestCase):
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


class SessionConfigurationTests(unittest.TestCase):
    def test_session_uses_complete_browser_request_headers(self) -> None:
        session = requests.Session()

        configure_session(session)

        self.assertIn("AppleWebKit", session.headers["User-Agent"])
        self.assertIn("text/html", session.headers["Accept"])
        self.assertEqual(session.headers["Accept-Language"], "en-US,en;q=0.9")


class BodyExtractionTests(unittest.TestCase):
    def test_extracts_edwards_investor_relations_body(self) -> None:
        title, body = extract_body(
            """
            <html><body>
              <h1>Edwards Lifesciences Reports Second Quarter Results</h1>
              <div class="evergreen-news-body">Q2 TAVR sales grew 11.3%.</div>
            </body></html>
            """
        )

        self.assertEqual(title, "Edwards Lifesciences Reports Second Quarter Results")
        self.assertEqual(body, "Q2 TAVR sales grew 11.3%.")

    def test_extracts_resmed_news_release_body(self) -> None:
        _title, body = extract_body(
            """
            <html><body>
              <div class="module_body">
                Resmed entered an agreement to sell MatrixCare.
              </div>
            </body></html>
            """
        )

        self.assertEqual(body, "Resmed entered an agreement to sell MatrixCare.")


class MedicalContextTests(unittest.TestCase):
    def setUp(self) -> None:
        self.hollister = {
            "canonical_name": "Hollister",
            "product_segments": [
                "ostomy_care",
                "continence_care",
                "wound_care",
            ],
        }

    def test_medical_terms_include_normalized_product_segments(self) -> None:
        self.assertEqual(
            medical_terms_for(self.hollister),
            [
                "medical",
                "healthcare",
                "medtech",
                "ostomy care",
                "continence care",
                "wound care",
            ],
        )

    def test_hollister_ostomy_title_passes_medical_filter(self) -> None:
        self.assertTrue(
            has_medical_context(
                "Hollister launches new ostomy care system", self.hollister
            )
        )

    def test_hollister_fashion_title_is_rejected(self) -> None:
        self.assertFalse(
            has_medical_context(
                "Hollister launches festival fashion retail collection",
                self.hollister,
            )
        )

    def test_medical_event_is_not_rejected_for_missing_exact_segment_phrase(self) -> None:
        medtronic = {
            "canonical_name": "Medtronic",
            "product_segments": ["cardiovascular_devices"],
        }

        self.assertTrue(
            has_medical_context(
                "Medtronic recalls heart valve delivery system due to safety risk",
                medtronic,
            )
        )

    def test_query_contains_medical_terms_and_date_range(self) -> None:
        query = build_news_query(
            self.hollister, date(2026, 7, 1), date(2026, 7, 27)
        )

        self.assertIn('"Hollister"', query)
        self.assertIn(
            '(medical OR healthcare OR medtech OR "ostomy care" OR '
            '"continence care" OR "wound care")',
            query,
        )
        self.assertIn("after:2026-07-01", query)
        self.assertIn("before:2026-07-27", query)


class PublicationDateTests(unittest.TestCase):
    def test_accepts_dates_inside_half_open_month_boundary(self) -> None:
        self.assertTrue(
            published_in_range(
                "Mon, 01 Jun 2026 00:00:00 GMT",
                date(2026, 6, 1),
                date(2026, 7, 1),
            )
        )
        self.assertTrue(
            published_in_range(
                "Tue, 30 Jun 2026 23:59:59 GMT",
                date(2026, 6, 1),
                date(2026, 7, 1),
            )
        )

    def test_rejects_google_results_outside_requested_month(self) -> None:
        for published in (
            "Sun, 25 Mar 2012 16:01:00 GMT",
            "Wed, 01 Jul 2026 00:00:00 GMT",
            "Fri, 24 Jul 2026 16:32:44 GMT",
        ):
            with self.subTest(published=published):
                self.assertFalse(
                    published_in_range(
                        published,
                        date(2026, 6, 1),
                        date(2026, 7, 1),
                    )
                )

    def test_rejects_missing_or_malformed_publication_dates(self) -> None:
        for published in ("", "not-a-date"):
            with self.subTest(published=published):
                self.assertFalse(
                    published_in_range(
                        published,
                        date(2026, 6, 1),
                        date(2026, 7, 1),
                    )
                )


if __name__ == "__main__":
    unittest.main()
