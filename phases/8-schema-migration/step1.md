# Step 1: status-columns

## 배경 (phase 8 공통)

이 저장소는 평소에 **에러·버그만 고친다**(CLAUDE.md, ADR-015). phase 8은 예외로 **사용자가 2026-10-17 승인한 기능**이다(known-issues K7, architecture-proposal P7). 승인된 내용은 다음과 같다.

> init_db 가 기존 탭 테이블에 빠진 컬럼을 `ADD COLUMN IF NOT EXISTS`(PG 9.6+)로 더하고, `status` 가 컬럼까지 확인한다. `tab_config.json` 에 컬럼을 더해도 저장이 42703 으로 죽지 않게 된다.

step 0 이 init_db 쪽(`schema.postgres_all_ddl()` 의 컬럼 더하기)을 했다. 이 step 은 `status` 쪽이다.

모든 step에 같은 규칙이 적용된다.
1. 기능이라 TDD 로 한다. 새 동작을 단언하는 테스트를 먼저 쓰고 실패를 본 뒤 구현한다. 처음 실패한 테스트 이름과 단언을 summary에 적는다.
2. 구현을 손으로 망가뜨려 새 테스트가 실패하는지 보고 손으로 되돌린다(변이 검사). `git checkout`/`git stash` 로 되돌리지 마라. 이유: 같은 step의 테스트 변경까지 사라진다.
3. **DB step 이다.** `GENDB_TEST_PG_DSN`(관리자 DSN)이 없으면 코드를 고치지 말고 `"status": "blocked"` 로 멈춘다. DB 테스트가 skip된 것은 통과가 아니다(`-rs` 로 확인한다).
4. SQL은 PostgreSQL 10~15에서 돌아야 한다(운영은 RHEL 7 + PG 15). 식별자는 `psycopg.sql.Identifier` 와 `schema.child_tables()`/`TABLE_COLUMNS` 로만 만든다. PG 16+ 문법을 쓰지 않는다.
5. `service/schema.py`, `scripts/init_db.py`, `config/config.py`, `scripts/__init__.py` 는 **Python 3.9 에서 import 되어야 한다**(CLAUDE.md CRITICAL, ADR-014). `service/diagnostics.py` 는 init_db 가 import 하지 않으므로 3.13 문법이어도 된다.
6. `config/tab_config.json` 의 키 구조를 바꾸지 않는다.
7. 이 파일의 행 번호는 2026-10-18(phase 7 직후) 기준 대략값이다. 이 phase 의 step 0 이 끝난 뒤의 코드이니 이름으로 찾아라.
8. 사용자에게 보이는 동작이 바뀌면 README·ADR 의 해당 절을 고친다. CLAUDE.md 의 테스트 기준선 숫자는 고치지 않는다(phase 마무리에서 고친다).

DB 테스트는 `tests/conftest.py` 의 `pg_dsn`, `db` fixture 를 쓴다. `db` 는 테스트마다 `postgres_all_ddl()` 을 전부 실행한 뒤 TRUNCATE 한다(step 0 뒤로는 빠진 컬럼도 되살린다).

## 이 step의 목적

`genviewer status` 가 테이블이 있는지뿐 아니라 **탭 테이블에 `tab_config.json` 의 컬럼이 다 있는지**까지 확인하게 한다.
- 빠졌으면 무엇이 빠졌는지 보이고, `genviewer-init-db` 를 다시 돌리라고 하고, 종료 코드 1 로 끝낸다.
- 지금은 테이블이 있으면 "모두 있음" 이라고 해서, 컬럼이 빠진 DB 에서도 status 는 정상인데 저장만 42703 으로 죽는다.

## 읽어야 할 파일

- `/CLAUDE.md`, `/docs/ADR.md`(ADR-003), `/docs/ARCHITECTURE.md`(스키마 절의 `diagnostics.expected_tables`)
- `phases/8-schema-migration/index.json` — step 0 summary
- `src/genviewer/service/diagnostics.py`
  - `expected_tables` (~136-138)
  - `ServerInfo` (~141-156): `missing_tables`, `schema_ready`
  - `probe` (~159-204): `pg_class` 에서 테이블 이름을 다 받아 Python 에서 비교한다(`name` 타입과 `text[]` 비교 주석). 예외를 내지 않는다
- `src/genviewer/cli.py` — `status` (~162-207): `missing_tables` 가 있으면 두 줄과 `Exit(1)`, 없으면 `스키마: 테이블 N개 모두 있음`
- `src/genviewer/service/schema.py` — `child_tables()`, step 0 이 더한 컬럼 더하기 함수
- `tests/test_cli.py`
  - `test_status_reports_the_schema_and_the_row_counts`
  - `test_status_points_at_init_db_when_a_table_is_missing`(docstring: 테스트가 지운 것을 다음 fixture 가 되살릴 수 있어야 한다)
  - `isolated` fixture
- `README.md` — `## 명령줄` 의 status 예시와 항목들

## 작업

### 1. 테스트 먼저

**`tests/test_cli.py` (DB 필요)**
- **컬럼이 빠지면 알린다**
  - 탭 테이블 하나의 마지막 payload 컬럼을 `ALTER TABLE … DROP COLUMN` 한다.
  - `status --dsn <pg_dsn>` 을 돌린다(`isolated` 와 함께).
  - 종료 코드가 1이다.
  - 출력에 `스키마: 컬럼 1개가 없다 (<테이블>.<컬럼>)` 이 있다.
  - 출력에 `genviewer-init-db 를 다시 실행할 것.` 이 있다.
  - `finally` 에서 `schema.postgres_all_ddl()` 을 실행해 되살린다.
  - **구현 전에는 실패해야 한다**(지금은 "모두 있음" 으로 0).
