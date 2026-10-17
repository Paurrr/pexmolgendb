# Step 2: controller-fixtures

## 배경 (phase 2 공통)

이 저장소는 이미 여러 명이 쓰는 도구다. 지금은 **에러·버그만 고친다**(CLAUDE.md, ADR-015). 다음 phase `3-gui-save-fixes` 와 `4-gui-robustness` 는 GUI 컨트롤러의 버그를 실패하는 테스트로 재현한 뒤 고친다. phase 2는 그 테스트를 쓸 수 있는 **GUI 테스트 기반만** 깐다. step 0은 pytest-qt와 모달 대화상자 가짜(`dialogs` fixture), step 1은 실제 repo와 같은 의미의 가짜 repo(`tests/gui_support/fakes.py`), step 2는 가짜 repo에 붙은 컨트롤러 fixture와 헬퍼다. **`src/` 는 한 줄도 바꾸지 않는다.**

모든 step에 같은 규칙이 적용된다.
1. `src/` 를 고치지 않는다. 이 phase에는 고칠 버그가 없으므로 "실패하는 테스트로 먼저 재현" 규칙 대신 **지금 코드의 동작을 그대로 드러내는 테스트만** 쓴다. 테스트를 쓰다 버그로 보이는 동작을 만나면 고치지 말고, 그 동작을 단언하지도 말고(뒤 phase가 고치면 깨질 단언을 남기지 않는다), summary에 `파일:행 — 관찰` 로 적는다.
2. 새 의존성은 pytest-qt 하나뿐이다(사용자 승인 2026-10-17). step 0이 넣었다.
3. 이 파일들에 적은 이름(fixture, 클래스, 메서드, 헬퍼, 모듈 경로)은 phase 3/4 step 파일이 그대로 쓴다. 이름·인자·의미를 바꾸지 마라. 더하는 것은 괜찮다.
4. 테스트 기반도 변이 검사를 한다. 가짜·fixture의 핵심 규칙 하나를 손으로 망가뜨려 그것을 지키는 테스트가 실패하는지 보고 되돌린다. `git checkout`/`git stash` 로 되돌리지 마라. 이유: 같은 step의 다른 변경까지 사라진다.
5. "아무 일도 일어나지 않음"은 고정 대기(`qtbot.wait`, `time.sleep`) 대신 fake가 기록한 호출이나 컨트롤러 상태를 `qtbot.waitUntil` 로 기다린 뒤 단언한다.
6. 이 파일의 행 번호는 2026-10-17 기준 대략값이다. 이름으로 찾아라.

## 이 step의 목적

가짜 repo에 붙은 **실제** `DeviceTabController` 와 `MainWindowController` 를 fixture 하나로 띄우고, 사용자 동작(process 고르기, device 행 고르기, 셀 고치기)을 헬퍼로 흉내 낸다. phase 3/4의 RED 테스트는 전부 이 fixture와 헬퍼 위에서 쓴다. smoke 테스트로 "띄우고, 읽고, 고치고, 바뀐 것을 알리고, 닫는다"가 도는 것을 보인다.

## 읽어야 할 파일

먼저 아래 파일들을 읽고 설계 의도를 파악하라.

