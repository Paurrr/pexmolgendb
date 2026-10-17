# Step 6: import-process-audit

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

(K32, **사용자 승인 2026-10-17**) 승인된 동작은 다음과 같다.

> CSV 불러오기가 새로 만든 process 마다 'process 추가' 이력 한 줄을 더 남긴다(`log`·History 에 줄이 늘어난다). 지금은 불러오기 한 줄에만 들어 있다.

불러오기 한 줄(`CSV 불러오기 …`)은 그대로 남는다. **DB step 이다.** step 5(K5)가 `io._process_id` 를 "SELECT 먼저, 없을 때만 INSERT … DO NOTHING RETURNING" 으로 바꿨다. 그 summary 에 "새로 만든 것을 알아내는 방법" 이 적혀 있다. 먼저 읽어라.

## 읽어야 할 파일

- `/CLAUDE.md`(쓰기와 이력은 같은 트랜잭션), `/docs/ADR.md`(ADR-005 change_log, ADR-006 CSV 는 누적)
- `phases/7-service-fixes/index.json` — step 5 summary
- `src/genviewer/service/repo/io.py`
  - `_process_id`(step 5 가 바꿈)
  - `import_data`: `per_process` 집계, 끝의 `audit.write(cur, actor, [audit.csv_import(...)])` (~161-168), `if created:` 조건
- `src/genviewer/service/repo/audit.py` — `process_add(name)` (~265-270), `csv_import` (~253-262), `write` (~71-96, 호출자의 커서)
- `src/genviewer/service/repo/process.py` — `add`, `get_or_create_id`. 둘 다 같은 `audit.process_add` 를 쓴다
- `tests/test_change_log.py`
  - `test_a_csv_import_is_one_line_and_fills_updated_by` (~334-357): `assert len(rows) == 1` 로 지금 동작을 고정한다. 이 step 이 고친다
  - `test_creating_a_process_is_recorded_once`, `_rows`
- `tests/test_csv_import.py` — `test_a_csv_without_the_required_columns_raises`(`InstCellName` 이 없으면 process 를 만든 뒤 `KeyError` 로 실패한다)
- `README.md` — `## 변경 이력` 의 예시

## 작업

### 1. 테스트 먼저 (`tests/test_change_log.py`, DB 필요)

**고치는 기존 테스트**: `test_a_csv_import_is_one_line_and_fills_updated_by`
- 이름을 새 계약에 맞게 바꾼다. 예: `test_a_csv_import_is_one_line_plus_one_per_new_process`.
- 단언
  - `action == IMPORT` 인 줄은 정확히 하나이고, `detail["processes"] == {"sf2p": 2, "sf4u": 1}` 는 그대로다(device 3개를 3줄로 남기지 않는다).
  - `action == PROCESS_ADD` 인 줄이 `sf2p`, `sf4u` 하나씩, actor `dh991` 로 있다.
  - process 추가 줄의 id 가 불러오기 줄보다 작다(만든 다음 불러왔다).
  - `updated_by` 단언은 그대로다.
- **수정 전에는 `PROCESS_ADD` 단언이 실패해야 한다.**

**새 테스트**
- 이미 있는 process: `ProcessRepository(db).add("sf2p", actor="관리자")` 다음에 같은 CSV 를 불러온다.
  - `dh991` 의 `PROCESS_ADD` 는 `sf4u` 하나뿐이다.
  - `sf2p` 의 process 추가 줄은 관리자의 한 줄뿐이다.
- 같은 파일을 두 번 불러온다. 두 번째 불러오기는 process 추가 줄을 더 남기지 않는다.
- 실패한 불러오기: `CdsLibName` 은 있고 `InstCellName` 은 없는 CSV 를 불러오면 `KeyError` 가 난다.
  - process 표가 비어 있다.
  - `change_log` 가 비어 있다(process 만들기와 이력이 같은 트랜잭션에서 롤백).
  - 수정 전에도 통과할 수 있다. 회귀 그물이다.

### 2. 구현 (`src/genviewer/service/repo/io.py` `import_data`)

