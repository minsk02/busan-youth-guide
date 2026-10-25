"""외부 호출 없이 서비스 동작을 확인한다. 여기의 프로그램은 테스트용 가상 자료다."""

from datetime import date
import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from openai import APIConnectionError
import httpx

from backend import create_app
from backend.ai import interpret_query, check_supported_conditions
from backend.data_source import normalize, safe_homepage, sync_programs
from backend.database import init_database, list_programs, start_sync, save_snapshot, latest_sync
from backend.errors import ServiceError
from backend.programs import validate_criteria, recruitment


def raw_program(title="테스트 면접 교육", **changes):
    record = {
        "bizNm": title, "busPlcNm": "교육분야", "trgtNm": "부산 청년, 대학생 가능",
        "aplyBgngYmd": "20261001", "aplyEndYmd": "20261031",
        "schdlBgngYmd": "20261101", "schdlEndYmd": "20261130",
        "paReStat": "모집중", "mngtMson": "테스트 기관",
        "inqryTlphnNo": None, "hopgUrlAddr": "https://example.org/program",
        "frstRegistPnttm": "2026-10-01",
    }
    record.update(changes)
    return record


def ai_result(**changes):
    value = {"category": "교육분야", "keywords": [], "target_keyword": None, "apply_from": None, "apply_until": None, "only_open": True, "unsupported_conditions": []}
    value.update(changes)
    return SimpleNamespace(status="completed", output_text=json.dumps(value), usage=SimpleNamespace(input_tokens=100, output_tokens=40))


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.path = str(Path(self.folder.name) / "test.db")
        self.app = create_app({"TESTING": True, "DATABASE": self.path, "TODAY": "2026-10-26", "OPENAI_API_KEY": "", "AI_RATE_LIMIT": 0})
        self.client = self.app.test_client()
        self.records = [
            raw_program(),
            raw_program("테스트 문화 행사", busPlcNm="복지·문화분야", hopgUrlAddr="javascript:alert(1)"),
            raw_program("테스트 마감 교육", aplyEndYmd="20261020", paReStat="모집마감"),
            raw_program("테스트 충돌 교육", paReStat="모집마감"),
        ]
        self.seed(self.records)

    def tearDown(self):
        self.folder.cleanup()

    def seed(self, records):
        run_id = start_sync(self.path)
        return save_snapshot(self.path, [normalize(item, "2026-10-26T00:00:00+09:00") for item in records], run_id, len(records))

    def test_status_and_no_secrets(self):
        response = self.client.get("/api/status")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["total"], 4)
        self.assertEqual(response.json["open_count"], 2)
        self.assertNotIn("API_KEY", response.text)

    def test_search_checks_local_dates_and_source_status(self):
        result = self.client.post("/api/search", json={"criteria": {}}).json
        self.assertEqual(result["total"], 2)
        self.assertTrue(all(item["status"] == "open" for item in result["items"]))

    def test_category_keyword_target_and_date_filters(self):
        criteria = {"category": "교육분야", "keywords": ["면접"], "target_keyword": "대학생", "apply_from": "2026-10-26", "apply_until": "2026-10-27"}
        result = self.client.post("/api/search", json={"criteria": criteria})
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json["total"], 1)
        self.assertEqual(result.json["items"][0]["title"], "테스트 면접 교육")

    def test_keywords_use_or_and_input_is_not_sql(self):
        result = self.client.post("/api/search", json={"criteria": {"keywords": ["면접", "문화"]}})
        self.assertEqual(result.json["total"], 2)
        result = self.client.post("/api/search", json={"criteria": {"keywords": ["' OR 1=1 --"]}})
        self.assertEqual(result.json["total"], 0)
        self.assertEqual(self.client.get("/api/status").json["total"], 4)

    def test_no_results_does_not_change_conditions(self):
        result = self.client.post("/api/search", json={"criteria": {"keywords": ["없는키워드"]}}).json
        self.assertEqual(result["total"], 0)
        self.assertEqual(result["criteria"]["keywords"], ["없는키워드"])

    def test_recommendation_gives_only_calculated_reasons(self):
        result = self.client.post("/api/search", json={"criteria": {"keywords": ["면접", "문화"]}, "mode": "recommend"}).json
        self.assertEqual(result["total"], 2)
        for item in result["items"]:
            self.assertTrue(item["reasons"])
            self.assertGreater(item["score"], 0)
            self.assertNotIn("확실히 참여", " ".join(item["reasons"]))

    def test_recommendation_orders_open_items_before_higher_scoring_closed_item(self):
        self.seed([
            raw_program("제목 면접"),
            raw_program("일반 안내", trgtNm="면접 준비 청년"),
            raw_program("마감 면접", aplyEndYmd="20261020", paReStat="모집마감"),
        ])
        result = self.client.post("/api/search", json={"criteria": {"keywords": ["면접"], "only_open": False}, "mode": "recommend"}).json
        self.assertEqual([item["title"] for item in result["items"]], ["제목 면접", "일반 안내", "마감 면접"])
        self.assertGreater(result["items"][0]["score"], result["items"][1]["score"])

    def test_pagination_has_no_repeated_items(self):
        self.seed([raw_program(f"페이지 확인 {number}") for number in range(15)])
        first = self.client.post("/api/search", json={"criteria": {}, "page": 1}).json
        second = self.client.post("/api/search", json={"criteria": {}, "page": 2}).json
        self.assertEqual((len(first["items"]), len(second["items"])), (12, 3))
        self.assertFalse({item["id"] for item in first["items"]} & {item["id"] for item in second["items"]})

    def test_comparison_and_invalid_counts(self):
        ids = [item["id"] for item in self.client.post("/api/search", json={"criteria": {}}).json["items"]]
        result = self.client.post("/api/compare", json={"ids": ids})
        self.assertEqual([item["id"] for item in result.json["items"]], ids)
        for bad in ([ids[0]], [ids[0], ids[0]], [True, ids[1]], "1,2", [1, 2, 3, 4]):
            with self.subTest(bad=bad):
                self.assertEqual(self.client.post("/api/compare", json={"ids": bad}).status_code, 400)

    def test_missing_program_and_stale_ids(self):
        self.assertEqual(self.client.get("/api/programs/999999").status_code, 404)
        ids = [item["id"] for item in list_programs(self.path)]
        self.seed([raw_program("새 수집본")])
        self.assertEqual(self.client.get(f"/api/programs/{ids[0]}").status_code, 404)

    def test_detail_has_source_and_no_bad_link_or_raw_json(self):
        item = next(item for item in list_programs(self.path) if item["category"] == "복지·문화분야")
        result = self.client.get(f"/api/programs/{item['id']}").json
        self.assertIsNone(result["homepage_url"])
        self.assertIsNone(result["contact_phone"])
        self.assertTrue(result["source_url"].startswith("https://www.data.go.kr/"))
        self.assertNotIn("raw_json", result)
        self.assertNotIn("content_hash", result)

    def test_invalid_json_dates_and_types(self):
        for bad in ({"only_open": "true"}, {"apply_from": "2026-02-30"}, {"apply_from": "2026-11-01", "apply_until": "2026-10-01"}, {"keywords": [1]}, {"category": "알수없음"}):
            with self.subTest(bad=bad):
                self.assertEqual(self.client.post("/api/search", json={"criteria": bad}).status_code, 400)
        self.assertEqual(self.client.post("/api/search", json=[]).status_code, 400)
        self.assertEqual(self.client.post("/api/search", json={"page": True}).status_code, 400)

    def test_external_origin_and_large_input(self):
        response = self.client.post("/api/interpret", json={"query": "교육"}, headers={"Origin": "https://other.example"})
        self.assertEqual(response.status_code, 403)
        response = self.client.post("/api/search", data="x" * 20000, content_type="application/json")
        self.assertEqual(response.status_code, 413)

    def test_ai_not_configured_and_provider_failure(self):
        self.assertEqual(self.client.post("/api/interpret", json={"query": "교육"}).status_code, 503)
        with patch("backend.interpret_query", side_effect=ServiceError("AI 연결 실패", 503, "ai_unavailable")):
            self.assertEqual(self.client.post("/api/interpret", json={"query": "교육"}).json["error"]["code"], "ai_unavailable")

    def test_rate_limit(self):
        self.app.config["AI_RATE_LIMIT"] = 1
        with patch("backend.interpret_query", return_value={"criteria": {}, "ai_used": True}):
            self.assertEqual(self.client.post("/api/interpret", json={"query": "교육"}).status_code, 200)
            self.assertEqual(self.client.post("/api/interpret", json={"query": "교육"}).status_code, 429)

    def test_empty_database_is_distinct_from_zero_results(self):
        empty_path = str(Path(self.folder.name) / "empty.db")
        client = create_app({"TESTING": True, "DATABASE": empty_path}).test_client()
        result = client.post("/api/search", json={"criteria": {}})
        self.assertEqual(result.status_code, 503)
        self.assertEqual(result.json["error"]["code"], "data_empty")

    def test_sync_deduplicates_and_preserves_same_ids(self):
        before = {item["content_hash"]: item["id"] for item in list_programs(self.path)}
        self.seed(self.records + [self.records[0]])
        self.assertEqual(len(list_programs(self.path)), 4)
        self.assertEqual(latest_sync(self.path)["duplicate_count"], 1)
        self.assertEqual(before, {item["content_hash"]: item["id"] for item in list_programs(self.path)})

    def test_failed_sync_keeps_previous_snapshot_and_hides_exception(self):
        def bad_fetch(page, rows):
            raise RuntimeError("serviceKey=SHOULD_NOT_LEAK")
        with self.assertRaises(ServiceError) as caught:
            sync_programs(self.path, "fake-key", bad_fetch)
        self.assertNotIn("SHOULD_NOT_LEAK", caught.exception.message)
        self.assertEqual(len(list_programs(self.path)), 4)
        self.assertEqual(latest_sync(self.path)["status"], "failed")

    def test_failed_database_write_rolls_back_active_snapshot(self):
        before = [item["id"] for item in list_programs(self.path)]
        record = normalize(raw_program("잘못된 저장"), "now")
        record["title"] = None
        run_id = start_sync(self.path)
        with self.assertRaises(sqlite3.IntegrityError):
            save_snapshot(self.path, [record], run_id, 1)
        self.assertEqual(before, [item["id"] for item in list_programs(self.path)])

    def test_incomplete_sync_keeps_previous_snapshot(self):
        def empty_fetch(page, rows):
            return b"", {"page_no": page, "total_count": 20, "num_rows": rows, "items": []}
        with self.assertRaises(ServiceError):
            sync_programs(self.path, "fake-key", empty_fetch)
        self.assertEqual(len(list_programs(self.path)), 4)

    def test_security_headers(self):
        response = self.client.get("/api/status")
        self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(response.headers["Cache-Control"], "no-store")


