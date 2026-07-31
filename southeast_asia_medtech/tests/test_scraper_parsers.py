from __future__ import annotations

import unittest
import logging
from datetime import date

from southeast_asia_medtech.scrapers.parsers import (
    find_mda_document_url,
    parse_hsa_detail,
    parse_hsa_embedded_list,
    parse_hsa_list,
    parse_mda_detail,
    parse_mda_list,
    parse_mda_safety_rows,
    parse_thai_fda_detail,
)
from southeast_asia_medtech.scrapers.run_phase1_sources import (
    asean_amdc_candidates,
    asean_amdc_fields,
)
from southeast_asia_medtech.scrapers.run_scraper import (
    merge_by_url,
    reclassify_short_existing_records,
    scrape_one_source,
)


HSA_SOURCE = {
    "base_url": "https://www.hsa.gov.sg",
}
MDA_SOURCE = {
    "base_url": "https://www.mda.gov.my",
}


class ParserTest(unittest.TestCase):
    def test_hsa_embedded_payload_filters_medical_devices(self):
        source = {"base_url": "https://www.hsa.gov.sg"}
        html = (
            r'\"id\":\"/announcements/device-one\",'
            r'\"date\":\"$D2026-07-01T00:00:00.000Z\",'
            r'\"title\":\"Medical device update\",'
            r'\"tags\":[{\"category\":\"Product type\",\"selected\":[\"Medical devices\"]}],'
            r'\"formattedDate\":\"1 July 2026\"}'
            r'\"id\":\"/announcements/drug-one\",'
            r'\"date\":\"$D2026-07-02T00:00:00.000Z\",'
            r'\"title\":\"Drug update\",'
            r'\"tags\":[{\"category\":\"Product type\",\"selected\":[\"Therapeutic Products\"]}],'
            r'\"formattedDate\":\"2 July 2026\"}'
        )
        records = parse_hsa_embedded_list(html, source)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].title, "Medical device update")
        self.assertEqual(records[0].published_date, "1 July 2026")
    def test_asean_amdc_list_and_detail_fields(self):
        source = {
            "base_url": "https://atr.asean.org",
        }
        html = """
        <a href="/standards/detail/149/iso-11607">Packaging for terminally
        sterilized medical devices / ISO 11607-2:2006</a>
        <a href="/standards/detail/149/iso-11607/?src=q">[More Details+]</a>
        """
        candidates = asean_amdc_candidates(
            html, "https://atr.asean.org/standards/result/q", source
        )
        self.assertEqual(len(candidates), 1)
        self.assertEqual(
            candidates[0]["url"],
            "https://atr.asean.org/standards/detail/149/iso-11607",
        )

        fields = asean_amdc_fields(
            "Document number assigned by ASEAN ISO 11607-2:2006 ICS 11.080 "
            "ASEAN Body responsible for Standard ASEAN Medical Device Committee (AMDC) "
            "Member States ID TH Date of harmonisation in ASEAN 16/10/2025 "
            "Date of Latest Review 20/10/2025 Links"
        )
        self.assertEqual(fields["standard_number"], "ISO 11607-2:2006")
        self.assertEqual(fields["member_states"], ["ID", "TH"])
        self.assertEqual(fields["harmonisation_date"], "16/10/2025")
    def test_hsa_list_and_detail(self) -> None:
        listing = """
        <a href="/announcements/device-update/">
          <p>17 July 2026</p>
          <h3><span title="Medical device update">Medical device update</span></h3>
          <div>Product type <b>Medical devices</b></div>
        </a>
        """
        stubs = parse_hsa_list(listing, HSA_SOURCE)
        self.assertEqual(len(stubs), 1)
        self.assertEqual(stubs[0].published_date, "17 July 2026")
        self.assertEqual(stubs[0].url, "https://www.hsa.gov.sg/announcements/device-update/")

        title, body = parse_hsa_detail(
            """
            <main><div class="max-w-[47.8rem]">
              <h1>Medical device update</h1><p>Substantive regulatory body.</p>
            </div></main>
            """,
            stubs[0].title,
        )
        self.assertEqual(title, "Medical device update")
        self.assertEqual(body, "Substantive regulatory body.")

    def test_mda_list_and_detail(self) -> None:
        listing = """
        <table><tr><th class="list-title">
          <a href="/index.php/announcement/42-device">Device notice</a>
        </th><td class="list-date small">20 July 2026</td></tr></table>
        """
        stubs = parse_mda_list(listing, MDA_SOURCE)
        self.assertEqual(len(stubs), 1)
        self.assertEqual(stubs[0].published_date, "20 July 2026")
        self.assertEqual(
            stubs[0].url,
            "https://www.mda.gov.my/index.php/announcement/42-device",
        )

        title, body = parse_mda_detail(
            """
            <div class="article-details">
              <h1>Device notice</h1><p>Registration requirements changed.</p>
            </div>
            """,
            stubs[0].title,
        )
        self.assertEqual(title, "Device notice")
        self.assertEqual(body, "Registration requirements changed.")

    def test_mda_safety_table_yields_individual_records(self) -> None:
        html = """
        <div class="article-details">
          <h1>MEDICAL DEVICE FIELD CORRECTIVE ACTION LISTING MARCH 2026</h1>
          <table>
            <tr><th>No.</th><th>Date Received</th><th>Title of FCA</th>
              <th>Affected Medical Device</th><th>MDA Reference Number</th>
              <th>MDA Registration Number</th><th>Local Establishment Contact Detail</th></tr>
            <tr><td>1</td><td>02/03/2026</td><td>Corrective action notice</td>
              <td>DEVICE A</td><td>MDA/FCA/1</td><td>GC123</td><td>COMPANY A</td></tr>
          </table>
        </div>
        """
        rows = parse_mda_safety_rows(
            html,
            {"base_url": "https://portal.mda.gov.my"},
            "https://portal.mda.gov.my/index.php/alert/example",
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["published_date"], "02 March 2026")
        self.assertEqual(rows[0]["affected_devices"], "DEVICE A")
        self.assertIn("#MDA/FCA/1", rows[0]["url"])

    def test_thai_fda_custom_detail_layout(self) -> None:
        title, body, published = parse_thai_fda_detail(
            """
            <div class="single single-news">
              <div class="single__title">Medical Device Registration Update</div>
              <div>5 March 2026</div>
              <div class="single__content ql-editor">
                <p>Thai FDA revised application forms for medical device
                manufacturers and importers to improve regulatory efficiency.</p>
              </div>
            </div>
            """,
            "fallback",
        )
        self.assertEqual(title, "Medical Device Registration Update")
        self.assertEqual(published, "5 March 2026")
        self.assertIn("revised application forms", body)

    def test_short_existing_body_is_not_reported_as_success(self) -> None:
        records = [
            {
                "body": "Heading only",
                "scrape_status": "success",
                "error_message": "",
            }
        ]
        self.assertEqual(reclassify_short_existing_records(records), 1)
        self.assertEqual(records[0]["scrape_status"], "failed")

    def test_mda_document_link_is_promoted_to_file_url(self) -> None:
        html = """
        <div class="article-details">
          <a href="/index.php/documents/ukk/42-device-notice">Download</a>
        </div>
        """
        self.assertEqual(
            find_mda_document_url(html, "https://www.mda.gov.my"),
            "https://www.mda.gov.my/index.php/documents/ukk/42-device-notice/file",
        )

    def test_failed_url_update_replaces_instead_of_duplicates(self) -> None:
        existing = [{"url": "https://example.test/a", "scrape_status": "failed"}]
        update = [{"url": "https://example.test/a", "scrape_status": "success"}]
        merged = merge_by_url(existing, update)
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["scrape_status"], "success")

    def test_source_list_failure_is_returned_without_raising(self) -> None:
        class FailingClient:
            def get_text(self, _url: str) -> tuple[str, int, str]:
                raise RuntimeError("synthetic list failure")

        source = {
            "source_id": "sg_hsa_announcements",
            "source_name": "Singapore HSA Announcements",
            "country": "SG",
            "organization": "Health Sciences Authority",
            "source_type": "regulator",
            "language": "en",
            "base_url": "https://www.hsa.gov.sg",
            "list_url": "https://www.hsa.gov.sg/announcements/",
        }
        raw, normalized, summary = scrape_one_source(
            source,
            FailingClient(),  # type: ignore[arg-type]
            logging.getLogger("test_source_failure"),
            date(2026, 7, 1),
            date(2026, 7, 31),
            set(),
            5,
        )
        self.assertEqual(raw, [])
        self.assertEqual(normalized, [])
        self.assertIn("synthetic list failure", summary["source_error"])


if __name__ == "__main__":
    unittest.main()
