import importlib.util
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).parents[1] / "scripts" / "convert_monthly_markdown_to_pdf.py"
SPEC = importlib.util.spec_from_file_location("convert_monthly_markdown_to_pdf", MODULE_PATH)
module = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(module)


class ReportTitleTests(unittest.TestCase):
    def test_reads_first_markdown_heading_for_pdf_title(self):
        markdown = "# Monthly Medical Device News Report\n\nPeriod: July 2026"

        self.assertEqual(module.report_title_from_markdown(markdown), "Monthly Medical Device News Report")


if __name__ == "__main__":
    unittest.main()
