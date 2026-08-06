import importlib.util
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).parents[1] / "scripts" / "analyze_pharma_top_opportunities.py"
SPEC = importlib.util.spec_from_file_location("analyze_pharma_top_opportunities", MODULE_PATH)
module = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(module)


class TopOpportunityAnalysisTests(unittest.TestCase):
    def test_normalize_keeps_only_ranking_fields(self):
        article = {
            "article_id": "article-1",
            "title": "Title",
            "source_name": "Source",
            "published": "2026-07-10",
            "link": "https://example.test/article",
        }
        result = module.normalize_analysis(
            {
                "primary_category": "市场与商业化",
                "relevance_score": 19,
                "amcor_relevance_score": 4,
                "amcor_relevance_reason": "明确销量放量，可能增加药品包装需求。",
                "summary_cn": "简短摘要",
                "companies": ["must be omitted"],
            },
            article,
        )

        self.assertEqual(
            set(result),
            {
                "article_id", "title", "source_name", "published", "link",
                "primary_category", "relevance_score", "amcor_relevance_score",
                "amcor_relevance_reason", "summary_cn",
            },
        )
        self.assertNotIn("companies", result)


if __name__ == "__main__":
    unittest.main()
