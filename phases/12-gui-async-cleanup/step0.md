# Step 0: history-test-fixture

## 배경 (phase 12 공통)

이 저장소는 이미 여러 명이 쓰는 도구다. 평소에는 **에러·버그만 고친다**(CLAUDE.md, ADR-015). phase 12는 2026-10-17에 `docs/notes/known-issues.md` 를 분류하면서 버그로 정한 GUI 비동기·수명 항목을 한 step에 하나씩 고친다.
- History 화면의 오류 문구, 다시 읽기 경합(K23a, K41)
- 변경 감지 폴링의 결과 묶기(K23b)
- Qt 객체 누수(K22의 나머지)

모두 버그이고 승인 대상이 아니다. 사용자에게 보이는 문구를 새로 만들지 않는다.

phase 0~11이 끝나 있다. 이 phase에 닿는 것은 다음과 같다.
- phase 7 step 3(`audit-naive-time`): `repo/audit.py` 의 읽기·purge가 naive datetime을 `.astimezone()` 으로 바꿔 비교한다.
- phase 10 step 4(`reload-guard`): 재접속 전에 저장 안 한 편집을 묻는다.
- phase 11 step 1·2: `_open_database` 가 원인이 담긴 예외를 내고, 실패하면 새 Database를 닫는다.
- `connect_db` 의 순서는 phase 4 그대로다. 새 DB를 열고, 도는 폴링을 기다린 뒤 옛 DB를 닫고, 그다음 `dbChanged(새)` 를 낸다.

모든 step에 같은 규칙이 적용된다.
1. 버그는 **주장**이다. 먼저 실패하는 테스트로 재현하고, RED 출력(테스트 이름과 실패한 단언)을 summary에 적는다.
2. RED는 **Windows 개발 PC에서** 보여야 한다.
3. 재현되지 않으면 `src/` 를 고치지 않는다. 테스트는 특성 테스트로 남기고 `"status": "completed"`, `"summary": "not reproduced: <이유>"` 로 끝낸다.
4. 고친 뒤 수정을 손으로 되돌려 새 테스트가 실패하는지 확인하고 다시 고친다(변이 검사). `git checkout`/`git stash` 로 되돌리지 마라. 이유: 같은 step의 테스트 변경까지 사라진다.
5. 이 파일의 행 번호는 2026-10-18(phase 11 직후) 기준 대략값이다. 이름으로 찾아라.
6. `DeviceTabController.connect_db`/`_open_database` 는 phase 7·10·11·12가 차례로 건드린다. 이 파일은 그 본문을 인용하지 않는다. 지금 코드를 읽고, 적힌 불변식만 지켜라.

GUI 테스트 기반은 phase 2가 만들었다. 이름을 그대로 쓴다. 작업 전에 `tests/gui/conftest.py`·`tests/gui_support/` 를 읽는다.
- `dialogs` (autouse `FakeDialogs`)
- `device_tab_ctrl`, `main_window`(History 화면은 만들지 않는다), `store`
  - 시드: sf2p(nfet_a, nfet_b), sf4u(pfet_a)
  - `store.calls_of(name)`: 끝난 호출의 인자 dict
  - `store.fail_next(name, exc)`, `store.touch_device`, `store.add_device`
- 헬퍼: `install_fake_db`, `select_process`, `select_device_row`
- `FakeDatabase.connection()` 은 `AssertionError` 를 낸다. 가짜 DB에 실제 repo(예: `AuditRepository`)가 붙으면 바로 드러난다.
- 고정 대기(`qtbot.wait`)는 쓰지 않는다. `waitUntil` 콜백은 bool을 돌려준다(`lambda: store.calls_of("recent") != []`).

## 이 step의 목적

History 컨트롤러(`controllers/history_tab.py`)를 GUI 테스트에서 돌릴 수 있게 테스트 기반을 더한다. `src/` 는 바꾸지 않는다.
- 지금은 History 테스트가 0개다. 가짜 audit repo도 없다(`tests/gui_support/fakes.py` docstring: "change_log(audit)는 흉내 내지 않는다").
- step 1·2가 History 를, step 3가 폴링을 이것으로 재현한다.

## 읽어야 할 파일

- `/CLAUDE.md`(테스트 관례: 가짜의 의미는 실제 repo가 기준이고 contract test가 고정한다), `/docs/ARCHITECTURE.md`(변경 감지, History)
- `src/genviewer/controllers/history_tab.py` 전체
  - `AuditRepository`·`ProcessRepository` 를 모듈 이름으로 import한다(~16-18).
  - `set_db`, `reload`(`repo.recent(...)` 와 `process_repo.list_all()` 을 `Task` 로), `_on_result`, `_on_failed`, `shutdown`
- `src/genviewer/views/history_tab.py`: 필터 위젯 `range_cb`·`who_field`·`process_cb`·`find_field`·`auto_cb`(기본 켜짐), `show_count`, `set_processes`
- `src/genviewer/service/repo/audit.py`
  - `Entry`, `write(cur, actor, entries)`, `source()`/`set_source`, `_COLUMNS`
  - `AuditRepository.recent` (~359-409): 조건에 맞는 마지막 `limit` 줄을 오래된 것부터 준다.
  - phase 7 step 3이 바꾼 naive datetime 처리도 읽는다.
