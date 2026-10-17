# Step 0: schema-tab-config-test

## 배경 (phase 5 공통)

이 저장소는 이미 여러 명이 쓰는 도구다. 평소에는 **에러·버그만 고친다**(CLAUDE.md, ADR-015). phase 5는 예외다. **사용자가 2026-10-17 승인한 제거 작업**이다.
데이터는 공유 PostgreSQL에 있고 `.sqlite` 파일은 더 이상 쓰지 않는다. 그래서 옛 `.sqlite` 이관 도구(`genviewer-import-sqlite`)와 레거시 SQLite 스키마·픽스처를 지운다. 지우기만 한다. 기능을 더하거나 리팩터하지 않는다.

모든 step에 같은 규칙이 적용된다.
1. 버그 수정이 아니므로 RED 재현은 없다. 대신 남거나 바뀐 검사가 **여전히 실패할 수 있는지** 확인한다. 코드를 손으로 망가뜨려 실패를 보고(변이 검사) 손으로 되돌린다. `git checkout`/`git stash` 로 되돌리지 마라. 이유: 같은 step의 다른 변경까지 사라진다.
2. 파일 삭제는 `git rm` 으로 한다(`rm -rf` 는 훅이 막는다).
3. PostgreSQL DDL·SQL은 바꾸지 않는다. 그래서 하네스 규칙 12(DB 테스트 필수)는 해당하지 않는다.
   - `GENDB_TEST_PG_DSN` 이 설정돼 있으면 `uv run pytest -q -rs` 로 DB 테스트까지 돌린다. summary에 `DB 테스트: <N passed | 안 돎(DSN 없음)>` 을 적는다.
   - DSN이 없어도 `blocked` 가 아니다.
4. 역사를 설명하는 문장은 남긴다. sqlite를 쓰라는 안내가 아니라 지금 구조가 왜 이런지 설명하는 문장이기 때문이다.
   - `README.md` 첫 문단("예전처럼 각자 `.sqlite` 파일을 들고 …")
   - `docs/PRD.md` 첫 문단
   - `docs/ADR.md` ADR-001 결정
   - `src/genviewer/utils/background.py` 모듈 docstring
   - `tests/test_export.py` 의 "SQLite 는 rowid 순서를 …" 주석
5. 이 파일의 행 번호는 2026-10-17 기준 대략값이다. 이름으로 찾아라.
6. step 순서는 다음과 같다.
   - 0: tab_config 검사를 PostgreSQL DDL 기준으로 옮긴다.
   - 1: 이관 도구와 그 문서를 지운다.
   - 2: 레거시 스키마·픽스처를 지우고 기준선 숫자를 고친다.

## 이 step의 목적

`tests/test_schema.py::test_child_tables_match_tab_config` 는 `config/tab_config.json` 과 생성 DDL이 어긋나는 것을 **DB 없이** 잡는 유일한 테스트다. 지금은 SQLite 렌더러(`schema.sqlite_all_ddl()`)를 in-memory sqlite에 만들어 검사한다.
step 2가 SQLite 렌더러를 지우기 전에, 이 검사를 실제로 쓰는 PostgreSQL 렌더러(`schema.postgres_all_ddl()`) 기준으로 옮긴다. `src/` 는 바꾸지 않는다.

## 읽어야 할 파일

- `/CLAUDE.md`, `/docs/ADR.md`(ADR-003 tab_config.json 이 단일 원본)
- `src/genviewer/service/schema.py` 에서 읽을 부분:
  - `child_tables()`, `PROCESS_TABLE`/`DEVICE_TABLE`/`CHANGE_LOG_TABLE`
  - `_PG_PROCESS_DDL`·`_PG_DEVICE_DDL`·`_PG_CHANGE_LOG_DDL`
  - `pg_child_ddl` (~212-222), `postgres_all_ddl` (~232-244)
- `src/genviewer/config/tab_config.json` — 탭마다 `table`, `columns`
- `tests/test_schema.py` 전체. 특히 아래 이름을 본다.
  - `generated` fixture, `_schema_of`, `test_child_tables_match_tab_config`, `test_generated_schema_matches_legacy_database`
  - `_pg_statements()` (~89-90, `as_string()` 은 접속 없이 된다)
  - `test_device_ddl_has_no_unique_constraint`

## 작업

### 1. 테스트 (`tests/test_schema.py`)

