# Step 1: hba-trust-refuse

## 배경 (phase 9 공통)

이 저장소는 이미 여러 명이 쓰는 도구다. 지금은 **에러·버그만 고친다**(CLAUDE.md, ADR-015). phase 9는 운영 셸 스크립트(`tools/initdb.sh`, `tools/deploy.sh`)의 알려진 문제(`docs/notes/known-issues.md` K26~K29)를 하나씩 고친다. K26 하나만 버그가 아니라 **사용자가 2026-10-17 승인한 동작 변경**이다(이 step).

셸 스크립트 테스트는 진짜 `sh`·`git` 으로 스크립트를 실행한다.
- PATH 앞(`initdb.sh` 는 `PGBIN`)에 둔 stub 명령이 받은 인자를 파일에 기록하고, 테스트는 그 기록과 결과 파일을 단언한다.
- 본보기는 `tests/test_initdb_sh.py`, `tests/test_deploy_sh.py` 다.
- 스크립트 본문의 토큰 검사만으로 끝내지 않는다.
- 개발 PC는 Windows이고, 이 테스트는 **Git Bash의 `sh`** 로 돈다. `sh` 가 PATH에 없으면(PowerShell) 두 파일이 통째로 skip된다(CLAUDE.md 기준선: 셸 스크립트 테스트 20개).

모든 step에 같은 규칙이 적용된다.
1. "버그"는 **분석 에이전트의 주장**이다. 먼저 실패하는 테스트로 재현하고, RED 출력(테스트 이름과 실패한 단언)을 summary에 적는다.
   - K26(이 step)은 승인된 동작 변경이라 "버그" 대신 "승인된 동작 변경" 절이 있다. 그래도 테스트를 먼저 쓰고 수정 전 실패를 본다.
2. RED는 **Windows 개발 PC에서**(Git Bash `sh`) 보여야 한다.
   - `posix_only` 테스트는 개발 PC에서 skip되므로 증명이 되지 않는다.
   - `sh`/`git` 이 없어서 skip된 테스트도 RED가 아니다. AC의 `-rs` 출력에 그런 skip이 보이면 성공이 아니다.
3. 재현되지 않으면 `tools/`·`src/` 를 고치지 않는다. 테스트는 특성 테스트로 남기고 `"status": "completed"`, `"summary": "not reproduced: <이유>"` 로 끝낸다.
4. 고친 뒤 수정을 손으로 되돌려 새 테스트가 실패하는지 확인하고 다시 고친다(변이 검사). `git checkout`/`git stash` 로 되돌리지 마라. 이유: 같은 step의 테스트 변경까지 사라진다.
5. `tools/*.sh` 는 LF와 실행 비트(100755)를 지킨다(`.gitattributes`, CLAUDE.md). Edit 도구가 줄 끝을 바꾸지 않았는지 AC의 `git ls-files --eol` 로 본다.
6. PostgreSQL을 쓰지 않는다. 하네스 규칙 12(DB 테스트 필수)는 해당하지 않는다.
7. 이 파일의 행 번호는 2026-10-18(phase 8 직후) 기준 대략값이다. 이름으로 찾아라.
8. step 순서는 다음과 같다.
   - 0: pg_hba 주석 줄 오탐(K27 일부)
   - 1: `PGHBA_CIDR` + 기본 trust 거부(K26, 승인, 이 step)
   - 2: `src/.git` 권한(K28)
   - 3: 없는 `DEPLOY_COMMANDS`(K29)

## 이 step의 목적

`PGHBA_CIDR` 로 원격 대역을 열면서 `PGAUTH_HOST` 를 정하지 않으면, 지금은 기본값 `trust` 가 그 대역 전체를 **인증 없이** 연다. 이런 실행을 거부하게 한다.

## 승인된 동작 변경 (사용자 승인 2026-10-17)

> initdb.sh 에 `PGHBA_CIDR` 를 주고 `PGAUTH_HOST` 를 안 주면(기본 trust) 거부하고 멈춤. 지금은 그 대역 전체가 무인증.

정확한 동작은 아래와 같다.

