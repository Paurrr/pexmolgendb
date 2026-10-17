# Step 7: bind-param-limit

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

(버그 K9) 한 SQL 문장의 바인드 파라미터가 65,535개를 넘으면 libpq 가 문장을 보내지 못하고 저장이 실패한다. `service/repo/` 에서 행 수만큼 VALUES 를 늘리는 문장을 나눠 보낸다. 저장의 의미(한 트랜잭션, 같은 이력, 같은 반환값)는 그대로다. **DB step 이다.**

## 읽어야 할 파일

- `/CLAUDE.md`(쓰기·이력 같은 트랜잭션), `/docs/ARCHITECTURE.md`(device 저장 흐름), `/docs/ADR.md`(ADR-004, ADR-005)
- `src/genviewer/service/repo/audit.py` — `write` (~71-96): 항목 하나에 파라미터 9개짜리 `(…)` 를 항목 수만큼 이어 붙인 INSERT 한 문장
- `src/genviewer/service/repo/device.py`
  - `upsert_devices` (~157-247)
  - `_update_existing` (~301-356): 행 하나에 6개 + actor 1개, `UPDATE … FROM (VALUES …)`, `RETURNING d.id, d.version` 으로 바뀐 행만 모은다
  - `_insert_new` (~358-382): 행마다 execute. 상한 없음
  - `_log` (~249-271)
- `src/genviewer/service/repo/parameter.py` — `replace_many_for_device`(`executemany`, 행마다 문장 하나)
- `src/genviewer/service/repo/io.py` — `import_data` 의 `executemany`
- `src/genviewer/service/repo/process.py` — `delete` 의 `capture_children`(`ANY(%s)` 배열 파라미터 하나)
- `tests/test_concurrency.py`(`process_id`, `_device`), `tests/test_change_log.py`(`log`, `_rows`)

## 버그

- 한계는 `audit.write` 항목 7,282개(7,282 × 9 = 65,538), `_update_existing` 행 10,923개(10,923 × 6 + 1 = 65,539)다.
- 예를 들어 device 가 1만 개 넘는 process 를 정렬하고 저장하거나, 그만큼을 한 번에 지우고 이력을 남기면 저장이 실패한다.
- 지금 규모(process 당 수백)에서는 닿지 않지만, 닿으면 저장 자체가 안 된다.

이것은 주장이다. 먼저 재현하라.

## 작업

### 0. 조사

- `service/repo/` 전체에서 파라미터 수가 입력 크기에 비례하는 문장을 찾는다. 예상되는 것은 `audit.write`, `_update_existing` 둘이다.
- `executemany`, 행마다 하는 execute, `ANY(%s)` 배열 파라미터는 문장 하나의 파라미터 수가 고정이라 해당하지 않는다.
- 찾은 목록과 판단을 summary에 적는다.

### 1. 실패하는 테스트 (DB 필요)

**`tests/test_change_log.py`**
- 커서 하나로 `audit.write(cur, "bulk", [audit.process_add(f"p{i}") for i in range(7_282)])` 를 한 뒤 커밋한다.
- 7,282 줄이 남아야 한다.
- **수정 전에는 파라미터 수 오류로 실패해야 한다.** 예외 타입과 문구를 summary에 적는다.

**`tests/test_concurrency.py`**
- device 10,923개를 만든다. 테스트 준비는 SQL 한 문장으로 빠르게 한다(예: `INSERT INTO device (process_id, name, celltype, "order") SELECT %s, 'd' || g, 'NFET', g FROM generate_series(1, 10923) g`).
- `DeviceRepository.fetch_devices_by_process` 로 읽고 `order` 를 모두 바꿔(예: 뒤집기) `upsert_devices` 한다.
- 단언
  - `SaveResult.updated == 10923`
  - 모든 행의 version 이 1 올랐다.
  - `change_log` 의 update 줄이 10,923개다. 이력도 7,282 를 넘으므로 `audit.write` 나누기까지 함께 본다.
- **수정 전에는 실패해야 한다.**
- 걸린 시간을 재서 summary에 적는다. 30초를 넘으면 행 수를 더 줄일 수는 없으니(한계값이다) 그대로 두고 summary에 적는다.

**회귀**: 기존 `test_unchanged_save_does_not_bump_version`, `test_save_counts_only_what_the_database_wrote`, `test_force_overrides_the_conflict` 와 이력 테스트가 그대로 통과한다.

