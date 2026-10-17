# Step 3: audit-naive-time

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

(버그 K6) 변경 이력의 시간 필터를 고친다. 대상은 `log --since`, `log --purge-before`, History 화면의 기간 콤보다. 서버 세션의 TimeZone 이 클라이언트와 달라도 맞는 줄을 고르게 한다. 고치는 곳은 `service/repo/audit.py` 한 곳이다. CLI 와 History 가 둘 다 이 저장소 클래스를 거치므로 함께 고쳐진다. **DB step 이다.**

## 읽어야 할 파일

- `/CLAUDE.md`, `/docs/ARCHITECTURE.md`, `/docs/ADR.md`(ADR-005 change_log)
- `src/genviewer/service/repo/audit.py`
  - `AuditRepository.recent` (~335-385): `since`/`until` 을 그대로 `at >= %s`/`at < %s` 에 바인드한다
  - `count_before` (~395-400), `purge` (~402-407)
- `src/genviewer/cli.py`
  - `_parse_when` (~305-322): `datetime.now() - timedelta(...)` 와 `strptime` 결과. 둘 다 naive 로컬 시각이다
  - `log` (~333-391), `_purge` (~449-458)
- `src/genviewer/controllers/history_tab.py` — `_since` (~211-216, naive 로컬 시각), `reload` 안의 `repo.recent(since=...)` (~125-140). 이 파일은 고치지 않는다
- `src/genviewer/service/schema.py` — `change_log.at TIMESTAMPTZ NOT NULL DEFAULT now()` (~127-141)
- `src/genviewer/service/pool.py` — 접속 옵션에 TimeZone 이 없다(`lock_timeout`, `statement_timeout` 만)
- `tests/test_change_log.py` — `log` fixture, `_rows`, `test_purge_removes_only_what_is_older` (~397-410)
- `tests/conftest.py` — `pg_dsn`, `db`

## 버그

- psycopg 는 tzinfo 가 없는(naive) `datetime` 을 `timestamp without time zone` 으로 보낸다.
- PostgreSQL 은 그 값을 `timestamptz` 컬럼과 비교하려고 **서버 세션의 TimeZone** 으로 해석한다.
- 클라이언트가 KST(+9)이고 서버 세션이 UTC 면, `--since 1h` 가 "9시간 뒤부터" 가 되어 아무것도 나오지 않는다.
- 같은 이유로 `--purge-before` 는 9시간 늦은 경계로 지운다(지우지 말아야 할 줄까지 지울 수 있다).
- 서버 TimeZone 이 클라이언트와 같으면 문제가 없다.

이것은 주장이다. 먼저 재현하라.

## 작업

### 1. 실패하는 테스트 (`tests/test_change_log.py`, DB 필요)

- 테스트 세션 TimeZone 을 클라이언트 로컬과 다르게 만든다.
  - 로컬 오프셋은 `datetime.now().astimezone().utcoffset()` 이다.
  - 0 이 아니면 `"UTC"`, 0 이면 `"Asia/Seoul"` 을 고른다.
  - 방법은 둘 중 하나다.
    - (a) `PGTZ` 환경변수를 `monkeypatch.setenv` 로 두고 **새** `Database(load_config(pg_dsn))` 를 연다.
    - (b) 관리자 커넥션으로 `ALTER DATABASE <current_database()> SET TimeZone = …` 를 한 뒤 새 `Database` 를 열고, `finally` 에서 `RESET TimeZone` 한다.
  - 어느 쪽이든 그 `Database` 에서 `SHOW TimeZone` 이 고른 값인지 먼저 단언한다(전제가 깨져 헛되이 통과하지 않게).
  - 다른 테스트에 설정이 새지 않게 하고, 연 `Database` 는 닫는다.
- 그 `Database` 로 이력 한 줄을 만든다(예: `ProcessRepository(db2).add("sf9z", actor="tz")`). `repo = AuditRepository(db2)` 로 다음을 단언한다.
  - `repo.recent(since=datetime.now() - timedelta(minutes=1))` 에 그 줄이 있다.
  - `repo.count_before(datetime.now() - timedelta(minutes=1)) == 0`
  - `repo.purge(datetime.now() - timedelta(minutes=1)) == 0`, 그리고 그 줄이 남아 있다.
  - `repo.count_before(datetime.now() + timedelta(minutes=1)) == 1`
- 수정 전에는 위 단언 중 하나 이상이 실패해야 한다. KST 개발 PC + UTC 세션이면 `recent` 가 비고, `purge` 가 1을 지운다. 실패한 단언을 summary에 적는다.
- 회귀
  - tz 가 붙은(aware) 시각을 넘겨도 같은 결과다.
  - 기존 `test_purge_removes_only_what_is_older`·`test_filters_narrow_the_result` 는 그대로 통과한다.

