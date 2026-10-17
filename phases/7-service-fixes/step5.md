# Step 5: import-process-lock

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

(버그 K5) CLI `load` 가 CSV 를 불러오는 동안 GUI 에서 같은 process 를 고르면, 5초 기다린 뒤 "다른 사용자가 저장하는 중이다"(55P03)로 실패한다. 불러오기가 이미 있는 process 행을 잠그지 않게 고친다. **DB step 이다.** step 6(K32, 새 process 이력)이 이 step 의 설계 위에 올라간다.

## 읽어야 할 파일

- `/CLAUDE.md`, `/docs/ADR.md`(ADR-008 일부러 거는 타임아웃, ADR-006 CSV 는 누적)
- `src/genviewer/service/repo/io.py`
  - `_process_id` (~55-64): `INSERT INTO process (name) VALUES (%s) ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name RETURNING id`
  - `import_data` (~66-170): 트랜잭션 하나 안에서 CSV 행마다 `_process_id` → `INSERT INTO device` → 끝에 자식 행과 audit
  - `get_or_create_process_id` (~49-53): 호출부가 없다
- `src/genviewer/service/repo/process.py` — `get_or_create_id` (~104-121). GUI 가 process 를 고를 때 부른다(`controllers/device_tab_toolbar.py` `get_process_id` → 이것). 같은 `ON CONFLICT … DO UPDATE` 이고 `xmax = 0` 으로 새로 만든 것만 `process_add` 이력을 남긴다
- `src/genviewer/cli.py` — `load` (~228-250): `statement_timeout_ms=0` 으로 연다(큰 파일이면 트랜잭션이 길다)
- `src/genviewer/service/config.py` — `DbConfig.lock_timeout_ms`(기본 5000)
- `tests/test_concurrency.py`, `tests/test_csv_import.py`(`_write_csv`, `_devices`), `tests/test_change_log.py`(`test_creating_a_process_is_recorded_once`, `test_adding_a_process_by_name_is_recorded`)
- `tests/gui/test_fake_repo_contract.py` 의 `test_get_or_create_id_is_stable_and_none_for_an_empty_name`(가짜와 실제의 계약)

## 버그

- 불러오기 트랜잭션이 첫 행에서 `ON CONFLICT (name) DO UPDATE` 로 그 process 행을 잠근다. 그리고 커밋할 때까지(큰 파일이면 오래) 쥐고 있다.
- 그 사이 GUI 의 `get_or_create_id` 도 같은 행을 `DO UPDATE` 로 잠그려다 `lock_timeout` 5초 뒤 55P03 으로 실패한다.

**잠금 분석(구현 전에 실험으로 확인하라)**
- device INSERT 의 외래키 검사는 process 행에 `FOR KEY SHARE` 를 잡는다.
- `ON CONFLICT … DO UPDATE SET name = …` 은 unique 인덱스가 걸린 컬럼(`name`)을 고치는 UPDATE 다. 그래서 `FOR UPDATE` 강도로 잠그고, 이것은 `FOR KEY SHARE` 와 충돌한다.
- 따라서 `io._process_id` 만 SELECT 먼저로 바꿔도, 불러오기의 device INSERT 가 잡은 `KEY SHARE` 에 GUI 의 `get_or_create_id`(DO UPDATE)가 여전히 막힐 수 있다.
- 그러면 `ProcessRepository.get_or_create_id` 도 같은 방식(SELECT 먼저)으로 바꿔야 한다. 같은 repo 레이어라 이 step 에서 한다.
- 어느 쪽이 필요했는지 summary에 적는다.

이것은 주장이다. 먼저 재현하라.

## 작업

### 1. 실패하는 테스트 (`tests/test_concurrency.py`, DB 필요)

- 준비: `ProcessRepository(db).get_or_create_id("sf2p")` 로 process 를 커밋해 둔다.
- 커넥션 A(`psycopg.connect(pg_dsn, row_factory=dict_row)`, 자동 커밋 아님)로 불러오기가 하는 일을 그대로 한다.
  - `IORepository._process_id(curA, "sf2p")`
  - 그 id 로 `INSERT INTO device (process_id, name, celltype, updated_by) VALUES (…)`
  - **커밋하지 않는다.**
- 다른 `Database(DbConfig(dsn=pg_dsn, lock_timeout_ms=300))` 로 `ProcessRepository(other).get_or_create_id("sf2p", actor="gui")` 를 부른다.
  - 예외 없이 같은 id 를 돌려줘야 한다.
  - 300ms 안에 끝나야 한다(시간을 재서 단언한다).
- **수정 전에는 `psycopg.errors.LockNotAvailable`(55P03)로 실패해야 한다.** 그 출력을 summary에 적는다.
- `finally` 에서 A 를 롤백하고 닫는다. `other` 도 닫는다. 열린 채 두면 다른 테스트와 `pg_dsn` 의 DROP DATABASE 가 막힌다.

회귀(수정 전에도 통과해야 한다)
- `_process_id` 의 계약
  - 없는 이름이면 새로 만들고 id 를 준다.
  - 있는 이름이면 같은 id 를 준다.
  - 빈 값·공백·NaN 이면 None 이다.
