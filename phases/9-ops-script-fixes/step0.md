# Step 0: hba-line-match

## 배경 (phase 9 공통)

이 저장소는 이미 여러 명이 쓰는 도구다. 지금은 **에러·버그만 고친다**(CLAUDE.md, ADR-015). phase 9는 운영 셸 스크립트(`tools/initdb.sh`, `tools/deploy.sh`)의 알려진 문제(`docs/notes/known-issues.md` K26~K29)를 하나씩 고친다. K26 하나만 버그가 아니라 **사용자가 2026-10-17 승인한 동작 변경**이다(step 1).

셸 스크립트 테스트는 진짜 `sh`·`git` 으로 스크립트를 실행한다.
- PATH 앞(`initdb.sh` 는 `PGBIN`)에 둔 stub 명령이 받은 인자를 파일에 기록하고, 테스트는 그 기록과 결과 파일을 단언한다.
- 본보기는 `tests/test_initdb_sh.py`, `tests/test_deploy_sh.py` 다.
- 스크립트 본문의 토큰 검사만으로 끝내지 않는다.
- 개발 PC는 Windows이고, 이 테스트는 **Git Bash의 `sh`** 로 돈다. `sh` 가 PATH에 없으면(PowerShell) 두 파일이 통째로 skip된다(CLAUDE.md 기준선: 셸 스크립트 테스트 20개).

모든 step에 같은 규칙이 적용된다.
1. 아래 "버그"는 **분석 에이전트의 주장**이다. 먼저 실패하는 테스트로 재현하고, RED 출력(테스트 이름과 실패한 단언)을 summary에 적는다.
   - K26(step 1)은 승인된 동작 변경이라 "버그" 대신 "승인된 동작 변경" 절이 있다. 그래도 테스트를 먼저 쓰고 수정 전 실패를 본다.
2. RED는 **Windows 개발 PC에서**(Git Bash `sh`) 보여야 한다.
   - `posix_only` 테스트는 개발 PC에서 skip되므로 버그를 증명하지 못한다.
   - `sh`/`git` 이 없어서 skip된 테스트도 RED가 아니다. AC의 `-rs` 출력에 그런 skip이 보이면 성공이 아니다.
3. 재현되지 않으면 `tools/`·`src/` 를 고치지 않는다. 테스트는 특성 테스트로 남기고 `"status": "completed"`, `"summary": "not reproduced: <이유>"` 로 끝낸다.
4. 고친 뒤 수정을 손으로 되돌려 새 테스트가 실패하는지 확인하고 다시 고친다(변이 검사). `git checkout`/`git stash` 로 되돌리지 마라. 이유: 같은 step의 테스트 변경까지 사라진다.
5. `tools/*.sh` 는 LF와 실행 비트(100755)를 지킨다(`.gitattributes`, CLAUDE.md). Edit 도구가 줄 끝을 바꾸지 않았는지 AC의 `git ls-files --eol` 로 본다.
6. PostgreSQL을 쓰지 않는다. 하네스 규칙 12(DB 테스트 필수)는 해당하지 않는다.
7. 이 파일의 행 번호는 2026-10-18(phase 8 직후) 기준 대략값이다. 이름으로 찾아라.
8. step 순서는 다음과 같다.
   - 0: pg_hba 주석 줄 오탐(K27 일부, 이 step)
   - 1: `PGHBA_CIDR` + 기본 trust 거부(K26, 승인)
   - 2: `src/.git` 권한(K28)
   - 3: 없는 `DEPLOY_COMMANDS`(K29)

## 이 step의 목적

`tools/initdb.sh` 가 원격 대역 hba 줄이 이미 있는지 볼 때 **주석 처리된 같은 줄**을 "있음" 으로 보지 않게 한다.

## 읽어야 할 파일

- `/CLAUDE.md`(셸 스크립트 관례, 테스트 관례의 셸 스크립트 항목), `/README.md` '서버' 절의 "1. 클러스터"(~639-677)
- `tools/initdb.sh`
  - 기본값 목록(~16-27)
  - `listen_addresses`·`port` 검사(~49-59). 둘 다 `grep -q "^..."` 로 줄 머리에 앵커가 있어 주석 줄을 오탐하지 않는다.
  - hba 절(~61-73): `hba_line="host $PGHBA_DB $PGHBA_USER $PGHBA_CIDR $PGAUTH_HOST"` 다음에 `if ! grep -qF "$hba_line" "$PGDATA/pg_hba.conf"; then … echo "==> pg_hba.conf 에 추가: $hba_line"`
- `tests/test_initdb_sh.py` 전체
  - `INITDB_STUB`: `-D` 디렉터리에 `PG_VERSION`, 빈 `postgresql.conf`·`pg_hba.conf` 를 만든다.
  - `pg` fixture(`bindir`, `record`, `state`, `data`)
  - `run_initdb(pg, **env)`: `PG*`·`SKIP_START`·`LISTEN_ADDRESSES` 를 지우고 주어진 값만 더한다.
  - `calls`
- `docs/notes/known-issues.md` K27: 값 반영은 "고치지 않기로 함(2026-10-17)" 이다. 이 step은 주석 줄 오탐만 고친다.

