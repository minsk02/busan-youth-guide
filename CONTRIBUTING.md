# 공동 작업 방법

## 기본 규칙

main에는 검토한 결과를 반영한다. 작업은 브랜치에서 하고 PR로 확인한다. 브랜치는 사람 이름보다 작업 내용으로 만든다.

- 한 PR은 한 가지 작업을 중심으로 정리한다.
- 문서·코드는 실제 수정한 사람이 자기 계정으로 커밋한다.
- 키, DB 파일, 수집 원본, 가상환경은 올리지 않는다.
- DOCX는 취합 담당자가 정리하고, 공동 초안은 Markdown으로 관리한다.
- 공유 브랜치에 force push를 하지 않는다.

## 일반적인 작업 순서

```powershell
git switch main
git pull --ff-only origin main
git switch -c docs/requirements-review
# 파일 수정 후
git add docs/requirements.md
git diff --cached
git commit -m "docs: 검색 조건과 예외 흐름 보완"
git push -u origin docs/requirements-review
```

저장소에서 main을 기준으로 PR을 만들고 변경 이유·확인한 내용·남은 문제를 적는다. 다른 팀원이 검토하고 병합한다.

현재 백엔드·화면 분리 전달은 [파일 전달 안내](docs/handoff.md)를 따른다. 화면 파일을 받는 사람은 직접 실행해보고 검토·수정한 내용을 PR에 기록한다.

## 충돌이 나면

같은 파일을 수정했다면 상대 변경 의도를 확인한다. 본인 작업 브랜치에서 `git fetch origin`, `git merge origin/main`으로 최신 main을 반영하고 충돌을 해결한다. 미완성 파일을 지우거나 강제로 덮어써서 해결하지 않는다.

## 문서와 검증

테스트 계획과 실행 결과를 구분한다. 코드 변경 시 관련 요구사항·컴포넌트·테스트 ID를 확인한다. 구현이 끝났더라도 팀 검토나 사용성 점검을 하지 않았다면 완료로 표시하지 않는다.
