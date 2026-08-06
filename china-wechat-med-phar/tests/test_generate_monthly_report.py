import importlib.util
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).parents[1] / "scripts" / "generate_monthly_report.py"
SPEC = importlib.util.spec_from_file_location("generate_monthly_report", MODULE_PATH)
module = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(module)


class CompactArticleForReportTests(unittest.TestCase):
    def test_article_rank_prioritizes_relevance_then_amcor_score(self):
        earlier = {
            "amcor_relevance_score": 4,
            "relevance_score": 19,
            "packaging_relevance": "low",
            "importance_level": "high",
            "published": "2026-07-20",
        }
        later = {
            "amcor_relevance_score": 4,
            "relevance_score": 19,
            "packaging_relevance": "high",
            "importance_level": "low",
            "published": "2026-07-21",
        }

        self.assertEqual(module.article_rank(earlier), (19, 4, 0, "2026-07-20"))
        self.assertEqual(module.article_rank(later), (19, 4, 0, "2026-07-21"))

    def test_article_rank_gives_bonus_to_explicit_opportunity_when_scores_tie(self):
        general = {"relevance_score": 18, "amcor_relevance_score": 3, "title": "新药获批"}
        explicit = {"relevance_score": 18, "amcor_relevance_score": 3, "title": "集采中选带来销量增长"}

        self.assertGreater(module.article_rank(explicit), module.article_rank(general))

    def test_compact_article_omits_obsolete_ranking_attributes(self):
        compact = module.compact_article_for_report(
            {
                "title": "Title",
                "relevance_score": 18,
                "amcor_relevance_score": 4,
                "importance_level": "high",
                "packaging_relevance": "high",
            }
        )

        self.assertNotIn("importance_level", compact)
        self.assertNotIn("packaging_relevance", compact)

    def test_keeps_report_fields_and_omits_raw_text(self):
        article = {
            "article_id": "a-1",
            "title": "Title",
            "main_text": "raw article body",
            "llm_input_text": "raw LLM input",
            "summary_cn": "Summary",
            "published": "2026-07-20T00:00:00Z",
            "link": "https://example.test/a",
            "relevance_score": 18,
            "amcor_relevance_score": 5,
            "packaging_relevance": "high",
            "primary_category": "包装相关",
        }

        compact = module.compact_article_for_report(article)

        self.assertEqual(compact["title"], "Title")
        self.assertEqual(compact["takeaway"], "Summary")
        self.assertEqual(compact["link"], "https://example.test/a")
        self.assertNotIn("main_text", compact)
        self.assertNotIn("llm_input_text", compact)

    def test_uses_one_takeaway_instead_of_repeated_long_analysis(self):
        article = {
            "title": "Title",
            "summary_cn": "Fallback summary",
            "one_sentence_takeaway": "Preferred concise takeaway",
            "key_points": ["long point one", "long point two"],
            "market_implication_cn": "Long market implication",
            "why_it_matters": "Long rationale",
            "risks_or_uncertainties": ["Long uncertainty"],
        }

        compact = module.compact_article_for_report(article)

        self.assertEqual(compact["takeaway"], "Preferred concise takeaway")
        self.assertNotIn("summary_cn", compact)
        self.assertNotIn("key_points", compact)
        self.assertNotIn("market_implication_cn", compact)
        self.assertNotIn("why_it_matters", compact)
        self.assertNotIn("risks_or_uncertainties", compact)


if __name__ == "__main__":
    unittest.main()
