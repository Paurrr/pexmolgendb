# Step 0: schema-add-column

## 배경 (phase 8 공통)

이 저장소는 평소에 **에러·버그만 고친다**(CLAUDE.md, ADR-015). phase 8은 예외로 **사용자가 2026-10-17 승인한 기능**이다(known-issues K7, architecture-proposal P7). 승인된 내용은 다음과 같다.

> init_db 가 기존 탭 테이블에 빠진 컬럼을 `ADD COLUMN IF NOT EXISTS`(PG 9.6+)로 더하고, `status` 가 컬럼까지 확인한다. `tab_config.json` 에 컬럼을 더해도 저장이 42703 으로 죽지 않게 된다.

지금은 DDL 이 `CREATE … IF NOT EXISTS` 뿐이다. 이미 있는 탭 테이블에 `tab_config.json` 의 새 컬럼이 생기지 않아서, 저장·불러오기가 `42703 undefined_column` 으로 실패한다(ADR-003 트레이드오프). step 0 은 init_db 쪽을, step 1 은 `status` 쪽을 한다.

모든 step에 같은 규칙이 적용된다.
1. 기능이라 TDD 로 한다. 새 동작을 단언하는 테스트를 먼저 쓰고 실패를 본 뒤 구현한다. 처음 실패한 테스트 이름과 단언을 summary에 적는다.
2. 구현을 손으로 망가뜨려 새 테스트가 실패하는지 보고 손으로 되돌린다(변이 검사). `git checkout`/`git stash` 로 되돌리지 마라. 이유: 같은 step의 테스트 변경까지 사라진다.
3. **DB step 이다.** `GENDB_TEST_PG_DSN`(관리자 DSN)이 없으면 코드를 고치지 말고 `"status": "blocked"` 로 멈춘다. DB 테스트가 skip된 것은 통과가 아니다(`-rs` 로 확인한다).
4. SQL은 PostgreSQL 10~15에서 돌아야 한다(운영은 RHEL 7 + PG 15). 식별자는 `psycopg.sql.Identifier` 와 `schema.child_tables()`/`TABLE_COLUMNS` 로만 만든다. PG 16+ 문법을 쓰지 않는다.
5. `service/schema.py`, `scripts/init_db.py`, `config/config.py`, `scripts/__init__.py` 는 **Python 3.9 에서 import 되어야 한다**(CLAUDE.md CRITICAL, ADR-014).
   - 런타임에 평가되는 `X | Y`, `match`, `zip(strict=)`, `dataclass(slots=/kw_only=)`, `tomllib` 를 쓰지 않는다.
   - `service/schema.py` 에는 `from __future__ import annotations` 가 없다. 그러니 그 파일의 애노테이션도 3.9 문법이어야 한다.
   - phase 6 이 만든 가드 테스트(`tests/test_boundaries.py` 등의 py39 검사)가 이것을 지킨다. 그 테스트가 없으면 `ast.parse(src, feature_version=(3, 9))` 를 직접 돌려 보고 summary에 적는다.
6. `config/tab_config.json` 의 키 구조를 바꾸지 않는다.
7. 이 파일의 행 번호는 2026-10-17 기준 대략값이다. phase 7 이 끝난 뒤의 코드이니 이름으로 찾아라.
8. 사용자에게 보이는 동작이 바뀌면 README·ADR 의 해당 절을 고친다. CLAUDE.md 의 테스트 기준선 숫자는 고치지 않는다(phase 마무리에서 고친다).

DB 테스트는 `tests/conftest.py` 의 `pg_dsn`, `db` fixture 를 쓴다. `db` 는 테스트마다 `postgres_all_ddl()` 을 전부 실행한 뒤 TRUNCATE 한다.

## 이 step의 목적

`schema.postgres_all_ddl()` 이 탭 테이블마다 "빠진 payload 컬럼을 `TEXT NOT NULL DEFAULT ''` 로 더하는" 문장을 내게 한다. init_db 와 `db` fixture 는 이 목록을 그대로 실행하므로 따로 고칠 것이 없다(확인은 한다).

