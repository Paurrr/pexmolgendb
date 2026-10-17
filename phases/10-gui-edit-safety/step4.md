# Step 4: reload-guard

## 배경 (phase 10 공통)

이 저장소는 이미 여러 명이 쓰는 도구다. 평소에는 **에러·버그만 고친다**(CLAUDE.md, ADR-015). phase 10은 GUI에서 저장하지 않은 편집이 말없이 사라지거나, 엉뚱한 충돌이나 잘못된 저장이 나는 경로를 한 step에 하나씩 고친다. 대상 경로는 충돌 대화상자의 덮어쓰기, 같은 행 재클릭, 붙여넣기의 version과 탭 편집, 재접속·CSV 불러오기, Remove Process, Virtuoso 필터 중 저장 순서다. 모두 2026-10-17 docs/notes 분류에서 나온 항목이다(`docs/notes/known-issues.md` K17·K19·K20·K36·K37·K38·K42).
- K17·K38은 버그다.
- K19·K20·K36·K37·K42는 **사용자가 2026-10-17 승인한 동작 변경**이다. 승인 step에는 승인된 동작 문장을 "승인된 동작"에 그대로 적었다. 그 문장을 넘는 변경(새 문구, 새 질문, 다른 경로의 동작 변경)은 하지 않는다.

phase 0~9가 먼저 끝나 있다.
- GUI 저장 경로의 계약은 phase 3·4가 만들었다.
  - `save_all() -> bool`(device·탭), `DeviceTabController.save_db() -> bool`
  - `select_process_silently(name) -> bool`
  - `deviceVersionBumped`/`adopt_device_version`, `_save_before_process_change`
  - device 표 붙여넣기의 `Unsaved Changes` 거부, `save_all` 의 `Save Skipped` 경고
- phase 6~9는 GUI 코드를 바꾸지 않았다(경계 가드 테스트, service·schema, 운영 스크립트).
- 정확한 계약은 코드와 `phases/3-gui-save-fixes/index.json`·`phases/4-gui-robustness/index.json` 의 summary로 확인하라.

모든 step에 같은 규칙이 적용된다.
1. 버그 step(K17, K38)
   - 아래 "버그"는 **분석의 주장**이다. 먼저 실패하는 테스트로 재현하고, RED 출력(테스트 이름과 실패한 단언)을 summary에 적는다.
   - 재현되지 않으면 `src/` 를 고치지 않는다. 테스트는 특성 테스트로 남기고 `"status": "completed"`, `"summary": "not reproduced: <이유>"` 로 끝낸다.
2. 승인 step(K19, K20, K36, K37, K42): 새 동작을 단언하는 테스트를 먼저 쓰고, 수정 전에 실패하는 것을 본다(RED). 그 출력도 summary에 적는다.
3. RED는 **Windows 개발 PC에서** 보여야 한다. `posix_only` 테스트는 개발 PC에서 skip되므로 증명이 아니다.
4. 고친 뒤 수정을 손으로 되돌려 새 테스트가 실패하는지 확인하고, 다시 고친다(변이 검사).
   - `git checkout`/`git stash` 로 되돌리지 마라. 이유: 같은 step의 테스트 변경까지 사라진다.
5. 이 파일의 행 번호는 2026-10-17(phase 5 직후) 기준 대략값이다. phase 10의 앞 step이 같은 파일을 바꿨을 수 있으니 이름으로 찾아라.
6. `DeviceTabController.connect_db`·`_open_database` 는 phase 7·10·11이 차례로 건드린다. 그래서 본문을 이 파일에 옮겨 적지 않았다. 지금 코드를 읽고, 이름과 아래 불변식으로 작업하라.
7. repo(`service/repo/`)와 가짜 repo(`tests/gui_support/fakes.py` 의 `Fake*Repository`)의 의미는 바꾸지 않는다.
   - 그래서 이 phase에는 DB 테스트가 필요 없다. `GENDB_TEST_PG_DSN` 이 없어도 `blocked` 가 아니다.
8. 문서(`docs/`, README)는 이 phase의 step에서 바꾸지 않는다. phase 마무리에서 고친다(ADR-004 보강, UI_GUIDE, known-issues).
   - 예외는 이 파일이 따로 적은 것뿐이다(step 1의 CLAUDE.md 한 줄).

