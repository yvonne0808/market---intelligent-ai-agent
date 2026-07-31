from pathlib import Path
import importlib.util
import unittest


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
CHINA_ROOT = REPOSITORY_ROOT / "china-wechat-med-phar"


class RepositoryLayoutTests(unittest.TestCase):
    def test_business_modules_are_separated(self):
        self.assertTrue(CHINA_ROOT.is_dir())
        self.assertTrue((REPOSITORY_ROOT / "southeast_asia_medtech").is_dir())

    def test_china_pipeline_files_live_under_china_module(self):
        expected_paths = (
            "config.yaml",
            "data",
            "prompts",
            "reports",
            "scripts/main.py",
            "website_scraper",
            "website_sources.yaml",
        )
        for relative_path in expected_paths:
            with self.subTest(relative_path=relative_path):
                self.assertTrue((CHINA_ROOT / relative_path).exists())

    def test_china_pipeline_files_are_not_left_at_repository_root(self):
        old_root_paths = (
            "config.yaml",
            "data",
            "prompts",
            "reports",
            "scripts",
            "website_scraper",
            "website_sources.yaml",
        )
        for relative_path in old_root_paths:
            with self.subTest(relative_path=relative_path):
                self.assertFalse((REPOSITORY_ROOT / relative_path).exists())

    def test_llm_scripts_resolve_shared_environment_from_repository_root(self):
        script_names = (
            "analyze_articles.py",
            "generate_monthly_report.py",
            "generate_weekly_report.py",
        )
        for script_name in script_names:
            with self.subTest(script_name=script_name):
                script_path = CHINA_ROOT / "scripts" / script_name
                spec = importlib.util.spec_from_file_location(
                    f"layout_test_{script_path.stem}", script_path
                )
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                self.assertEqual(
                    getattr(module, "REPOSITORY_ROOT", None), REPOSITORY_ROOT
                )


if __name__ == "__main__":
    unittest.main()
