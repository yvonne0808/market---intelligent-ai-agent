import json
import re
import unittest
from pathlib import Path


PROMPT_DIR = Path(__file__).resolve().parents[1] / "prompts"


class PromptContractTests(unittest.TestCase):
    def test_required_prompt_files_exist(self):
        for name in (
            "website_article_analysis_prompt.txt",
            "procurement_award_extraction_prompt.txt",
            "monthly_report_prompt.txt",
            "README.md",
        ):
            self.assertTrue((PROMPT_DIR / name).is_file(), name)

    def test_article_prompt_json_contract_is_valid(self):
        text = (PROMPT_DIR / "website_article_analysis_prompt.txt").read_text(
            encoding="utf-8"
        )
        blocks = re.findall(r"\{(?:[^{}]|\[[^\]]*\])*\}", text, re.DOTALL)
        contract = json.loads(blocks[-1])
        required = {
            "article_id",
            "country",
            "organization",
            "include_in_monthly_report",
            "relevance_score",
            "packaging_relevance_score",
            "regulatory_events",
            "procurement_events",
            "url",
        }
        self.assertTrue(required.issubset(contract))

    def test_monthly_prompt_has_runtime_placeholders(self):
        text = (PROMPT_DIR / "monthly_report_prompt.txt").read_text(
            encoding="utf-8"
        )
        for placeholder in (
            "{reporting_period}",
            "{generated_at}",
            "{source_scope}",
            "{analyzed_articles_json}",
        ):
            self.assertIn(placeholder, text)

    def test_prompts_do_not_contain_api_credentials(self):
        for path in PROMPT_DIR.glob("*.txt"):
            text = path.read_text(encoding="utf-8").lower()
            self.assertNotIn("sk-", text)
            self.assertNotIn("api_key=", text)


if __name__ == "__main__":
    unittest.main()