GUI 테스트 기반은 phase 2(`2-gui-test-infra`)가 만들었다. 아래 이름을 그대로 쓰고, 같은 일을 하는 것을 새로 만들지 마라. 작업 전에 `tests/gui/conftest.py`·`tests/gui_support/` 를 읽고, 이 파일의 서술과 다르면 실제 코드를 따른다.
- **대화상자 대역**: `tests/gui_support/dialogs.py` 의 `FakeDialogs` 이고, autouse `dialogs` fixture로 들어온다.
  - `dialogs.answer_question(*bools)` 는 Yes/No 질문에, `dialogs.answer_conflict(*choices)` 는 충돌 대화상자에 순서대로 답한다. 충돌 답은 `genviewer.dialogs.conflict` 의 `RELOAD`/`OVERWRITE`/`CANCEL` 이다.
  - 뜬 상자는 `dialogs.shown` 에 `(kind, title, text)` 로 쌓인다. kind는 `info`/`warning`/`error`/`critical`/`question` 이고, 충돌 대화상자는 `("conflict", "Save Conflict", <충돌 설명>)` 이다.
  - 답을 정하지 않은 모달은 `AssertionError` 를 내고 `dialogs.unexpected` 에 남는다. `@report` 가 그 예외를 삼키므로 실패는 **teardown에서** 드러난다. 쓰이지 않고 남은 답도 teardown 실패다.
- **`device_tab_ctrl`**: 가짜에 붙어 이미 접속한 `DeviceTabController` 다. `notifyRequested` 를 `dialogs.record_notify` 에 이어 두었으므로 알림도 `dialogs.shown` 에서 본다.
  - `main_window` fixture는 `MainWindowController` 다(`.device_tab` 이 같은 컨트롤러).
- **시드**(`seeded_store()`)
  - process `sf2p`(device `nfet_a` order 0, `nfet_b` order 1), `sf4u`(device `pfet_a`). 탭은 `"InstTerm"`·`"InstSchParam"`.
  - id는 `store.find_device("pfet_a")["id"]` 로 얻는다.
  - 접속하면 `sf2p` 가 자동으로 선택된다. autouse로 `GENDB_APP_USER=tester` 다.
- **store**
  - `store.calls` 는 `(메서드 이름, 인자 dict의 deep copy)` 이고, 호출이 **끝난 뒤**(예외로 끝나도) 기록된다.
  - `store.calls_of(name)`, `store.fail_next(name, exc)`(repo 메서드 이름 또는 `"open_database"`)
  - 남의 변경: `store.touch_device(id, actor="bob", **changes)`, 남의 삭제: `store.remove_device(id)`
  - 시드 추가: `store.add_device(process_id, name, celltype, order=…)`
  - 다른 사용자가 process를 지우는 흉내는 `ctrl.device_tab_toolbar.repo.delete("sf4u", actor="bob")` 다.
- **`tests/gui_support/helpers.py`**: `select_process(ctrl, name)`, `select_device_row(ctrl, row)`, `edit_device_cell(ctrl, row, column, value)`, `edit_tab_cell(ctrl, tab_name, row, column, value)`.
  - helpers는 기다리지 않는다. 기다림은 테스트가 `qtbot.waitUntil` 로 한다.
- "아무 일도 일어나지 않았다" 를 `qtbot.wait` 고정 대기로 확인하지 않는다. `store.calls` 를 `qtbot.waitUntil(lambda: <bool>)` 로 기다린 뒤 단언한다.
  - 콜백은 bool을 돌려줘야 한다(`lambda: store.calls_of("upsert_devices") != []`). 리스트를 돌려주면 pytest-qt가 `ValueError` 를 낸다.
  - 시그널 emit이나 직접 호출처럼 동기로 끝나는 동작은 돌아온 뒤 바로 단언해도 된다.
- 비슷한 테스트의 본보기: `tests/gui/test_device_save_result.py`, `tests/gui/test_tab_save_result.py`, `tests/gui/test_tab_version_sync.py`(`open_nfet_a`, `edit_nfet_a_tab`), `tests/gui/test_deleted_process_revert.py`, `tests/gui/test_process_list_refresh.py`, `tests/gui/test_device_save_guards.py`.

## 이 step의 목적