- 불러오는 동안 **이번 트랜잭션에서 새로 만든** process 이름을 처음 나온 순서대로, 중복 없이 모은다. 판단은 step 5 의 INSERT … RETURNING 결과로 한다.
- 끝의 `audit.write` 한 번에 `[process_add(이름) …] + [csv_import(…)]` 순서로 넘긴다. 같은 커서, 같은 actor, 같은 출처다.
- `if created:` 조건 아래에 둔다. process 는 device 를 만들 행에서만 생기므로 둘은 함께 0 이다.
- `audit.process_add` 를 그대로 쓴다. 문구("process 추가  <이름>")는 바꾸지 않는다.
- step 5 의 잠금 불변식(이미 있는 process 는 잠그지 않는다)을 깨지 않는다.

### 3. 변이 검사

- 새로 만든 이름 대신 CSV 에 나온 모든 이름을 이력에 넣게 바꾸면 "이미 있는 process" 테스트가 실패하는지 본다.
- process 추가 줄을 빼면 고친 기존 테스트가 실패하는지 본다.
- 둘 다 손으로 되돌린다.

### 4. 문서

- README `## 변경 이력` 에 한 문장을 더한다. "CSV 불러오기로 새로 생긴 process 는 'process 추가' 줄이 따로 남는다(불러오기 줄 앞에)." 예시 출력은 바꾸지 않아도 된다.
- `docs/notes/known-issues.md` 의 K32 행을 지운다.

## Acceptance Criteria

```bash
test -n "$GENDB_TEST_PG_DSN" || { echo "GENDB_TEST_PG_DSN 없음 → blocked"; exit 1; }
uv run pytest tests/test_change_log.py tests/test_csv_import.py tests/test_cli.py -q -rs   # DSN 사유의 SKIPPED 없음 (수정 전에는 고친 기존 테스트가 실패해야 한다)
uv run ruff check src tests
uv run pytest -q -rs
```

## 검증 절차

1. 위 AC 커맨드를 실행한다. `GENDB_TEST_PG_DSN` 이 없으면 아무것도 고치지 말고 blocked 로 끝낸다.
2. 아키텍처 체크리스트를 확인한다.
   - 이력이 저장과 같은 트랜잭션·커서로 쓰이는가(`audit.write(cur, …)`)?
   - process 를 고르는 GUI 경로(`get_or_create_id`)의 이력은 그대로인가?
   - 가짜 `FakeIORepository` 는 이력을 흉내 내지 않으므로 바꿀 것이 없는가?
3. 결과에 따라 `phases/7-service-fixes/index.json` 의 step 6을 업데이트한다.
   - 성공 → `"status": "completed"`, `"summary": "import_data: 이번에 새로 만든 process 마다 process_add 이력(불러오기 줄 앞, 같은 트랜잭션). 기존 테스트 이름을 <새 이름> 으로 바꾸고 단언 갱신. 처음 실패한 단언: <내용>. 변이: <결과>. README 변경 이력 한 문장. DB 테스트: <N passed>"`
   - 수정 3회 시도 후에도 실패 → `"status": "error"`, `"error_message": "구체적 에러 내용"`
   - `GENDB_TEST_PG_DSN` 없음 → `"status": "blocked"`, `"blocked_reason": "GENDB_TEST_PG_DSN 이 없어 DB 테스트를 돌릴 수 없다"` 후 즉시 중단

## 금지사항

- device 마다 이력 줄을 남기지 마라. 이유: 불러오기는 한 사건이다(ADR-005). 승인된 것은 새 process 줄뿐이다.
- 이력을 별도 트랜잭션이나 별도 커넥션으로 쓰지 마라. 이유: 실패한 불러오기에 이력이 남는다(CLAUDE.md CRITICAL).
- `csv_import`·`process_add` 의 문구나 `detail` 모양을 바꾸지 마라. 이유: `log`·History 와 기존 이력이 같은 형식을 쓴다.
- 기존 테스트를 깨뜨리지 마라. 바꾸는 것은 위에 적은 하나뿐이다.
