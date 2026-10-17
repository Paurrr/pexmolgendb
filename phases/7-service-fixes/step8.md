# Step 8: xlsx-literal

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

(K12, **사용자 승인 2026-10-17**) 승인된 동작은 다음과 같다.

> xlsx 내보내기(GUI·CLI)에서 `=` 로 시작하는 값을 수식이 아닌 문자열 셀로 저장한다. 내보낸 파일 내용이 바뀐다.

CSV 내보내기는 바꾸지 않는다. molgen 이 그 원문을 그대로 읽는다.

## 읽어야 할 파일

- `/CLAUDE.md`, `/docs/ADR.md`(ADR-003 tab_config 가 단일 원본, ADR-012 CLI)
- `src/genviewer/utils/exporter.py` — `write_xlsx` (~24-38): `ws.append(row)` 로 쓴다. openpyxl 은 `=` 로 시작하는 문자열을 수식(`data_type == "f"`)으로 저장한다
- `src/genviewer/cli.py` — `export` (~253-287): 확장자가 `.xlsx` 면 `write_xlsx`
- `src/genviewer/controllers/device_table.py` — GUI 내보내기가 `write_xlsx` 를 부르는 곳(이름으로 찾는다). 이 파일은 고치지 않는다
- `tests/test_export.py` — 지금은 DB 가 필요한 테스트 둘뿐이다. 이 step 은 DB 없이 도는 테스트를 같은 파일에 더한다

## 작업

### 1. 테스트 먼저 (`tests/test_export.py`, DB 불필요)

- `write_xlsx(tmp_path / "out.xlsx", ["CellType", "Param"], [["=1+1", "x"], ["a=b", "=SUM(A1:A2)"], ["plain", ""]])` 로 쓴 뒤 `openpyxl.load_workbook` 으로 다시 읽는다.
- 단언
  - `=` 로 시작하던 값의 셀은 `data_type == "s"` 이고, `value` 가 원래 문자열(`"=1+1"`, `"=SUM(A1:A2)"`)과 같다.
  - 그 밖의 값(`"a=b"`, `"plain"`, `"x"`)과 헤더는 지금과 같다.
  - 빈 문자열 셀도 지금과 같다(지금 어떻게 저장되는지 먼저 보고 그대로 고정한다).
- **수정 전에는 `data_type == "s"` 단언이 실패해야 한다**(지금은 `"f"`).
- CSV 회귀: 같은 행을 `write_csv` 로 쓰고 읽으면 원문 그대로다(수정 전에도 통과).

### 2. 구현 (`src/genviewer/utils/exporter.py` `write_xlsx`)

- 행을 추가한 뒤 `=` 로 시작하는 문자열 셀은 문자열로 저장되게 한다(예: 그 셀의 `data_type` 을 `"s"` 로).
- 헤더 행에도 같은 규칙을 적용해도 된다. 헤더는 탭 이름이라 `=` 로 시작하지 않는다.
- 저장된 파일을 다시 열었을 때 값이 바뀌지 않는다는 것을 테스트로 보인다(openpyxl 버전에 따라 쓰는 방식이 다를 수 있다).
- 함수 시그니처와 예외 동작(실패를 삼키지 않는다)은 그대로다.

### 3. 변이 검사

- 문자열로 바꾸는 줄을 빼면 새 테스트가 실패하는지 본다. 손으로 되돌린다.

### 4. 문서

- README `## 명령줄` 의 `export` 항목에 한 문장을 더한다. "`.xlsx` 로 낼 때 `=` 로 시작하는 값은 수식이 아니라 글자 그대로 들어간다(창의 내보내기도 같다)."
- `docs/notes/known-issues.md` 의 K12 행을 지운다.

## Acceptance Criteria

```bash
uv run pytest tests/test_export.py -q -rs   # 새 테스트는 DB 없이 돈다 (수정 전에는 실패해야 한다)
uv run ruff check src tests
uv run pytest -q
```

## 검증 절차

1. 위 AC 커맨드를 실행한다.
2. 아키텍처 체크리스트를 확인한다.
   - `utils/exporter.py` 가 PySide6 를 import 하지 않는가(Qt 금지 구역)?
   - 새 테스트가 DB 없이 실제로 도는가(skip 이 아닌가)?
   - CSV 출력이 그대로인가?
3. 결과에 따라 `phases/7-service-fixes/index.json` 의 step 8을 업데이트한다.
   - 성공 → `"status": "completed"`, `"summary": "write_xlsx: '=' 로 시작하는 문자열 셀을 data_type 's' 로 저장(GUI·CLI 공통, CSV 불변). 처음 실패한 단언: <내용>. 변이: <결과>. README export 한 문장. DB 테스트: <N passed | 안 돎(DSN 없음)>"`
   - 수정 3회 시도 후에도 실패 → `"status": "error"`, `"error_message": "구체적 에러 내용"`
   - 사용자 개입 필요 → `"status": "blocked"`, `"blocked_reason": "구체적 사유"` 후 즉시 중단

## 금지사항

- 값 앞에 `'` 를 붙이거나 값을 바꾸지 마라. 이유: 승인된 것은 "글자 그대로" 다. 셀 값은 원문과 같아야 한다.
- CSV(`write_csv`)를 바꾸지 마라. 이유: molgen 이 원문을 읽고, 승인 범위가 xlsx 다.
- `+`, `-`, `@` 로 시작하는 값까지 처리를 넓히지 마라. 이유: 승인된 것은 `=` 뿐이고, openpyxl 은 그 값들을 수식으로 만들지 않는다.
- 기존 테스트를 깨뜨리지 마라.