(**사용자 승인 2026-10-17**, K36) 저장하지 않은 편집을 묻지 않고 버리는 경로가 둘 있다. 버려지기 전에 묻게 한다.
- **재접속**(Database → Connect…): `apply_db()` 가 device 표를 다시 읽고(`refresh_devices`) 탭 섹션을 다시 만든다(`rebuild_all_sections`). 그래서 device 표 편집도 탭 편집도 사라진다.
- **CSV 불러오기**: 끝에서 `refresh_devices()` 로 device 표를 다시 읽는다. 탭 편집은 남는다.

**승인된 동작**: "저장 안 한 편집(device 표·탭)이 있으면 재접속·CSV 불러오기 전에 기존 'Refresh' 질문(문구 그대로)을 띄우고, 아니오면 멈춘다."

이 step의 해석(UI_GUIDE 원칙 2: 버려질 상황이면 먼저 묻는다):
- 재접속은 device 표 **또는** 탭이 dirty면 묻는다. 둘 다 버려지기 때문이다.
- CSV 불러오기는 device 표가 dirty일 때만 묻는다. 탭 편집은 불러오기가 지우지 않는다.
  - 탭 편집만 있을 때 물으면 버려지지 않을 것을 버린다고 말하게 된다.
  - phase 3 테스트 `test_loading_a_csv_keeps_the_current_process_and_its_tab_edits` 가 "탭 편집은 묻지 않고 남는다" 를 고정한다.
  - Virtuoso device 목록 응답(`MainWindowController._on_received_from_controller`)도 같은 이유로 device 표만 본다.
- 질문은 **새 DB를 열기 전, 불러오기 전에** 한다. 아니오면 아무것도 하지 않는다. 지금 DB, repo, 폴링, 화면, 편집이 그대로이고 알림도 없다.

질문은 `DeviceTabController._on_refresh_requested` 와 같은 `question(self.ui, "Refresh", "저장하지 않은 편집이 있습니다.\n서버 내용으로 다시 읽으면 그 편집은 사라집니다. 계속할까요?")` 이다. 문구를 한 글자도 바꾸지 않는다.

## 읽어야 할 파일

- `/CLAUDE.md`, `/docs/UI_GUIDE.md`(원칙 2·3, "Refresh" 질문), `/docs/ARCHITECTURE.md`(데이터 흐름 → DB 접속: 새 DB를 먼저 열고 실패하면 지금 DB 유지), `/docs/ADR.md`(ADR-004, ADR-009 "phase 4 보강")
- `src/genviewer/controllers/device_tab.py`
  - `_on_connect(dsn)` (~109-116): 사용자가 Connect… 창에서 확인했을 때의 유일한 입구. `connect_db` 가 False면 "Connect Failed" 를 알린다.
  - `connect_db(dsn) -> bool`: 생성자의 첫 접속(`QTimer.singleShot`)과 테스트도 직접 부른다. 본문과 순서는 phase 7·11도 건드린다. **이 step에서는 바꾸지 않는다.**
  - `apply_db` (~280-286), `on_load_csv_requested(path)` (~354-380, `@report("Load CSV Failed")`), `_on_refresh_requested` (~239-253, 질문 문구의 원본)
- `src/genviewer/views/device_tab.py`
  - `dbConnectRequested`/`loadCsvRequested` (~68-69)
  - `_open_connect` (~133-137, 창에서 확인하면 `dbConnectRequested.emit(dsn)`), `_ask_load_csv` (~139-143, 파일을 고르면 `loadCsvRequested.emit(path)`)
- `src/genviewer/controllers/main_window.py` `_on_received_from_controller` (~162-184): device 표만 보고 같은 질문을 하는 본보기다. 이 파일은 바꾸지 않는다.
- `tests/gui/test_process_list_refresh.py`
  - `test_loading_a_csv_keeps_the_current_process_and_its_tab_edits` (~65-84)
  - `test_reconnecting_keeps_the_current_process` (~111-122, `connect_db("")` 를 직접 부른다)
  - `CSV_TEXT`, `edit_pfet_a_tab`, `open_sf4u`
- `tests/gui/test_connect_db.py`(재접속 테스트 본보기, `store.fail_next("open_database", …)`), `tests/gui/test_window_guards.py`(같은 "Refresh" 질문 단언의 본보기)

## 승인된 동작 변경

