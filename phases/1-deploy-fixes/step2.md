# Step 2: deploy-python-perms

## 배경 (phase 1 공통)

이 저장소는 이미 여러 명이 쓰는 도구다. 지금은 **에러·버그만 고친다**(CLAUDE.md, ADR-015). phase 1은 배포·클러스터 셸 스크립트(`tools/deploy.sh`, `tools/initdb.sh`)와 deploy.sh 가 만드는 런처(`<ROOT>/bin/<명령>`)의 버그 넷을 하나씩 고친다. 셸 스크립트 테스트는 진짜 `sh`·`git` 으로 스크립트를 실행한다. PATH 앞(또는 `PGBIN`)에 둔 stub 명령이 받은 인자를 파일에 기록하고, 테스트는 그 기록과 결과 디렉터리를 단언한다(`tests/test_deploy_sh.py` 방식). 스크립트 본문의 토큰 검사만으로 끝내지 않는다. 개발 PC는 Windows이고 테스트는 Git Bash `sh` 로 돈다(2026-10-17 기준 `tests/test_deploy_sh.py` 는 개발 PC에서 11 passed / 5 skipped).

모든 step에 같은 규칙이 적용된다.
1. 아래 "버그"는 **분석 에이전트의 주장**이다. 먼저 실패하는 테스트로 재현하고, RED 출력(테스트 이름과 실패한 단언)을 summary에 적는다.
2. RED는 **Windows 개발 PC에서**(Git Bash `sh`) 보여야 한다. `posix_only` 테스트는 개발 PC에서 skip되므로 버그를 증명하지 못한다. `sh`/`git` 이 없어서 skip된 테스트도 RED가 아니다.
3. 재현되지 않으면 `tools/`·`src/` 를 고치지 않는다. 테스트는 특성 테스트로 남기고 `"status": "completed"`, `"summary": "not reproduced: <이유>"` 로 끝낸다.
4. 고친 뒤 수정을 손으로 되돌려 새 테스트가 실패하는지 확인하고 다시 고친다(변이 검사). `git checkout`/`git stash` 로 되돌리지 마라. 이유: 같은 step의 테스트 변경까지 사라진다.
5. 이 파일의 행 번호는 2026-10-17 기준 대략값이다. 이름으로 찾아라.

## 이 step의 목적

`<ROOT>/python` 이 있으면 `tools/deploy.sh` 가 `src`·`venv`·`bin` 처럼 `a+rX` 로 연다. 이곳은 README와 deploy.sh 자신의 경고가 uv 관리 CPython을 두라고 시키는 곳이다. 지금은 열지 않아서, umask가 027 같은 사이트에서는 배포한 사람만 실행되고 나머지 사용자는 `Permission denied` 를 본다.

## 읽어야 할 파일

- `/CLAUDE.md`, `/docs/ADR.md`(ADR-007의 권한 거부, ADR-011 트레이드오프의 `DEPLOY_PYTHON`), `/docs/ARCHITECTURE.md`(배포 구조)
- `/README.md` '배포' — "venv 인터프리터가 **배포한 사람 홈 안**이면 경고한다. …" 항목(~288-294). 끝부분이 "지금 스크립트는 `<루트>/python` 을 `a+rX` 로 열지 않으므로 … `phases/1-deploy-fixes` 에 있다)." 다
- `tools/deploy.sh` — 머리 주석의 `DEPLOY_PYTHON` 설명(~26-27), 권한 절(~183-192. step 0에서 런처 줄이 빠져 몇 줄 당겨졌다): `chmod a+rx "$root"`, `chmod -R a+rX "$root/src" "$root/venv" "$root/bin"`. 확인 절의 홈 경고(~225-242): `UV_PYTHON_INSTALL_DIR=$root/python uv python install 3.13`, `DEPLOY_PYTHON=$(ls -d $root/python/*/bin/python3.* | head -1)`. `check_exec`(~249-257)
- `src/genviewer/service/env_file.py` — `check_permissions`(비밀이 든 파일을 other가 읽을 수 있으면 거부)
- `tests/test_deploy_sh.py` — `stub` fixture, `deploy(**env)`(키워드 인자가 환경변수가 된다), `test_uv_is_asked_for_a_locked_non_editable_install` 의 경로 비교 주석(Git Bash는 `/tmp/...`, 파이썬은 `C:\...`), `test_the_config_is_not_opened_up_by_the_chmod`·`test_the_tree_is_readable_by_others`(둘 다 `posix_only`)
- 이전 step에서 수정된 파일: `tools/deploy.sh`(런처 heredoc, `uv sync --locked`), `tests/test_deploy_sh.py`, `tests/test_env_file.py`, `README.md`('찾는 순서', '배포'), `docs/ADR.md`(ADR-011), `docs/ARCHITECTURE.md`, `src/genviewer/service/env_file.py`(docstring), `src/genviewer/utils/logs.py`(주석)

## 버그

권한 절은 이것뿐이다.