**잠금 조건**: 컬럼이 이미 다 있으면 그 테이블에 `ALTER TABLE` 을 **실행하지 않는다.**
- `ALTER TABLE … ADD COLUMN IF NOT EXISTS` 는 컬럼이 이미 있어도 `ACCESS EXCLUSIVE` 잠금을 먼저 잡는다.
- README 는 사람이 쓰는 중에 init_db 를 다시 돌리는 순서("① init-db → ② deploy.sh 순서로 하면 멈추는 시간이 없다")를 안내한다.
- 그런데 잠금을 잡으면 init_db 가 읽는 트랜잭션 뒤에서 기다리고, 그동안 그 탭을 읽는 모든 사람이 줄을 선다.
- 그래서 카탈로그를 보고 빠진 컬럼이 있을 때만 `ALTER TABLE … ADD COLUMN IF NOT EXISTS` 를 실행하는 DO 블록으로 만든다. `_PG_DEVICE_DROP_NAME_UNIQUE` 와 같은 형태다.

## 읽어야 할 파일

- `/CLAUDE.md`, `/docs/ADR.md`(ADR-003 트레이드오프, ADR-010 role 두 개, ADR-014), `/docs/ARCHITECTURE.md`(스키마 절, 권한 절)
- `src/genviewer/service/schema.py`
  - 모듈 머리말, `child_tables`, `TABLE_COLUMNS`
  - `_PG_DEVICE_DROP_NAME_UNIQUE` (~73-100): DO 블록. `%` 를 쓰지 않는 이유, `name` 타입과 `text[]` 비교 주석
  - `pg_child_ddl` (~161-171), `pg_child_index_ddl` (~174-178), `postgres_all_ddl` (~181-193)
- `src/genviewer/scripts/init_db.py`
  - `build_plan` (~49-106): DDL 마다 `Step(label=_first_line(stmt), conn="db")`
  - `_first_line` (~175-181): 첫 줄이 라벨이다. device DO 블록은 첫 줄이 주석(`-- device 의 옛 UNIQUE …`)이라 그것이 `--dry-run` 에 찍힌다
  - `run_plan` (~209-242): db 단계는 트랜잭션 하나다
- `tests/test_schema.py`
  - `_CREATE_TABLE`, `_pg_tables`: `CREATE TABLE` 문만 읽는다
  - `test_child_tables_match_tab_config`
  - `test_ddl_drops_an_old_unique_constraint_whatever_its_name`: DB 테스트의 본보기
- `tests/test_init_db.py`: `test_app_role_adds_grants_after_the_ddl` 등. 계획 순서의 불변식
- `tests/test_cli.py` — `test_status_points_at_init_db_when_a_table_is_missing` 의 docstring(테스트가 스키마를 망가뜨리면 다음 테스트의 fixture 가 되살릴 수 있어야 한다는 주의)
- `README.md` — `## CSV 컬럼과 탭` 의 "탭을 추가한 뒤에는 …" 문단 (~337-340), 서버 절의 init_db 순서

## 작업

### 0. 먼저 확인

- `service/repo/` 와 `cli.py` 가 탭 테이블을 읽고 쓸 때 컬럼 이름을 명시하는지 본다(`SELECT {cols}`, `INSERT … ({cols})`, `DELETE … RETURNING id, {cols}`).
- 새 컬럼은 물리적으로 맨 뒤에 붙는다. 그러니 `SELECT *`·위치에 기대는 코드가 탭 테이블에 있으면 고치지 말고 `"status": "blocked"` 로 그 위치를 적고 멈춘다. 2026-10-17 기준 `SELECT *` 는 `audit.recent` 의 `change_log` 뿐이다.

### 1. 테스트 먼저

**DB 불필요 (`tests/test_schema.py`)**
- `postgres_all_ddl()` 을 렌더링한 문장들에 대해, 모든 탭 테이블의 모든 payload 컬럼이 그 테이블의 "빠진 컬럼 더하기" 문장 안에 `ADD COLUMN IF NOT EXISTS "<컬럼>" TEXT NOT NULL DEFAULT ''` 로 나온다.
- 그 문장은 같은 테이블의 `CREATE TABLE` 보다 뒤에 있다.
- 기대값은 `tab_config.values()` 에서 바로 만든다. 같은 함수(`child_tables`)끼리 비교하지 마라.
- 기존 `test_child_tables_match_tab_config` 는 그대로 통과한다(새 문장은 `CREATE TABLE` 정규식에 걸리지 않는다).