- `test_child_tables_match_tab_config` 를 `_pg_statements()` 기준으로 다시 쓴다. 이름은 그대로 두고, `generated` fixture 인자는 뺀다.
- 단언할 성질:
  - `CREATE TABLE IF NOT EXISTS <이름>` 으로 만드는 테이블 집합 == tab_config 의 `table` 집합 ∪ {`schema.PROCESS_TABLE`, `schema.DEVICE_TABLE`, `schema.CHANGE_LOG_TABLE`}
  - 자식 테이블마다 `id`·`device_id` 를 뺀 컬럼 이름이 tab_config 의 `columns` 와 **순서까지** 같다. 실패 메시지는 지금처럼 `f"{table} 의 컬럼이 tab_config 와 다르다"`.
- 렌더링 형태(2026-10-17):
  - 자식 테이블은 이름이 큰따옴표로 감싸여 나온다(`CREATE TABLE IF NOT EXISTS "inst_terms" (`).
  - payload 컬럼은 `"reserved_key" TEXT NOT NULL DEFAULT ''` 처럼 한 줄에 하나다.
  - process/device/change_log 는 손으로 쓴 DDL이라 이름에 따옴표가 없다.
  - 따옴표가 있든 없든 이름을 뽑게 쓴다.
- 기대값은 지금처럼 `tab_config.values()` 에서 바로 만든다. `schema.child_tables()`·`schema.TABLE_COLUMNS` 로 만들지 마라. 이유: DDL도 그 함수로 만드니 같은 함수끼리 비교하는 셈이 된다.
- `test_generated_schema_matches_legacy_database`, `generated`, `_schema_of`, `_indexes_of`, `sqlite3` import 는 이 step에서 그대로 둔다. step 2가 지운다.

### 2. 변이 검사

- `src/genviewer/service/schema.py` 의 `pg_child_ddl` 이 payload 컬럼 하나를 빠뜨리게 손으로 바꾼다(예: `for c in columns` → `for c in columns[:-1]`).
  - `uv run pytest tests/test_schema.py -q` 에서 이 테스트가 실패하는지 본다.
  - 손으로 되돌리고 통과를 확인한다.
- `postgres_all_ddl` 의 자식 테이블 반복에서 테이블 하나를 빼도(예: `list(child_tables().items())[:-1]`) 실패하는지 본다. 되돌린다.
- 두 변이의 실패 단언을 summary에 적는다.

### 3. 문서

- 없다. `tests/test_schema.py` 모듈 docstring 의 (b)는 step 2가 고친다.

## Acceptance Criteria

```bash
uv run pytest tests/test_schema.py -q        # 바꾼 테스트 통과
uv run ruff check src tests                  # 린트 통과
uv run pytest -q                             # 전체 통과 (DSN 이 있으면 -rs 로 DB 테스트가 돌았는지 본다)
git diff --stat -- src                       # 비어 있어야 한다 (변이 검사 뒤 되돌렸다)
```

## 검증 절차

1. 위 AC 커맨드를 실행한다.
2. 아키텍처 체크리스트를 확인한다:
   - `src/` 가 바뀌지 않았는가?
   - 바꾼 테스트가 DB 없이(개발 PC에서) 실제로 도는가(skip이 아닌가)?
3. 결과에 따라 `phases/5-sqlite-removal/index.json` 의 step 0을 업데이트한다:
   - 성공 → `"status": "completed"`, `"summary": "test_child_tables_match_tab_config 를 postgres_all_ddl 기준으로 바꿈(src 불변, sqlite 테스트는 step 2 가 지움). 변이: 컬럼 하나 뺌 → <단언>, 테이블 하나 뺌 → <단언>. DB 테스트: <N passed | 안 돎(DSN 없음)>"`
   - 수정 3회 시도 후에도 실패 → `"status": "error"`, `"error_message": "구체적 에러 내용"`
   - 사용자 개입 필요 → `"status": "blocked"`, `"blocked_reason": "구체적 사유"` 후 즉시 중단

## 금지사항

- `src/` 를 바꾸지 마라(변이 검사는 되돌린다). 이유: 이 step은 검사를 옮기기만 한다.
- 이 테스트를 DB가 필요한 테스트(`db` fixture, `information_schema`)로 만들지 마라. 이유: 개발 PC는 DSN 없이 돌아서 skip되고, 그러면 아무것도 지키지 않는다.
- SQLite 렌더러 결과와 PostgreSQL 렌더러 결과를 비교하지 마라. 이유: step 2가 SQLite 렌더러를 지운다.
- DDL 문자열 전체를 스냅샷으로 비교하지 마라. 이유: 공백이나 타입만 바뀌어도 깨지고, 지키려는 성질(테이블·컬럼 이름과 순서)이 흐려진다.
- 기존 테스트를 깨뜨리지 마라.
