# Step 2: pool-failure-cause

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

DB 테스트는 `tests/conftest.py` 의 `pg_dsn`(세션마다 만드는 `gendb_test_<pid>` DB 의 DSN)과 `db`(스키마가 적용된 빈 `Database`, 테스트마다 TRUNCATE) fixture를 쓴다.

## 이 step의 목적

(K3, **사용자 승인 2026-10-17**) 승인된 동작은 다음과 같다. psycopg 3.3.5 는 접속 실패에 SQLSTATE 를 싣지 않으므로, 승인 문장의 "기존 SQLSTATE 안내 문구" 대신 실제 오류의 첫 줄(비밀번호 가림)을 원인으로 보이는 것으로 사용자가 2026-10-17 확인했다.

> 풀 타임아웃이면 한 번 직접 접속해 실제 원인(비밀번호 틀림·DB 없음·접속 수 초과)을 보여준다. 실패할 때 대기가 최대 `connect_timeout`(기본 5초) 더 길어진다.

### 확인된 제약

- psycopg 3.3.5 는 접속 실패 예외에 `.sqlstate` 를 채우지 않는다(`.venv/Lib/site-packages/psycopg/generators.py` 의 `OperationalError(..., pgconn=...)`, `errors.py` 는 `info` 가 있을 때만 sqlstate 를 채운다).
- `PoolTimeout` 에는 원인(`__cause__`)이 없다.
- 그래서 `errors._BY_SQLSTATE` 의 28P01/3D000/53300 문장으로는 안내할 수 없다. 대신 **직접 접속이 낸 오류의 첫 줄**(서버·libpq 원문, scrub 거침)을 `DbUnavailableError` 의 설명으로 쓴다.
- 화면에는 지금처럼 `_UNAVAILABLE` 머리말("데이터베이스에 접속할 수 없다. 서버 상태와 접속 설정을 확인할 것.")이 나오고, 그 아래 줄이 `couldn't get a connection after 5.00 sec` 대신 실제 원인이 된다.

### 이 step 의 범위

- `Database.connection()` 을 거치는 경로(CLI 전부, `status` 의 `probe`)가 원인을 보여준다.
- GUI 의 시작·재접속은 `DeviceTabController._open_database` 가 `ping()` 의 bool 을 보고 고정 문구를 내므로 아직 바뀌지 않는다. 그쪽은 phase 11 step 1(connect-failure-cause)이 한다.
- `ping()` 은 bool 그대로 둔다.

## 읽어야 할 파일

- `/CLAUDE.md`, `/docs/ARCHITECTURE.md`(데이터 흐름 → 풀), `/docs/ADR.md`(ADR-008 일부러 거는 타임아웃, ADR-013)
- `src/genviewer/service/pool.py`
  - `Database.__init__` (~28-49): 풀에 넘기는 `kwargs`(row_factory, application_name, connect_timeout, options)
  - `connection()` (~63-81): `except psycopg.OperationalError as e: raise DbUnavailableError(str(e)) from e`
  - `ping()` (~83-90)
- `src/genviewer/service/errors.py` — `DbUnavailableError`, `_UNAVAILABLE`, `_detail`(diag 가 없으면 `str(exc)` 첫 줄을 scrub), `user_message`
- `src/genviewer/service/diagnostics.py` — `probe`(모든 예외를 `user_message` 로)
- `src/genviewer/cli.py` — `_fail`(→ `user_message`)
- `tests/test_pool.py` 전체
  - `closed_port_db` fixture(`connect_timeout=1`)
  - `_FakePool`
  - `test_closed_port_raises_db_unavailable`(`__cause__` 가 OperationalError, `"접속할 수 없다"`)
- `.venv/Lib/site-packages/psycopg_pool/pool.py` — `ConnectionPool.connection`/`getconn` 이 `PoolTimeout` 을 내는 곳 (~218, 244, 285)

## 작업