```sh
chmod a+rx "$root"
chmod -R a+rX "$root/src" "$root/venv" "$root/bin"
```

deploy.sh 확인 절의 경고와 README는, 인터프리터가 배포한 사람 홈 안에 있으면 `UV_PYTHON_INSTALL_DIR=<ROOT>/python uv python install 3.13` 으로 CPython을 루트 안에 깔고 `DEPLOY_PYTHON` 으로 그것을 가리켜 다시 배포하라고 한다. 그러면 venv의 `bin/python` 은 `<ROOT>/python/cpython-3.13.*/bin/python3.13` 을 가리키는 심볼릭 링크가 된다. 그런데 위 chmod는 `<ROOT>/python` 을 열지 않는다. umask가 027이면 uv가 만든 `<ROOT>/python` 디렉터리에 other 권한이 없다(0750). 다른 사용자가 런처를 실행하면 인터프리터에서 `Permission denied` 가 난다.
- 배포 마지막 확인(`check_exec`)은 배포한 사람, 곧 소유자로 돌아서 이것을 보지 못한다.
- 확인 절의 홈 경고도 인터프리터가 `$root` 아래면 조용하다.
- README는 지금 "한 번 `chmod -R a+rX <루트>/python` 을 직접 한다" 는 수동 우회를 적어 두었다.

재현(테스트): 받은 인자를 기록하는 `chmod` stub을 PATH 앞에 둔다. `<root>/python/...` 을 미리 만든 뒤 배포하면, 기록에 `<root>/python` 을 여는 `-R a+rX` 호출이 없다. uv가 실제로 어떤 권한으로 까는지는 개발 PC에서 재현할 수 없다. 이 step이 고정하는 것은 "스크립트가 그 디렉터리를 연다" 다.

## 작업

### 1. 테스트 먼저 (`tests/test_deploy_sh.py`)

- chmod 기록 fixture를 새로 둔다(예: `chmod_record`). 기존 `stub` fixture에는 넣지 않는다(금지사항).
  - `stub["bindir"] / "chmod"` 에 `#!/bin/sh` stub을 `newline="\n"` 으로 쓰고 `chmod(0o755)` 한다.
  - stub은 호출 하나를 한 줄로 `$CHMOD_RECORD` 에 덧붙인다. 인자를 구분할 수 있게 적는다(예: `(IFS='|'; printf '%s\n' "$*") >> "$CHMOD_RECORD"`). 그다음 `exec "$REAL_CHMOD" "$@"` 로 진짜 chmod를 부른다. 그래야 Windows Git Bash에서도 배포가 끝까지 돈다.
  - `REAL_CHMOD` 는 PATH를 바꾸기 전에 `subprocess.run(["sh", "-c", "command -v chmod"], …)` 로 얻는다(개발 PC Git Bash에서는 `/usr/bin/chmod`).
  - `deploy(root, source_repo, stub, CHMOD_RECORD=…, REAL_CHMOD=…)` 로 넘긴다. 가짜 uv의 `chmod 755` 도 기록되는데 상관없다.
- 경로는 끝부분으로 비교한다. Git Bash가 `/tmp/...` 를, 파이썬이 `C:\...` 를 보기 때문이다. 인자가 `/{root.name}/python` 으로 끝나는지 본다.
- `<root>/python/cpython-3.13-test/bin/python3.13` 을 배포 전에 만들고 배포한다. returncode는 0이다. 기록에 `-R` 과 `a+rX` 가 있고 인자 하나가 `/{root.name}/python` 으로 끝나는 호출이 있다. **수정 전에는 실패해야 한다.**
- 같은 배포에서 `genviewer.env` 로 끝나는 인자를 가진 호출은 mode가 `640` 인 것뿐이다. `-R` 호출의 인자 중에 루트 자체(`/{root.name}` 로 끝나는 것)는 없다. 루트를 재귀로 열면 `genviewer.env` 가 열린다.
- `<root>/python` 이 없을 때 배포하면 returncode는 0이고, `/python` 으로 끝나는 인자를 가진 chmod 호출이 없다(수정 전에도 통과).
- (선택) `posix_only` 실제 권한 테스트: `<root>/python` 트리의 디렉터리를 0o750, 인터프리터 파일을 0o700으로 만들고 배포한다. 디렉터리마다 `(st_mode & 0o005) == 0o005`, 인터프리터 파일도 `(st_mode & 0o005) == 0o005` 이다. `genviewer.env` 는 여전히 `(st_mode & 0o004) == 0` 이다. 괄호를 빼지 마라. 파이썬에서 `==` 가 `&` 보다 먼저 묶인다. Windows에서는 skip되므로 RED로 쓰지 않는다.

### 2. 수정 (`tools/deploy.sh` 권한 절)

