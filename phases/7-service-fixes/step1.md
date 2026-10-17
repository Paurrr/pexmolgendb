# Step 1: status-dsn-override

## 배경 (phase 7 공통)

이 저장소는 이미 여러 명이 쓰는 도구다. 평소에는 **에러·버그만 고친다**(CLAUDE.md, ADR-015). phase 7은 2026-10-17 `docs/notes/known-issues.md` 분류에서 Qt를 쓰지 않는 계층(`cli.py`, `service/`, `service/repo/`, `utils/exporter.py`, `utils/lisp.py`)에 남은 항목을 한 step에 하나씩 처리한다. 항목은 두 종류다.

- **버그**(승인 없이 고친다): K31, K6, K5, K9, K13. 분석에서 나온 **주장**이다. 재현부터 한다.
- **사용자가 승인한 동작 변경**(2026-10-17): K1, K3, K10, K32, K12. step 파일에 적힌 승인 문장대로만 바꾼다. 새 동작을 단언하는 테스트를 먼저 쓰고 실패를 본 뒤 구현한다(TDD).

모든 step에 같은 규칙이 적용된다.
1. 버그 step: 실패하는 테스트로 먼저 재현하고 RED 출력(테스트 이름과 실패한 단언)을 summary에 적는다. RED는 **Windows 개발 PC에서** 보여야 한다. `posix_only` 테스트는 개발 PC에서 skip되므로 버그를 증명하지 못한다.
2. 재현되지 않으면 `src/` 를 고치지 않는다. 테스트는 특성 테스트로 남기고 `"status": "completed"`, `"summary": "not reproduced: <이유>"` 로 끝낸다.
3. 고친 뒤 수정을 손으로 되돌려 새 테스트가 실패하는지 보고 다시 고친다(변이 검사). `git checkout`/`git stash` 로 되돌리지 마라. 이유: 같은 step의 테스트 변경까지 사라진다.
4. 승인 step: 승인 문장 밖의 동작(기존 문구, 종료 코드, 다른 명령)을 바꾸지 않는다. 새 문구는 그 step 파일에 적힌 것만 쓴다.
5. DB step(3·4·5·6·7): `GENDB_TEST_PG_DSN`(관리자 DSN)이 있어야 한다. 없으면 코드를 고치지 말고 `"status": "blocked"` 로 멈춘다. DB 테스트가 skip된 것은 통과가 아니다(`-rs` 로 확인한다). SQL은 PostgreSQL 10~15에서 돌아야 하고, 식별자는 `psycopg.sql` 과 `schema.TABLE_COLUMNS`/`child_tables()` 로만 조립하며, 값은 바인드 파라미터로만 넘긴다. 쓰기는 `device.version` 잠금과 `change_log` 기록을 같은 트랜잭션에서 한다.
6. 고쳤으면 `docs/notes/known-issues.md` 에서 그 K 행을 지운다(재현 안 됐으면 남기고 summary에 적는다). 사용자에게 보이는 동작이 바뀌면 README 의 해당 절을 고친다. CLAUDE.md 의 테스트 기준선 숫자는 고치지 않는다(phase 마무리에서 고친다).
7. 이 파일의 행 번호는 2026-10-17(phase 5 직후) 기준 대략값이다. 앞 step 이 같은 파일을 바꿨을 수 있다(`cli.py`: step 0·1·4, `service/pool.py`: 2, `repo/audit.py`: 3·4·6·7, `repo/io.py`: 5·6). 이름으로 찾고, 앞 step 의 summary(`phases/7-service-fixes/index.json`)를 먼저 읽어라.
8. 비밀번호를 화면·로그·argv에 남기지 마라. 예외 문구는 `user_message(exc)`, DSN·접속 문자열은 `utils.logs.scrub()` 을 거친다(CLAUDE.md CRITICAL).
9. 경계는 테스트가 지킨다(phase 6). `tests/test_boundaries.py` 는 Qt 금지 구역(이 phase 가 고치는 `cli.py`·`service/`·`utils/exporter.py`·`utils/lisp.py` 전부)이 PySide6·티어 3·4 모듈을 import 하지 않는지(함수 안 import 포함)를, `tests/test_py39_compat.py` 는 init_db 에서 닿는 모듈의 Python 3.9 호환을 본다. 새 import 가 이 테스트를 깨면 import 를 다시 생각한다. 이 두 테스트와 `tests/fixtures/imports.py` 를 고쳐서 통과시키지 마라. 이유: CLAUDE.md CRITICAL 경계 규칙을 지키는 그물이다.