**DB 필요 (`tests/test_schema.py`)**
- **빠진 컬럼을 되살린다**
  - 탭 테이블 하나를 고르고 그 테이블의 **마지막** payload 컬럼을 고른다. 그래야 되살린 뒤 물리 순서가 DDL 과 같다.
  - 행 하나를 넣고, 그 컬럼을 `ALTER TABLE … DROP COLUMN` 한 뒤, `postgres_all_ddl()` 을 모두 실행한다.
  - 그 컬럼이 `text`, NOT NULL, 기본값 `''` 로 다시 있고 넣었던 행의 값이 `''` 다.
  - `finally` 에서 `ALTER TABLE … ADD COLUMN IF NOT EXISTS` 로 되돌려 둔다. 수정 전에는 fixture 가 되살리지 못해 세션의 다른 테스트가 깨지기 때문이다.
- **두 번 돌려도 같다**: `postgres_all_ddl()` 을 두 번 실행해도 오류가 없고 컬럼 목록(information_schema 또는 pg_attribute)이 같다.
- **컬럼이 다 있으면 잠그지 않는다**
  - 커넥션 A 가 트랜잭션을 열고 탭 테이블 하나를 `SELECT … LIMIT 1` 으로 읽은 채 기다린다(`AccessShareLock`).
  - 다른 커넥션이 `SET lock_timeout = '500ms'` 후 `postgres_all_ddl()` 을 모두 실행한다. 오류 없이 끝나야 한다.
  - A 는 `finally` 에서 롤백·닫는다.
  - 지금 DDL(새 문장 없음)로 먼저 돌려 통과하는 것을 본다(`CREATE INDEX IF NOT EXISTS` 는 `ShareLock` 이라 읽기와 부딪히지 않는다).
  - 그다음 조건 없는 `ALTER TABLE … ADD COLUMN IF NOT EXISTS` 로 구현해 보면 55P03 으로 실패해야 한다(변이 검사로 확인).

**`tests/test_init_db.py` (DB 불필요)**
- `build_plan("", "", "", APP)` 에서 컬럼 더하기 단계가 그 테이블의 CREATE TABLE 단계 뒤, `GRANT` 단계보다 앞에 있다.
- `--dry-run` 라벨이 어느 테이블인지 알아볼 수 있다(예: 첫 줄 주석 `-- <테이블> 에 빠진 컬럼을 더한다`).

### 2. 구현 (`src/genviewer/service/schema.py`)

- 탭 테이블 하나에 대한 "빠진 컬럼 더하기" 문장을 만드는 함수를 둔다. 예: `pg_child_add_columns_ddl(table, columns) -> sql.Composed`.
  - DO 블록 안에서 컬럼마다 카탈로그(`pg_attribute`, `attisdropped` 제외, 현재 스키마의 그 테이블)를 보고, 없을 때만 `ALTER TABLE <tbl> ADD COLUMN IF NOT EXISTS <col> TEXT NOT NULL DEFAULT ''` 를 실행한다.
  - 테이블·컬럼 이름은 `sql.Identifier`/`sql.Literal` 로 넣는다. 문자열 포맷으로 이어 붙이지 않는다.
  - `%` 를 쓰지 않는다. 이유는 `_PG_DEVICE_DROP_NAME_UNIQUE` 주석과 같다.
  - `name` 타입을 `text[]` 와 그냥 비교하지 않는다.
  - 첫 줄을 주석으로 두어 `--dry-run` 라벨이 되게 한다.
- `postgres_all_ddl()` 은 탭마다 `CREATE TABLE`, 인덱스, 컬럼 더하기 순서로 낸다.
- PG 10 에서는 `ADD COLUMN … DEFAULT ''` 가 테이블을 다시 쓴다(PG 11+ 는 즉시). 운영은 PG 15 다. 이 사실을 주석 한 줄로 남긴다.
- `init_db.py` 는 바꿀 것이 없을 것이다. 라벨이 읽기 어렵거나 순서가 어긋나면 고치고 summary에 적는다.
- 불변식
  - 새 DB 에서 결과 스키마는 지금과 같다(`CREATE TABLE` 이 이미 모든 컬럼을 만든다).
  - 이미 있는 컬럼·데이터는 건드리지 않는다.
  - DDL 은 여전히 여러 번 돌려도 된다.

### 3. 변이 검사

- 컬럼 더하기 문장을 `postgres_all_ddl()` 에서 빼면 "되살린다" 테스트가 실패하는지 본다.
- 카탈로그 조건을 빼면(언제나 `ALTER`) "잠그지 않는다" 테스트가 실패하는지 본다.
- 컬럼 하나를 빠뜨리면(`columns[:-1]`) DB 불필요 테스트가 실패하는지 본다.
- 모두 손으로 되돌린다.

