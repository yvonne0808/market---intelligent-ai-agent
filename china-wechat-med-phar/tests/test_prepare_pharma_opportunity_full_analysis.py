import importlib.util
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).parents[1] / "scripts" / "archive" / "prepare_pharma_opportunity_full_analysis.py"
SPEC = importlib.util.spec_from_file_location("prepare_pharma_opportunity_full_analysis", MODULE_PATH)
module = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(module)


class PrepareOpportunityFullAnalysisTests(unittest.TestCase):
    def test_selects_only_true_classification_ids_in_source_order(self):
        articles = [{"article_id": "a"}, {"article_id": "b"}, {"article_id": "c"}]
        classifications = [
            {"article_id": "c", "is_top_opportunity": True},
            {"article_id": "a", "is_top_opportunity": False},
        ]

        self.assertEqual(module.select_articles(articles, classifications), [{"article_id": "c"}])


if __name__ == "__main__":
    unittest.main()
