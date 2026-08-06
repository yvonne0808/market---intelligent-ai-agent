import importlib.util
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).parents[1] / "scripts" / "select_pharma_top10.py"
SPEC = importlib.util.spec_from_file_location("select_pharma_top10", MODULE_PATH)
module = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(module)


class SelectPharmaTop10Tests(unittest.TestCase):
    def test_select_top_orders_by_relevance_then_amcor_then_explicit_opportunity(self):
        articles = [
            {"article_id": "a", "relevance_score": 18, "amcor_relevance_score": 3, "title": "新药获批", "published": "2026-07-10"},
            {"article_id": "b", "relevance_score": 18, "amcor_relevance_score": 3, "title": "集采中选销售放量", "published": "2026-07-09"},
            {"article_id": "c", "relevance_score": 17, "amcor_relevance_score": 5, "title": "包装供应链", "published": "2026-07-11"},
        ]

        self.assertEqual([item["article_id"] for item in module.select_top(articles, 3)], ["b", "a", "c"])
        self.assertEqual(module.select_top(articles, 1)[0]["rank"], 1)


if __name__ == "__main__":
    unittest.main()
