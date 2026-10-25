"""Offline contract and failure-path checks; these do not call the real API."""

import importlib.util
from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from datetime import date
from unittest.mock import patch
from urllib.error import HTTPError, URLError

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "validate_youth_api.py"
SPEC = importlib.util.spec_from_file_location("validate_youth_api", MODULE_PATH)
api = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(api)


def response(items, *, total=1, page=1, rows=100, code="00"):
    return json.dumps({"response": {
        "header": {"resultCode": code, "resultMsg": "not trusted"},
        "body": {"items": items, "totalCount": str(total), "pageNo": str(page), "numOfRows": str(rows)},
    }}).encode()


def parsed(items, *, total, page):
    return api.parse_page(response({"item": items}, total=total, page=page))


class ResponseTests(unittest.TestCase):
    def test_single_item_and_string_pagination(self):
        result = api.parse_page(response({"item": {"bizNm": "example"}}))
        self.assertEqual(result["items"], [{"bizNm": "example"}])
        self.assertEqual(result["total_count"], 1)

    def test_empty_items(self):
        for empty in (None, "", {}, {"item": None}, {"item": []}):
            with self.subTest(empty=empty):
                self.assertEqual(api.parse_page(response(empty, total=0))["items"], [])

    def test_business_failure_and_malformed_json(self):
        for payload in (response({}, code="30"), b'not-json', b'{"response": {}}'):
            with self.subTest(payload=payload):
                with self.assertRaises(api.ValidationError):
                    api.parse_page(payload)

    def test_xml_gateway_error_hides_server_text(self):
        payload = b'<error><returnReasonCode>30</returnReasonCode><message>SECRET</message></error>'
        with self.assertRaises(api.ValidationError) as caught:
            api.parse_page(payload)
        self.assertIn("30", str(caught.exception))
        self.assertNotIn("SECRET", str(caught.exception))

    def test_invalid_item_and_pagination(self):
        for payload in (response({"item": ["bad"]}), response({}, total=-1), response({}, page=0)):
            with self.assertRaises(api.ValidationError):
                api.parse_page(payload)


class PaginationTests(unittest.TestCase):
    def test_multiple_pages_with_final_short_page(self):
        def fetch(page, rows):
            values = [{"id": 1}, {"id": 2}] if page == 1 else [{"id": 3}]
            return b"raw", parsed(values, total=3, page=page)
        items, summary = api.collect_pages(fetch, 2, 3)
        self.assertEqual(len(items), 3)
        self.assertTrue(summary["complete"])
        self.assertEqual(summary["pages_requested"], 2)

    def test_repeated_page_is_not_complete(self):
        def fetch(page, rows):
            return b"raw", parsed([{"id": 1}], total=3, page=page)
        _, summary = api.collect_pages(fetch, 1, 5)
        self.assertFalse(summary["complete"])
        self.assertEqual(summary["stop_reason"], "repeated_page_detected")

    def test_page_cap_and_changing_total_are_incomplete(self):
        def fetch(page, rows):
            return b"raw", parsed([{"id": page}], total=3 if page == 1 else 2, page=page)
        _, capped = api.collect_pages(fetch, 1, 1)
        self.assertFalse(capped["complete"])
        _, changing = api.collect_pages(fetch, 1, 3)
        self.assertFalse(changing["complete"])
        self.assertFalse(changing["reported_totals_consistent"])

    def test_wrong_page_number(self):
        def fetch(page, rows):
            return b"raw", parsed([{"id": 1}], total=2, page=1)
        with self.assertRaises(api.ValidationError):
            api.collect_pages(fetch, 1, 3)

    def test_zero_total_is_complete(self):
        def fetch(page, rows):
            return b"raw", parsed([], total=0, page=page)
        items, summary = api.collect_pages(fetch, 100, 3)
        self.assertEqual(items, [])
        self.assertTrue(summary["complete"])


class QualityAndSecretTests(unittest.TestCase):
    def test_date_and_url_quality(self):
        record = {"paReStat": "모집중", "aplyBgngYmd": "20261001", "aplyEndYmd": "20261025", "hopgUrlAddr": "javascript:alert(1)"}
        report = api.summarize([record, dict(record), {"aplyBgngYmd": "20260230"}], date(2026, 10, 26))
        self.assertEqual(report["source_recruiting_but_end_date_passed"], 2)
        self.assertEqual(report["exact_duplicate_record_count"], 1)
        self.assertEqual(report["invalid_date_count"]["aplyBgngYmd"], 1)
        self.assertEqual(report["homepage_url_syntax"]["invalid"], 2)
        self.assertEqual(report["homepage_url_syntax"]["missing"], 1)

    def test_inclusive_boundary_and_reversed_period(self):
        records = [
            {"aplyBgngYmd": "20261026", "aplyEndYmd": "20261026"},
            {"aplyBgngYmd": "20261027", "aplyEndYmd": "20261025"},
        ]
        periods = api.summarize(records, date(2026, 10, 26))["application_period_vs_as_of"]
        self.assertEqual(periods["within"], 1)
        self.assertEqual(periods["reversed"], 1)

    def test_encoded_and_raw_keys_preserve_literal_plus(self):
        with tempfile.TemporaryDirectory() as folder:
            env = Path(folder) / ".env"
            with patch.dict(os.environ, {"DATA_GO_KR_SERVICE_KEY": ""}):
                for value in ("abc%2Bdef%2Fghi%3D", "abc+def/ghi="):
                    env.write_text(f'export DATA_GO_KR_SERVICE_KEY = "{value}"\n', encoding="utf-8-sig")
                    self.assertEqual(api.load_key(env), "abc+def/ghi=")

    def test_http_and_network_errors_hide_request_url(self):
        key = "test-secret"
        for error in (
            HTTPError("https://example.invalid/?serviceKey=" + key, 403, key, {}, None),
            URLError("failed with " + key),
        ):
            with patch.object(api, "urlopen", side_effect=error):
                with self.assertRaises(api.ValidationError) as caught:
                    api.fetch_page(key, 1, 100)
                self.assertNotIn(key, str(caught.exception))

    def test_filters_cannot_override_credentials_or_endpoint(self):
        with self.assertRaises(api.ValidationError):
            api.fetch_page("test-secret", 1, 100, {"serviceKey": "bad"})

    def test_main_reports_filter_failure_without_exposing_key(self):
        record = {"bizNm": "example", "busPlcNm": "교육분야", "paReStat": "모집마감"}
        def fake_fetch(key, page_no, rows, filters=None):
            return b"local fixture", parsed([record], total=1, page=page_no)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / ".env").write_text("DATA_GO_KR_SERVICE_KEY=test-secret\n", encoding="utf-8")
            output = io.StringIO()
            with patch.object(api, "ROOT", root), patch.object(api, "fetch_page", side_effect=fake_fetch):
                with patch.dict(os.environ, {"DATA_GO_KR_SERVICE_KEY": ""}):
                    with patch.object(api.sys, "argv", ["validate_youth_api.py", "--as-of", "2026-10-26", "--check-filters"]):
                        with redirect_stdout(output):
                            code = api.main()
            self.assertEqual(code, 3)
            report_text = (root / "data/reports/youth-program-validation.json").read_text(encoding="utf-8")
            self.assertNotIn("test-secret", output.getvalue() + report_text)
            report = json.loads(report_text)
            self.assertTrue(report["pagination"]["complete"])
            self.assertFalse(report["filter_checks"][1]["sample_matches_filter"])


if __name__ == "__main__":
    unittest.main()
