# Step 2: deploy-git-perms

## 배경 (phase 9 공통)

이 저장소는 이미 여러 명이 쓰는 도구다. 지금은 **에러·버그만 고친다**(CLAUDE.md, ADR-015). phase 9는 운영 셸 스크립트(`tools/initdb.sh`, `tools/deploy.sh`)의 알려진 문제(`docs/notes/known-issues.md` K26~K29)를 하나씩 고친다. K26 하나만 버그가 아니라 **사용자가 2026-10-17 승인한 동작 변경**이다(step 1).

셸 스크립트 테스트는 진짜 `sh`·`git` 으로 스크립트를 실행한다.
- PATH 앞(`initdb.sh` 는 `PGBIN`)에 둔 stub 명령이 받은 인자를 파일에 기록하고, 테스트는 그 기록과 결과 파일을 단언한다.
- 본보기는 `tests/test_initdb_sh.py`, `tests/test_deploy_sh.py` 다.
- 스크립트 본문의 토큰 검사만으로 끝내지 않는다.
- 개발 PC는 Windows이고, 이 테스트는 **Git Bash의 `sh`** 로 돈다. `sh` 가 PATH에 없으면(PowerShell) 두 파일이 통째로 skip된다(CLAUDE.md 기준선: 셸 스크립트 테스트 20개).

모든 step에 같은 규칙이 적용된다.
1. 아래 "버그"는 **분석 에이전트의 주장**이다. 먼저 실패하는 테스트로 재현하고, RED 출력(테스트 이름과 실패한 단언)을 summary에 적는다.
2. RED는 **Windows 개발 PC에서**(Git Bash `sh`) 보여야 한다.
   - `posix_only` 테스트는 개발 PC에서 skip되므로 버그를 증명하지 못한다.
   - `sh`/`git` 이 없어서 skip된 테스트도 RED가 아니다. AC의 `-rs` 출력에 그런 skip이 보이면 성공이 아니다.
3. 재현되지 않으면 `tools/`·`src/` 를 고치지 않는다. 테스트는 특성 테스트로 남기고 `"status": "completed"`, `"summary": "not reproduced: <이유>"` 로 끝낸다.
4. 고친 뒤 수정을 손으로 되돌려 새 테스트가 실패하는지 확인하고 다시 고친다(변이 검사). `git checkout`/`git stash` 로 되돌리지 마라. 이유: 같은 step의 테스트 변경까지 사라진다.
5. `tools/*.sh` 는 LF와 실행 비트(100755)를 지킨다(`.gitattributes`, CLAUDE.md). Edit 도구가 줄 끝을 바꾸지 않았는지 AC의 `git ls-files --eol` 로 본다.
6. PostgreSQL을 쓰지 않는다. 하네스 규칙 12(DB 테스트 필수)는 해당하지 않는다.
7. 이 파일의 행 번호는 2026-10-17 기준 대략값이다. 이름으로 찾아라.
8. step 순서는 다음과 같다.
   - 0: pg_hba 주석 줄 오탐(K27 일부)
   - 1: `PGHBA_CIDR` + 기본 trust 거부(K26, 승인)
   - 2: `src/.git` 권한(K28, 이 step)
   - 3: 없는 `DEPLOY_COMMANDS`(K29)

## 이 step의 목적

`tools/deploy.sh` 가 배포 트리를 모두에게 여는 `chmod -R a+rX` 가 `<ROOT>/src/.git` 까지 연다. 그래서 다른 사용자가 `.git/config`(clone URL, 넣었다면 토큰)를 읽는다. `.git` 만 다시 닫는다.

## 읽어야 할 파일

- `/CLAUDE.md`, `/docs/ADR.md` ADR-011(배포는 단일 슬롯 deploy.sh), `/docs/ARCHITECTURE.md` "배포 구조"(~126-133)
- `/README.md` '배포' 절(~236-300). 특히 아래 두 문장이다.
  - "저장소 URL 에 토큰을 넣지 않는다. 트리를 `a+rX` 로 열기 때문에 `src/.git/config` 를 모두가 읽는다."(~280-281)
  - `genviewer.env` 제외 설명(~282-284)
- `tools/deploy.sh`
  - 소스 체크아웃(~54-69): `git clone "$url" "$root/src"` 라서 `src/.git` 이 언제나 있다.
  - 권한 절(~184-201): `chmod a+rx "$root"`, `chmod -R a+rX "$root/src" "$root/venv" "$root/bin"`(~198), `<ROOT>/python` 분기
