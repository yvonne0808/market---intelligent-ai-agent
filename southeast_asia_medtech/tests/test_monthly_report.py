from __future__ import annotations

import unittest

from southeast_asia_medtech.reports.generate_monthly_report import (
    EMPTY_SECTION,
    build_company_rows,
    generate_markdown,
    packaging_details,
    parse_month,
    sections_for_article,
)
from southeast_asia_medtech.reports.llm_interface import generate_llm_summary


def article(**overrides):
    record = {
        "article_id": "a1",
        "title": "Medical device update",
        "source_name": "Official Source",
        "country": "MY",
        "organization": "Authority",
        "source_type": "regulator",
        "published_date": "20 July 2026",
        "url": "https://example.test/a1",
        "body": "Medical device registration details. " * 5,
        "business_categories": ["regulatory_registration"],
        "matched_keywords": ["medical device", "registration"],
        "device_relevance_score": 14,
        "packaging_relevance_score": 0,
        "priority_level": "matched",
    }
    record.update(overrides)
    return record


class MonthlyReportTest(unittest.TestCase):
    def test_month_validation(self) -> None:
        self.assertEqual(parse_month("2026-07"), (2026, 7))
        with self.assertRaises(ValueError):
            parse_month("2026-7")

    def test_malay_procurement_terms_route_to_procurement(self) -> None:
        row = article(
            body=(
                "SEBUT HARGA PERKHIDMATAN PENYEBUT HARGA YANG BERJAYA "
                "HARGA SETUJU TERIMA PINNACLE CONCEPTS SDN. BHD. RM 100"
            ),
            business_categories=[],
        )
        self.assertEqual(sections_for_article(row), ["procurement"])

    def test_packaging_fields_only_use_explicit_terms(self) -> None:
        details = packaging_details(
            article(
                body="Tyvek thermoformed tray with EO sterilization under ISO 11607.",
                packaging_relevance_score=10,
            )
        )
        self.assertEqual(details["packaging_material"], "Tyvek")
        self.assertEqual(details["packaging_format"], "thermoformed tray")
        self.assertEqual(details["sterilization_method"], "EO sterilization")
        self.assertTrue(details["ISO_11607_relevance"])

    def test_unknown_packaging_attributes_stay_empty(self) -> None:
        details = packaging_details(article(body="General medical equipment market update."))
        self.assertEqual(details["packaging_material"], "")
        self.assertEqual(details["packaging_format"], "")
        self.assertEqual(details["sterilization_method"], "")
        self.assertEqual(details["possible_business_implication"], "")

    def test_company_extraction_uses_label(self) -> None:
        rows = build_company_rows(
            [article(country="SG", body="Local Company: BD Holdings Pte Ltd Description of Issue: recall")]
        )
        self.assertEqual([row["company_name"] for row in rows], ["BD Holdings Pte Ltd"])

    def test_company_extraction_removes_mda_authority_prefix(self) -> None:
        rows = build_company_rows(
            [
                article(
                    body=(
                        "PIHAK BERKUASA PERANTI PERUBATAN "
                        "PINNACLE CONCEPTS SDN. BHD. RM 314,280"
                    ),
                    business_categories=["procurement_contract_award"],
                )
            ]
        )
        self.assertEqual(rows[0]["company_name"], "PINNACLE CONCEPTS SDN. BHD")

    def test_empty_sections_use_required_message(self) -> None:
        markdown = generate_markdown("2026-07", [], [], [])
        self.assertIn(EMPTY_SECTION, markdown)
        self.assertIn("## 7. Medical Device Packaging Signals", markdown)

    def test_llm_placeholder_never_calls_provider(self) -> None:
        class Provider:
            def __getattr__(self, _name):
                raise AssertionError("provider must not be accessed")

        self.assertEqual(generate_llm_summary(article(), Provider()), "")


if __name__ == "__main__":
    unittest.main()