| `PGHBA_CIDR` | `PGAUTH_HOST` | 동작 |
|---|---|---|
| 비었음 | 아무거나(비었음 포함) | 지금과 같다. 기본값 `trust` 는 루프백에만 쓰인다(개발 기본값, README 표 1행) |
| 있음 | 비었음(정의 안 됨 또는 빈 문자열) | **거부.** stderr에 안내, exit 1. initdb·`postgresql.conf`/`pg_hba.conf` 수정·pg_ctl·createdb 어느 것도 하지 않는다 |
| 있음 | `trust` 를 **명시** | 지금과 같다(사용자가 고른 것이다) |
| 있음 | `scram-sha-256` 등 | 지금과 같다 |

- 이미 클러스터가 있는 다시 돌리기에도 같은 규칙이다.
- 거부 판단은 스크립트 맨 앞, 기본값을 채우기 **전의** 원래 값으로 한다. 지금은 `PGAUTH_HOST="${PGAUTH_HOST:-trust}"` 가 빈 값을 trust로 바꾼다.
- 안내 문구(정확히 이 문장, 두 줄):
  ```
  오류: PGHBA_CIDR 를 주면 PGAUTH_HOST 도 정해야 한다(예: PGAUTH_HOST=scram-sha-256).
        기본값 trust 는 그 대역 전체를 인증 없이 연다. 정말 그러려면 PGAUTH_HOST=trust 로 명시할 것.
  ```

## 읽어야 할 파일

- `/CLAUDE.md`, `/docs/ADR.md` ADR-010(role 두 개, peer + scram)
- `/README.md` '서버' 절의 "1. 클러스터"(~639-677)
  - 호출 예시가 이미 `PGAUTH_HOST=scram-sha-256` 와 `PGHBA_CIDR` 를 함께 쓴다(~646-650).
  - 그 아래에 인증 표가 있다.
- `tools/initdb.sh`
  - 머리 주석(~1-13)
  - 기본값 목록(~16-27, `PGAUTH_HOST="${PGAUTH_HOST:-trust}"` ~24, `PGHBA_CIDR` ~25)
  - initdb 호출(~46, `--auth-host="$PGAUTH_HOST"`)
  - hba 절(~61-73, step 0이 `grep -qxF` 로 바꿨다)
  - createdb 실패 출력 형식(~107, `echo "   실패: $err" >&2`)
- `tests/test_initdb_sh.py`
  - `pg` fixture, `run_initdb`(`PG*` 환경변수를 모두 지우므로 `PGAUTH_HOST` 는 주지 않으면 정의되지 않는다), `calls`
  - step 0이 더한 hba 테스트들(`PGAUTH_HOST` 를 명시한다)
- 이전 step에서 수정된 파일: `tools/initdb.sh`(hba 검사 `grep -qxF`), `tests/test_initdb_sh.py`

## 작업

### 1. 테스트 먼저 (`tests/test_initdb_sh.py`)

- **RED: CIDR만 주면 거부한다**
  - `run_initdb(pg, PGHBA_CIDR="10.0.0.0/8")`
  - 단언
    - returncode 1
    - stderr에 `PGAUTH_HOST` 와 `trust` 가 있다
    - `pg["record"]` 가 없다(stub이 하나도 불리지 않았다)
    - `pg["data"]` 가 만들어지지 않았다
  - **수정 전에는 returncode 0 이고 hba 줄이 `… trust` 로 더해져서 실패해야 한다.**
- **RED: 이미 있는 클러스터에 다시 돌려도 거부한다**
  - `run_initdb(pg)` 로 만든 뒤 `PGHBA_CIDR="10.0.0.0/8"` 만 주고 다시 돌린다.
  - returncode 1, `pg_hba.conf` 는 그대로(빈 파일)다.
- **빈 문자열도 정하지 않은 것으로 본다**: `PGAUTH_HOST=""` + CIDR → 거부.
- **회귀: 명시한 trust 는 허용한다**
  - `PGAUTH_HOST="trust"` + CIDR → returncode 0, `pg_hba.conf` 에 `host all all 10.0.0.0/8 trust` 한 줄.
  - 수정 전에도 통과한다.
