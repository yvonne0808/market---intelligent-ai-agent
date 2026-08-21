import importlib.util
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).parents[1] / "scripts" / "analyze_pharma_articles.py"
SPEC = importlib.util.spec_from_file_location("analyze_pharma_articles", MODULE_PATH)
module = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(module)


class PharmaScoreBandTests(unittest.TestCase):
    def _analysis(self, score, include):
        return module.coerce_analysis(
            {
                "relevance_score": score,
                "amcor_relevance_score": 0,
                "include_in_weekly_report": include,
            },
            {"article_id": "a-1", "title": "Title"},
        )

    def test_high_score_is_always_included(self):
        self.assertTrue(self._analysis(18, False)["include_in_weekly_report"])
        self.assertTrue(self._analysis(20, False)["include_in_weekly_report"])

    def test_low_score_is_always_excluded(self):
        self.assertFalse(self._analysis(0, True)["include_in_weekly_report"])
        self.assertFalse(self._analysis(11, True)["include_in_weekly_report"])

    def test_amcor_score_alone_does_not_minimize_an_important_article(self):
        self.assertFalse(
            module.should_minimize_low_value_analysis(
                {"relevance_score": 16, "amcor_relevance_score": 0}
            )
        )

    def test_low_relevance_still_uses_minimized_analysis(self):
        self.assertTrue(
            module.should_minimize_low_value_analysis(
                {"relevance_score": 9, "amcor_relevance_score": 5}
            )
        )


if __name__ == "__main__":
    unittest.main()
