# 공동 작업 방법

이 문서는 Git에 익숙하지 않은 팀원이 문서와 코드를 함께 관리하기 위한 작업 규칙입니다.

## 기본 규칙

- `main`은 검토된 공통 결과물입니다. 작업 브랜치에서 수정하고 Pull Request로 반영합니다.
- 브랜치는 사람별 고정 공간이 아니라 작업별로 만듭니다. `develop` 브랜치는 당분간 사용하지 않습니다.
- 본인 계정으로 본인이 수행한 작업을 커밋합니다. 커밋 수를 맞추기 위한 작업은 하지 않습니다.
- Markdown은 공동 작성용입니다. 제출용 DOCX는 담당자가 취합해 동시 편집을 피합니다.
- 인증키, 인증키가 포함된 요청 URL, 원본 개인정보를 커밋·PR·Issue에 넣지 않습니다.

## 초기 자료 반영 순서

현재 초기 자료는 `setup/project-foundation` 브랜치에서 작성합니다. 친구가 초대를 수락하면 이 브랜치의 PR을 검토합니다. 검토 후 `main`에 병합한 다음 각자 새 브랜치를 만듭니다.

초기 자료가 main에 병합되기 전에는 다음 명령으로 열람할 수 있습니다.

```powershell
git clone https://github.com/minsk02/busan-youth-guide.git
cd busan-youth-guide
git switch --track origin/setup/project-foundation
```

이미 clone한 경우에는 `git fetch origin` 후 브랜치를 전환합니다. 해당 로컬 브랜치가 이미 있으면 `git switch setup/project-foundation`만 실행합니다.

## 역할별 다음 브랜치 예시

| 담당 | 다음 작업 | 브랜치 예시 |
|---|---|---|
| 팀원 1 | 실제 API 호출과 데이터 검증 | `data/api-validation` |
| 팀원 2 | 사용자 화면 흐름과 AI 입출력 설계 | `design/ui-ai-flow` |
| 팀원 3 | 요구사항과 유스케이스 보완 | `docs/requirements-review` |
| 팀원 4 | 테스트 케이스와 추적표 보완 | `docs/test-plan` |

## 친구가 작업을 시작할 때

먼저 GitHub 초대를 수락합니다. 자신의 PC에서 저장소를 clone하고 초기 PR이 main에 병합된 뒤 다음 작업을 시작합니다. 이미 clone했다면 처음 두 명령은 생략합니다.

```powershell
git clone https://github.com/minsk02/busan-youth-guide.git
cd busan-youth-guide
git switch main
git pull --ff-only origin main
git switch -c design/ui-ai-flow
```

해당 브랜치에서 화면 흐름과 AI 입출력 초안을 작성합니다. 필요한 Markdown 파일을 `docs/`에 추가하고 설계서의 관련 부분을 보완합니다. 아래 경로는 실제로 작성한 파일명에 맞게 바꿉니다.

```powershell
git status
git add docs/ui-ai-flow.md
git diff --cached
git commit -m "docs: 화면 흐름과 AI 입출력 초안 작성"
git push -u origin design/ui-ai-flow
```

`git add` 전에 파일을 저장하고, `git diff --cached`에서 키나 개인정보가 없는지 확인합니다. 변경사항이 없으면 커밋하지 않습니다.

## PR과 검토

1. GitHub 저장소의 `Pull requests`에서 `New pull request`를 선택합니다.
2. `base: main`, `compare: 본인 작업 브랜치`로 설정합니다.
3. 변경한 내용, 검증 결과, 미정 사항을 적습니다. 관련 Issue가 있다면 연결합니다.
4. 다른 팀원 1명에게 검토를 요청합니다.
5. 수정 후 검토가 끝나면 `Squash and merge` 등 팀이 정한 방식으로 main에 반영합니다.

초대 수락 후 PR을 열어 검토합니다. 문서 검토는 댓글로도 남길 수 있습니다.

## 다음 작업과 충돌 예방

작업을 마친 뒤 깨끗한 작업 폴더에서 `main`으로 전환하고 최신 내용을 받은 다음 새 브랜치를 만듭니다. 병합 전 브랜치를 기준으로 계속 새 작업을 쌓지 않습니다.

```powershell
git status
git switch main
git pull --ff-only origin main
git switch -c feat/next-task
```

작업 도중 main이 바뀌면 본인 브랜치에서 `git fetch origin`, `git merge origin/main`으로 반영합니다. 충돌은 변경 의도를 확인해 해결하고 검토합니다. 공유 브랜치에 force push를 하지 않습니다.

## Codex와 작업할 때

이 대화에서 본인 작업의 브랜치 생성·커밋·업로드를 요청한 상태입니다. 작업마다 저장소와 현재 변경사항을 확인하고, 적절한 브랜치를 사용해 수정·확인·업로드합니다. main 병합은 별도의 검토 단계로 둡니다. 실패하거나 인증이 필요한 작업은 완료했다고 표시하지 않습니다.

친구는 본인 환경에서 본인 계정으로 작업합니다. 서로 같은 작업 브랜치를 동시에 수정하기보다 별도 작업 브랜치를 사용합니다.