- `tests/test_deploy_sh.py`
  - `UV_STUB`, `source_repo`/`stub`/`root` fixture, `deploy()`
  - **`CHMOD_STUB` 과 `chmod_record` fixture**(~104-125): PATH 앞에 chmod 기록기를 두고 진짜 chmod에 넘긴다. 호출 하나가 `|` 로 이은 한 줄이다.
  - `chmod_calls`
  - 이 기록기를 쓰는 테스트들
    - `test_the_bundled_python_is_opened_up`
    - `test_opening_the_python_does_not_open_the_config`: 모든 `-R` 호출의 인자가 루트 자체로 끝나지 않아야 한다.
    - `test_without_a_bundled_python_nothing_more_is_chmodded`
  - `posix_only` 테스트들(`test_the_tree_is_readable_by_others` 등)
- 이전 step에서 수정된 파일: `tools/initdb.sh`, `tests/test_initdb_sh.py`(이 step과 겹치지 않는다)

## 버그

```sh
chmod a+rx "$root"
chmod -R a+rX "$root/src" "$root/venv" "$root/bin"
```

- `$root/src` 는 `git clone` 결과라 `.git/config` 에 clone URL이 있다.
- URL에 토큰이나 비밀번호를 넣어 clone했다면 그 서버의 모든 사용자가 읽는다.
- README는 "URL 에 토큰을 넣지 않는다" 고 사람에게 맡긴다.
- 앱 실행에는 `src/.git` 이 필요 없다. 코드는 `--no-editable` venv의 site-packages 사본에서 돈다(ADR-011).
- 기대 동작: 배포가 끝나면 `src/.git` 은 배포한 사람만 읽고 들어갈 수 있다(group·other 권한 없음). `src` 의 나머지(작업 트리)는 지금처럼 `a+rX` 다.

이것은 주장이다. 먼저 재현하라.

## 작업

### 1. 테스트 먼저 (`tests/test_deploy_sh.py`)

- **RED (Windows에서 돈다): `.git` 을 다시 닫는 chmod 호출이 있다**
  - `chmod_record` fixture로 `deploy(root, source_repo, stub, **chmod_record)` 를 돌린다.
  - `chmod_calls` 에서 확인한다.
    - ⓐ `-R` 과 `a+rX` 를 받고 `/{root.name}/src` 로 끝나는 인자가 있는 호출
    - ⓑ `-R` 과 group·other 권한을 빼는 모드(예: `go-rwx`)를 받고 `/{root.name}/src/.git` 으로 끝나는 인자가 있는 호출
  - 둘 다 있고 ⓑ가 ⓐ **뒤에** 온다.
  - Git Bash는 `/tmp/...`, 파이썬은 `C:\...` 를 보므로 경로는 끝부분만 비교한다(기존 테스트와 같다).
  - **수정 전에는 ⓑ가 없어서 실패해야 한다.**
- **posix_only: 실제 비트**
  - 배포 뒤 확인한다.
    - `root/src/.git/config` 의 `st_mode & 0o077 == 0`
    - `root/src/.git` 디렉터리도 `& 0o077 == 0`
    - `root/src/pyproject.toml` 은 여전히 `& 0o004` 이고, `root/src` 는 `& 0o005` 다.
  - 개발 PC에서는 skip된다. RED 증명은 위 테스트가 한다.
- **회귀**
  - `test_opening_the_python_does_not_open_the_config`, `test_without_a_bundled_python_nothing_more_is_chmodded`, `test_the_tree_is_readable_by_others` 가 그대로 통과한다.
  - 새 호출의 경로는 `/.git` 으로 끝나므로 "루트 자체" 검사에 걸리지 않는다. 걸리면 그 테스트가 지키려던 성질(루트를 재귀로 열지 않음)을 다시 읽고 판단해 summary에 적는다.
- **업그레이드**: 같은 루트에 다른 태그로 두 번 배포해도(`with_url=False`) 두 번째 실행이 성공하고 ⓑ 호출이 또 있다.
  - 배포한 사람은 소유자라 닫힌 `.git` 에서도 `git fetch`/`checkout` 이 된다.

### 2. 수정 (`tools/deploy.sh` 권한 절)