### 4. 문서

- `/docs/ADR.md` ADR-003 트레이드오프를 고친다.
  - "기존 탭에 컬럼을 추가하면 `init_db` 재실행이 빠진 컬럼을 `''` 로 더한다(2026-10-17 승인)."
  - "컬럼 이름 변경·삭제·순서 변경은 여전히 마이그레이션이 없다."
- README `## CSV 컬럼과 탭` 문단을 "탭을 추가하거나 기존 탭에 컬럼을 더한 뒤에는 …" 으로 고친다.
  - "빠진 컬럼만 더하고(기존 행의 값은 빈 문자열) 이름을 바꾸거나 지운 컬럼은 손대지 않는다."
  - "PostgreSQL 10 에서는 컬럼을 더할 때 그 테이블을 다시 쓴다."
- `/docs/ARCHITECTURE.md` 스키마 절의 "전부 `CREATE … IF NOT EXISTS` 라 …" 에 "+ 탭 테이블의 빠진 컬럼은 카탈로그를 보고 `ADD COLUMN`" 을 붙인다.
- `docs/notes/known-issues.md` 의 K7 행은 step 1 이 끝나면 지운다. 이 step 에서는 그대로 둔다.

## Acceptance Criteria

```bash
test -n "$GENDB_TEST_PG_DSN" || { echo "GENDB_TEST_PG_DSN 없음 → blocked"; exit 1; }
uv run pytest tests/test_schema.py tests/test_init_db.py -q -rs   # DSN 사유의 SKIPPED 없음 (구현 전에는 새 테스트가 실패해야 한다)
uv run python -c "import ast,pathlib; [ast.parse(pathlib.Path(p).read_text(encoding='utf-8'), feature_version=(3, 9)) for p in ['src/genviewer/service/schema.py','src/genviewer/scripts/init_db.py']]"
uv run genviewer-init-db --dry-run                                  # 새 단계의 라벨 확인
uv run ruff check src tests
uv run pytest -q -rs
```

## 검증 절차

1. 위 AC 커맨드를 실행한다. `GENDB_TEST_PG_DSN` 이 없으면 아무것도 고치지 말고 blocked 로 끝낸다.
2. 아키텍처 체크리스트를 확인한다.
   - SQL 이 PG 10~15 에서 도는가? DO 블록·`ADD COLUMN IF NOT EXISTS` 는 9.6+ 다.
   - 식별자가 `sql.Identifier` 인가?
   - `schema.py` 가 3.9 에서 import 되는가?
   - `tab_config.json` 을 바꾸지 않았는가?
   - 테스트가 세션 스키마를 되돌리는가?
3. 결과에 따라 `phases/8-schema-migration/index.json` 의 step 0을 업데이트한다.
   - 성공 → `"status": "completed"`, `"summary": "schema.postgres_all_ddl: 탭마다 빠진 payload 컬럼만 ADD COLUMN IF NOT EXISTS 하는 DO 블록(<함수 이름>), 다 있으면 ALTER 안 함(잠금 없음). 처음 실패한 테스트: <이름과 단언>. 변이: <3개 결과>. --dry-run 라벨: <예>. ADR-003·README·ARCHITECTURE 고침. DB 테스트: <N passed>"`
   - 수정 3회 시도 후에도 실패 → `"status": "error"`, `"error_message": "구체적 에러 내용"`
   - `GENDB_TEST_PG_DSN` 없음 또는 위치에 기대는 코드 발견 → `"status": "blocked"`, `"blocked_reason": "구체적 사유"` 후 즉시 중단

## 금지사항

- 컬럼을 지우거나 이름을 바꾸거나, 순서를 맞추려고 테이블을 다시 만들지 마라. 이유: 데이터를 잃을 수 있고, 승인된 것은 "빠진 컬럼 더하기" 뿐이다.
- 조건 없이 `ALTER TABLE` 을 실행하지 마라. 이유: 컬럼이 다 있어도 `ACCESS EXCLUSIVE` 를 잡아, 쓰는 중의 init_db 재실행이 사람들을 멈춰 세운다.
- 타입·기본값을 `TEXT NOT NULL DEFAULT ''` 말고 다른 것으로 하지 마라. 이유: `pg_child_ddl` 과 같아야 새 DB 와 옮긴 DB 가 같은 스키마다.
- `status` 쪽을 이 step 에서 고치지 마라. 이유: step 1 의 일이다.
- 기존 테스트를 깨뜨리지 마라.