- `tests/gui_support/fakes.py`: `REPO_METHODS`, `FAILABLE`, `_recorded`, `FakeStore`, `FakeDatabase`
- `tests/gui_support/helpers.py`: `install_fake_db`, `FAKE_REPOSITORIES`
- `tests/gui/test_fake_repo_contract.py`: `backend` fixture. 기대값을 직접 적는다. "fake 결과 == real 결과" 비교는 금지다.
- `tests/gui/test_fake_store.py`, `tests/conftest.py`(`db` fixture)

## 작업

### 1. `FakeAuditRepository` (`tests/gui_support/fakes.py`)

- `FakeAuditRepository(db)` 를 만든다. `recent(*, limit=50, since=None, until=None, actor="", process="", device="", contains="", after_id=None) -> list[dict]` 하나만 둔다.
  - 실제 `AuditRepository.recent` 와 시그니처·의미가 같다.
    - 조건에 맞는 줄 중 id가 큰 쪽에서 `limit` 개를 골라 id 오름차순으로 준다.
    - 필터: `after_id`(id >), `since`(at >=), `until`(at <), `actor`·`process`(=`process_name`)·`device`(=`device_name`) 일치.
    - `contains` 는 summary 또는 detail(JSON 텍스트)에서 대소문자를 무시하고 찾는다.
    - naive `since`/`until` 은 phase 7 step 3 이후의 실제와 같은 규칙으로 다룬다.
  - 행의 키는 실제 `_COLUMNS` 와 같다. `id, at, actor, source, action, process_name, device_name, device_id, table_name, summary, detail`
  - History가 부르지 않는 `latest_id`·`count_before`·`purge` 는 만들지 않는다.
- `FakeStore` 에 이력 줄 목록과 자체 id 시퀀스를 두고, 시드 메서드 `add_audit(actor, entry, *, source="") -> dict` 를 더한다.
  - `entry` 는 실제 `audit.Entry` 다. 예: `audit.process_add("p")`, `audit.device_insert(...)`
  - `at` 은 store 시계(`_tick()`)로 매긴다.
  - 시드라서 `calls` 에 남지 않고 `fail_next` 를 따르지 않는다(기존 `add_device` 와 같은 분류).
- `REPO_METHODS` 에 `"recent"` 를 더한다. 그러면 `store.calls_of("recent")` 와 `store.fail_next("recent", exc)` 가 된다. 이름이 다른 메서드와 겹치지 않는지 확인한다.
- 가짜 쓰기(add, delete, upsert …)는 지금처럼 **이력을 쓰지 않는다**. docstring의 "change_log(audit)는 흉내 내지 않는다" 를 다음으로 고친다: "change_log 는 읽기(`recent`)만 흉내 낸다. 줄은 `store.add_audit` 로 넣는다".

### 2. `store.hold_next(method) -> threading.Event` (`tests/gui_support/fakes.py`)

- 그 이름의 **다음 호출 하나**를 잡아 둔다. 그 호출은 돌려준 Event가 set될 때까지 기다렸다가 평소처럼 돈다.
  - `fail_next` 와 같은 호출에 함께 걸리면 기다린 뒤 그 실패를 낸다.
- 기다림은 반드시 `store.lock` 을 잡기 **전에** 한다. 이유: 잡은 채 기다리면 GUI 스레드의 다른 가짜 호출이 모두 멈춘다.
- 안전장치: 10초 안에 풀리지 않으면 `AssertionError("hold_next(<name>) 가 풀리지 않았다")` 를 낸다. 테스트가 영원히 멈추지 않게 한다.
- step 2(History `recent`)와 step 3(폴링 `etag`)이 이것으로 `Task` 를 붙잡아 둔다.
- `tests/gui/test_fake_store.py` 에 테스트를 더한다.
  - 워커 스레드의 잡힌 호출이 기다리는 동안 GUI 스레드의 다른 호출은 끝난다.
  - set하면 잡힌 호출이 끝나고 `calls` 에 남는다.
  - `fail_next` 와 함께 걸면 기다린 뒤 실패한다.

### 3. History fixture (`tests/gui_support/helpers.py`, `tests/gui/conftest.py`)

- `helpers.py` 에 `install_fake_history(monkeypatch)` 를 더한다. `genviewer.controllers.history_tab` 모듈의 `AuditRepository`·`ProcessRepository` 를 가짜로 바꾼다(`install_fake_db` 와 같은 방식).
- `conftest.py` 에 `history_ctrl` fixture를 더한다.
  - `install_fake_history` 후 `HistoryTab()`(`qtbot.addWidget`)과 `HistoryTabController(view)` 를 만든다.
  - `set_db(FakeDatabase(store))` 를 부르고, 첫 다시 읽기가 끝날 때까지 기다린다(`qtbot.waitUntil(lambda: ctrl._task is None and store.calls_of("recent") != [])`).
  - 정리 때 `ctrl.shutdown()` 을 부른다.