지금은 재접속과 CSV 불러오기가 묻지 않고 편집을 버린다. 위 승인된 동작으로 바꾼다.

## 작업

### 결과 × 상태: 재접속 (`_on_connect(dsn)`, `ui.dbConnectRequested` 로 들어온다)

| 편집 | 질문 | 답 | 접속 | 최종 상태 | 알림 |
|---|---|---|---|---|---|
| 없음 | 없음 | - | 성공 | 새 DB, `apply_db` (지금과 같다) | info "Connected" |
| 없음 | 없음 | - | 실패 | 지금 DB 유지 (지금과 같다) | error "Connect Failed" |
| device 표 또는 탭 dirty | "Refresh" | 아니오 | **시도하지 않음**(`open_database` 호출 없음) | 지금 DB·repo·폴링·화면·편집 그대로 | 없음 |
| 〃 | "Refresh" | 예 | 성공 | 새 DB, `apply_db` 가 편집을 버림(device 표·탭 dirty 아님) | info "Connected" |
| 〃 | "Refresh" | 예 | 실패 | 지금 DB 유지, `apply_db` 를 부르지 않으므로 **편집도 그대로** | error "Connect Failed" |

- 첫 접속(생성자의 예약)은 `connect_db` 를 직접 부르므로 묻지 않는다. 그때는 편집이 있을 수 없다.
- `connect_db` 의 반환 계약(bool)과 그 안의 순서(새 DB 먼저, 실패하면 지금 DB 유지, 옛 DB는 폴링이 끝난 뒤 닫음)는 바꾸지 않는다. 질문은 `_on_connect` 에서 `connect_db` 를 부르기 전에 한다.
  - 아니오를 `connect_db` 의 False로 흉내 내지 마라. "Connect Failed" 가 뜬다.

### 결과 × 상태: CSV 불러오기 (`on_load_csv_requested(path)`)

| 접속 | device 표 dirty | 질문 | 답 | 불러오기 | 최종 상태 | 알림 |
|---|---|---|---|---|---|---|
| 안 됨 | - | 없음 | - | 없음 | 지금과 같다 | warn "Database Not Loaded" (지금과 같다. 질문보다 먼저) |
| 됨 | 아니오(탭만 dirty 포함) | 없음 | - | 함 | 지금과 같다. 탭 편집은 남는다 | info "Load CSV" |
| 됨 | 예 | "Refresh" | 아니오 | **안 함**(`import_data` 호출 없음) | 편집·목록 그대로 | 없음 |
| 됨 | 예 | "Refresh" | 예 | 함 | device 표 다시 읽음(편집 버림), 탭 편집은 남음 | info "Load CSV" |
| 됨 | 예 | "Refresh" | 예 | 실패(예외) | `refresh_devices` 전에 멈추므로 device 편집이 남는다 | error "Load CSV Failed" (`@report`, 지금과 같다) |

### 1. 테스트 먼저 (새 파일 `tests/gui/test_reload_guard.py`)

공통 준비: `device_tab_ctrl`, `store`, `dialogs`.
- device 편집은 `edit_device_cell(ctrl, 0, "description", …)` 로 만든다(sf2p nfet_a).
- 탭 편집은 nfet_a를 골라 `edit_tab_cell` 로 만든다.
- 재접속은 `ctrl.ui.dbConnectRequested.emit("")` 로, CSV는 `ctrl.on_load_csv_requested(str(path))` 로 한다(`test_process_list_refresh.py` 의 `CSV_TEXT` 형태, `encoding="utf-8"`).
- 질문 단언은 `("question", "Refresh", <위 문구>)` 가 `dialogs.shown` 에 정확히 한 번 있는지로 한다.

재접속:
- **device dirty + 아니오(RED)**: `answer_question(False)` → emit. 단언은 다음과 같다.
  - `open_database` 호출이 늘지 않았다.
  - `ctrl.db` 가 같은 객체다.
  - device 표가 dirty이고 값이 남아 있다.
  - `dialogs.shown` 이 질문 하나뿐이다("Connected"/"Connect Failed" 없음).
  - **수정 전에는 질문이 뜨지 않아 실패해야 한다**(쓰이지 않은 답 또는 dirty 단언).
