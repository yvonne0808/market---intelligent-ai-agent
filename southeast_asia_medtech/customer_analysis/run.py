from __future__ import annotations

import argparse
from pathlib import Path

from .report_generator import generate_draft
from .workflow import export_site_assets, prepare_issue


MODULE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_ROOT = MODULE_DIR / "data" / "customer_analysis"
DEFAULT_SITE_PUBLIC = MODULE_DIR / "report_site" / "public"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build customer analysis evidence and report assets.")
    parser.add_argument("--issue", required=True, help="Issue label in YYYY-MM format.")
    parser.add_argument("--input", type=Path, action="append", required=True, help="Analyzed customer-discovery JSON file. Repeatable.")
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--site-public-dir", type=Path, default=DEFAULT_SITE_PUBLIC)
    parser.add_argument("--generate", action="store_true", help="Call DeepSeek to create/update draft.json.")
    parser.add_argument("--export", action="store_true", help="Export draft/approved report and evidence to the static website.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    ledger = prepare_issue(args.input, issue=args.issue, output_root=args.output_root)
    print(
        f"Prepared {args.issue}: {ledger['counts']['events']} display events, "
        f"{ledger['counts']['priority_evidence']} priority-evidence articles."
    )
    if args.generate:
        draft = generate_draft(output_root=args.output_root, issue=args.issue)
        print(f"Generated draft: {draft}")
    if args.export:
        report, events = export_site_assets(
            args.output_root, issue=args.issue, site_public_dir=args.site_public_dir
        )
        print(f"Exported site assets: {report}, {events}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