DB 테스트는 `tests/conftest.py` 의 `pg_dsn`(세션마다 만드는 `gendb_test_<pid>` DB 의 DSN)과 `db`(스키마가 적용된 빈 `Database`, 테스트마다 TRUNCATE) fixture를 쓴다.

## 이 step의 목적

(K1, **사용자 승인 2026-10-17**) 승인된 동작은 다음과 같다.

> `--dsn`/`GENDB_PG_DSN` 을 주면 `status` 도 다른 명령처럼 설정 파일을 읽지 않는다. 그러면 `status` 가 다른 명령에서 실제로 일어나는 일(비밀번호 없음·접속 실패)을 보여준다.

`--check-config` 는 승인 범위가 아니다. 이 step 에서 바꾸지 않는다(사용자가 2026-10-17 "status 만" 으로 확인했다. `--check-config` 는 설정 파일을 읽어 보여주는 진단 명령이라 지금 동작을 둔다).

## 읽어야 할 파일

- `/CLAUDE.md`, `/docs/ADR.md`(ADR-007 접속 설정은 .env 파일 하나), `/docs/ARCHITECTURE.md`(데이터 흐름 → 접속 설정)
- `src/genviewer/service/config.py`
  - `resolve_dsn` (~53-79): `--dsn` 이나 `GENDB_PG_DSN` 이 있으면 `env_file.load` 를 **부르지 않고** 바로 돌려준다
  - `load_config` (~82-102)
- `src/genviewer/service/diagnostics.py`
  - `ConfigInfo` (~39-51)
  - `inspect_config` (~54-83): 첫 줄에서 항상 `env_file.load` 를 부른다(`os.environ.setdefault` 로 파일 값을 환경에 넣는다)
  - `config_lines` (~86-100)
- `src/genviewer/service/env_file.py` — `load`(찾은 파일 하나를 읽어 `os.environ.setdefault`), `SECRET_KEYS`, `libpq_env_present`
- `src/genviewer/cli.py`
  - `status` (~160-203): `inspect_config()` 를 먼저 부르고, 그다음 `load_config(override)`. override 는 `dsn or ctx.obj` 이고 `GENDB_PG_DSN` 환경변수는 보지 않는다
  - `_open` (~141-152): 다른 명령은 `load_config` 만 부른다
  - `_print_config` (~126-138): `--check-config`. 바꾸지 않는다
- `tests/test_cli.py`
  - `isolated` fixture (~46-64)
  - `test_status_without_connection_info_says_where_to_look`, `test_no_password_reaches_the_output`, `test_status_reports_the_schema_and_the_row_counts`
- `README.md` — `### 일회성으로 다른 데 붙기` 의 "(예외로 `status` 와 `--check-config` 는 …)" 문단 (~123-127)

## 지금 동작

- `genviewer processes --dsn X` 는 `resolve_dsn` 이 설정 파일을 읽지 않으므로, 파일의 `PGPASSWORD` 가 쓰이지 않는다.
- `genviewer status --dsn X` 는 `inspect_config()` 가 파일을 먼저 읽는다.
  - 그래서 `PGPASSWORD` 가 환경에 들어가 libpq 가 그것으로 붙는다.
  - `적용된 값:` 에 `PGPASSWORD=(설정됨)` 이 찍힌다.