- `/CLAUDE.md`(테스트 관례: step 0·1이 더한 GUI 줄), `/docs/ARCHITECTURE.md`(스레딩, 변경 감지), `/docs/UI_GUIDE.md`(레이아웃, 문구)
- `src/genviewer/controllers/device_tab.py` — `__init__` (~44-89: 마지막 줄 `self.connect_db(dsn)`. 지금은 생성자 안에서 동기로 접속한다), `set_repo` (~91-97: 이 모듈의 이름 `IORepository`/`DeviceRepository`/`ParameterRepository`/`ProcessRepository` 로 repo를 만든다), `_open_database` (~129-136, staticmethod), `connect_db` (~138-169), `_poll_remote_changes`/`_on_poll_result` (~176-209), `close_db` (~234-251), `apply_db` (~253-259), `on_current_row_changed` (~357-370), `on_process_changed` (~380-403), `_switch_device_by_index` (~420-454)
- `controllers/device_table.py` — `refresh_devices` (~256-297), `is_dirty` (~212), `_on_current_changed`/`last_selected_device` (~222-241)
- `controllers/parameter_tab.py` — `section(name)` (~44), `is_dirty` (~47), `set_device_to_section` (~117)
- `controllers/tab_section.py` — `update_model` (~182-192: device를 고르면 GUI 스레드에서 동기로 `fetch_by_device`), `model`, `columns`
- `controllers/device_tab_toolbar.py` — `refresh_processes` (~130-135, `@report("Process List Failed")`), `get_process_id` (~143-150)
- `views/device_tab_toolbar.py` — `set_processes` (~158-161): `clear()` 가 `currentTextChanged("")` 를, `addItems` 가 첫 항목을 내므로 **접속 직후 첫 process가 자동으로 골라진다**
- `views/device_table.py` — `model()` 은 정렬 proxy, `model_safe()` 는 source. `models/device_table.py` `_columns = ["name", "celltype", "description"]`, `setData` (~182)
- `views/tab_section.py`, `models/generic_table.py` `setData` (~79-97: `delegate_config` 로 검증하고 실패하면 False)
- `views/main_window.py` — `MainWindow(hostname, show_history=False)`, `notify`
- `controllers/main_window.py` — `MainWindowController(ui, dsn)` (~21-62: `DeviceTabController` 를 만든 **뒤에** `notifyRequested` 를 잇는다), `shutdown` (~64-69)
- `config/tab_config.json` — `"InstTerm"` → `inst_terms` [`reserved_key`, `cds_inst_term_name`], `"InstSchParam"` → `inst_sch_params` [`reserved_key`, `cds_inst_parameter_name`]. `config/delegate_config.json` — `device.celltype.items`, NFET/PFET의 `inst_terms.reserved_key` 는 DRN·GATE·SRC·BULK, `inst_sch_params.reserved_key` 는 LENGTH·WIDTH·WNS·NFIN·NF·MBC
- 이전 step에서 만든 파일: `pyproject.toml`, `tests/gui/conftest.py`, `tests/gui_support/dialogs.py`, `tests/gui_support/fakes.py`, `tests/gui/test_dialogs_fixture.py`, `tests/gui/test_fake_repo_contract.py`, `tests/gui/test_fake_store.py`

## 작업

### 1. 시드와 헬퍼 (`tests/gui_support/helpers.py`, 새 파일)

```python
def seeded_store() -> FakeStore: ...
def install_fake_db(monkeypatch, store: FakeStore) -> None: ...
def select_process(ctrl: DeviceTabController, name: str) -> None: ...
def select_device_row(ctrl: DeviceTabController, row: int) -> None: ...
def edit_device_cell(ctrl: DeviceTabController, row: int, column: str, value: str) -> None: ...
def edit_tab_cell(ctrl: DeviceTabController, tab_name: str, row: int, column: str, value: str) -> None: ...
```

`seeded_store()` 는 아래를 이 순서로 넣는다(id는 FakeStore가 매긴다: process sf2p=1, sf4u=2, device nfet_a=1, nfet_b=2, pfet_a=3. 테스트는 숫자 대신 `store.find_device("nfet_a")["id"]` 를 쓴다). description `""`, version 1, updated_by `"seed"`. 값은 `delegate_config` 검증을 통과한다.

| process | device | celltype | order | InstTerm (`inst_terms`) | InstSchParam (`inst_sch_params`) |
|---|---|---|---|---|---|
| sf2p | nfet_a | NFET | 0 | DRN d / GATE g / SRC s / BULK b | LENGTH l / WIDTH w |
| sf2p | nfet_b | NFET | 1 | DRN d2 / GATE g2 | NF nf2 |
| sf4u | pfet_a | PFET | 0 | DRN pd / GATE pg | LENGTH pl |

