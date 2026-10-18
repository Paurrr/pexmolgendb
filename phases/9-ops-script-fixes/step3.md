# Step 3: deploy-missing-command

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
7. 이 파일의 행 번호는 2026-10-18(phase 8 직후) 기준 대략값이다. 이름으로 찾아라.
8. step 순서는 다음과 같다.
   - 0: pg_hba 주석 줄 오탐(K27 일부)
   - 1: `PGHBA_CIDR` + 기본 trust 거부(K26, 승인)
   - 2: `src/.git` 권한(K28)
   - 3: 없는 `DEPLOY_COMMANDS`(K29, 이 step)

## 이 step의 목적

`DEPLOY_COMMANDS` 에 venv에 없는 이름이 섞여 있으면 `tools/deploy.sh` 가 **런처를 만들기 전에** 실패하게 한다. 지금은 깨진 런처를 만들고 "Deployed" 로 끝난다.

## 읽어야 할 파일

- `/CLAUDE.md`, `/docs/ADR.md` ADR-011, `/README.md` '배포' 절(~247-311)
- `tools/deploy.sh`
  - 머리 주석의 환경변수 설명(`DEPLOY_COMMANDS`, ~28-29)
  - `python="$root/venv/bin/python"`(~92)
  - "어떤 명령을 낼 것인가"(~94-115): `DEPLOY_COMMANDS` 가 있으면 그대로 쓰고, 없으면 console_scripts를 읽는다. 비었으면 `error: …` 로 exit 1이다(~112-115).
  - 런처 절(~117-164): 지난 배포의 런처를 지운 다음(~140-145) 명령마다 `exec "$here/../venv/bin/python" "$here/../venv/bin/$cmd"` 런처를 쓴다.
  - 확인 절 `check_exec`(~253-275): 126·127만 실패로 본다.
- `tests/test_deploy_sh.py`
  - `UV_STUB`(~34-58)
    - 가짜 uv가 `venv/bin/python` 과 `STUB_COMMANDS`(기본 `genviewer`, `deploy()` 는 `genviewer genviewer-init-db`)마다 `venv/bin/<명령>` 을 만든다.
    - 가짜 python은 인자와 상관없이 exit 0이다. 그래서 진짜에서는 exit 2(파일 없음)인 경우도 여기서는 0이다. 어느 쪽이든 `check_exec` 를 통과한다.
  - `deploy()`, `test_deploy_commands_overrides_discovery`, `test_a_renamed_command_leaves_no_stale_launcher`
- 이전 step에서 수정된 파일: `tools/deploy.sh`(권한 절의 `src/.git` 닫기), `tests/test_deploy_sh.py`. 권한 절과 이 step의 위치(명령 목록 바로 뒤)는 겹치지 않는다.

## 버그

```sh
if [ -n "${DEPLOY_COMMANDS:-}" ]; then
    commands=$DEPLOY_COMMANDS
...
for cmd in $commands; do
    cat > "$root/bin/$cmd" <<LAUNCHER
```

- `DEPLOY_COMMANDS` 의 이름은 검사 없이 받아들여진다.
- 오타가 있으면 그 이름으로 런처가 생긴다. 런처는 `venv/bin/<오타>` 를 python에 넘기고, python은 exit 2로 끝난다.
- 마지막 확인은 126·127만 실패로 보므로 배포는 "Deployed …" 로 성공한다. 사용자는 내일 "있는데 안 되는" 명령을 만난다.
- 지난 배포의 런처는 이미 지워진 뒤다.
- 기대 동작
  - 명령 목록이 정해진 직후, 런처 절에 들어가기 **전에** 이름마다 `"$root/venv/bin/$cmd"` 가 파일로 있는지 본다.
  - 하나라도 없으면 stderr에 그 이름을 알리고 exit 1이다.
  - 그러면 `bin/` 의 지난 런처는 손대지 않은 채 남는다.

이것은 주장이다. 먼저 재현하라.

## 작업

### 1. 테스트 먼저 (`tests/test_deploy_sh.py`)

- **RED: 없는 이름이면 실패한다**
  - `deploy(root, source_repo, stub, DEPLOY_COMMANDS="genviewer nosuch")`(가짜 uv는 `genviewer`, `genviewer-init-db` 만 만든다)
  - 단언: returncode != 0, stderr에 `nosuch` 가 있다, `root / "bin" / "nosuch"` 가 없다.
  - **수정 전에는 returncode 0 이고 런처가 생겨서 실패해야 한다.**