## 버그

```sh
hba_line="host $PGHBA_DB $PGHBA_USER $PGHBA_CIDR $PGAUTH_HOST"
if ! grep -qF "$hba_line" "$PGDATA/pg_hba.conf"; then
```

- `grep -qF` 는 **줄의 일부**만 같아도 맞는다. 그래서 사람이 꺼 둔 `# host molgen molgen_app 10.0.0.0/8 scram-sha-256` 이나 `#host …` 가 있으면 "이미 있음" 으로 보고 활성 줄을 더하지 않는다.
- 스크립트는 성공으로 끝난다. 원격 대역은 열리지 않는데 아무 말도 없다.
- 기대 동작: 주석이 아닌 **같은 줄 전체**가 있을 때만 건너뛴다. 없으면 지금처럼 끝에 더하고 "==> pg_hba.conf 에 추가: …" 를 찍는다.

이것은 주장이다. 먼저 재현하라.

## 작업

### 1. 테스트 먼저 (`tests/test_initdb_sh.py`)

- **RED: 주석 처리된 같은 줄이 있으면 활성 줄을 더한다**
  1. `run_initdb(pg)` 로 클러스터를 한 번 만든다(stub이 빈 `pg_hba.conf` 를 만든다).
  2. `pg["data"] / "pg_hba.conf"` 에 `# host molgen molgen_app 10.0.0.0/8 scram-sha-256\n` 을 쓴다(`encoding="utf-8", newline="\n"`).
  3. `run_initdb(pg, PGHBA_CIDR="10.0.0.0/8", PGHBA_DB="molgen", PGHBA_USER="molgen_app", PGAUTH_HOST="scram-sha-256")`
  4. 단언: returncode 0, `pg_hba.conf` 의 줄 목록에 `"host molgen molgen_app 10.0.0.0/8 scram-sha-256"` 이 **정확히 한 줄로** 있다, stdout에 "pg_hba.conf 에 추가" 가 있다.
  - **수정 전에는 줄이 없어서 실패해야 한다.**
- **회귀: 같은 활성 줄이 이미 있으면 더하지 않는다**
  - 위 값으로 두 번 돌린다. 그 줄은 한 번만 있고, 두 번째 stdout에는 "추가" 가 없다.
  - 수정 전에도 통과한다.
- `PGAUTH_HOST` 는 **항상 명시**한다. 이유: step 1이 `PGHBA_CIDR` 를 주고 `PGAUTH_HOST` 를 비우면 거부하게 바꾼다. 비워 두면 그 step에서 이 테스트가 깨진다.

### 2. 수정 (`tools/initdb.sh` hba 절)

- 줄 전체가 같은지 비교한다(`grep -qxF`).
- 바로 위 주석에 이유를 한 줄 적는다("주석 처리된 같은 줄을 있음으로 보지 않게 줄 전체를 비교한다").
- 메시지와 나머지 흐름은 그대로 둔다.

### 3. 문서

- 없다. known-issues K27 정리는 phase 마무리에서 한다.

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
   - `listen_addresses`·`port` 검사를 건드리지 않았는가?
   - 이미 있는 줄을 고치거나 지우지 않았는가(값 반영은 범위 밖)?
   - LF·실행 비트가 그대로인가?
3. 결과에 따라 `phases/9-ops-script-fixes/index.json` 의 step 0을 업데이트한다:
   - 성공 → `"status": "completed"`, `"summary": "initdb.sh hba 줄 검사를 grep -qxF(줄 전체)로: 주석 처리된 같은 줄을 있음으로 보지 않음. RED: <테스트 이름> (<단언>). 변이: -qF 로 되돌리면 <테스트> 실패. 셸 테스트 <N passed / M skipped(posix_only)>"`
   - 재현 안 됨 → `"status": "completed"`, `"summary": "not reproduced: <이유>"`
   - 수정 3회 시도 후에도 실패 → `"status": "error"`, `"error_message": "구체적 에러 내용"`
   - 사용자 개입 필요(Git Bash `sh` 없음 등) → `"status": "blocked"`, `"blocked_reason": "구체적 사유"` 후 즉시 중단

## 금지사항

- 이미 있는 `listen_addresses`·`port`·hba 줄을 새 값으로 바꾸거나 지우는 로직을 넣지 마라. 이유: K27의 "다시 돌릴 때 값 반영" 은 고치지 않기로 했다(2026-10-17, 처음 한 번 쓰는 도구).
- `^listen_addresses`·`^port` 검사를 바꾸지 마라. 이유: 이미 줄 머리에 앵커가 있어 주석 줄을 오탐하지 않는다.
- 출력 문구("==> pg_hba.conf 에 추가: …")를 바꾸지 마라. 이유: 버그 수정 중에 문구를 바꾸지 않는다(UI_GUIDE·CLAUDE.md).
- 스크립트 본문 문자열만 검사하는 테스트로 끝내지 마라. 이유: stub으로 실제 실행하는 것이 이 저장소의 셸 테스트 관례다.
- 기존 테스트를 깨뜨리지 마라.