(각 칸은 `reserved_key 값` 쌍. 두 번째 컬럼은 `cds_inst_term_name` / `cds_inst_parameter_name`.)

`install_fake_db(monkeypatch, store)`: `genviewer.controllers.device_tab` 모듈에서
- `DeviceTabController._open_database` 를 `staticmethod(store.open_database)` 로,
- `DeviceRepository`, `ParameterRepository`, `ProcessRepository`, `IORepository` 를 `FakeDeviceRepository`, `FakeParameterRepository`, `FakeProcessRepository`, `FakeIORepository` 로 바꾼다.

fixture가 쓰고, 접속 전에 store를 손봐야 하는 테스트(첫 접속 실패: `store.fail_next("open_database", DbUnavailableError("x"))` 뒤에 직접 컨트롤러를 만든다)도 쓴다.

헬퍼는 사용자 동작 하나만 흉내 내고 **기다리지 않는다**. 결과(탭 로드, 저장)는 테스트가 `qtbot.waitUntil` 로 기다린다. 이유: phase 4가 탭 로드나 첫 접속을 비동기로 옮겨도 헬퍼는 그대로 써야 한다. 전제가 틀리면 메시지가 있는 `AssertionError` 를 낸다.
- `select_process(ctrl, name)`: `ctrl.device_tab_toolbar.ui.process_selector` 에 그 이름이 있는지 확인(없으면 목록을 담은 AssertionError)하고 `setCurrentText(name)`. 이미 골라진 process면 콤보가 시그널을 내지 않으므로 아무 일도 일어나지 않는다(접속 직후에는 `"sf2p"` 가 이미 골라져 있다).
- `select_device_row(ctrl, row)`: `view = ctrl.ui.device_table_view`, `index = view.model().index(row, 0)`(proxy, 화면에 보이는 순서). 유효한지 확인하고 `view.setCurrentIndex(index)`. 사용자가 행을 클릭한 것과 같은 `currentChanged`/`currentRowChanged` 가 나간다.
- `edit_device_cell(ctrl, row, column, value)`: column은 `"name"`/`"celltype"`/`"description"`. proxy의 `setData(proxy.index(row, col), value, Qt.EditRole)` 가 True인지 확인한다(False면 같은 값이거나 검증 실패다).
- `edit_tab_cell(ctrl, tab_name, row, column, value)`: `sec = ctrl.parameter_tab.section(tab_name)`(tab_config 키, 예 `"InstTerm"`). `sec` 와 `sec.model` 이 있는지 확인(device를 먼저 골라야 한다)하고 `sec.model.setData(sec.model.index(row, sec.columns.index(column)), value, Qt.EditRole)` 가 True인지 확인한다.

### 2. fixture (`tests/gui/conftest.py` 에 더한다)

```python
@pytest.fixture(autouse=True)
def _app_user(monkeypatch) -> None:
    monkeypatch.setenv("GENDB_APP_USER", "tester")    # current_user() → "tester". actor 가 정해진다

@pytest.fixture
def store() -> FakeStore:
    return seeded_store()

@pytest.fixture
def device_tab_ctrl(qtbot, monkeypatch, store, dialogs) -> Iterator[DeviceTabController]:
    install_fake_db(monkeypatch, store)
    view = DeviceTab()
    qtbot.addWidget(view)
    ctrl = DeviceTabController(view, "")
    ctrl.notifyRequested.connect(dialogs.record_notify)
    qtbot.waitUntil(lambda: ctrl.connected is not None)
    yield ctrl
    ctrl.close_db()

@pytest.fixture
def main_window(qtbot, monkeypatch, store, dialogs) -> Iterator[MainWindowController]:
    install_fake_db(monkeypatch, store)
    ui = MainWindow("localhost")
    qtbot.addWidget(ui)
    controller = MainWindowController(ui, "")
    qtbot.waitUntil(lambda: controller.device_tab.connected is not None)
    yield controller
    controller.shutdown()
    ui.close()
```

