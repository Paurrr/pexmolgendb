# Step 3: initdb-rerun

## 배경 (phase 1 공통)

이 저장소는 이미 여러 명이 쓰는 도구다. 지금은 **에러·버그만 고친다**(CLAUDE.md, ADR-015). phase 1은 배포·클러스터 셸 스크립트(`tools/deploy.sh`, `tools/initdb.sh`)와 deploy.sh 가 만드는 런처(`<ROOT>/bin/<명령>`)의 버그 넷을 하나씩 고친다. 셸 스크립트 테스트는 진짜 `sh`·`git` 으로 스크립트를 실행한다. PATH 앞(또는 `PGBIN`)에 둔 stub 명령이 받은 인자를 파일에 기록하고, 테스트는 그 기록과 결과 디렉터리를 단언한다(`tests/test_deploy_sh.py` 방식). 스크립트 본문의 토큰 검사만으로 끝내지 않는다. 개발 PC는 Windows이고 테스트는 Git Bash `sh` 로 돈다(2026-10-17 기준 `tests/test_deploy_sh.py` 는 개발 PC에서 11 passed / 5 skipped).

모든 step에 같은 규칙이 적용된다.
1. 아래 "버그"는 **분석 에이전트의 주장**이다. 먼저 실패하는 테스트로 재현하고, RED 출력(테스트 이름과 실패한 단언)을 summary에 적는다.
2. RED는 **Windows 개발 PC에서**(Git Bash `sh`) 보여야 한다. `posix_only` 테스트는 개발 PC에서 skip되므로 버그를 증명하지 못한다. `sh`/`git` 이 없어서 skip된 테스트도 RED가 아니다.
3. 재현되지 않으면 `tools/`·`src/` 를 고치지 않는다. 테스트는 특성 테스트로 남기고 `"status": "completed"`, `"summary": "not reproduced: <이유>"` 로 끝낸다.
4. 고친 뒤 수정을 손으로 되돌려 새 테스트가 실패하는지 확인하고 다시 고친다(변이 검사). `git checkout`/`git stash` 로 되돌리지 마라. 이유: 같은 step의 테스트 변경까지 사라진다.
5. 이 파일의 행 번호는 2026-10-17 기준 대략값이다. 이름으로 찾아라.

## 이 step의 목적

이미 떠 있는 클러스터에 `tools/initdb.sh` 를 다시 돌려도 `pg_ctl start` 에서 죽지 않게 한다. start를 건너뛰고 `createdb` 까지 가야 한다. 스크립트는 다시 돌리는 경우를 이미 지원한다. `PG_VERSION` 이 있으면 initdb를 건너뛰고, createdb의 "already exists" 는 "이미 있음" 으로 넘어간다. 빠진 것은 start 하나다.

## 읽어야 할 파일

- `/CLAUDE.md`, `/docs/ADR.md`(ADR-010)
- `/README.md` '개발 클러스터 (한 번만)'(~453-477. 특히 "`SKIP_START=1` 로 처음 돌리면 …" 문단의 마지막 문장 "리눅스에서 이미 떠 있는 클러스터에 다시 돌리면 `pg_ctl start` 에서 멈춘다 …"), '서버' 절의 "1. 클러스터"(재부팅 생존 행: systemd로 띄운 서버)
- `tools/initdb.sh` — 기본값 목록(~16-27), `PGBIN` 분기(~29-33), `PG_VERSION` 검사(~35-47), conf·hba 추가(~49-73), start 블록(~75-80), createdb와 "이미 있음" 판정(~82-102)
- `tests/test_deploy_sh.py` — 모듈 `pytestmark`(skip 조건), stub을 `newline="\n"` 으로 쓰고 `chmod(0o755)` 하는 방식, 환경변수를 지우는 `deploy()` 헬퍼
- `docs/notes/known-issues.md` K26, K27, K30(이 step의 범위 밖)
- 이전 step에서 수정된 파일: `tools/deploy.sh`, `tests/test_deploy_sh.py`, `tests/test_env_file.py`, `README.md`('찾는 순서', '배포'), `docs/ADR.md`, `docs/ARCHITECTURE.md`, `src/genviewer/service/env_file.py`(docstring), `src/genviewer/utils/logs.py`(주석). 이 step과는 관계없다.

## 버그

`tools/initdb.sh` 의 start 블록:

```sh
if [ "$SKIP_START" = "1" ]; then
    echo "==> start 건너뜀 (SKIP_START=1)"
else
    echo "==> start (port $PGPORT)"
    "$pg_ctl" -D "$PGDATA" -o "-p $PGPORT" -l "$PGDATA/server.log" -w start
fi
```