- 같은 인자인데 `status` 는 붙고 다른 명령은 비밀번호가 없다고 한다. `GENDB_PG_DSN` 환경변수로 줘도 같다.

## 작업

### 1. 테스트 먼저 (`tests/test_cli.py`, DB 불필요)

준비
- `tmp_path` 에 설정 파일을 만든다: `PGHOST=127.0.0.1`, `PGPORT=1`, `PGPASSWORD=from_file_secret`.
- `GENDB_CONFIG` 로 그 파일을 가리키고, `GENDB_PG_CONNECT_TIMEOUT=1` 로 둔다(닫힌 포트라 빨리 끝나게).
- `isolated` 처럼 `PG*`/`GENDB_PG_DSN` 을 비운다.
- **환경을 흘리지 마라.** `env_file.load` 는 `os.environ.setdefault` 로 값을 넣는다. `monkeypatch.delenv(k, raising=False)` 만으로는 테스트가 넣은 키를 끝나고 지우지 않는다. 다음 중 하나로 반드시 원래대로 돌린다.
  - 파일이 넣을 키마다 `monkeypatch.setenv(k, "x")` 뒤 `monkeypatch.delenv(k)` 를 한다(끝날 때 "없음" 으로 되돌린다).
  - `os.environ` 을 사본으로 바꾼다.

테스트
- **`--dsn` (새 동작)**: `status --dsn "host=127.0.0.1 port=1 dbname=x user=x"` 를 돌린다.
  - 출력에 `PGPASSWORD=(설정됨)` 이 없다.
  - 첫 줄이 `설정 파일: (읽지 않음 - --dsn 또는 GENDB_PG_DSN 이 있다)` 이다.
  - 종료 코드는 1이다(닫힌 포트).
  - 실행 뒤 `os.environ` 에 `PGPASSWORD` 가 없다. `processes --dsn …` 를 돌렸을 때와 같은 환경이다.
  - **수정 전에는 실패해야 한다.**
- **`GENDB_PG_DSN` (새 동작)**: 같은 DSN 을 `GENDB_PG_DSN` 환경변수로 주고 `status` 를 돌린다. 기대값은 위와 같다. **수정 전에는 실패해야 한다.**
- **회귀 — override 없음**: 같은 설정 파일만 있을 때 `status` 는 지금처럼 파일을 읽는다.
  - `<-- 이것` 표시와 `PGPASSWORD=(설정됨)` 이 보인다.
  - 수정 전에도 통과해야 한다.
- 기존 `test_no_password_reaches_the_output`, `test_status_without_connection_info_says_where_to_look` 이 그대로 통과한다.

### 2. 구현

- `diagnostics.inspect_config(explicit: str = "", *, read_file: bool = True) -> ConfigInfo`
  - `read_file=False` 면 `env_file.load` 를 부르지 않는다.
  - 그때 `used=None`, `searched=[]` 이고, 나머지 값(`values`, `secrets`, `has_connection_info`)은 지금처럼 `os.environ` 에서 모은다.
  - 파일을 일부러 읽지 않았다는 것을 `ConfigInfo` 에 남긴다(예: `file_skipped: bool = False`).
- `diagnostics.config_lines(info)`
  - 파일을 읽지 않았으면 첫 줄을 `설정 파일: (읽지 않음 - --dsn 또는 GENDB_PG_DSN 이 있다)` 로 쓴다.
  - 그때는 `찾아본 곳:` 블록을 내지 않는다.
  - 그 밖의 줄(`적용된 값:`, `로그 파일:`)은 그대로다.
- `cli.status`
  - override 는 `dsn or ctx.obj or os.environ.get(DSN_ENV, "")` 로 정한다(공백 제거).
  - 그것이 있으면 `inspect_config(read_file=False)` 로 부른다.
  - 그 뒤 흐름(`접속 대상:`, probe, 종료 코드, 문구)은 그대로다.
