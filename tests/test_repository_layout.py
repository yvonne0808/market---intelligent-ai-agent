from pathlib import Path
import importlib.util
import re
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

    def test_coverage_script_resolves_sibling_wewe_rss_database(self):
        script_path = (
            CHINA_ROOT / "scripts" / "check_july_pharma_coverage.py"
        )
        spec = importlib.util.spec_from_file_location(
            "layout_test_check_july_pharma_coverage", script_path
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        expected = (
            REPOSITORY_ROOT.parent
            / "wewe-rss-local"
            / "data"
            / "wewe-rss.db"
        )
        self.assertEqual(module.DEFAULT_DB_PATH, expected)

    def test_china_readme_has_no_obsolete_script_commands(self):
        readme = (CHINA_ROOT / "README.md").read_text(encoding="utf-8")
        obsolete_patterns = (
            r"(?m)^python3? scripts/main\.py",
            r"scripts/scripts/",
        )
        for pattern in obsolete_patterns:
            with self.subTest(pattern=pattern):
                self.assertIsNone(re.search(pattern, readme))

    def test_shared_environment_metadata_uses_current_repository_path(self):
        old_root = str(
            REPOSITORY_ROOT.parent / "wechat-rss-data-collector"
        )
        metadata_paths = tuple(
            path
            for path in (
                REPOSITORY_ROOT / ".venv" / "pyvenv.cfg",
                REPOSITORY_ROOT / ".venv" / "bin" / "activate",
                REPOSITORY_ROOT / ".venv" / "bin" / "activate.csh",
                REPOSITORY_ROOT / ".venv" / "bin" / "activate.fish",
                REPOSITORY_ROOT / ".venv" / "bin" / "pip",
                REPOSITORY_ROOT / ".venv" / "bin" / "pip3",
                REPOSITORY_ROOT / ".venv" / "bin" / "pip3.14",
            )
            if path.is_file()
        )
        metadata_paths += tuple(
            (REPOSITORY_ROOT / ".playwright-browsers" / ".links").glob("*")
        )
        for path in metadata_paths:
            with self.subTest(path=path):
                self.assertNotIn(old_root, path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