### 1. 테스트 먼저 (`tests/test_pool.py`, DB 불필요)

- **실제 원인이 보인다**: `closed_port_db` 로 `connection()` 에 들어가 `DbUnavailableError` 를 받는다. `msg = user_message(e)` 에 대해 단언한다.
  - `"couldn't get a connection"` 이 없다.
  - 직접 접속 오류의 흔적이 있다(예: `"127.0.0.1"` 또는 `"port 1"`). libpq 문구가 지역화될 수 있으니, 실제로 나오는 문구를 보고 고르고 summary에 적는다.
  - **수정 전에는 실패해야 한다.**
- **비밀번호를 가린다**: 직접 접속이 `psycopg.OperationalError('connection failed: FATAL:  password authentication failed for user "x" password=topsecret')` 를 내게 monkeypatch 한다.
  - 구현이 부르는 이름을 patch 한다. 예: `psycopg.Connection.connect` 를 classmethod 로 바꾼다. 풀도 같은 함수로 붙으니 풀은 계속 실패한다.
  - `msg` 에 `"password authentication failed"` 가 있고 `"topsecret"` 은 없다.
  - `msg` 는 `_UNAVAILABLE` 로 시작한다.
- **직접 접속은 되면 지금 문구를 둔다**: 직접 접속이 가짜 커넥션(`close()` 를 기록)을 돌려주게 patch 한다.
  - `msg` 에 지금처럼 풀의 문구가 남는다.
  - 가짜 커넥션의 `close()` 가 불렸다.
  - 풀 크기 초과처럼 서버는 멀쩡한 경우다.
- **회귀**: 기존 `test_closed_port_raises_db_unavailable`, `_FakePool` 테스트 넷, `test_ping_returns_false_on_closed_port` 가 그대로 통과한다. `with` 본문·commit 에서 난 예외는 타입 그대로 올라간다.
- (DSN 이 있으면) `pg_dsn` 의 dbname 을 없는 이름으로 바꾼 `Database` 로 붙는다. `msg` 에 서버의 "does not exist" 계열 원문이 보이는지 확인하고 summary에 적는다. 이 테스트가 있으면 `requires_pg` 나 `pg_dsn` 으로 DSN 이 없을 때 skip 되게 둔다.

### 2. 구현 (`src/genviewer/service/pool.py`)

- 풀에 넘기는 접속 인자를 `Database` 가 들고 있게 한다(예: `self._connect_kwargs`). 직접 접속도 같은 conninfo(`cfg.dsn`)와 같은 인자(`application_name`, `connect_timeout`, `options`)를 쓴다.
- `connection()` 에서 풀이 커넥션을 못 줄 때(`psycopg.OperationalError`, 대개 `PoolTimeout`):
  - 직접 접속을 **한 번** 시도한다(`connect_timeout` 그대로).
  - 그것이 `psycopg.Error` 를 내면, 그 문자열의 첫 줄을 `scrub()` 해서 `DbUnavailableError(<그 줄>)` 로 올린다.
  - 직접 접속이 성공하면 바로 닫고, 지금처럼 `DbUnavailableError(str(e))` 를 올린다.
  - 어느 쪽이든 `from e`(풀의 예외)를 유지한다. 기존 테스트가 `__cause__` 를 본다.
- 직접 접속이 낸 예외의 `.sqlstate` 가 실제로 None 인지 확인하고 summary에 적는다. 만약 값이 있으면 그 값을 쓰는 방법을 따로 만들지 말고 summary에 적기만 한다.
- `ping()` 은 bool 그대로다(이 경로를 거쳐 False).
- 불변식
  - 커넥션을 얻지 못한 것만 `DbUnavailableError` 가 된다. `with` 본문과 commit 의 예외는 타입 그대로다.
  - 직접 접속은 실패 경로에서만, 한 번만 한다.

### 3. 변이 검사

