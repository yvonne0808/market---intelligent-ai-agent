from __future__ import annotations

import unittest
import json
import copy
from pathlib import Path
from tempfile import TemporaryDirectory

from southeast_asia_medtech.customer_analysis.workflow import (
    build_event_ledger,
    export_site_assets,
    prepare_issue,
    resolve_display_report,
    validate_report,
)


def event(**overrides):
    value = {
        "article_id": "a1",
        "url": "https://example.test/a1",
        "title": "Customer launches sterile device",
        "organization": "Acme MedTech",
        "published_date": "Wed, 15 Jul 2026 00:00:00 GMT",
        "customer_relevance": "direct_customer",
        "relevance_score": 17,
        "importance_level": "high",
        "primary_category": "产品与商业化",
        "summary_cn": "客户发布无菌医疗器械。",
        "one_sentence_takeaway": "客户发布无菌医疗器械。",
        "customer_impact_cn": "可能带来包装需求。",
        "packaging_relevance_score": 3,
        "packaging_relevance_reason": "一次性无菌器械。",
        "matched_customers": ["Acme MedTech"],
        "related_customer_groups": [],
        "competitor_companies": [],
        "report_countries": [],
        "source_name": "Official source",
        "source_confidence": "high",
    }
    value.update(overrides)
    return value


def report(actions):
    return {
        "report_metadata": {"issue": "2026-07", "language": "en"},
        "executive_summary": "Customer activity is concentrated in product launches.",
        "priority_actions": actions,
        "opportunity_themes": [
            {
                "name": f"Theme {index}",
                "summary": "New launches create account conversations.",
                "evidence_article_ids": ["a1"],
            }
            for index in range(1, 5)
        ],
    }


def action(index: int, article_id: str = "a1"):
    return {
        "title": f"Priority action {index}",
        "companies": ["Acme MedTech"],
        "event_type": "product commercialization",
        "commercial_implication_en": "Discuss sterile-device packaging needs.",
        "packaging_angle_en": "Packaging relevance is evidenced in the source.",
        "recommended_next_step_en": "Contact the account team.",
        "priority": "high",
        "evidence_article_ids": [article_id],
    }


class CustomerAnalysisWorkflowTests(unittest.TestCase):
    def test_ledger_deduplicates_urls_and_excludes_none_records(self) -> None:
        ledger = build_event_ledger(
            [
                event(article_id="a1", url="https://example.test/duplicate"),
                event(article_id="a2", url="https://example.test/duplicate", relevance_score=19),
                event(article_id="a3", customer_relevance="industry_only"),
                event(article_id="a4", customer_relevance="none"),
            ],
            source_label="fixture.json",
        )

        self.assertEqual([item["article_id"] for item in ledger["events"]], ["a2", "a3"])
        self.assertEqual(ledger["counts"], {
            "source_articles": 4,
            "excluded_none": 1,
            "deduplicated": 1,
            "events": 2,
            "priority_evidence": 1,
        })
        self.assertEqual(ledger["events"][0]["provenance"]["source_labels"], ["fixture.json"])

    def test_priority_evidence_keeps_only_direct_customer_and_competitor(self) -> None:
        ledger = build_event_ledger(
            [
                event(article_id="customer", url="https://example.test/customer"),
                event(article_id="competitor", url="https://example.test/competitor", customer_relevance="competitor"),
                event(article_id="industry", url="https://example.test/industry", customer_relevance="industry_only"),
            ],
            source_label="fixture.json",
        )

        self.assertEqual(
            [item["article_id"] for item in ledger["priority_evidence"]],
            ["competitor", "customer"],
        )

    def test_report_requires_ten_unique_actions_with_known_evidence(self) -> None:
        evidence = [event(article_id=f"a{index}", url=f"https://example.test/a{index}") for index in range(1, 11)]
        valid_actions = [action(index, article_id=f"a{index}") for index in range(1, 11)]

        report_without_themes = report(valid_actions)
        report_without_themes.pop("opportunity_themes")
        validate_report(report_without_themes, evidence)

        with self.assertRaisesRegex(ValueError, "exactly 10"):
            validate_report(report(valid_actions[:9]), evidence)
        with self.assertRaisesRegex(ValueError, "duplicate priority action"):
            validate_report(report([action(index, article_id="a1") for index in range(1, 11)]), evidence)
        with self.assertRaisesRegex(ValueError, "unknown evidence"):
            validate_report(report([action(index, article_id="missing") for index in range(1, 11)]), evidence)
        non_english = copy.deepcopy(report(valid_actions))
        non_english["executive_summary"] = "客户活动集中于产品上市。"
        with self.assertRaisesRegex(ValueError, "English"):
            validate_report(non_english, evidence)

    def test_approved_report_takes_precedence_over_draft(self) -> None:
        self.assertEqual(
            resolve_display_report({"edition": "draft"}, {"edition": "approved"}),
            ({"edition": "approved"}, "approved"),
        )

    def test_prepare_issue_appends_to_master_ledger_without_removing_prior_issue(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary) / "customer_analysis"
            july_source = Path(temporary) / "july.json"
            august_source = Path(temporary) / "august.json"
            july_source.write_text(json.dumps([event(article_id="a1")]), encoding="utf-8")
            august_source.write_text(
                json.dumps([
                    event(
                        article_id="a2",
                        url="https://example.test/a2",
                        published_date="Mon, 03 Aug 2026 00:00:00 GMT",
                    )
                ]),
                encoding="utf-8",
            )

            prepare_issue([july_source], issue="2026-07", output_root=root)
            august = prepare_issue([august_source], issue="2026-08", output_root=root)

            master = json.loads((root / "master_events.json").read_text(encoding="utf-8"))
            self.assertEqual({item["article_id"] for item in master["events"]}, {"a1", "a2"})
            self.assertTrue((root / "issues" / "2026-07" / "evidence.json").exists())
            self.assertTrue((root / "issues" / "2026-08" / "prompt_evidence.json").exists())
            self.assertEqual(august["counts"]["priority_evidence"], 2)

            prepare_issue([august_source], issue="2026-07", output_root=root)
            july_evidence = json.loads((root / "issues" / "2026-07" / "evidence.json").read_text(encoding="utf-8"))
            self.assertEqual([item["article_id"] for item in july_evidence["events"]], ["a1"])

    def test_site_export_uses_approved_report_when_available(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary) / "customer_analysis"
            public = Path(temporary) / "public"
            issue_dir = root / "issues" / "2026-07"
            issue_dir.mkdir(parents=True)
            (root / "master_events.json").write_text(
                json.dumps({"events": [event()], "counts": {}}), encoding="utf-8"
            )
            (issue_dir / "draft.json").write_text(json.dumps({"edition": "draft"}), encoding="utf-8")
            (issue_dir / "approved.json").write_text(json.dumps({"edition": "approved"}), encoding="utf-8")
            (issue_dir / "evidence.json").write_text(
                json.dumps({"events": [event()], "counts": {}}), encoding="utf-8"
            )

            export_site_assets(root, issue="2026-07", site_public_dir=public)

            report_asset = json.loads((public / "customer-analysis" / "report.json").read_text(encoding="utf-8"))
            events_asset = json.loads((public / "customer-analysis" / "events.json").read_text(encoding="utf-8"))
            self.assertEqual(report_asset["edition"], "approved")
            self.assertEqual(report_asset["editorial_status"], "approved")
            self.assertEqual(events_asset[0]["article_id"], "a1")
        self.assertEqual(
            resolve_display_report({"edition": "draft"}, None),
            ({"edition": "draft"}, "draft"),
        )


if __name__ == "__main__":
    unittest.main()