- 불변식: **같은 인자와 환경이면 `status` 와 `processes`/`load`/`export`/`log` 가 같은 설정을 본다.** 판단 기준은 `resolve_dsn` 과 같다(`--dsn` 또는 `GENDB_PG_DSN` 이 있으면 파일을 읽지 않는다).
- `_print_config`(`--check-config`)는 바꾸지 않는다.

### 3. 변이 검사

- `status` 의 override 판단에서 `GENDB_PG_DSN` 을 빼면 두 번째 테스트가 실패하는지 본다.
- `read_file=False` 를 무시하게 바꾸면 첫 테스트가 실패하는지 본다.
- 둘 다 손으로 되돌린다.

### 4. 문서

- README `### 일회성으로 다른 데 붙기` 의 괄호 문단에서 `status` 를 빼고 `--check-config` 만 남긴다. 예: "(예외로 `--check-config` 는 진단을 위해 파일을 먼저 읽는다 — …)".
- README `## 명령줄` 의 `--dsn` 항목("이때는 `genviewer.env` 를 읽지 않는다")은 이제 `status` 에도 맞다. 지금 문장을 그대로 둔다.
- `docs/notes/known-issues.md` 의 K1 행은 지우지 말고 남은 부분으로 고친다.
  - 문제: "`--check-config` 는 `--dsn`·`GENDB_PG_DSN` 이 있어도 설정 파일을 읽는다(status 는 2026-10-17 phase 7 에서 고침)"
  - 왜 기록만 하나: "승인 범위 밖"

## Acceptance Criteria

```bash
uv run pytest tests/test_cli.py -q        # 새 테스트 통과 (수정 전에는 --dsn·GENDB_PG_DSN 테스트가 실패해야 한다)
uv run ruff check src tests
uv run pytest -q
```

## 검증 절차

1. 위 AC 커맨드를 실행한다.
2. 아키텍처 체크리스트를 확인한다.
   - `diagnostics.py` 가 값으로 비밀번호를 내지 않는가(화이트리스트 유지)?
   - `cli.py` 모듈 수준에 PySide6 import 가 없는가?
   - 테스트가 끝난 뒤 `os.environ` 에 파일 값이 남지 않는가(같은 세션의 다른 테스트를 돌려 확인한다)?
3. 결과에 따라 `phases/7-service-fixes/index.json` 의 step 1을 업데이트한다.
   - 성공 → `"status": "completed"`, `"summary": "status: --dsn/GENDB_PG_DSN 이면 inspect_config(read_file=False), 첫 줄 '설정 파일: (읽지 않음 - …)'. --check-config 불변. 처음 실패한 테스트: <이름과 단언>. 변이: <결과>. README·known-issues K1 고침. DB 테스트: <N passed | 안 돎(DSN 없음)>"`
   - 수정 3회 시도 후에도 실패 → `"status": "error"`, `"error_message": "구체적 에러 내용"`
   - 사용자 개입 필요 → `"status": "blocked"`, `"blocked_reason": "구체적 사유"` 후 즉시 중단

## 금지사항

- 다른 명령(`processes`/`load`/`export`/`log`, GUI)이 설정 파일을 읽게 바꾸지 마라. 이유: `--dsn` 으로 다른 서버에 붙을 때 팀 비밀번호가 그 서버로 간다. 사용자가 그 방향은 거절했다.
- `--check-config` 를 바꾸지 마라. 이유: 승인 범위가 `status` 다.
- `status` 의 다른 줄 문구(`접속 대상:`, `접속: 됨/안 됨`, `스키마: …`, `내용: …`)와 종료 코드를 바꾸지 마라. 이유: 스크립트가 `if genviewer status` 로 쓴다(README).
- `config_lines` 에 비밀번호 값을 내지 마라. 이유: 화면 캡처와 로그로 샌다.
- 기존 테스트를 깨뜨리지 마라.