- 접속은 `qtbot.waitUntil(lambda: ….connected is not None)` 로만 기다린다. 지금은 생성자 안에서 끝나 바로 참이 되고, phase 4가 첫 접속을 `QTimer.singleShot(0)` 으로 옮겨도 그대로 돈다.
- `device_tab_ctrl` 은 MainWindow 없이 뜨므로 `notifyRequested` 를 `dialogs.record_notify` 에 이어 알림이 `dialogs.shown` 에 남게 한다(MainWindow.notify와 같은 kind). 생성 **뒤에** 잇는 것은 `MainWindowController` 와 같은 순서다. 생성 중(지금은 첫 접속 중)의 알림은 실제 앱에서도 어디에도 가지 않는다. 이 순서를 "고치지" 마라.
- `main_window` 는 `MainWindowController` 를 돌려준다. `main_window.ui` 가 `MainWindow`, `main_window.device_tab` 이 `DeviceTabController` 다(헬퍼에는 이것을 넘긴다). 창은 띄우지 않는다. 포커스가 필요한 테스트(Ctrl+S 라우팅은 `focusWidget()` 을 본다)는 직접 `main_window.ui.show()` 와 `qtbot.waitExposed(main_window.ui)` 를 한다. History 화면(`show_history=True`)은 만들지 않는다.
- teardown은 몇 번 불려도 안전해야 한다(`close_db`/`shutdown` 은 이미 닫혔으면 아무것도 안 한다). 테스트가 먼저 `shutdown()` 해도 된다.
- pytest-qt는 fixture teardown **전에** `qtbot.addWidget` 으로 등록한 위젯을 `close()`·`deleteLater()` 한다. `close_db`/`shutdown` 이 그 뒤에 불려도 C++ 객체가 살아 있는지(`RuntimeError: Internal C++ object … already deleted` 가 없는지) 확인한다. 문제가 있으면 `qtbot.addWidget(view, before_close_func=lambda _w: ctrl.close_db())` 처럼 close 전에 부른다. 위젯을 등록하지 않고 두지는 마라(남은 창이 다음 테스트에 섞인다).

### 3. smoke 테스트 (`tests/gui/test_smoke.py`, 새 파일)