- 시드: `store` fixture는 그대로 둔다. History 테스트는 필요한 줄을 `store.add_audit` 로 넣은 뒤 `ctrl.reload()` 한다. fixture가 만들기 전에 넣어야 하면 그 테스트 모듈에서 store를 덮어쓴다.
- `main_window` fixture는 바꾸지 않는다. History 화면을 만들지 않는 것이 그 fixture의 계약이다.

### 4. contract test (`tests/gui/test_fake_repo_contract.py`)

- `backend` namespace에 다음을 더한다.
  - `.audit`: 실제는 `AuditRepository(db)`, 가짜는 `FakeAuditRepository(fake_db)`
  - 시드 헬퍼 `.log(actor, entry)`: 실제는 `with db.connection() as conn: audit.write(conn.cursor(), actor, [entry])`, 가짜는 `store.add_audit(actor, entry)`
- 기대값을 직접 적는 테스트
  - (a) 세 줄을 넣고 `limit=2` 면 둘째·셋째가 오래된 것부터 온다.
  - (b) `actor`·`process`·`device` 필터
  - (c) `contains` 는 summary와 detail 양쪽에서 대소문자를 무시하고 찾는다.
  - (d) `since`/`until` 경계. 기준 시각은 반환된 줄의 `at` 에서 만든다. 실제는 서버 `now()`, 가짜는 store 시계라 벽시계로 만들면 안 된다.
  - (e) `after_id`
  - (f) 행의 키 집합이 `_COLUMNS` 와 같다.
- "fake 결과 == real 결과" 비교를 두지 마라(그 파일의 docstring).

### 5. smoke (`tests/gui/test_history_smoke.py`, 새 파일)

- `history_ctrl` 에서 줄 둘을 넣고 `reload()` 한 뒤 기다린다. 표가 최신 것부터 두 줄, 개수 표시가 `"2줄"`, process 콤보에 `"(전체)"` 와 시드 process들이 있다.
- 필터 하나(`who_field` + `returnPressed`)가 `recent` 호출의 `actor` 인자로 간다.

## Acceptance Criteria

```bash
# GENDB_TEST_PG_DSN 이 없으면 blocked 로 멈춘다 (contract test 의 real 쪽이 skip 되면 이 step 은 검증되지 않는다)
uv run pytest tests/gui/test_fake_repo_contract.py tests/gui/test_fake_store.py tests/gui/test_history_smoke.py -q -rs   # real 매개변수가 skip 이 아니어야 한다
uv run ruff check src tests
uv run pytest -q
git diff --stat -- src                       # 비어 있어야 한다
```

## 검증 절차

1. 위 AC 커맨드를 실행한다. `-rs` 출력에 contract test의 real 쪽 skip이 있으면 통과로 보지 않는다.
2. 아키텍처 체크리스트를 확인한다.
   - `src/` 가 바뀌지 않았는가?
   - 가짜 repo 메서드에 실제에 없는 인자를 더하지 않았는가(fakes.py 원칙)?
   - `hold_next` 가 `store.lock` 밖에서 기다리는가?
   - 테스트 헬퍼가 `tests/gui_support/` 에 있고, 테스트가 conftest나 다른 테스트 모듈을 import하지 않는가?
3. 결과에 따라 `phases/12-gui-async-cleanup/index.json` 의 step 0을 업데이트한다.
   - 성공 → `"status": "completed"`, `"summary": "FakeAuditRepository.recent + store.add_audit + store.hold_next(method)->Event(lock 밖 대기, 10초 안전장치) + install_fake_history + history_ctrl fixture. contract: <테스트 이름들> (real <N> passed). src 불변"`
   - 수정 3회 시도 후에도 실패 → `"status": "error"`, `"error_message": "구체적 에러 내용"`
   - `GENDB_TEST_PG_DSN` 이 없음 → `"status": "blocked"`, `"blocked_reason": "GENDB_TEST_PG_DSN 없음: contract test real 쪽이 돌지 않는다"` 후 즉시 중단

## 금지사항

- `src/` 를 바꾸지 마라. 이유: 이 step은 테스트 기반만 깐다. History 버그는 step 1·2가 재현부터 한다.
- 가짜 쓰기 메서드가 이력을 남기게 하지 마라. 이유: 다른 GUI 테스트의 기대(이력 없음)가 바뀌고 범위가 커진다. 이력은 `add_audit` 로만 넣는다.
- `hold_next` 를 `store.lock` 을 잡은 채 기다리게 만들지 마라. 이유: GUI 스레드가 굳어 테스트가 10초 안전장치까지 멈춘다.
- `main_window` fixture가 History 화면을 만들게 바꾸지 마라. 이유: 기존 테스트가 그 fixture의 지금 모양에 기대어 있다(`FakeDatabase.connection()` 이 실제 repo를 막는다).
- 기대값을 벽시계(`datetime.now()`)로 만들지 마라. 이유: 가짜는 store 시계(2026-10-17 09:00 UTC부터)를 쓴다.
- 기존 테스트를 깨뜨리지 마라.
