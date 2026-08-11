from __future__ import annotations

import unittest
from unittest.mock import patch

from southeast_asia_medtech.config import config_loader

from southeast_asia_medtech.config.config_loader import (
    load_company_watchlist,
    load_keywords,
    load_sources,
)


REQUIRED_SOURCE_FIELDS = {
    "source_id",
    "source_name",
    "country",
    "organization",
    "list_url",
    "base_url",
    "source_type",
    "category",
    "priority",
    "language",
    "enabled",
    "parsing_strategy",
    "report_frequency",
    "requires_javascript",
    "selectors",
    "notes",
}
REQUIRED_SELECTORS = {"article_card", "title", "date", "article_link", "body"}
REQUIRED_TERMS = {
    "medical device",
    "medical consumables",
    "registration",
    "procurement",
    "contract award",
    "local manufacturing",
    "capacity expansion",
    "sterile barrier system",
    "medical device packaging",
    "ISO 11607",
    "cleanroom packaging",
}


class ConfigLoadingTest(unittest.TestCase):
    def test_default_config_paths_follow_section_ownership(self) -> None:
        with patch.object(config_loader, "_load_yaml", return_value={}) as loader:
            config_loader.load_sources()
            self.assertEqual(
                loader.call_args.args[0],
                config_loader.MODULE_DIR / "monthly_report" / "config" / "sources.yaml",
            )
            config_loader.load_keywords()
            self.assertEqual(
                loader.call_args.args[0],
                config_loader.MODULE_DIR / "monthly_report" / "config" / "keywords.yaml",
            )
            config_loader.load_company_watchlist()
            self.assertEqual(
                loader.call_args.args[0],
                config_loader.MODULE_DIR
                / "customer_analysis"
                / "config"
                / "company_watchlist.yaml",
            )

    def test_sources_have_customer_first_source_families(self) -> None:
        config = load_sources()
        sources = config["sources"]
        self.assertGreaterEqual(len(sources), 15)
        self.assertEqual(len({item["source_id"] for item in sources}), len(sources))
        self.assertTrue({"SG", "MY", "TH", "ID", "VN", "PH"}.issubset(
            {item["country"] for item in sources}
        ))

        allowed = set(config["allowed_parsing_strategies"])
        workflows = set(config["allowed_workflows"])
        for source in sources:
            self.assertTrue(REQUIRED_SOURCE_FIELDS.issubset(source))
            self.assertEqual(set(source["selectors"]), REQUIRED_SELECTORS)
            self.assertIn(source["parsing_strategy"], allowed)
            self.assertIn(source["workflow"], workflows)
            self.assertTrue(source["extract_fields"])
            self.assertTrue(source["search_terms"])
            self.assertTrue(source["list_url"].startswith("https://"))
            self.assertTrue(source["base_url"].startswith("https://"))

    def test_keywords_have_supported_metadata_and_required_terms(self) -> None:
        config = load_keywords()
        categories = config["categories"]
        self.assertTrue(
            {"medical_device_business", "medical_device_packaging"}.issubset(
                {item["category"] for item in categories}
            )
        )

        terms: set[str] = set()
        for category in categories:
            self.assertTrue(category["keywords"])
            for entry in category["keywords"]:
                self.assertEqual(
                    {"keyword", "synonyms", "weight", "language"},
                    set(entry),
                )
                self.assertIsInstance(entry["synonyms"], list)
                self.assertGreater(entry["weight"], 0)
                self.assertTrue(entry["language"])
                terms.add(entry["keyword"])

        self.assertTrue(REQUIRED_TERMS.issubset(terms))

    def test_company_watchlist_has_twenty_unique_customers_and_valid_competitors(self) -> None:
        config = load_company_watchlist()
        customers = config["customers"]
        self.assertEqual(len(customers), 20)
        self.assertEqual(
            len({customer["customer_id"] for customer in customers}),
            len(customers),
        )
        self.assertEqual(
            len({customer["canonical_name"] for customer in customers}),
            len(customers),
        )
        known_companies = set(config["competitor_companies"])
        customer_ids = {customer["customer_id"] for customer in customers}
        allowed_country_codes = set(
            config["southeast_asia_footprint_metadata"][
                "allowed_country_codes"
            ]
        )
        for customer in customers:
            self.assertTrue(customer["aliases"])
            self.assertTrue(customer["product_segments"])
            self.assertNotIn("headquarters_country", customer)
            self.assertNotIn("headquarters_country_code", customer)
            self.assertIsInstance(customer["southeast_asia_footprint"], list)
            self.assertTrue(
                set(customer["southeast_asia_footprint"])
                <= allowed_country_codes
            )
            for competitor in customer["competitors"]:
                self.assertIn(
                    competitor["company_id"],
                    known_companies | customer_ids,
                )
                self.assertTrue(competitor["competition_dimensions"])

        for company in config["competitor_companies"].values():
            self.assertNotIn("headquarters_country", company)
            self.assertNotIn("headquarters_country_code", company)
            self.assertIsInstance(company["southeast_asia_footprint"], list)
            self.assertTrue(
                set(company["southeast_asia_footprint"])
                <= allowed_country_codes
            )

        customer_by_id = {
            customer["customer_id"]: customer for customer in customers
        }
        for company_id in customer_ids & known_companies:
            self.assertEqual(
                customer_by_id[company_id]["southeast_asia_footprint"],
                config["competitor_companies"][company_id][
                    "southeast_asia_footprint"
                ],
            )


if __name__ == "__main__":
    unittest.main()