### 2. 수정 (`src/genviewer/service/repo/audit.py`)

- 시각 인자를 바인드하기 전에 naive 면 로컬 시각으로 보고 aware 로 바꾸는 작은 함수를 둔다(`dt.astimezone()`). 이미 aware 면 그대로 둔다.
- 쓰는 곳: `recent` 의 `since`·`until`, `count_before`, `purge`.
- 호출부(`cli._parse_when`, `history_tab._since`)는 바꾸지 않는다. 이유: 저장소에서 한 번 바꾸면 둘 다 고쳐지고, `history_tab.py` 는 GUI 레이어다.
- `cli._purge` 의 출력(`{when} 이전 이력 …`, `strftime`)은 그대로다.

### 3. 변이 검사

- 변환 함수가 그대로 돌려주게(naive 유지) 바꾸면 새 테스트가 실패하는지 본다. 손으로 되돌린다.

### 4. 범위 밖으로 남기는 것

- 화면과 CSV 에 찍히는 `at` 은 서버 세션 TimeZone 으로 표시된다(`format_line`, History, `log --out`). 서버가 UTC 면 UTC 로 보인다.
- 이것은 고치지 않는다. `docs/notes/known-issues.md` 의 데이터·DB 표에 다음 빈 번호(K43 등)로 새 행을 더한다.
  - 문제: "표시 시각이 서버 세션 TimeZone 기준이다"
  - 위치: `audit.format_line`, `history_tab`, `cli._write_log_csv`
  - 왜 기록만 하나: "표시가 바뀌는 동작 변경이다. 서버 TimeZone 이 KST 면 문제가 없다"
- summary 에도 적는다.

### 5. 문서

- `docs/notes/known-issues.md` 의 K6 행을 지운다(위 새 행은 남긴다).

## Acceptance Criteria

```bash
test -n "$GENDB_TEST_PG_DSN" || { echo "GENDB_TEST_PG_DSN 없음 → blocked"; exit 1; }
uv run pytest tests/test_change_log.py -q -rs   # 새 테스트 통과, DSN 사유의 SKIPPED 가 없어야 한다 (수정 전에는 실패해야 한다)
uv run ruff check src tests
uv run pytest -q -rs                             # 전체 통과, DB 테스트가 skip 되지 않았는지 본다
```

## 검증 절차

1. 위 AC 커맨드를 실행한다. `GENDB_TEST_PG_DSN` 이 없으면 아무것도 고치지 말고 blocked 로 끝낸다.
2. 아키텍처 체크리스트를 확인한다.
   - SQL 문자열이 바뀌지 않았는가(값만 aware 로)? PG 10~15 에서 그대로 돈다.
   - `controllers/` 를 고치지 않았는가?
   - 테스트가 DB 수준 설정(TimeZone)을 되돌리는가?
3. 결과에 따라 `phases/7-service-fixes/index.json` 의 step 3을 업데이트한다.
   - 성공 → `"status": "completed"`, `"summary": "audit.py: recent(since/until)·count_before·purge 가 naive 시각을 astimezone() 으로 바꿔 바인드(CLI·History 공통). RED: <테스트 이름> (<세션 TZ>, <실패한 단언>). 변이: <결과>. 표시 시각 문제는 known-issues K<번호> 로 남김. DB 테스트: <N passed>"`
   - 재현 안 됨 → `"status": "completed"`, `"summary": "not reproduced: <이유>"`
   - 수정 3회 시도 후에도 실패 → `"status": "error"`, `"error_message": "구체적 에러 내용"`
   - `GENDB_TEST_PG_DSN` 없음 → `"status": "blocked"`, `"blocked_reason": "GENDB_TEST_PG_DSN 이 없어 DB 테스트(재현)를 돌릴 수 없다"` 후 즉시 중단

## 금지사항

- 풀 접속 옵션에 `TimeZone` 을 넣어 세션 TZ 를 바꾸지 마라. 이유: 표시 시각과 `now()` 해석까지 바뀌는 동작 변경이다(승인 없음).
- 표시(`format_line`, History, CSV 의 `at`)를 로컬 시각으로 바꾸지 마라. 이유: 화면에 보이는 값이 바뀐다. known-issues 에 기록만 한다.
- `history_tab.py`·`cli._parse_when` 을 고치지 마라. 이유: 저장소 한 곳에서 고치면 충분하고, 레이어를 넘는다.
- `ALTER DATABASE … SET` 을 되돌리지 않은 채 두지 마라. 이유: 같은 세션의 다른 DB 테스트가 그 설정으로 돈다.
- 기존 테스트를 깨뜨리지 마라.
