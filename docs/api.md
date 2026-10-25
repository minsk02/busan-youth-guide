# API와 데이터 구조

2026-10-26 · 서버 주소 http://127.0.0.1:8765

## HTTP API

| 메서드·경로 | 요청 | 응답 |
|---|---|---|
| GET /api/status | 없음 | 저장 건수, 현재 신청기간 건수, 수집 시점, 분야 |
| POST /api/interpret | query 문자열 1~600자 | 해석 조건, 적용 불가 조건, AI 사용 여부 |
| POST /api/search | criteria, mode, page | 프로그램 목록, 총 건수, 페이지, 적용 조건 |
| GET /api/programs/{id} | 내부 ID | 상세 정보·출처·수집 시점 |
| POST /api/compare | 서로 다른 정수 ID 2~3개 | 동일 항목의 상세 데이터 |

수집 명령은 HTTP로 공개하지 않고 `manage.py sync`로 실행한다. JSON 오류는 `error.code`와 `error.message`로 반환한다. 잘못된 요청 400, 없는 항목 404, AI 요청 제한 429, 외부 실패 502/503을 사용한다. 실제 키나 외부 예외 원문은 전달하지 않는다.

## 검색 조건

```json
{
  "criteria": {
    "category": "교육분야",
    "keywords": ["면접", "취업"],
    "target_keyword": null,
    "apply_from": null,
    "apply_until": null,
    "only_open": true
  },
  "mode": "recommend",
  "page": 1
}
```

- category는 5개 원천 분야 중 하나 또는 null이다.
- keywords는 최대 5개이며 하나라도 제목·대상·기관에 포함되면 검색된다.
- target_keyword는 대상 원문의 부분 문자열 검색이다. 자격 판정은 아니다.
- 기간은 신청기간이 검색 기간과 하루라도 겹치는지 검사한다.
- only_open은 날짜와 원천 모집 상태가 모두 현재 신청기간에 해당하는 항목만 찾는다.
- mode는 search 또는 recommend다. 페이지 크기는 12개이다.

## 추천 규칙

현재 신청기간인 후보가 우선이다. 추천 모드에서는 분야 일치 5점, 제목 키워드별 4점, 대상·기관 키워드별 1점, 대상 키워드 일치 2점, 현재 신청기간 1점을 합산한다. 같은 점수는 신청 마감일, 내부 ID 순이다. 점수는 참가 가능성이나 효과를 예측하는 값이 아니다.

## 테이블

| 테이블 | 주요 항목 | 용도 |
|---|---|---|
| programs | id, content_hash, title, category, target_text, 신청·운영기간, source_status, 기관·문의·URL, raw_json, fetched_at, active, sync_run_id | 프로그램 저장·조회 |
| sync_runs | id, started_at, finished_at, status, source_count, stored_count, duplicate_count, error_message | 수집 실행 기록 |

실제 DDL은 `backend/database.py`의 SCHEMA에 있다. 원본 ID가 없어 내용이 수정된 레코드는 새 ID로 저장한다. 동일한 내용의 재수집은 기존 ID를 유지한다. DB 교체 중 오류가 나면 트랜잭션을 롤백한다.

## LLM 사용

OpenAI Responses API와 Structured Outputs를 사용한다. 질문과 기준일·지원 조건 설명만 전달하며 프로그램 1,000건을 매번 보내지 않는다. 출력은 서버에서 다시 검증하고 화면에 반영한다. 사용자가 확인하기 전 결과 검색을 자동 실행하지 않는다.

OpenAI 호출은 25초 제한, 자동 재시도 없음, 최대 출력 700토큰으로 설정했다. 로컬 시연에서 연속 호출을 줄이기 위해 서버 전체 분당 12회 제한을 둔다. 여러 사용자 환경의 인증·과금·분산 제한은 구현 범위 밖이다.

참고: [Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs), [Flask](https://flask.palletsprojects.com/en/stable/), [SQLite](https://www.sqlite.org/whentouse.html).
