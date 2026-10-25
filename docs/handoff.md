# 백엔드와 화면 파일 전달

2026-10-26

현재 로컬 폴더에는 백엔드와 화면이 모두 있다. 저장소 소유자의 `feat/backend-service`에는 백엔드·DB·테스트·공통 문서를 올리고 화면은 별도 전달한다.

## 파일 구분

| 담당 범위 | 파일 |
|---|---|
| 저장소 소유자 쪽 | app.py, manage.py, requirements.txt, backend/, scripts/, tests/, 공통 docs/ |
| 개발 협업자 검토·통합 쪽 | frontend/index.html, frontend/static/style.css, frontend/static/app.js, docs/ui-guide.md |

두 번째 묶음은 `handoff/frontend-files.zip`에 준비한다. 키·DB·원본 데이터·가상환경은 포함하지 않는다. 친구가 실행·검토하고 필요한 부분을 수정한 뒤 본인 계정으로 올린다. PR에는 검토·수정·통합한 내용을 기록한다.

## 친구가 올리는 순서

먼저 소유자의 백엔드 PR을 main에 병합한 상태를 기준으로 한다.

```powershell
git clone https://github.com/minsk02/busan-youth-guide.git
cd busan-youth-guide
git switch -c feat/frontend-ui
```

이미 clone했다면 `git switch main`, `git pull --ff-only origin main` 후 브랜치를 만든다. 저장소 폴더 안에 zip을 풀어 `frontend/`와 `docs/ui-guide.md`가 해당 경로에 놓이게 한다.

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

자신의 키를 로컬 .env에 설정하고 수집·실행한다. 이미 .env가 있으면 복사로 덮어쓰지 않는다.

```powershell
.venv/Scripts/python.exe manage.py sync
.venv/Scripts/python.exe app.py
```

화면에서 검색, 추천, 상세, 비교, 오류 안내를 확인하고 `docs/ui-guide.md`에 확인 환경과 수정 내용을 적는다. 확인 후 올린다.

```powershell
git add frontend docs/ui-guide.md
git diff --cached
git commit -m "feat: 프로그램 탐색 화면 통합"
git push -u origin feat/frontend-ui
```

GitHub에서 base main, compare feat/frontend-ui로 PR을 만든다. 소유자가 검토·병합하면 원격 저장소에도 전체 시스템이 갖춰진다.

## 백엔드 PR 병합 전 확인만 할 경우

```powershell
git clone https://github.com/minsk02/busan-youth-guide.git
cd busan-youth-guide
git switch -c feat/frontend-ui origin/feat/backend-service
```

이 경우 처음에는 소유자 브랜치를 기준으로 작업한다. PR의 base도 feat/backend-service로 잡아 화면 변경만 비교할 수 있다. 브랜치 관계가 익숙하지 않다면 백엔드가 main에 반영된 뒤 시작하는 편이 간단하다.