- **회귀: scram 은 그대로다**: `PGAUTH_HOST="scram-sha-256"` + CIDR → returncode 0.
- **회귀: CIDR 없이 PGAUTH_HOST 도 없으면 지금처럼 된다**: 기존 테스트(`test_a_second_run_on_a_running_cluster_succeeds` 등)가 그대로 통과한다. initdb stub 기록의 `--auth-host=trust` 도 단언한다.

### 2. 수정 (`tools/initdb.sh`)

- 기본값 목록의 `PGAUTH_HOST` 줄보다 **앞에서** 원래 값으로 검사하고 거부한다(위 표).
- 위 문구를 그대로 `>&2` 로 찍고 `exit 1` 한다.
- 검사 위에 이유를 주석으로 적는다(K26: 기본값 trust 가 원격 대역 전체를 무인증으로 연다. 명시한 trust 는 사용자의 선택이라 허용한다).
- 머리 주석 "조절할 수 있는 값은 아래 기본값 목록이 전부다." 근처에 이 거부 규칙을 한 줄 더한다.

### 3. 문서

- `README.md` '서버' 절 "1. 클러스터" 의 호출 예시 바로 아래에 한 문장을 더한다.
  - 예: "`PGHBA_CIDR` 를 주면서 `PGAUTH_HOST` 를 비워 두면 스크립트가 거부한다. 기본값 `trust` 는 그 대역을 인증 없이 열기 때문이다(꼭 그래야 하면 `PGAUTH_HOST=trust` 로 명시한다)."
- 인증 표의 `trust | trust` 행 설명("개발 기본값. 원격이 무인증 — 공유 서버엔 불가")은 그대로 둔다.
- known-issues K26 정리는 phase 마무리에서 한다.

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
   - 거부가 initdb·설정 파일 수정보다 먼저 일어나는가(stub 기록이 비어 있는가)?
   - CIDR 없는 개발 기본 경로(루프백 trust)가 그대로인가?
   - 명시한 `PGAUTH_HOST=trust` 가 여전히 되는가?
   - LF·실행 비트가 그대로인가?
3. 결과에 따라 `phases/9-ops-script-fixes/index.json` 의 step 1을 업데이트한다:
   - 성공 → `"status": "completed"`, `"summary": "initdb.sh: PGHBA_CIDR 가 있고 PGAUTH_HOST 가 비었으면 무엇도 하기 전에 exit 1(명시한 trust 는 허용, 승인 2026-10-17). RED: <테스트 이름> (<단언>). 변이: 검사를 지우면 <테스트> 실패. README 서버 절 한 문장. 셸 테스트 <N passed / M skipped(posix_only)>"`
   - 수정 3회 시도 후에도 실패 → `"status": "error"`, `"error_message": "구체적 에러 내용"`
   - 사용자 개입 필요(Git Bash `sh` 없음 등) → `"status": "blocked"`, `"blocked_reason": "구체적 사유"` 후 즉시 중단

## 금지사항

- `PGAUTH_HOST` 의 기본값을 `scram-sha-256` 등으로 바꾸지 마라. 이유: 승인된 것은 "거부" 다. 기본값을 바꾸면 CIDR 없는 개발 클러스터(Windows는 유닉스 소켓이 없어 루프백 trust)가 비밀번호를 요구하게 된다.
- 명시한 `PGAUTH_HOST=trust` 를 거부하지 마라. 이유: 승인 범위는 "안 주면" 이다.
- `PGAUTH_LOCAL` 에 같은 규칙을 넣지 마라. 이유: 승인 범위 밖이다(local 은 원격 대역과 무관하다).
- 위 안내 문구를 다른 말로 바꾸거나 기존 출력 문구를 고치지 마라. 이유: 문구는 step 파일에 정한 대로 둔다(UI_GUIDE·CLAUDE.md).
- step 0의 hba 테스트에서 `PGAUTH_HOST` 를 빼지 마라. 이유: 그 테스트는 이 거부와 무관한 주석 줄 오탐을 본다.
- 기존 테스트를 깨뜨리지 마라.