### 2. 수정

- 각 문장을 행 묶음으로 나눠 **같은 커서·같은 트랜잭션** 안에서 차례로 실행한다.
- 묶음 크기는 파라미터 상한(65,535)을 행당 파라미터 수로 나눈 값보다 넉넉히 작게 둔다(예: 1,000행). 상수 하나로 두고 이유를 주석으로 적는다.
- `_update_existing`
  - 묶음마다 받은 `RETURNING` 을 합쳐 지금과 같은 `{id: 새 version}` 을 돌려준다.
  - `force` 와 version 가드, `IS DISTINCT FROM` 가드는 묶음마다 똑같이 걸린다.
- `audit.write`: 항목 순서를 지킨다(나중에 쓴 묶음의 id 가 크다).
- 불변식
  - 하나라도 실패하면 전부 롤백된다(호출자의 `with db.connection()` 하나).
  - 반환값과 이력 내용은 나누기 전과 같다.

### 3. 변이 검사

- 묶음 크기를 아주 크게(나누지 않게) 바꾸면 두 테스트가 실패하는지 본다.
- `_update_existing` 에서 묶음 결과를 합치지 않고 마지막 것만 돌려주게 바꾸면 `updated == 10923` 이 실패하는지 본다.
- 모두 손으로 되돌린다.

### 4. 문서

- `docs/notes/known-issues.md` 의 K9 행을 지운다.

## Acceptance Criteria

```bash
test -n "$GENDB_TEST_PG_DSN" || { echo "GENDB_TEST_PG_DSN 없음 → blocked"; exit 1; }
uv run pytest tests/test_change_log.py tests/test_concurrency.py -q -rs --durations=5   # DSN 사유의 SKIPPED 없음 (수정 전에는 새 테스트가 실패해야 한다)
uv run pytest tests/gui/test_fake_repo_contract.py -q -rs
uv run ruff check src tests
uv run pytest -q -rs
```

## 검증 절차

1. 위 AC 커맨드를 실행한다. `GENDB_TEST_PG_DSN` 이 없으면 아무것도 고치지 말고 blocked 로 끝낸다.
2. 아키텍처 체크리스트를 확인한다.
   - 나눈 문장이 모두 같은 트랜잭션인가?
   - SQL 식별자·값 규칙(psycopg.sql, 바인드)을 지키는가?
   - PG 10~15 문법인가?
3. 결과에 따라 `phases/7-service-fixes/index.json` 의 step 7을 업데이트한다.
   - 성공 → `"status": "completed"`, `"summary": "repo/ 의 가변 파라미터 문장 <목록> 을 <N>행 묶음으로 나눠 같은 트랜잭션에서 실행(나머지는 고정 파라미터라 해당 없음). RED: <테스트 이름> (<예외/문구>), <테스트 이름>. 변이: <결과>. 10,923 device 테스트 <초>. DB 테스트: <N passed>"`
   - 재현 안 됨 → `"status": "completed"`, `"summary": "not reproduced: <이유>"`
   - 수정 3회 시도 후에도 실패 → `"status": "error"`, `"error_message": "구체적 에러 내용"`
   - `GENDB_TEST_PG_DSN` 없음 → `"status": "blocked"`, `"blocked_reason": "GENDB_TEST_PG_DSN 이 없어 DB 테스트(재현)를 돌릴 수 없다"` 후 즉시 중단

## 금지사항

- 묶음마다 커밋하거나 새 커넥션을 쓰지 마라. 이유: 저장이 반쯤 쓰이고 이력과 어긋난다(CLAUDE.md CRITICAL).
- 값을 SQL 문자열에 리터럴로 넣어(`sql.Literal`) 파라미터 수를 줄이지 마라. 이유: 값은 항상 바인드 파라미터로 넘긴다(CLAUDE.md CRITICAL).
- 큰 저장을 거부하거나 경고하는 새 동작을 넣지 마라. 이유: 승인 없는 동작 변경이다.
- `IS DISTINCT FROM` 가드나 version 가드를 빼지 마라. 이유: 손대지 않은 device 의 version 이 오르고 남의 저장과 충돌한다(ADR-004).
- 기존 테스트를 깨뜨리지 마라.