- **탭만 dirty + 아니오**: 같은 단언, 탭 값과 dirty가 남는다.
- **dirty + 예 + 성공**: "Connected" info, device 표·탭 dirty 아님, `ctrl.db` 가 새 객체다.
- **dirty + 예 + 실패**: `store.fail_next("open_database", DbUnavailableError("boom"))` → "Connect Failed" error, `ctrl.db` 가 같은 객체, device 편집이 남는다.
- **편집 없음**: 질문 없이 접속하고 "Connected"(특성 테스트).

CSV:
- **device dirty + 아니오(RED)**: `import_data` 호출이 없다, 편집이 남는다, "Load CSV" 알림이 없다.
- **device dirty + 예**: "Load CSV" info, device 표 dirty 아님.
- **device dirty + 예 + 실패**: `store.fail_next("import_data", RuntimeError("boom"))` → "Load CSV Failed" error, device 편집이 남는다.
- 탭만 dirty: 질문 없음. 기존 `test_loading_a_csv_keeps_the_current_process_and_its_tab_edits` 가 그대로 통과해야 한다.

### 2. 수정

- `controllers/device_tab.py` 의 `_on_connect` 와 `on_load_csv_requested` 앞부분에 위 표의 질문을 더한다. `connect_db`·`apply_db` 본문은 바꾸지 않는다.
- 질문 문구가 이 파일에 두 번 나오게 되면 이 모듈 안의 상수 하나로 묶어도 된다. `main_window.py` 의 같은 문구는 건드리지 않는다.

### 3. 변이 검사

`_on_connect` 의 질문을 손으로 지워 재접속 RED 테스트가 실패하는지 본다. CSV의 조건을 `device 표 or 탭` 으로 바꿔 `test_loading_a_csv_keeps_the_current_process_and_its_tab_edits` 가 실패하는지 본다(쓰이지 않은 질문). 둘 다 되돌린다.

## Acceptance Criteria

```bash
uv run pytest tests/gui/test_reload_guard.py -q   # 새 테스트 통과 (수정 전에는 '아니오' 테스트가 실패해야 한다)
uv run pytest tests/gui/test_process_list_refresh.py tests/gui/test_connect_db.py -q   # phase 3·4 재접속·CSV 테스트 그대로 통과
uv run ruff check src tests
uv run pytest tests/gui -q
uv run pytest -q
```

## 검증 절차

1. 위 AC 커맨드를 실행한다.
2. 아키텍처 체크리스트를 확인한다.
   - 질문 제목·문구가 `_on_refresh_requested` 와 글자까지 같은가? 새 알림·로그 문구가 없는가?
   - `connect_db` 의 반환 계약과 접속 순서(ARCHITECTURE "DB 접속")가 그대로인가?
   - 아니오를 고르면 DB 호출이 하나도 없는가?
3. 결과에 따라 `phases/10-gui-edit-safety/index.json` 의 step 4를 업데이트한다.
   - 성공 → `"status": "completed"`, `"summary": "K36(승인): _on_connect 는 device 표나 탭이 dirty 면, on_load_csv_requested 는 device 표가 dirty 면 기존 Refresh 질문을 먼저 하고 아니오면 아무것도 하지 않음(connect_db 불변). RED: <테스트 이름과 단언>. 변이: <결과>. tests/gui/test_reload_guard.py"`
   - 수정 3회 시도 후에도 실패 → `"status": "error"`, `"error_message": "구체적 에러 내용"`
   - 사용자 개입 필요 → `"status": "blocked"`, `"blocked_reason": "구체적 사유"` 후 즉시 중단

## 금지사항

- 질문을 `connect_db` 안에 넣지 마라. 이유: 첫 접속과 테스트가 직접 부르고 반환값이 bool이라 "아니오" 를 실패와 구별할 수 없다. phase 7·11도 그 본문을 바꾼다.
- "Save Changes"(저장할까요?)를 묻거나 저장을 먼저 하지 마라. 이유: 승인된 동작은 기존 "Refresh" 질문이다.
- CSV 불러오기에서 탭 편집만 있을 때 묻지 마라. 이유: 불러오기는 탭 편집을 지우지 않는다. phase 3 테스트가 고정한 동작이다.
- `MainWindowController` 의 Virtuoso 목록 질문과 Refresh 배너 경로를 바꾸지 마라. 이유: 범위 밖이다.
- 기존 테스트를 깨뜨리지 마라.
