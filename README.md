# 부산청년 프로그램 찾기

소프트웨어공학 1분반 10팀 프로젝트입니다. 부산 청년 대상 프로그램을 자연어로 찾고, 관심 조건으로 추천받고, 2~3개 항목을 비교하는 웹 서비스입니다.

## 주요 기능

- 자연어 검색: 질문을 LLM으로 해석하고, 사용자가 확인한 조건으로 실제 데이터를 찾습니다.
- 맞춤 추천: 분야·키워드·대상 원문의 일치 정도를 점수로 계산하고 이유를 보여줍니다.
- 프로그램 비교: 선택한 항목의 대상, 신청기간, 운영기간, 기관을 나란히 봅니다.

프로그램 정보는 공공데이터에서 가져옵니다. LLM이 프로그램명이나 신청 링크를 만들어내지는 않습니다. 추천 이유도 서버에서 계산한 값으로 작성합니다. 로그인·실제 신청 대행·지도·이미지 분석은 이번 범위에서 제외했습니다.

## 실행

Python 3.12 기준입니다. PowerShell에서 프로젝트 폴더를 열고 실행합니다.

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

이미 `.env`가 있으면 복사하지 말고 필요한 설정만 추가합니다.

```dotenv
DATA_GO_KR_SERVICE_KEY=발급받은_키
OPENAI_API_KEY=발급받은_키
OPENAI_MODEL=gpt-4o-mini
```

```powershell
.venv/Scripts/python.exe manage.py sync
.venv/Scripts/python.exe app.py
```

브라우저에서 **http://127.0.0.1:8765**를 엽니다. 별도 MySQL 설치나 프론트 빌드는 필요하지 않습니다. `data/app.db`는 수집 시 생성됩니다. 위 서버는 로컬 개발·발표 시연용입니다.

현재 백엔드 전달 브랜치에는 `frontend/`가 제외되어 있습니다. 로컬 완성본에는 화면이 있으며, 친구가 전달받은 화면 파일을 검토해 별도 PR로 반영한 뒤 저장소 전체 실행이 가능합니다. 화면 파일이 없더라도 JSON API는 실행할 수 있습니다.

## 사용 순서

1. 질문을 입력하고 '조건 읽기'를 누릅니다.
2. 해석된 분야·기간·키워드를 확인하고 수정할 수 있습니다.
3. '이 조건으로 검색'을 누릅니다.
4. '맞춤 추천'에서 일치 근거를 확인합니다.
5. 관심 항목을 2~3개 담고 '비교하기'를 누릅니다.

무료·지역·거리 조건은 전용 데이터가 없어 지원하지 않습니다. 질문에 들어오면 적용하지 못한 조건으로 안내합니다. 대상 키워드는 원문 문자열 검색이며 참가 자격 판정이 아닙니다.

## 데이터와 주의할 점

[부산광역시 청년지원프로그램 정보 API](https://www.data.go.kr/data/15163604/openapi.do)를 사용합니다. 2026-10-26 수집본은 원본 1,000건, 완전 중복 제거 후 997건입니다. 이 중 96건은 수집된 상태와 날짜가 현재 신청기간에 해당합니다. 실제 접수 여부는 홈페이지 확인이 필요합니다.

원천 모집 상태 필터가 검증 요청에서 적용되지 않아 서버에서 다시 판정합니다. 홈페이지 URL에도 누락·부적합 값이 있습니다. 등록일, 실제 수집 시점, 접수 마감 시각을 구분해서 안내합니다. 자세한 내용은 [데이터 검증 기록](docs/data-api-review.md)에 있습니다.

키·DB·수집 원본은 Git에 올리지 않습니다. 원문 질문은 DB에 저장하지 않으며 AI 요청 시 OpenAI에 전달됩니다. Responses API의 `store=False`를 사용하며, 제공자의 보관 정책은 별도로 적용됩니다.

## 확인

```powershell
.venv/Scripts/python.exe -m unittest discover -s tests -v
.venv/Scripts/python.exe scripts/smoke_test.py
```

첫 명령은 가상 자료와 대체 응답을 사용하는 오프라인 테스트입니다. 두 번째는 실제 DB·OpenAI API를 사용하므로 키 설정과 소량의 API 비용이 필요합니다. 결과는 [시스템 점검 기록](docs/test-results.md)에 정리했습니다.

## 구조

```text
backend/       설정, SQLite, 데이터 수집, 검색·추천·비교, LLM, HTTP API
frontend/      HTML, CSS, JavaScript (별도 전달)
scripts/       데이터 검증과 실제 연동 점검
tests/         오프라인 테스트
docs/          계획서, SRS, SDD, 협업·발표 자료
data/          로컬 DB·원본, 공유용 집계 보고서
```

## 문서

- [프로젝트 계획서](docs/project-plan.md)
- [요구사항명세서](docs/requirements.md)
- [유스케이스](docs/use-cases.md)
- [설계서 1~3장](docs/architecture.md)
- [API와 데이터 구조](docs/api.md)
- [테스트 계획](docs/test-plan.md) · [실행 결과](docs/test-results.md)
- [팀 작업 안내](docs/team-tasks.md) · [친구 파일 전달 방법](docs/handoff.md)
- [Git 작업 규칙](CONTRIBUTING.md)

제출용 DOCX는 교수님 양식에 맞춰 작성하며 팀원 실명·학번·최종 검토 정보는 팀에서 확인해야 합니다. 중간 제출 파일명은 `SoftwareEngineering_Midterm_Class1_Team10.zip`입니다.