class DomainAndAITests(unittest.TestCase):
    def test_unsupported_conditions_cannot_turn_into_matching_keywords(self):
        result = {"keywords": ["무료", "부산진구", "면접"], "target_keyword": None, "unsupported_conditions": []}
        checked = check_supported_conditions("부산진구 무료 면접 교육", result)
        self.assertEqual(checked["keywords"], ["면접"])
        self.assertIn("비용 조건", checked["unsupported_conditions"])
        self.assertIn("장소·거리 조건", checked["unsupported_conditions"])

    def test_deadline_boundary_missing_and_conflicting_status(self):
        program = normalize(raw_program(aplyEndYmd="20261026"), "now")
        self.assertEqual(recruitment(program, date(2026, 10, 26))[0], "open")
        self.assertEqual(recruitment(program, date(2026, 10, 27))[0], "check")
        program["application_start"] = None
        self.assertEqual(recruitment(program, date(2026, 10, 26))[0], "unknown")

    def test_url_schemes_and_credentials(self):
        for value in ("javascript:alert(1)", "https://user:pass@example.org", "https://example.org/has space", None):
            self.assertIsNone(safe_homepage(value))
        self.assertEqual(safe_homepage("https://example.org/x"), "https://example.org/x")

    def test_structured_ai_output_and_storage_setting(self):
        client = SimpleNamespace(responses=SimpleNamespace(create=lambda **kwargs: ai_result()))
        result = interpret_query("교육 프로그램", "fake", "gpt-4o-mini", date(2026, 10, 26), client)
        self.assertEqual(result["criteria"]["category"], "교육분야")
        self.assertTrue(result["ai_used"])
        with patch.object(client.responses, "create", return_value=ai_result()) as call:
            interpret_query("교육", "fake", "gpt-4o-mini", date(2026, 10, 26), client)
            self.assertFalse(call.call_args.kwargs["store"])
            self.assertTrue(call.call_args.kwargs["text"]["format"]["strict"])

    def test_invalid_ai_response_and_refusal_are_not_success(self):
        for response in (SimpleNamespace(status="completed", output_text="not json"), SimpleNamespace(status="incomplete", output_text="")):
            client = SimpleNamespace(responses=SimpleNamespace(create=lambda **kwargs: response))
            with self.assertRaises(ServiceError):
                interpret_query("교육", "fake", "gpt-4o-mini", date(2026, 10, 26), client)

    def test_invalid_model_value_is_provider_error(self):
        client = SimpleNamespace(responses=SimpleNamespace(create=lambda **kwargs: ai_result(category="없는분야")))
        with self.assertRaises(ServiceError) as caught:
            interpret_query("교육", "fake", "gpt-4o-mini", date(2026, 10, 26), client)
        self.assertEqual(caught.exception.status, 502)

    def test_ai_network_error_is_safe(self):
        client = SimpleNamespace(responses=SimpleNamespace(create=None))
        error = APIConnectionError(message="private credential", request=httpx.Request("POST", "https://example.org"))
        with patch.object(client.responses, "create", side_effect=error):
            with self.assertRaises(ServiceError) as caught:
                interpret_query("교육", "fake", "gpt-4o-mini", date(2026, 10, 26), client)
            self.assertNotIn("private credential", caught.exception.message)


if __name__ == "__main__":
    unittest.main()
