import importlib.util
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).parents[1] / "scripts" / "generate_readable_monthly_html.py"
SPEC = importlib.util.spec_from_file_location("generate_readable_monthly_html", MODULE_PATH)
module = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(module)


class SplitWeekArticlesTests(unittest.TestCase):
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