이 블록은 `set -eu` 아래에서 `pg_ctl start` 를 무조건 부른다. 서버가 이미 떠 있으면 pg_ctl은 "another server might be running" 을 찍은 뒤 "could not start server" 로 exit 1 한다. 그러면 스크립트가 createdb 전에 끝난다. `initdb.sh` 로 띄웠든 `postgresql-15.service` 로 띄웠든, 리눅스에서 두 번째 실행은 늘 실패한다. README '개발 클러스터' 는 "그때는 `pg_ctl stop` 뒤에 돌린다" 는 우회를 적어 두었다.

`pg_ctl status` 의 종료 코드(PostgreSQL 문서 pg_ctl): 0 = 떠 있음, 3 = 안 떠 있음, 4 = 데이터 디렉터리가 없거나 잘못됨.

재현: 아래 stub으로 두 번 돌리면 두 번째가 exit 1로 끝나고, stderr에 stub의 start 실패 문구가 나온다(2026-10-17 개발 PC Git Bash에서 확인. Windows 경로의 `PGBIN`·`PGDATA` 를 그대로 줘도 돈다).

## 작업

### 1. 테스트 먼저 (`tests/test_initdb_sh.py`, 새 파일, DB 불필요)

- skip 조건: `tests/test_deploy_sh.py` 와 같은 모듈 `pytestmark = pytest.mark.skipif(shutil.which("sh") is None, reason=…)`. 이 파일은 git을 쓰지 않으므로 `sh` 만 본다.
- stub 셋을 `tmp_path / "pgbin"` 에 쓰고 `PGBIN` 으로 넘긴다. 모두 `#!/bin/sh` 로 시작하고 `newline="\n"` 으로 쓰고 `chmod(0o755)` 한다. 각 stub은 "이름 인자…" 를 한 줄로 `$STUB_RECORD` 에 덧붙인다. 상태 파일은 `$STUB_STATE` 디렉터리에 둔다.
  - `initdb`: 인자에서 `-D <dir>` 를 찾아 그 디렉터리에 `PG_VERSION`(내용 `15`), 빈 `postgresql.conf`, 빈 `pg_hba.conf` 를 만든다.
  - `pg_ctl`: 마지막 인자가 동작이다. `status` 는 `$STUB_STATE/running` 이 있으면 exit 0, 없으면 exit 3이다. `start` 는 `running` 이 이미 있으면 stderr에 `pg_ctl: could not start server` 를 쓰고 exit 1, 없으면 그 파일을 만들고 exit 0이다. `STUB_START_FAIL=1` 이면 `start` 가 항상 exit 1이다(포트 충돌 흉내).
  - `createdb`: `$STUB_STATE/db` 가 없으면 만들고 exit 0이다. 있으면 stderr에 `createdb: error: database creation failed: ERROR:  database "molgen" already exists` 를 쓰고 exit 1이다.
- 실행 헬퍼: `os.environ` 사본에서 `PG`, `SKIP_START`, `LISTEN_ADDRESSES` 로 시작하는 변수를 지운다. 개발 PC에 `PGPORT`·`PGUSER`·`PGDATA` 가 있을 수 있다. 그다음 `PGBIN`, `PGDATA=tmp_path / "data"`, `STUB_RECORD`, `STUB_STATE` 와 인자로 받은 값을 준다. `["sh", str(REPO / "tools" / "initdb.sh")]` 를 `capture_output=True, text=True, encoding="utf-8", errors="replace"` 로 돌린다. `PGDATA` 는 반드시 준다. 기본값은 `$HOME/pgdata/molgen` 이다.
- 테스트:
  - 두 번 돌린다. 둘 다 returncode 0이다. 두 번째 stdout에 `이미 있음` 이 있다. 기록에서 `pg_ctl` 의 `start` 호출은 정확히 한 번, `initdb` 호출도 한 번이다. **수정 전에는 두 번째 실행이 1로 끝나 실패해야 한다.**
  - 두 번째 stdout에 start를 건너뛰었다는 줄이 있다(문구는 아래 수정 참고).
  - start 실패는 여전히 실패다. `STUB_START_FAIL=1` 로 처음 돌리면 returncode가 0이 아니고, 기록에 `createdb` 가 없다. `|| true` 같은 수정을 막는다(수정 전에도 통과).
  - `SKIP_START=1` 이면 `pg_ctl` 이 아예 불리지 않는다(`status` 도 없음). 지금 흐름을 지킨다, K30(수정 전에도 통과).

### 2. 수정 (`tools/initdb.sh` 의 start 블록)

- `SKIP_START=1` 분기는 그대로 둔다.
- 그 밖에는 `"$pg_ctl" -D "$PGDATA" status` 가 0이면 `==> start 건너뜀 (이미 떠 있다)` 를 찍고 start하지 않는다. 0이 아니면(3, 4 등) 지금처럼 `echo "==> start (port $PGPORT)"` 를 찍고 같은 인자로 `pg_ctl … -w start` 한다.
- `status` 는 `if` 조건으로 부른다. 그래야 `set -e` 에 걸리지 않는다. 출력은 `>/dev/null 2>&1` 로 버려도 된다.
- 떠 있는 서버의 포트가 `$PGPORT` 와 다르면 뒤의 createdb가 "실패" 로 끝난다. 이 경우를 따로 처리하지 않는다. 지금도 이유가 찍힌다.
- 주석으로 남긴다: `status` 종료 코드의 뜻, 그리고 `|| true` 가 아닌 이유(진짜 start 실패는 멈춰야 한다).