- **둘 이상 빠지면 개수와 이름을 모두 보인다.** 순서는 `tab_config.json` 순서, 그 안에서는 컬럼 순서다.
- **회귀**
  - `test_status_reports_the_schema_and_the_row_counts` 의 `모두 있음`, `process 2개, device 3개` 가 그대로다.
  - 테이블이 통째로 없을 때(`test_status_points_at_init_db_when_a_table_is_missing`)는 지금 문구가 먼저 나온다. 없는 테이블의 컬럼을 "빠진 컬럼" 으로 세지 않는다.

**`tests/test_schema.py` 또는 진단 단위 (DB 필요, 선택)**
- `diagnostics.probe(db)` 가 돌려준 `ServerInfo` 의 빠진 컬럼 목록과 `schema_ready` 를 직접 본다.

### 2. 구현

- `diagnostics.ServerInfo` 에 빠진 컬럼 목록 필드를 더한다. 예: `missing_columns: list[str]`, 원소는 `"<테이블>.<컬럼>"`.
- `schema_ready` 는 그것까지 비어 있어야 True 다.
- `diagnostics.probe`
  - 있는 탭 테이블에 대해 현재 스키마의 컬럼 이름을 카탈로그에서 읽는다. `pg_attribute` + `pg_class` + `pg_namespace`, `attnum > 0`, `NOT attisdropped` 를 쓴다.
  - `information_schema.columns` 는 권한이 없는 컬럼을 숨기므로 쓰지 않는다.
  - 이름은 다 받아서 Python 에서 비교한다(`name` 타입 주석과 같은 이유).
  - 기대값은 `child_tables()` 다.
  - 여전히 예외를 내지 않는다.
- `cli.status`
  - 테이블 검사 다음, "모두 있음" 줄 앞에서 빠진 컬럼이 있으면 두 줄을 내고 `Exit(1)` 한다.
    - `스키마: 컬럼 {n}개가 없다 ({목록, ", " 로 이음})`
    - `genviewer-init-db 를 다시 실행할 것.`(stderr)
  - 없으면 지금 그대로다.
- 다른 줄의 문구와 순서는 바꾸지 않는다.

### 3. 변이 검사

- `probe` 가 빠진 컬럼을 늘 빈 목록으로 내게 하면 새 테스트가 실패하는지 본다.
- `attisdropped` 조건을 빼면(지운 컬럼이 남아 보이면) "빠지면 알린다" 가 실패하는지 본다.
- 둘 다 손으로 되돌린다.

### 4. 문서

- README `## 명령줄` 항목에 한 줄을 더한다. "`status` 는 탭 테이블의 컬럼까지 본다. `tab_config.json` 에 컬럼을 더하고 init-db 를 안 돌렸으면 빠진 컬럼을 보여주고 `1` 로 끝난다."
- `/docs/ARCHITECTURE.md` 스키마 절의 `diagnostics.expected_tables`(17개) 언급 뒤에 "와 탭 테이블의 컬럼" 을 붙인다.
- `docs/notes/known-issues.md` 의 K7 행을 지운다(step 0 과 함께 해소).

## Acceptance Criteria

```bash
test -n "$GENDB_TEST_PG_DSN" || { echo "GENDB_TEST_PG_DSN 없음 → blocked"; exit 1; }
uv run pytest tests/test_cli.py tests/test_schema.py -q -rs   # DSN 사유의 SKIPPED 없음 (구현 전에는 새 테스트가 실패해야 한다)
uv run ruff check src tests
uv run pytest -q -rs
```

## 검증 절차

1. 위 AC 커맨드를 실행한다. `GENDB_TEST_PG_DSN` 이 없으면 아무것도 고치지 말고 blocked 로 끝낸다.
2. 아키텍처 체크리스트를 확인한다.
   - `diagnostics.py`·`cli.py` 가 Qt 를 import 하지 않는가?
   - `probe` 가 여전히 예외를 내지 않는가?
   - SQL 이 PG 10~15 에서 도는가?
   - 테스트가 지운 컬럼을 되살리는가?
3. 결과에 따라 `phases/8-schema-migration/index.json` 의 step 1을 업데이트한다.
   - 성공 → `"status": "completed"`, `"summary": "diagnostics.probe: 탭 테이블 컬럼을 pg_attribute 로 읽어 missing_columns(<테이블>.<컬럼>), schema_ready 반영. status: '스키마: 컬럼 N개가 없다 (…)' + 'genviewer-init-db 를 다시 실행할 것.' + exit 1. 처음 실패한 테스트: <이름과 단언>. 변이: <결과>. README·ARCHITECTURE·known-issues K7 고침. DB 테스트: <N passed>"`
   - 수정 3회 시도 후에도 실패 → `"status": "error"`, `"error_message": "구체적 에러 내용"`
   - `GENDB_TEST_PG_DSN` 없음 → `"status": "blocked"`, `"blocked_reason": "GENDB_TEST_PG_DSN 이 없어 DB 테스트를 돌릴 수 없다"` 후 즉시 중단

## 금지사항

- `status` 가 스스로 컬럼을 더하게 하지 마라. 이유: 앱 role(`molgen_app`)은 DDL 권한이 없고(ADR-010), 진단은 읽기만 한다.
- 탭 테이블에 없는 "남는 컬럼" 을 오류로 보지 마라. 이유: 승인된 것은 빠진 컬럼 확인이다. 지운 컬럼은 남겨 두는 것이 step 0 의 정책이다.
- 기존 status 줄(`접속 대상:`, `접속:`, `서버:`, `계정:`, `스키마: 테이블 …`, `내용:`)의 문구·순서·종료 코드를 바꾸지 마라. 이유: 스크립트가 `if genviewer status` 로 쓴다(README).
- 기존 테스트를 깨뜨리지 마라.
