from __future__ import annotations

import unittest
from pathlib import Path

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

    def test_complete_sources_registry_belongs_to_monthly_report(self):
        legacy = MODULE_DIR / "config" / "sources.yaml"
        owned = MODULE_DIR / "monthly_report" / "config" / "sources.yaml"
        self.assertEqual(
            legacy.read_text(encoding="utf-8"),
            owned.read_text(encoding="utf-8"),
        )
        self.assertFalse(
            (MODULE_DIR / "customer_analysis" / "config" / "sources.yaml").exists()
        )

    def test_company_watchlist_belongs_to_customer_analysis(self):
        legacy = MODULE_DIR / "config" / "company_watchlist.yaml"
        owned = (
            MODULE_DIR
            / "customer_analysis"
            / "config"
            / "company_watchlist.yaml"
        )
        self.assertEqual(
            legacy.read_text(encoding="utf-8"),
            owned.read_text(encoding="utf-8"),
        )

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
