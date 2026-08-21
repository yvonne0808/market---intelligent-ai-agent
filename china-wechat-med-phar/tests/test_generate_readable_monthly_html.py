import importlib.util
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).parents[1] / "scripts" / "generate_readable_monthly_html.py"
SPEC = importlib.util.spec_from_file_location("generate_readable_monthly_html", MODULE_PATH)
module = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(module)


class SplitWeekArticlesTests(unittest.TestCase):
    def test_extracts_week_summary_without_a_nested_overview_heading(self):
        markdown = """# Monthly Pharma News Report

### Week 1: 2026-07-01 至 2026-07-07

本周以药包材政策监管为主线，并出现多项新药商业化进展。

### Week 2: 2026-07-08 至 2026-07-14

本周行业重点转向 BD 出海。
"""

        self.assertEqual(
            module.extract_week_overview(markdown, "Week 1"),
            "本周以药包材政策监管为主线，并出现多项新药商业化进展。",
        )

    def test_pharma_sorting_prioritizes_relevance_before_amcor_score(self):
        articles = [
            {"title": "High Pharma Relevance", "relevance_score": 20, "amcor_relevance_score": 1},
            {"title": "High Amcor Relevance", "relevance_score": 12, "amcor_relevance_score": 5},
        ]

        featured, _ = module.split_week_articles(articles, "Pharma")

        self.assertEqual(featured[0]["title"], "High Pharma Relevance")

    def test_medical_device_sorting_keeps_amcor_priority(self):
        articles = [
            {"title": "High Pharma Relevance", "relevance_score": 20, "amcor_relevance_score": 1},
            {"title": "High Amcor Relevance", "relevance_score": 12, "amcor_relevance_score": 5},
        ]

        featured, _ = module.split_week_articles(articles, "Medical Device")

        self.assertEqual(featured[0]["title"], "High Amcor Relevance")

    def test_render_badges_omits_packaging_when_attribute_is_absent(self):
        html = module.render_badges(
            {
                "primary_category": "BD出海",
                "relevance_score": 18,
                "amcor_relevance_score": 4,
            }
        )

        self.assertNotIn("Packaging", html)
        self.assertNotIn("        \n", html)

    def test_build_html_uses_top_opportunity_override(self):
        base_article = {
            "title": "Existing article",
            "source_name": "Source",
            "published": "2026-07-01",
            "relevance_score": 18,
            "amcor_relevance_score": 4,
        }
        override_article = {**base_article, "title": "Rescored opportunity"}

        html = module.build_html(
            {
                "articles": [base_article],
                "top_opportunity_articles": [override_article],
                "weeks": [],
            }
        )

        top_section = html.split('id="top-opportunities"', 1)[1].split('id="weeks"', 1)[0]
        self.assertIn("Rescored opportunity", top_section)
        self.assertNotIn("Existing article", top_section)

    def test_limits_featured_articles_and_keeps_remaining_articles_below_week(self):
        articles = [
            {
                "title": f"Article {index}",
                "amcor_relevance_score": 5,
                "relevance_score": 20 - index,
                "packaging_relevance": "high",
                "published": "2026-07-20T00:00:00Z",
            }
            for index in range(5)
        ]

        featured, other = module.split_week_articles(articles)

        self.assertEqual([item["title"] for item in featured], ["Article 0", "Article 1", "Article 2", "Article 3"])
        self.assertEqual([item["title"] for item in other], ["Article 4"])

    def test_render_week_shows_total_count_and_other_articles(self):
        articles = [
            {
                "title": f"Article {index}",
                "amcor_relevance_score": 5,
                "relevance_score": 20 - index,
                "packaging_relevance": "high",
                "published": "2026-07-20T00:00:00Z",
            }
            for index in range(5)
        ]
        week = {
            "week": "Week 1",
            "start_date": "2026-07-15",
            "end_date": "2026-07-21",
            "articles": articles,
        }

        html = module.render_week(week)

        self.assertIn("5 articles", html)
        self.assertIn("Other Important Pharma News", html)
        self.assertIn("Article 4", html)


if __name__ == "__main__":
    unittest.main()
