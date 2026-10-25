"""로컬 DB와 실제 LLM을 함께 확인한다. 실행 시 소량의 OpenAI API 비용이 발생한다."""

import json
import calendar
from datetime import timedelta
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend import create_app
from backend.config import now_iso, today


def main():
    app = create_app()
    client = app.test_client()
    current = today()
    first = current.replace(day=1)
    previous = first - timedelta(days=1)
    current_end = current.replace(day=calendar.monthrange(current.year, current.month)[1])
    previous_start = previous.replace(day=1)
    cases = [
        ("이번 달 신청할 수 있는 교육 프로그램 찾아줘", {"category": "교육분야", "apply_from": first.isoformat(), "apply_until": current_end.isoformat(), "only_open": True}),
        ("취업이나 면접 준비에 도움이 되는 프로그램 찾아줘", {"category": "일자리분야", "only_open": True}),
        ("부산진구에서 무료로 들을 수 있는 교육을 찾아줘", {"category": "교육분야", "only_open": True}),
        ("지난달 문화 프로그램을 마감된 것도 포함해서 찾아줘", {"category": "복지·문화분야", "apply_from": previous_start.isoformat(), "apply_until": previous.isoformat(), "only_open": False}),
    ]
    report = {"checked_at_kst": now_iso(), "model": app.config["OPENAI_MODEL"], "cases": [], "checks": {}}
    for query, expected in cases:
        started = time.monotonic()
        response = client.post("/api/interpret", json={"query": query})
        result = response.json
        passed = response.status_code == 200 and all(result["criteria"].get(key) == value for key, value in expected.items())
        if "무료" in query:
            passed = passed and bool(result.get("unsupported_conditions"))
        report["cases"].append({"query": query, "expected": expected, "response": result, "passed": passed, "elapsed_seconds": round(time.monotonic() - started, 2)})
    status = client.get("/api/status").json
    report["data_status"] = status
    search = client.post("/api/search", json={"criteria": {}})
    items = search.json.get("items", [])
    report["checks"]["search"] = search.status_code == 200 and bool(items)
    recommendation = client.post("/api/search", json={"criteria": {"category": "교육분야"}, "mode": "recommend"})
    report["checks"]["recommendation"] = recommendation.status_code == 200 and bool(recommendation.json.get("items")) and all(item["reasons"] for item in recommendation.json["items"])
    if len(items) >= 2:
        comparison = client.post("/api/compare", json={"ids": [item["id"] for item in items[:2]]})
        report["checks"]["comparison"] = comparison.status_code == 200 and len(comparison.json["items"]) == 2
        report["checks"]["detail"] = client.get(f"/api/programs/{items[0]['id']}").status_code == 200
    report["checks"]["zero_results"] = client.post("/api/search", json={"criteria": {"keywords": ["없는프로그램테스트문자열"]}}).json["total"] == 0
    report["passed"] = all(case["passed"] for case in report["cases"]) and all(report["checks"].values())
    target = ROOT / "data/reports/service-smoke-test.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"passed": report["passed"], "ai_cases": [case["passed"] for case in report["cases"]], "checks": report["checks"], "total": status["total"], "open_count": status["open_count"]}, ensure_ascii=True, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
