from __future__ import annotations

import unittest
from pathlib import Path

import yaml


MODULE_DIR = Path(__file__).resolve().parents[1]


class ReportStreamLayoutTests(unittest.TestCase):
    def test_existing_prompts_are_copied_verbatim_to_owning_sections(self):
        pairs = [
            (
                MODULE_DIR / "prompts" / "website_article_analysis_prompt.txt",
                MODULE_DIR
                / "customer_analysis"
                / "prompts"
                / "article_analysis_prompt.txt",
            ),
            (
                MODULE_DIR / "prompts" / "monthly_report_prompt.txt",
                MODULE_DIR
                / "monthly_report"
                / "prompts"
                / "report_generation_prompt.txt",
            ),
            (
                MODULE_DIR
                / "customer_analysis"
                / "prompts"
                / "customer_analysis_report_prompt.txt",
                MODULE_DIR
                / "customer_analysis"
                / "prompts"
                / "report_generation_prompt.txt",
            ),
        ]
        for legacy, owned in pairs:
            with self.subTest(owned=owned):
                self.assertEqual(
                    legacy.read_text(encoding="utf-8"),
                    owned.read_text(encoding="utf-8"),
                )

    def test_sources_are_partitioned_without_rewriting_rows(self):
        legacy = yaml.safe_load(
            (MODULE_DIR / "config" / "sources.yaml").read_text(encoding="utf-8")
        )
        monthly = yaml.safe_load(
            (
                MODULE_DIR / "monthly_report" / "config" / "sources.yaml"
            ).read_text(encoding="utf-8")
        )
        customer = yaml.safe_load(
            (
                MODULE_DIR / "customer_analysis" / "config" / "sources.yaml"
            ).read_text(encoding="utf-8")
        )
        legacy_by_id = {row["source_id"]: row for row in legacy["sources"]}
        monthly_ids = {row["source_id"] for row in monthly["sources"]}
        customer_ids = {row["source_id"] for row in customer["sources"]}
        self.assertFalse(monthly_ids & customer_ids)
        self.assertEqual(len(monthly_ids), 9)
        self.assertEqual(len(customer_ids), 7)
        for row in monthly["sources"] + customer["sources"]:
            self.assertEqual(row, legacy_by_id[row["source_id"]])

    def test_section_owned_script_entrypoints_exist(self):
        self.assertTrue(
            (
                MODULE_DIR
                / "monthly_report"
                / "scrapers"
                / "collect_monthly_articles.py"
            ).is_file()
        )

    def test_monthly_keywords_are_copied_verbatim(self):
        legacy = MODULE_DIR / "config" / "keywords.yaml"
        owned = MODULE_DIR / "monthly_report" / "config" / "keywords.yaml"
        self.assertEqual(
            legacy.read_text(encoding="utf-8"),
            owned.read_text(encoding="utf-8"),
        )
        self.assertTrue(
            (
                MODULE_DIR
                / "customer_analysis"
                / "scrapers"
                / "run_customer_news_discovery.py"
            ).is_file()
        )


if __name__ == "__main__":
    unittest.main()
