import importlib.util
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).parents[1] / "scripts" / "archive" / "classify_pharma_opportunity_candidates.py"
SPEC = importlib.util.spec_from_file_location("classify_pharma_opportunity_candidates", MODULE_PATH)
module = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(module)


class OpportunityCandidateClassifierTests(unittest.TestCase):
    def test_chunked_splits_pending_articles_without_reordering(self):
        articles = [{"article_id": str(number)} for number in range(5)]

        self.assertEqual(
            module.chunked(articles, 2),
            [
                [{"article_id": "0"}, {"article_id": "1"}],
                [{"article_id": "2"}, {"article_id": "3"}],
                [{"article_id": "4"}],
            ],
        )

    def test_limit_batches_keeps_only_requested_batch_count(self):
        batches = [[{"article_id": str(number)}] for number in range(4)]

        self.assertEqual(module.limit_batches(batches, 2), batches[:2])

    def test_normalize_results_keeps_only_requested_fields(self):
        raw = [
            {
                "article_id": "article-1",
                "is_top_opportunity": True,
                "new_category": "市场与商业化",
                "confidence": "high",
                "reason": "Should not be saved",
            },
            {
                "article_id": "article-2",
                "is_top_opportunity": False,
                "new_category": "市场与商业化",
                "confidence": "medium",
            },
        ]

        self.assertEqual(
            module.normalize_results(raw, {"article-1", "article-2"}),
            [
                {
                    "article_id": "article-1",
                    "is_top_opportunity": True,
                    "new_category": "市场与商业化",
                    "confidence": "high",
                },
                {
                    "article_id": "article-2",
                    "is_top_opportunity": False,
                    "new_category": "",
                    "confidence": "medium",
                },
            ],
        )

    def test_normalize_results_rejects_invalid_true_category(self):
        with self.assertRaisesRegex(ValueError, "new_category"):
            module.normalize_results(
                [
                    {
                        "article_id": "article-1",
                        "is_top_opportunity": True,
                        "new_category": "药品监管",
                        "confidence": "high",
                    }
                ],
                {"article-1"},
            )


if __name__ == "__main__":
    unittest.main()
