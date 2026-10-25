# 공동 작업 방법

## 기본 규칙

main에는 검토한 결과를 반영한다. 작업은 브랜치에서 하고 PR로 확인한다. 브랜치는 사람 이름보다 작업 내용으로 만든다.

- 한 PR은 한 가지 작업을 중심으로 정리한다.
- 문서·코드는 실제 수정한 사람이 자기 계정으로 커밋한다.
- 키, DB 파일, 수집 원본, 가상환경은 올리지 않는다.
- 과제 제출 문서는 로컬에서 취합하고, 코드 변경과 검토 내용은 GitHub에서 관리한다.
- 공유 브랜치에 force push를 하지 않는다.

## 일반적인 작업 순서

```powershell
git switch main
git pull --ff-only origin main
git switch -c fix/search-filter
# 파일 수정 후
git add backend/programs.py
git diff --cached
git commit -m "fix: 검색 조건 처리 보완"
git push -u origin fix/search-filter
```

저장소에서 main을 기준으로 PR을 만들고 변경 이유·확인한 내용·남은 문제를 적는다. 다른 팀원이 검토하고 병합한다.

화면 작업은 frontend 폴더에서 진행한다. 실행·검토 후 변경 내용을 PR에 기록한다.

## 충돌이 나면

같은 파일을 수정했다면 상대 변경 의도를 확인한다. 본인 작업 브랜치에서 `git fetch origin`, `git merge origin/main`으로 최신 main을 반영하고 충돌을 해결한다. 미완성 파일을 지우거나 강제로 덮어써서 해결하지 않는다.

## 문서와 검증

과제 제출용 계획서·요구사항분석서·설계서는 로컬 submission 폴더에서 별도 관리하고 LMS로 제출한다. 코드 변경 시 관련 테스트를 확인하고 PR에 실제 수행한 점검을 적는다.