- **RED: 실패한 배포는 지난 런처를 남긴다**
  - 먼저 정상 배포(`deploy(root, source_repo, stub)`)로 `bin/genviewer`, `bin/genviewer-init-db` 를 만든다.
  - 그다음 `DEPLOY_COMMANDS="genviewer nosuch"`, `with_url=False` 로 다시 돌린다.
  - 단언: 실패하고, `bin/` 이름 목록이 `["genviewer", "genviewer-init-db"]` 그대로다.
  - **수정 전에는 `genviewer-init-db` 가 지워지고 `nosuch` 가 생겨서 실패해야 한다.**
- **회귀**
  - 자동으로 읽은 명령(`DEPLOY_COMMANDS` 없음)은 그대로 성공한다(기존 테스트).
  - `test_deploy_commands_overrides_discovery`(`DEPLOY_COMMANDS="genviewer"`)도 그대로 통과한다.

### 2. 수정 (`tools/deploy.sh`)

- `[ -n "$commands" ] || { … }` 바로 뒤에 명령마다 `"$root/venv/bin/$cmd"` 가 있는지 보는 검사를 둔다.
  - 경로는 런처의 `exec` 줄(`$here/../venv/bin/$cmd`)과 같은 것을 본다.
  - 이 스크립트는 리눅스 대상이라 `venv/bin` 이다. 윈도우 venv의 `Scripts/` 를 따로 다루지 않는다. 테스트의 가짜 uv도 `bin/` 을 만든다.
- 자동으로 읽은 명령에도 똑같이 적용한다(언제나 있으므로 통과한다).
- 문구는 기존 `error: …` 형식을 따른다.
  - 예: `error: $root/venv/bin/$cmd 가 없다. DEPLOY_COMMANDS 의 이름이 프로젝트의 console_scripts 와 맞는지 볼 것.`
- 머리 주석의 `DEPLOY_COMMANDS` 설명에 "venv 에 없는 이름이면 런처를 만들기 전에 멈춘다" 를 덧붙인다.

### 3. 문서

- 없다. README '배포' 절은 `DEPLOY_COMMANDS` 를 다루지 않는다(스크립트 머리 주석이 설명한다). known-issues K29 정리는 phase 마무리에서 한다.

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
   - 검사가 지난 런처 정리(`for old in "$root"/bin/*`)보다 앞에 있는가?
   - 자동으로 읽은 명령의 정상 배포가 그대로인가?
   - LF·실행 비트가 그대로인가?
3. 결과에 따라 `phases/9-ops-script-fixes/index.json` 의 step 3을 업데이트한다:
   - 성공 → `"status": "completed"`, `"summary": "deploy.sh: 명령 목록 직후 venv/bin/<cmd> 가 없으면 런처를 만들기 전에 exit 1(지난 런처 보존). RED: <테스트 이름> (<단언>), <테스트 이름> (<단언>). 변이: 검사를 지우면 두 테스트 실패, 런처 정리 뒤로 옮기면 보존 테스트 실패. 셸 테스트 <N passed / M skipped(posix_only)>"`
   - 재현 안 됨 → `"status": "completed"`, `"summary": "not reproduced: <이유>"`
   - 수정 3회 시도 후에도 실패 → `"status": "error"`, `"error_message": "구체적 에러 내용"`
   - 사용자 개입 필요(Git Bash `sh` 없음 등) → `"status": "blocked"`, `"blocked_reason": "구체적 사유"` 후 즉시 중단

## 금지사항

- `check_exec` 가 0 이 아닌 모든 종료 코드를 실패로 보게 바꾸지 마라. 이유: 그 확인은 `--help` 만 돌리고, "프로그램이 실제로 돌았다" 까지만 보는 것이 주석에 적힌 의도다. 이 버그는 런처를 쓰기 전에 막는 것으로 고친다.
- 없는 이름만 건너뛰고 나머지로 배포를 계속하지 마라. 이유: 오타를 조용히 넘기면 같은 문제가 남는다. 멈추고 알린다.
- 런처 절의 지난 런처 정리 순서를 바꾸지 마라. 이유: 이 step의 범위가 아니다. 검사를 그 앞에 두는 것으로 충분하다.
- 기존 문구를 바꾸지 마라. 이유: 버그 수정 중에 문구를 바꾸지 않는다.
- 기존 테스트를 깨뜨리지 마라.