- `chmod -R a+rX "$root/src" …` 바로 다음에 `$root/src/.git` 의 group·other 권한을 재귀로 뺀다.
- 그 위 주석에 이유를 적는다. `.git/config` 에 clone URL(토큰을 넣었다면 그것도)이 있다. 실행에는 필요 없다(`--no-editable`).
- 권한 절 머리 주석의 "모두가 읽고 지나갈 수 있게 …" 근처에 "`src/.git` 은 다시 닫는다" 를 한 줄 더한다.

### 3. 문서

- `README.md` '배포' 절의 토큰 문장을 고친다.
  - 예: "배포는 `src/.git` 을 다른 사용자에게서 다시 닫는다(`go-rwx`). 그래도 저장소 URL 에 토큰을 넣지 않는다."
- `docs/ARCHITECTURE.md` "배포 구조" 의 `<ROOT>/src` 줄에 "(`.git` 은 배포한 사람만)" 정도를 덧붙인다.
- known-issues K28 정리는 phase 마무리에서 한다.

## Acceptance Criteria

```bash
# Git Bash 에서 돌린다 (sh 와 git 이 PATH 에 있어야 한다)
command -v sh && command -v git
uv run pytest tests/test_initdb_sh.py tests/test_deploy_sh.py -q -rs   # 통과. skip 은 posix_only("윈도우에서는 chmod / ln -s …")뿐이어야 한다
sh -n tools/initdb.sh                        # 문법 검사 (파일마다 따로)
sh -n tools/deploy.sh
git ls-files --eol tools/                    # 두 파일 모두 i/lf w/lf
git ls-files -s tools/                       # 두 파일 모두 100755
uv run ruff check src tests
uv run pytest -q
```

## 검증 절차

1. 위 AC 커맨드를 실행한다. `-rs` 출력에 "sh 가 없다"/"sh 나 git 이 없다" skip이 있으면 RED·GREEN을 본 것이 아니다. 성공으로 적지 말고 `blocked`(사유: Git Bash `sh` 없음)로 멈춘다.
2. 아키텍처 체크리스트를 확인한다:
   - `src` 작업 트리, `venv`, `bin` 은 여전히 `a+rX` 인가? `genviewer.env` 는 640 그대로인가?
   - 닫는 호출이 여는 호출 뒤에 오는가(앞에 오면 a+rX 가 다시 연다)?
   - LF·실행 비트가 그대로인가?
3. 결과에 따라 `phases/9-ops-script-fixes/index.json` 의 step 2를 업데이트한다:
   - 성공 → `"status": "completed"`, `"summary": "deploy.sh: a+rX 뒤에 chmod -R go-rwx <ROOT>/src/.git (clone URL·토큰 비공개). RED: <테스트 이름> (<단언>). 변이: 그 줄을 지우면 <테스트> 실패, a+rX 앞으로 옮기면 <테스트> 실패. posix_only 비트 테스트 추가(개발 PC skip). README 배포·ARCHITECTURE 배포 구조. 셸 테스트 <N passed / M skipped(posix_only)>"`
   - 재현 안 됨 → `"status": "completed"`, `"summary": "not reproduced: <이유>"`
   - 수정 3회 시도 후에도 실패 → `"status": "error"`, `"error_message": "구체적 에러 내용"`
   - 사용자 개입 필요(Git Bash `sh` 없음 등) → `"status": "blocked"`, `"blocked_reason": "구체적 사유"` 후 즉시 중단

## 금지사항

- `src` 전체를 닫거나 `a+rX` 대상에서 `src` 를 빼지 마라. 이유: README·ADR-011이 설명하는 공유 트리 구조가 바뀐다. 버그는 `.git` 뿐이다.
- `.git/config` 에서 URL을 지우거나 `git remote set-url` 로 바꾸지 마라. 이유: 다음 배포의 `git fetch origin` 이 깨진다.
- RED를 `posix_only` 테스트로만 증명하지 마라. 이유: 개발 PC에서 skip된다. chmod 기록기(`chmod_record`)로 Windows에서 보인다.
- `CHMOD_STUB`·`chmod_record` 를 `stub` fixture에 합치지 마라. 이유: 그 fixture 주석대로 `CHMOD_RECORD` 를 넘기지 않는 다른 테스트가 모두 깨진다.
- 기존 테스트를 깨뜨리지 마라.