- 직접 접속 시도를 빼면 "실제 원인" 테스트가 실패하는지 본다.
- `scrub()` 을 빼면 "비밀번호" 테스트가 실패하는지 본다.
- 성공한 직접 접속을 닫지 않게 바꾸면 세 번째 테스트가 실패하는지 본다.
- 모두 손으로 되돌린다.

### 4. 문서

- README `## 에러와 로그` 에 문단 하나를 더한다.
  - "접속에 실패하면 '데이터베이스에 접속할 수 없다' 아래에 서버나 libpq 가 준 실제 이유(비밀번호가 틀렸다, 데이터베이스가 없다 등, 원문 첫 줄)가 나온다."
  - "그 이유를 알아내려고 한 번 더 붙어 보므로 실패가 최대 `connect_timeout`(기본 5초)만큼 늦게 뜬다."
  - "창의 시작·재접속 알림은 아직 이전 문구다."
- `/docs/ARCHITECTURE.md` 풀 절의 "커넥션을 얻지 못한 것(`PoolTimeout`)만 `DbUnavailableError` 가 되고" 뒤에 "(그때 한 번 직접 접속해 실제 원인을 설명으로 싣는다)" 를 붙인다.
- `docs/notes/known-issues.md` 의 K3 행을 고친다. "CLI·status 는 phase 7 에서 고침. GUI 시작·재접속 문구는 phase 11 step 1" 로 남긴다. 다 고쳐지는 것은 phase 11 이다.

## Acceptance Criteria

```bash
uv run pytest tests/test_pool.py -q -rs   # 새 테스트 통과 (수정 전에는 '실제 원인' 테스트가 실패해야 한다)
uv run ruff check src tests
uv run pytest -q
```

## 검증 절차

1. 위 AC 커맨드를 실행한다.
2. 아키텍처 체크리스트를 확인한다.
   - `service/` 가 Qt 를 import 하지 않는가?
   - `DbUnavailableError` 의 문자열에 비밀번호가 남을 길이 없는가(scrub 를 거친 첫 줄만)?
   - 성공·본문 예외 경로의 동작이 그대로인가?
3. 결과에 따라 `phases/7-service-fixes/index.json` 의 step 2를 업데이트한다.
   - 성공 → `"status": "completed"`, `"summary": "Database.connection: 풀 실패 시 직접 접속 1회, 실패 문구 첫 줄(scrub)을 DbUnavailableError 설명으로. 성공하면 닫고 기존 문구. ping 은 bool 유지, GUI 는 phase 11. 직접 접속 예외 sqlstate=<관찰값>. 처음 실패한 테스트: <이름과 단언>. 변이: <결과>. DB 테스트: <N passed | 안 돎(DSN 없음)>"`
   - 수정 3회 시도 후에도 실패 → `"status": "error"`, `"error_message": "구체적 에러 내용"`
   - 사용자 개입 필요 → `"status": "blocked"`, `"blocked_reason": "구체적 사유"` 후 즉시 중단

## 금지사항

- `PoolTimeout` 대신 직접 접속의 `OperationalError` 를 그대로 올리지 마라. 이유: "커넥션을 얻지 못한 것은 `DbUnavailableError`" 가 계약이다. 호출부(`ping`, GUI `connect_db`, `probe`)가 그 타입을 본다.
- 실패 원인을 알아내려고 여러 번 다시 붙거나 기다리지 마라. 이유: 승인된 대기는 최대 `connect_timeout` 한 번이다.
- `_BY_SQLSTATE` 를 고치거나 영어 원문을 해석해 문장을 만들지 마라. 이유: 서버 메시지는 `lc_messages` 에 따라 바뀌고, 승인 범위 밖이다.
- `ping()` 의 반환 타입이나 `DeviceTabController._open_database` 를 바꾸지 마라. 이유: GUI 쪽은 phase 11 step 1 의 일이다.
- 기존 테스트를 깨뜨리지 마라.
