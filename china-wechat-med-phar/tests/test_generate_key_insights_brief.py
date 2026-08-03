import importlib.util
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).parents[1] / "scripts" / "generate_key_insights_brief.py"
SPEC = importlib.util.spec_from_file_location("generate_key_insights_brief", MODULE_PATH)
module = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(module)


class BriefHtmlTests(unittest.TestCase):
    def test_build_brief_has_sections_and_source_link(self):
        report = {
            "start_date": "2026-07-01",
            "end_date": "2026-07-31",
            "articles": [
                {
                    "article_id": "a-1",
                    "title": "Commercial launch",
                    "source_name": "Source",
                    "published": "2026-07-20T00:00:00Z",
                    "link": "https://example.test/article",
                    "summary_cn": "A launch creates volume signal.",
                    "one_sentence_takeaway": "A launch creates volume signal.",
                    "companies": ["Company"],
                    "relevance_score": 18,
                    "amcor_relevance_score": 5,
                    "packaging_relevance": "high",
                }
            ],
        }

        html = module.build_brief_html(report, ["a-1"], "Pharma")

        self.assertIn("Five Key Takeaways", html)
        self.assertIn("Top Opportunities", html)
        self.assertIn("Watchlist &amp; References", html)
        self.assertIn('href="https://example.test/article"', html)


if __name__ == "__main__":
    unittest.main()
