# Step 9: skill-escape

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

(버그 K13) Virtuoso 로 보내는 SKILL 문자열 리터럴을 이스케이프한다. 지금은 process 이름이나 파라미터 값에 `"`·`\` 가 있으면 명령이 깨지거나, 의도한 것 이상의 SKILL 이 실행될 수 있다. 그런 문자가 없는 값의 출력은 한 글자도 바뀌지 않아야 한다.

## 읽어야 할 파일

- `/CLAUDE.md`, `/docs/ARCHITECTURE.md`(레이어 표: `utils/lisp.py` 는 티어 0, `service/` 는 티어 1. service 는 티어 0 을 import 해도 된다)
- `src/genviewer/utils/lisp.py` 전체(~1-12): `to_lisp_list_string` 이 `f'"{v}"'`, `f'\'{key} "{value}"'` 로 따옴표만 두른다
- `src/genviewer/service/virtuoso_protocol.py`
  - `make_filter_cell_has_symbol_layout` (~12-14): `f'filterCellHasSymbolLayout(list("{p}" "{p}_esd"))'`
  - `make_library_list_request`(빈 stub, K15). 바꾸지 않는다
- 호출부(고치지 않는다, 확인만): `controllers/device_tab.py` 의 `to_lisp_list_string`(보내기, ~343), `controllers/main_window.py` 의 `make_filter_cell_has_symbol_layout`(~152)
- 테스트: 이 둘을 직접 보는 테스트가 아직 없다. `tests/test_virtuoso_protocol.py` 를 새로 만든다(Qt 없음)

## 버그

```python
inner = " ".join(f'"{v}"' for v in value)    # utils/lisp.py
return f'filterCellHasSymbolLayout(list("{p}" "{p}_esd"))'   # virtuoso_protocol.py
```

- 값이 `a"b` 면 `"a"b"` 가 되어 문자열이 일찍 닫히고, 남은 `b"…` 가 SKILL 코드로 읽힌다.
- 값이 `a\` 면 닫는 따옴표가 이스케이프되어 문자열이 끝나지 않는다.
- SKILL 문자열 리터럴은 `\\` 와 `\"` 이스케이프를 쓴다.

이것은 주장이다. 먼저 재현하라.

## 작업

### 1. 실패하는 테스트 (`tests/test_virtuoso_protocol.py`, 새 파일, DB·Qt 불필요)

- 테스트 안에 작은 SKILL 문자열 리터럴 읽개를 둔다.
  - `"…"` 를 찾고, 안의 `\\`·`\"` 를 풀어 값 목록을 돌려준다.
  - 따옴표가 짝이 맞지 않으면 실패한다.
- `to_lisp_list_string({"InstTerm": ['a"b', "c\\d", "plain"], "Desc": 'x"y'})` 의 출력에서 읽어 낸 문자열 값들이 넣은 값 그대로(`['a"b', 'c\\d', 'plain', 'x"y']`, 순서대로)여야 한다.
- `make_filter_cell_has_symbol_layout('My"Lib')` 에서 읽어 낸 값이 `['my"lib', 'my"lib_esd']` 여야 한다(지금처럼 소문자·strip).
- **수정 전에는 두 테스트가 실패해야 한다**(따옴표 짝이 안 맞거나 값이 다르다). 그 출력을 summary에 적는다.
- 특성 테스트(수정 전에도 통과): 특수 문자가 없는 값의 출력은 지금과 **바이트 단위로 같다**.
  - 지금 함수로 만든 문자열을 테스트에 그대로 적는다.
  - 예: `to_lisp_list_string({"InstTerm": ["DRN d", "GATE g"], "Desc": "x"})`
  - 예: `make_filter_cell_has_symbol_layout(" SF2P ")`

### 2. 수정

- `utils/lisp.py` 에 SKILL 문자열 리터럴을 만드는 함수 하나를 둔다. 예: `skill_string(value) -> str`.
  - `str(value)` 의 `\` 를 먼저 `\\` 로, 그다음 `"` 를 `\"` 로 바꾼다.
  - 그 결과를 큰따옴표로 감싸 돌려준다.
- `to_lisp_list_string` 의 두 갈래(리스트 값, 단일 값)와 `virtuoso_protocol.make_filter_cell_has_symbol_layout` 이 그 함수를 쓴다. `virtuoso_protocol.py` 는 `genviewer.utils.lisp` 를 import 한다(티어 1 → 티어 0, 허용).
- 키(`'InstTerm` 같은 심볼)는 tab_config 이름이라 바꾸지 않는다.
- 줄바꿈 등 다른 제어 문자는 이 step 에서 다루지 않는다. 다룰 필요가 보이면 summary에 적는다.

### 3. 변이 검사

- 이스케이프 순서를 바꾸면(`"` 먼저, `\` 나중) 백슬래시가 든 값의 테스트가 실패하는지 본다.
- `make_filter_cell_has_symbol_layout` 만 원래대로 되돌려도 실패하는지 본다.
- 둘 다 손으로 되돌린다.

### 4. 문서

- `docs/notes/known-issues.md` 의 K13 행을 지운다.

## Acceptance Criteria

```bash
uv run pytest tests/test_virtuoso_protocol.py -q   # 새 테스트 통과 (수정 전에는 이스케이프 테스트가 실패해야 한다)
uv run pytest tests/gui -q                          # 보내기·Virtuoso 경로 GUI 테스트 그대로
uv run ruff check src tests
uv run pytest -q
```

## 검증 절차

1. 위 AC 커맨드를 실행한다.
2. 아키텍처 체크리스트를 확인한다.
   - `utils/lisp.py` 가 stdlib 만 import 하는가(티어 0)?
   - `service/virtuoso_protocol.py` 가 Qt 를 import 하지 않는가?
   - 특수 문자가 없는 값의 출력이 바이트 단위로 같은가(특성 테스트)?
3. 결과에 따라 `phases/7-service-fixes/index.json` 의 step 9을 업데이트한다.
   - 성공 → `"status": "completed"`, `"summary": "utils/lisp.skill_string: 백슬래시 먼저, 그다음 큰따옴표를 백슬래시로 이스케이프. to_lisp_list_string·make_filter_cell_has_symbol_layout 이 사용. 특수 문자 없는 출력 불변(특성 테스트). RED: <테스트 이름> (<단언>). 변이: <결과>. tests/test_virtuoso_protocol.py 추가. DB 테스트: <N passed | 안 돎(DSN 없음)>"`
   - 재현 안 됨 → `"status": "completed"`, `"summary": "not reproduced: <이유>"`
   - 수정 3회 시도 후에도 실패 → `"status": "error"`, `"error_message": "구체적 에러 내용"`
   - 사용자 개입 필요 → `"status": "blocked"`, `"blocked_reason": "구체적 사유"` 후 즉시 중단

## 금지사항

- 특수 문자가 든 값을 거부하거나 지우지 마라. 이유: 값은 그대로 Virtuoso 에 가야 한다. 이스케이프만 한다.
- `make_library_list_request`(K15 stub)를 채우지 마라. 이유: Virtuoso 쪽 함수가 정해지지 않은 기능이다(고치지 않기로 함).
- 보내는 문자열의 다른 모양(`pydata = list(...)`, 공백, 순서)을 바꾸지 마라. 이유: Virtuoso 쪽 SKILL 이 그 모양을 읽는다.
- `controllers/` 를 고치지 마라. 이유: 이 step 은 Qt-free 계층만 다룬다.
- 기존 테스트를 깨뜨리지 마라.
