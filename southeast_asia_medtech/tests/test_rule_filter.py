from __future__ import annotations

import unittest

from southeast_asia_medtech.processors.rule_filter import (
    calculate_packaging_score,
    deduplicate,
    duplicate_reason,
    load_keyword_definitions,
    normalized_url,
    preferred_record,
    score_article,
)


def article(title: str, body: str, **overrides):
    record = {
        "article_id": overrides.pop("article_id", title.lower().replace(" ", "_")),
        "title": title,
        "source_name": "Official Regulator",
        "country": "SG",
        "organization": "Authority",
        "source_type": "regulator",
        "published_date": "20 July 2026",
        "collected_at": "2026-07-24T10:00:00+08:00",
        "url": overrides.pop("url", f"https://example.test/{abs(hash(title))}"),
        "language": "en",
        "body": body,
        "raw_text_length": len(body),
        "scrape_status": "success",
        "error_message": "",
    }
    record.update(overrides)
    return record


class RuleFilterTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.definitions = load_keyword_definitions()

    def test_01_registration_is_high_value(self) -> None:
        result = score_article(
            article(
                "Medical device registration approval",
                "Singapore approved a medical device registration for market authorization. " * 3,
            ),
            self.definitions,
        )
        self.assertGreaterEqual(result["device_relevance_score"], 16)
        self.assertTrue(result["include_in_llm_analysis"])
        self.assertIn("regulatory_registration", result["business_categories"])

    def test_02_procurement_award_is_high_value(self) -> None:
        result = score_article(
            article(
                "Medical consumables contract award",
                "Malaysia government procurement tender named the successful bidder for medical consumables. " * 3,
            ),
            self.definitions,
        )
        self.assertGreaterEqual(result["device_relevance_score"], 16)
        self.assertIn("procurement_contract_award", result["business_categories"])

    def test_03_factory_expansion_is_high_value(self) -> None:
        result = score_article(
            article(
                "New medical device manufacturing facility",
                "A local manufacturing production line will deliver capacity expansion in Malaysia. " * 3,
            ),
            self.definitions,
        )
        self.assertGreaterEqual(result["device_relevance_score"], 16)
        self.assertIn("manufacturing_capacity", result["business_categories"])

    def test_04_financing_and_acquisition_classification(self) -> None:
        result = score_article(
            article(
                "Medical device acquisition",
                "A medical device company announced financing and an acquisition in Singapore. " * 3,
            ),
            self.definitions,
        )
        self.assertIn("corporate_transaction", result["business_categories"])

    def test_05_specific_packaging_scores_high(self) -> None:
        result = score_article(
            article(
                "ISO 11607 sterile barrier system",
                "The medical device uses Tyvek, forming film and a thermoformed tray under ISO 11607. " * 3,
            ),
            self.definitions,
        )
        self.assertEqual(result["packaging_relevance_score"], 10)
        self.assertTrue(result["include_in_llm_analysis"])

    def test_06_sterilization_packaging_scores_medium_high(self) -> None:
        result = score_article(
            article(
                "Sterile medical device packaging",
                "EO sterilization compatibility was validated for sterile packaging in a cleanroom. " * 3,
            ),
            self.definitions,
        )
        self.assertGreaterEqual(result["packaging_relevance_score"], 4)

    def test_07_general_device_sales_has_low_packaging_score(self) -> None:
        result = score_article(
            article(
                "Medical equipment sales update",
                "The company reported general medical equipment sales through a distributor. " * 3,
            ),
            self.definitions,
        )
        self.assertLessEqual(result["packaging_relevance_score"], 2)

    def test_08_training_registration_is_penalized(self) -> None:
        result = score_article(
            article(
                "Training on medical device sterilisation",
                "Registration open until Friday. Register here for training on medical device sterilisation. " * 3,
            ),
            self.definitions,
        )
        self.assertFalse(result["include_in_llm_analysis"])
        self.assertEqual(result["priority_level"], "excluded")
        self.assertIn("lowered: training or event", result["filter_reason"])

    def test_09_recruitment_is_penalized(self) -> None:
        result = score_article(
            article(
                "Medical device job vacancy",
                "Jawatan kosong and recruitment for the medical device authority. " * 4,
            ),
            self.definitions,
        )
        self.assertEqual(result["priority_level"], "excluded")

    def test_10_failed_scrape_is_excluded(self) -> None:
        result = score_article(
            article(
                "Medical device approval",
                "",
                scrape_status="failed",
                error_message="empty PDF",
            ),
            self.definitions,
        )
        self.assertEqual(result["device_relevance_score"], 0)
        self.assertFalse(result["include_in_llm_analysis"])
        self.assertEqual(result["priority_level"], "excluded")

    def test_11_tracking_url_is_exact_duplicate(self) -> None:
        left = article(
            "Device notice",
            "Medical device registration information. " * 3,
            url="https://example.test/notices/42?utm_source=email",
        )
        right = article(
            "Device notice",
            "Different body but the same canonical URL. " * 3,
            url="https://example.test/notices/42/",
        )
        self.assertEqual(normalized_url(left["url"]), normalized_url(right["url"]))
        self.assertEqual(duplicate_reason(left, right), "exact_url")

    def test_12_similar_title_duplicate_keeps_more_complete_official_record(self) -> None:
        short = score_article(
            article(
                "Official medical device registration update",
                "Medical device registration changed. " * 3,
                article_id="short",
                url="https://example.test/a",
            ),
            self.definitions,
        )
        long = score_article(
            article(
                "Official Medical Device Registration Update!",
                "Medical device registration changed with complete requirements and implementation details. " * 8,
                article_id="long",
                url="https://example.test/b",
            ),
            self.definitions,
        )
        kept, review = deduplicate([short, long])
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0]["article_id"], "long")
        loser = next(item for item in review if item["article_id"] == "short")
        self.assertEqual(loser["priority_level"], "duplicate")
        self.assertEqual(loser["duplicate_of"], "long")

    def test_13_official_source_wins_before_body_length(self) -> None:
        official = article(
            "Same notice",
            "Official body. " * 8,
            source_type="regulator",
        )
        unofficial = article(
            "Same notice repost",
            "Long unofficial repost. " * 50,
            source_type="media",
        )
        self.assertIs(preferred_record(official, unofficial), official)

    def test_14_packaging_score_function_caps_at_ten(self) -> None:
        score = calculate_packaging_score(
            ["Tyvek", "forming film", "ISO 11607", "sterile packaging", "cleanroom packaging"],
            "",
        )
        self.assertEqual(score, 10)

    def test_15_any_non_negative_keyword_match_enters_llm(self) -> None:
        result = score_article(
            article(
                "Distributor update",
                "A medical equipment distributor announced ordinary channel activity in Singapore. " * 3,
            ),
            self.definitions,
        )
        self.assertTrue(result["matched_keywords"])
        self.assertTrue(result["include_in_llm_analysis"])
        self.assertIn(result["priority_level"], {"high", "matched"})


if __name__ == "__main__":
    unittest.main()