- `get_or_create_id` 의 계약
  - 새로 만들 때만 `process_add` 이력 한 줄을 남긴다(기존 `test_creating_a_process_is_recorded_once` 등).
  - 빈 이름이면 None 이다.
- 가짜와 실제 계약: `uv run pytest tests/gui/test_fake_repo_contract.py -q -rs` 가 그대로 통과한다.

### 2. 수정

- `IORepository._process_id(cur, process_name)` 의 순서
  1. `SELECT id FROM process WHERE name = %s` 를 한다. 있으면 그 id 다. 잠그지 않는다.
  2. 없으면 `INSERT … ON CONFLICT (name) DO NOTHING RETURNING id` 를 한다.
  3. 그것이 행을 못 돌려주면(동시에 누가 만들었다) 다시 SELECT 한다.
- step 6 이 "이번에 새로 만들었는가" 를 알아야 한다. 그러니 그 정보를 낼 수 있는 모양으로 둔다(예: 2번에서 행이 나오면 새로 만든 것). 이 step 에서 반환 타입을 바꿀 필요는 없다. 바꾼다면 호출부를 모두 고치고 summary에 적는다.
- 실험해 보고 필요하면 `ProcessRepository.get_or_create_id` 도 SELECT 먼저로 바꾼다. 새로 만든 경우에만 `process_add` 를 남기는 계약은 그대로다.
- 불변식
  - 이미 있는 process 를 찾는 경로는 process 행에 행 잠금을 잡지 않는다.
  - 동시에 같은 새 이름을 만들 때 process 는 하나만 생기고, 둘 다 같은 id 를 얻는다.
  - 불러오기는 여전히 트랜잭션 하나다(실패하면 process·device·이력 모두 롤백).

### 3. 변이 검사

- `_process_id` 를 `DO UPDATE` 로 되돌리면 새 테스트가 실패하는지 본다.
- `get_or_create_id` 를 바꿨다면 그것만 되돌려도 실패하는지 본다.
- 모두 손으로 되돌린다.

### 4. 문서

- `docs/notes/known-issues.md` 의 K5 행을 지운다.

## Acceptance Criteria

```bash
test -n "$GENDB_TEST_PG_DSN" || { echo "GENDB_TEST_PG_DSN 없음 → blocked"; exit 1; }
uv run pytest tests/test_concurrency.py tests/test_csv_import.py tests/test_change_log.py -q -rs   # DSN 사유의 SKIPPED 없음 (수정 전에는 새 테스트가 실패해야 한다)
uv run pytest tests/gui/test_fake_repo_contract.py -q -rs     # 가짜·실제 계약 그대로
uv run ruff check src tests
uv run pytest -q -rs
```

## 검증 절차

1. 위 AC 커맨드를 실행한다. `GENDB_TEST_PG_DSN` 이 없으면 아무것도 고치지 말고 blocked 로 끝낸다.
2. 아키텍처 체크리스트를 확인한다.
   - SQL 이 PG 10~15 에서 도는가(`ON CONFLICT DO NOTHING` 은 9.5+)?
   - 값은 바인드 파라미터인가?
   - 불러오기가 트랜잭션 하나로 남았는가?
   - 가짜(`tests/gui_support/fakes.py`)의 의미와 어긋나지 않는가?
3. 결과에 따라 `phases/7-service-fixes/index.json` 의 step 5를 업데이트한다.
   - 성공 → `"status": "completed"`, `"summary": "io._process_id: SELECT 먼저, 없을 때만 INSERT ON CONFLICT DO NOTHING RETURNING(+재 SELECT). get_or_create_id <바꿈|안 바꿈: 이유(잠금 실험 결과)>. 새로 만든 것을 알아내는 방법: <설명>(step 6 이 씀). RED: <테스트 이름> (LockNotAvailable). 변이: <결과>. DB 테스트: <N passed>"`
   - 재현 안 됨 → `"status": "completed"`, `"summary": "not reproduced: <이유>"`
   - 수정 3회 시도 후에도 실패 → `"status": "error"`, `"error_message": "구체적 에러 내용"`
   - `GENDB_TEST_PG_DSN` 없음 → `"status": "blocked"`, `"blocked_reason": "GENDB_TEST_PG_DSN 이 없어 DB 테스트(재현)를 돌릴 수 없다"` 후 즉시 중단

## 금지사항

- 불러오기를 행마다 커밋하거나 트랜잭션을 쪼개지 마라. 이유: 실패한 불러오기가 반쯤 쌓이면 되돌릴 수 없다(CSV 는 누적, ADR-006).
- `lock_timeout` 을 늘리거나 불러오기에서 풀지 마라. 이유: ADR-008 의 일부러 거는 타임아웃이다.
- process 이력(K32)을 이 step 에서 더하지 마라. 이유: step 6 의 승인 항목이다.
- `FakeProcessRepository` 의 의미를 바꾸지 마라. 이유: `get_or_create_id` 의 계약(같은 id, 빈 이름은 None)은 그대로다.
- 기존 테스트를 깨뜨리지 마라.