- `test_connecting_fills_the_process_list`: `connected is True`, 콤보 항목이 `["sf2p", "sf4u"]`, 현재 `"sf2p"`, device 표(proxy 순서)의 이름이 `["nfet_a", "nfet_b"]`, `store.calls` 에 `list_all`·`fetch_devices_by_process` 가 있고, `ctrl.db` 가 닫히지 않은 FakeDatabase다.
- `test_selecting_a_device_loads_its_tab_rows`: `select_device_row(ctrl, 0)` 뒤 `qtbot.waitUntil` 로 `InstTerm` 섹션 모델이 4행이 되기를 기다리고, 내용이 `store.rows("inst_terms", nfet_a id)` 의 두 컬럼과 같다. `InstSchParam` 은 2행이다.
- `test_choosing_another_process_shows_its_devices`: `select_process(ctrl, "sf4u")` 뒤 이름이 `["pfet_a"]`, `current_process_id` 가 sf4u의 id다. 질문은 뜨지 않았다(`dialogs.shown` 에 question 없음).
- `test_an_edit_marks_the_screen_dirty_without_writing`: device 0을 고르고 `edit_device_cell(ctrl, 0, "description", "edited")` → `ctrl.device_table.is_dirty()`, `edit_tab_cell(ctrl, "InstTerm", 0, "cds_inst_term_name", "dd")` → `ctrl.parameter_tab.is_dirty()`. `store.calls` 에 `upsert_device`·`upsert_devices`·`replace_many_for_device` 가 없고 store 값도 그대로다.
- `test_a_poll_without_changes_keeps_the_banner_hidden`: `n = len(store.calls_of("etag"))`, `ctrl._poll_remote_changes()` 뒤 `qtbot.waitUntil(lambda: len(store.calls_of("etag")) == n + 1 and ctrl._poll_task is None)` 로 워커 스레드의 폴링과 결과 슬롯이 끝나기를 기다리고, `ctrl.ui.refresh_banner.isHidden()` 을 단언한다. 이것이 "아무 일도 일어나지 않음"의 표준 모양이다.
- `test_another_users_save_shows_the_banner`: `store.touch_device(nfet_a id, actor="kim")` 뒤 폴링하면 `qtbot.waitUntil` 로 배너가 보이고(`not isHidden()`) 문구에 `"kim"` 이 있다. 자동으로 다시 읽지 않는다(`fetch_devices_by_process` 호출 수 그대로, ADR-004).
- `test_a_failing_call_is_reported`: `store.fail_next("list_all", RuntimeError("boom"))` 뒤 `ctrl.device_tab_toolbar.refresh_processes()` → `dialogs.shown` 에 kind `"error"`, 제목 `"Process List Failed"`, 본문에 `"boom"`.
- `test_the_main_window_starts_and_shuts_down_cleanly(main_window, store, dialogs)`: `main_window.device_tab.connected is True`, 접속만으로는 대화상자가 하나도 뜨지 않는다(`dialogs.shown == []`), `history_tab is None`. `db = main_window.device_tab.db` 를 잡고 `main_window.shutdown()` 하면 `db.closed`, `device_tab.db is None`, `connected is False`, `store.calls` 에 `"db.close"` 가 있다.

변이 검사: `install_fake_db` 에서 `_open_database` 패치를 빼면(진짜 접속 시도 → 실패) 또는 repo 이름 하나를 빼면(실제 repo가 `FakeDatabase.connection()` 에서 AssertionError) smoke 테스트가 실패하는지 확인하고 되돌린다.

### 4. 문서

- `CLAUDE.md` "테스트 관례"에 한 줄: 컨트롤러 테스트는 `tests/gui/conftest.py` 의 `store`(시드: sf2p/nfet_a·nfet_b, sf4u/pfet_a, 탭 InstTerm·InstSchParam), `device_tab_ctrl`, `main_window` fixture와 `from gui_support.helpers import select_process, select_device_row, edit_device_cell, edit_tab_cell` 로 쓴다. 장애는 `store.fail_next(메서드, 예외)`, 남의 변경은 `store.touch_device`/`store.remove_device`, 일어난 일은 `store.calls`/`store.calls_of` 로 본다. actor는 `GENDB_APP_USER=tester` 다.
- 기준선 숫자: Git Bash에서 `uv run pytest -q` 결과로 `CLAUDE.md` "테스트 관례"의 기준선과 `README.md` "검사" 절의 숫자를 고친다. PowerShell 숫자는 `sh` 가 필요한 셸 스크립트 테스트를 옮겨 적는다(passed −N, skipped +N). N은 Git Bash에서 `uv run pytest -q tests/test_deploy_sh.py tests/test_initdb_sh.py` 의 passed 수다(phase 1 뒤 2026-10-17 기준 20). 날짜도 고친다.
- `README.md` "검사" 절 명령 블록에 `uv run pytest tests/gui -q   # GUI 테스트만 (pytest-qt, 화면 없이 offscreen)` 을 더한다.
- `docs/ARCHITECTURE.md` 디렉토리 구조: `gui/` 줄에 `store/device_tab_ctrl/main_window`, `gui_support/` 줄에 `helpers.py(시드, install_fake_db, 사용자 동작)` 를 더한다.

## Acceptance Criteria