### 3. 문서

- `README.md` '개발 클러스터' 의 "리눅스에서 이미 떠 있는 클러스터에 다시 돌리면 `pg_ctl start` 에서 멈춘다 — 그때는 `pg_ctl stop` 뒤에 돌린다(고치는 작업이 `phases/1-deploy-fixes` 에 있다)." 를 고친 동작으로 다시 쓴다. 뜻: 이미 떠 있는 클러스터에 다시 돌리면 start를 건너뛰고 데이터베이스만 확인한다.
- `docs/notes/known-issues.md` K30은 그대로 둔다(윈도우 `SKIP_START=1` 첫 실행의 createdb 실패는 바뀌지 않는다).
- `tools/initdb.sh` 머리 주석은 바꾸지 않는다.

## Acceptance Criteria

```bash
sh -n tools/deploy.sh && sh -n tools/initdb.sh       # 문법 검사 (sh -n 은 첫 파일만 보므로 따로 돌린다)
! git ls-files --eol tools/*.sh | grep -v 'w/lf'     # 작업 트리가 LF 그대로
uv run pytest tests/test_initdb_sh.py -q -rs         # 새 테스트 통과 (수정 전에는 두 번 돌리는 테스트가 실패해야 한다). skip 없이 돌았는지 -rs 로 본다
uv run ruff check src tests
uv run pytest -q
```

## 검증 절차

1. 위 AC 커맨드를 실행한다.
2. 아키텍처 체크리스트를 확인한다:
   - initdb.sh가 여전히 POSIX `#!/bin/sh` 이고 `set -eu` 인가?
   - start가 진짜로 실패하면 여전히 그 자리에서 멈추는가(위 `STUB_START_FAIL` 테스트)?
   - 조절 가능한 값 목록(`PGPORT` … `PGHBA_USER`)이 그대로인가? 머리 주석이 "조절할 수 있는 값은 아래 기본값 목록이 전부다" 라고 약속한다.
3. 결과에 따라 `phases/1-deploy-fixes/index.json` 의 step 3을 업데이트한다:
   - 성공 → `"status": "completed"`, `"summary": "initdb.sh: pg_ctl status 가 0 이면 start 건너뜀 (SKIP_START 흐름 불변, start 실패는 그대로 중단). RED: <테스트 이름>. tests/test_initdb_sh.py 추가, README 개발 클러스터 정리"`
   - 재현 안 됨 → `"status": "completed"`, `"summary": "not reproduced: <이유>"`
   - 수정 3회 시도 후에도 실패 → `"status": "error"`, `"error_message": "구체적 에러 내용"`
   - 사용자 개입 필요 → `"status": "blocked"`, `"blocked_reason": "구체적 사유"` 후 즉시 중단

## 금지사항

- `pg_ctl start || true` 처럼 start 실패를 삼키지 마라. 이유: 포트 충돌·권한·잘못된 설정으로 진짜 못 띄운 경우까지 넘어간다. 그러면 createdb가 엉뚱한 이유로 실패하거나, 같은 포트의 다른 인스턴스에 데이터베이스를 만든다.
- `postmaster.pid` 가 있는지로 "떠 있음" 을 판단하지 마라. 이유: 비정상 종료 뒤에 남은 pid 파일을 떠 있다고 오판한다. `pg_ctl status` 는 프로세스가 살아 있는지까지 본다.
- `pg_ctl stop`/`restart` 를 넣지 마라. 이유: 공유 서버에서 붙어 있는 사람을 끊는다. 바뀐 설정을 반영하는 일(K27)은 이 step의 범위가 아니다.
- `SKIP_START` 흐름을 바꾸지 마라(첫 실행의 createdb 실패 포함, known-issues K30). 이유: 기록만 한 문제이고 README가 우회를 안내한다.
- `listen_addresses`·`port`·pg_hba 줄 추가 로직(K27)과 `PGAUTH_*` 기본값(K26)을 바꾸지 마라. 이유: known-issues에 기록만 한 문제이고, 바꾸면 기존 동작이 바뀐다.
- createdb의 "already exists" 판정과 `-h` 를 주지 않는 접속 방식을 바꾸지 마라. 이유: 스크립트 주석에 적힌 의도(peer 인증, 실패를 삼키지 않음)다.
- 테스트에서 진짜 PostgreSQL 바이너리를 부르지 마라. 이유: 개발 PC에서 RED가 보여야 하고, stub으로 충분하다.
- 기존 테스트를 깨뜨리지 마라.