- `[ -d "$root/python" ]` 이면 `chmod -R a+rX "$root/python"` 를 더한다. 없으면 아무것도 하지 않고 계속한다. `set -e` 아래에서 없는 경로를 chmod하면 배포가 죽는다.
- 기존 두 줄(`chmod a+rx "$root"`, `chmod -R a+rX "$root/src" "$root/venv" "$root/bin"`)은 그대로 둔다. `genviewer.env` 는 여전히 대상이 아니다(640).
- 권한 절 주석에 이유를 적는다. 확인 절 경고가 CPython을 두라고 시키는 곳이고, 배포한 사람으로 도는 마지막 확인은 다른 사용자의 권한 문제를 보지 못한다.
- 머리 주석의 `DEPLOY_PYTHON` 설명에 "`<ROOT>/python` 아래면 배포가 열어 준다" 를 더하는 것은 선택이다.

### 3. 문서

- `README.md` '배포' 항목의 "지금 스크립트는 `<루트>/python` 을 `a+rX` 로 열지 않으므로, umask 가 027 같은 곳이면 한 번 `chmod -R a+rX <루트>/python` 을 직접 한다(스크립트가 하도록 고치는 작업이 `phases/1-deploy-fixes` 에 있다)." 를 고친 동작으로 다시 쓴다. 뜻: `<루트>/python` 이 있으면 배포가 `src`·`venv`·`bin` 과 함께 `a+rX` 로 연다. 그래서 umask가 027이어도 다른 사용자가 실행할 수 있다. 다른 곳에 두면 그 권한은 직접 맞춘다.
- `docs/ARCHITECTURE.md` 배포 구조에 한 줄을 더한다: `<ROOT>/python   (선택) DEPLOY_PYTHON 용 CPython. 있으면 a+rX`.
- `docs/ADR.md` 는 바꾸지 않는다. ADR-011 트레이드오프("uv 관리 CPython이 배포자 홈에 있으면 남이 실행하지 못한다")는 그대로 맞다.

## Acceptance Criteria

```bash
sh -n tools/deploy.sh && sh -n tools/initdb.sh       # 문법 검사 (sh -n 은 첫 파일만 보므로 따로 돌린다)
! git ls-files --eol tools/*.sh | grep -v 'w/lf'     # 작업 트리가 LF 그대로
uv run pytest tests/test_deploy_sh.py -q -rs         # 새 테스트 통과 (수정 전에는 python 디렉터리 테스트가 실패해야 한다). 새 테스트가 skip 되지 않았는지 -rs 로 본다
uv run ruff check src tests
uv run pytest -q
```

## 검증 절차

1. 위 AC 커맨드를 실행한다.
2. 아키텍처 체크리스트를 확인한다:
   - `genviewer.env` 가 여전히 640이고 어떤 `a+rX` 대상에도 들지 않는가(ADR-007, ADR-011)?
   - `$root` 밖의 경로를 chmod하지 않는가?
   - deploy.sh가 여전히 POSIX `#!/bin/sh` 인가?
3. 결과에 따라 `phases/1-deploy-fixes/index.json` 의 step 2를 업데이트한다:
   - 성공 → `"status": "completed"`, `"summary": "deploy.sh 가 <ROOT>/python 이 있으면 chmod -R a+rX (genviewer.env 는 계속 제외). RED: <테스트 이름>. chmod 기록 stub fixture 추가, README 배포·ARCHITECTURE 정리"`
   - 재현 안 됨 → `"status": "completed"`, `"summary": "not reproduced: <이유>"`
   - 수정 3회 시도 후에도 실패 → `"status": "error"`, `"error_message": "구체적 에러 내용"`
   - 사용자 개입 필요 → `"status": "blocked"`, `"blocked_reason": "구체적 사유"` 후 즉시 중단

## 금지사항

- `chmod -R a+rX "$root"` 처럼 루트를 재귀로 열지 마라. 이유: `genviewer.env`(PGPASSWORD)가 other에게 열린다. 그러면 앱이 `check_permissions` 로 실행을 거부해 전원의 앱이 뜨지 않는다(ADR-007).
- `DEPLOY_PYTHON` 이 가리키는 경로(예: `/usr/bin/python3.13`)나 `readlink -f` 로 푼 인터프리터 디렉터리를 `$root` 밖에서 chmod하지 마라. 이유: 배포한 사람 것이 아니라서 권한이 없으면 `set -e` 로 배포가 실패하고, 시스템 파일 권한을 바꾸면 안 된다.
- `<root>/python` 이 없을 때 실패하거나 경고하게 하지 마라. 이유: 시스템 파이썬을 쓰는 배포가 정상 경로다.
- 기존 `stub` fixture에 chmod stub을 넣지 마라. 이유: 모든 deploy 테스트가 stub을 거치게 되고, `CHMOD_RECORD`/`REAL_CHMOD` 를 넘기지 않는 기존 테스트가 깨진다.
- `src/.git/config` 가 열리는 문제(known-issues K28)는 고치지 마라. 이유: 기록만 한 문제이고, README가 저장소 URL에 토큰을 넣지 말라고 안내한다.
- 확인 절의 홈 경고 문구와 조건을 바꾸지 마라. 이유: 이 step의 범위가 아니다.
- 기존 테스트를 깨뜨리지 마라.