```bash
uv run ruff check src tests                        # 린트 (import 정렬은 uv run ruff check --fix tests 로 고쳐도 된다)
uv run pytest tests/gui/test_smoke.py -q           # smoke 통과
for i in 1 2 3; do uv run pytest tests/gui -q || exit 1; done   # 세 번 연속 통과 (타이밍 의존 검사)
uv run pytest -q                                   # 전체 통과
git status --porcelain -- src                      # 출력이 비어 있어야 한다 (src 불변)
```

## 검증 절차

1. 위 AC 커맨드를 실행한다.
2. 아키텍처 체크리스트를 확인한다:
   - `src/` 가 바뀌지 않았는가?
   - fixture와 smoke 테스트에 `qtbot.wait(`, `time.sleep(` 이 없는가(`grep -rn "qtbot.wait(\|time.sleep(" tests/gui tests/gui_support` 가 비어 있어야 한다)?
   - fixture가 띄운 창·컨트롤러를 teardown에서 닫는가(`close_db`/`shutdown`, `qtbot.addWidget`)?
   - 문서의 기준선 숫자가 실제 실행 결과와 같은가?
3. 결과에 따라 `phases/2-gui-test-infra/index.json` 의 step 2를 업데이트한다:
   - 성공 → `"status": "completed"`, `"summary": "tests/gui_support/helpers.py: seeded_store, install_fake_db, select_process/select_device_row/edit_device_cell/edit_tab_cell. conftest: autouse _app_user(GENDB_APP_USER=tester), store, device_tab_ctrl(notifyRequested→dialogs.record_notify), main_window(MainWindowController 반환). smoke N개. 기준선 <P> passed / <S> skipped. 관찰: <없음 또는 파일:행 — 관찰>"`
   - 수정 3회 시도 후에도 실패 → `"status": "error"`, `"error_message": "구체적 에러 내용"`
   - 사용자 개입 필요 → `"status": "blocked"`, `"blocked_reason": "구체적 사유"` 후 즉시 중단

## 금지사항

- `src/` 를 고치지 마라. 특히 생성자 안의 접속, `_open_database` 같은 private 이름, 시그널 연결 순서를 테스트하기 좋게 바꾸지 마라. 이유: phase 3/4가 지금 코드를 기준으로 RED를 만들고, 첫 접속을 옮기는 일은 phase 4의 몫이다.
- fixture나 테스트에서 `qtbot.wait`/`time.sleep` 으로 기다리지 마라. 이유: 접속·폴링·저장이 비동기로 바뀌어도 같은 테스트가 돌아야 하고, 고정 대기는 "아무 일도 없음"을 증명하지 못한다.
- smoke 테스트에서 저장·충돌·접속 실패·창 닫기 중 경로를 단언하지 마라. 위 목록 밖에서 버그로 보이는 동작도 단언하지 마라. 이유: 그 경로는 phase 3/4가 RED로 재현해 고친다. 여기서 지금 동작을 고정하면 고칠 때 이 phase의 테스트가 깨진다. 관찰은 summary에 적는다.
- `question`·`ask_conflict` 를 fixture나 헬퍼에서 따로 패치하지 마라. 답은 `dialogs.answer_question`/`answer_conflict` 로만 준다. 이유: 패치가 두 겹이면 `dialogs.shown` 과 teardown 검사가 빈다.
- 헬퍼 안에서 기다리거나 분기하지 마라. 사용자 동작 하나만 흉내 낸다. 이유: phase 4가 동작을 비동기로 바꿔도 헬퍼는 그대로 써야 한다.
- `MainWindow(show_history=True)` 를 fixture에 넣지 마라. 이유: `HistoryTabController` 는 자기 모듈에서 실제 `AuditRepository` 를 만들어 `FakeDatabase.connection()` 에서 AssertionError가 난다. 이 phase의 범위가 아니다.
- 테스트 모듈에서 conftest를 import하지 마라. 헬퍼는 `from gui_support.helpers import ...` 로만 쓴다.
- 기존 테스트를 깨뜨리지 마라.
