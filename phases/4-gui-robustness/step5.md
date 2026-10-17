# Step 5: window-guards

## 배경 (phase 4 공통)

이 저장소는 이미 여러 명이 쓰는 도구다. 지금은 **에러·버그만 고친다**(CLAUDE.md, ADR-015). phase 4는 GUI가 실패·경합 상황에서 데이터를 잘못 쓰거나 죽는 버그를 한 step에 하나씩 고친다(탭 로드 실패, 탭 섹션 입력, "+" 탭, 필터 중 정렬, DB 재접속, 창 닫기, Virtuoso 소켓 워커). phase 3(`3-gui-save-fixes`)이 먼저 끝나 있다. 저장 함수가 결과를 돌려주고(`save_all() -> bool`, `DeviceTabController.save_db() -> bool`), `select_process_silently` 가 생겼다. 그 밖에 `deviceVersionBumped`/`adopt_device_version`(내 device 저장 뒤 탭이 version을 따라간다), `DeviceTabController._save_before_process_change`(process 전환 전 질문·저장), `DeviceTableModel.is_row_changed`, device 표 붙여넣기의 `Unsaved Changes` 거부, `save_all` 의 `Save Skipped` 경고가 있다. 정확한 반환 계약은 코드와 `phases/3-gui-save-fixes/index.json` 의 summary로 확인하라.

모든 step에 같은 규칙이 적용된다.
1. 아래 "버그"는 **분석 에이전트의 주장**이다. 먼저 실패하는 테스트로 재현하고, RED 출력(테스트 이름과 실패한 단언)을 summary에 적는다.
2. RED는 **Windows 개발 PC에서** 보여야 한다. `posix_only` 테스트는 개발 PC에서 skip되므로 버그를 증명하지 못한다.
3. 재현되지 않으면 `src/` 를 고치지 않는다. 테스트는 특성 테스트로 남기고 `"status": "completed"`, `"summary": "not reproduced: <이유>"` 로 끝낸다.
4. 고친 뒤 수정을 손으로 되돌려 새 테스트가 실패하는지 확인하고 다시 고친다(변이 검사). `git checkout`/`git stash` 로 되돌리지 마라. 이유: 같은 step의 테스트 변경까지 사라진다.
5. 이 파일의 행 번호는 2026-10-17 기준 대략값이다. 이름으로 찾아라.

GUI 테스트 기반은 phase 2(`2-gui-test-infra`)가 만들었다. 아래 이름을 그대로 쓰고, 같은 일을 하는 것을 새로 만들지 마라.
- `tests/gui/conftest.py`: offscreen Qt. autouse `dialogs` fixture — `dialogs.answer_question(*bools)`·`dialogs.answer_conflict(*choices)` 로 다음 대화상자의 답을 미리 넣고, 뜬 상자는 `dialogs.shown` 에 `(kind, title, text)` 로 쌓인다. 답을 넣지 않은 모달이 뜨면 AssertionError다. `store`(시드된 FakeStore: process "sf2p" 에 device "nfet_a"·"nfet_b", "sf4u" 에 device 하나, 탭 행), `device_tab_ctrl`(`DeviceTabController._open_database` 가 `FakeDatabase(store)` 를 돌려주게 바꿔 접속한 컨트롤러. `qtbot.waitUntil(lambda: ctrl.connected is not None)` 까지 기다린다), `main_window`(fake 위의 MainWindowController + MainWindow. 정리 때 shutdown 후 close).
- `tests/gui_support/fakes.py`: `FakeStore`(`calls` 에 호출 기록, `fail_next(method_name, exc)` 로 그 메서드의 다음 호출 하나를 실패시킨다), `FakeDatabase`(`.cfg.dsn`, `close()`), 실제와 같은 의미의 fake repo들.
- `tests/gui_support/helpers.py`: `select_process`, `select_device_row`, `edit_device_cell`, `edit_tab_cell`.
- 새 테스트는 `tests/gui/test_<주제>.py` 에 둔다. "아무 일도 일어나지 않았다" 를 `qtbot.wait` 고정 대기로 확인하지 않는다. 비동기 경로는 fake가 기록한 호출(`store.calls`)을 `qtbot.waitUntil` 로 기다린 뒤 단언하고, 동기 경로는 호출이 돌아온 뒤 바로 단언한다. 필요한 helper·fake가 없으면 `tests/gui_support/` 에 더한다(기존 이름과 동작은 바꾸지 않는다).
- fixture가 돌려주는 객체의 정확한 모양과 helper 인자는 `tests/gui/conftest.py`·`tests/gui_support/` 를 읽고 맞춘다. 이 파일의 예시는 이름만 가리킨다.

### phase 2 에서 확정된 테스트 기반 세부 (이 파일의 서술보다 우선)

이 step 파일은 phase 2(`2-gui-test-infra`)와 동시에 작성됐다. 이름이나 동작이 엇갈리면 **phase 2 가 실제로 만든 코드(`tests/gui_support/`, `tests/gui/conftest.py`)가 기준**이다. 작업 전에 그 파일들을 읽고, 아래나 이 파일의 서술과 다르면 실제 코드를 따른다.
- 대화상자 대역은 `tests/gui_support/dialogs.py` 의 `FakeDialogs`(`install_dialogs`)이고 autouse `dialogs` fixture로 들어온다. `dialogs.shown` 의 kind는 `info`/`warning`/`error`/`critical`/`question` 이고, 충돌 대화상자는 `("conflict", "Save Conflict", <충돌 설명>)` 이다.
- 답을 정하지 않은 모달과 워커 스레드에서 뜬 모달은 `AssertionError` 를 내고 `dialogs.unexpected` 에 남는다. `@report`·`connect_db` 가 그 예외를 삼키므로 실패는 **teardown에서** 드러난다. 쓰이지 않고 남은 답(`answer_question`/`answer_conflict`)도 teardown 실패다. 일부러 답 없는 모달을 확인하는 테스트는 확인한 뒤 `dialogs.unexpected.clear()` 한다.
- `device_tab_ctrl` 은 `notifyRequested` 를 `dialogs.record_notify` 에 이어 두었다. 알림도 `dialogs.shown` 에서 본다.
- `main_window` fixture는 `MainWindowController` 를 돌려준다(`.ui`, `.device_tab`).
- 시드(`seeded_store()`): process `sf2p`(device `nfet_a`, `nfet_b`), `sf4u`(device `pfet_a`). 탭은 `"InstTerm"`·`"InstSchParam"`. id는 숫자 대신 `store.find_device("nfet_a")["id"]` 로 얻는다. 접속하면 `sf2p` 가 자동으로 선택된다. autouse로 `GENDB_APP_USER=tester` 다.
- `store.calls` 항목은 `(메서드 이름, 인자 dict의 deep copy)` 이고 호출이 **끝난 뒤** 기록된다. `store.calls_of(name)` 이 인자 dict 리스트를 준다. `fail_next(name, exc)` 는 순서대로 쌓인다.
- 다른 사용자의 저장 흉내는 `store.touch_device(device_id, actor="other", **changes)`(version+1, updated_by, 새 version을 반환), 삭제 흉내는 `store.remove_device(device_id)` 다. 둘 다 `calls` 에 남지 않는다. 이 파일에 `bump_version` 이라고 적힌 곳은 `touch_device` 로 읽는다.
- 첫 접속 실패는 `store.fail_next("open_database", DbUnavailableError("x"))` 를 건 뒤 `install_fake_db(monkeypatch, store)` 로 컨트롤러를 직접 만든다(`_open_database` 는 `store.open_database` 로 바뀌어 있다).
- `FakeDatabase` 는 `closed` 와 `cfg.dsn` 을 갖는다. `connection()` 은 부르면 AssertionError다(가짜 repo만 쓴다).
- helpers는 기다리지 않는다. 기다림은 테스트가 `qtbot.waitUntil` 로 한다.
- 필요한 헬퍼·가짜 메서드가 없으면 `tests/gui_support/` 에 더한다. 그 경우 phase 2 contract test(`tests/gui/test_fake_repo_contract.py`)의 의미를 깨지 않는다.

## 이 step의 목적

저장 안 한 편집이 말없이 사라지는 두 경로를 막는다(UI_GUIDE 원칙 2: "버려질 상황이면 먼저 묻는다").
- (G6, **사용자 승인 2026-10-17**) 창을 닫을 때 device 표나 탭에 저장 안 한 편집이 있으면 묻는다. Yes면 저장하고 저장에 성공했을 때만 닫는다. No면 버리고 닫는다.
- (G15c, **사용자가 승인한 2026-10-17 계획에 포함**) Virtuoso의 `[DeviceList]` 응답이 왔을 때 device 표에 저장 안 한 편집이 있으면 다시 읽기 전에 묻는다. No면 Virtuoso 목록 표만 갱신하고 device 표는 그대로 둔다. 기존 "Refresh" 질문과 같은 문구·형태를 쓴다.

## 읽어야 할 파일

- `/CLAUDE.md`, `/docs/UI_GUIDE.md`(원칙 2·4, 문구: `question` 은 Yes/No 두 개뿐), `/docs/ARCHITECTURE.md`(레이어 표: views는 controllers를 모른다, "현재 어긋난 곳"), `/docs/ADR.md`(ADR-004, ADR-009)
- `src/genviewer/controllers/main_window.py` — `__init__` (~21-62), `shutdown` (~64-69), `_on_received_from_controller` (~125-142, DeviceList면 dirty 검사 없이 `refresh_devices()`), `_on_notify_requested` (~223-231)
- `src/genviewer/views/main_window.py` — `MainWindow`(QMainWindow). `closeEvent` 가 없다
- `src/genviewer/controllers/device_tab.py` — `save_db` (~114-140, phase 3에서 `-> bool`: device 저장 뒤 탭도 늘 저장하고 둘 다 True일 때만 True. device 충돌을 취소해도 탭은 저장하고, device 예외면 탭으로 가지 않는다), `_on_refresh_requested` (~231-245, 기존 질문 문구), `_save_before_process_change` (~418-454, "Save Changes" 질문 ~428-432. process 전환용이다)
- `src/genviewer/controllers/device_table.py` — `is_dirty`, `refresh_devices` (`update_devices` → `reset_modified()`)
- `src/genviewer/controllers/parameter_tab.py` — `is_dirty`
- `src/genviewer/utils/dialogs.py` — `question(parent, title, message) -> bool`
- `src/genviewer/utils/background.py` — `is_busy()`(지금 `run_blocking` 안인가)
- `src/genviewer/main.py` — `run_gui`(`app.exec()` 뒤 `controller.shutdown()`)
- `tests/gui/conftest.py`(`main_window` 의 정리 순서), `tests/gui_support/`
- 이전 step에서 수정된 파일: `src/genviewer/controllers/device_tab.py`(첫 접속이 `QTimer.singleShot` 으로 미뤄짐, 재접속 순서), `tests/gui/test_connect_db.py`, `tests/gui/conftest.py`

## 버그

**G6.** `closeEvent` 도 닫기 이벤트 필터도 코드 어디에도 없다(`grep -rn "closeEvent\|eventFilter" src` 결과 없음). device 표나 탭을 고친 뒤 창을 닫으면 아무것도 묻지 않고 닫히고, `run_gui` 가 `shutdown()` 으로 풀을 닫는다. 편집이 말없이 사라진다. 다른 버려지는 경로(process 바꾸기, device 바꾸기, 배너의 새로고침)는 이미 묻는다.

**G15c.** `_on_received_from_controller` 의 DeviceList 분기:

```python
if msg_type == "DeviceList":
    device_state_data = virtuoso_protocol.to_device_state(msg)
    self.device_tab.ui.virtuoso_device_table.update_devices(device_state_data)
    self.device_tab.ui.filtered_device_table.update_devices(device_state_data)
    self.device_tab.device_table.device_state_data = device_state_data
    self.device_tab.device_table.refresh_devices()
    self.ui.append_log(f"Received Virtuoso device list: {len(device_state_data)} item(s).")
```

`refresh_devices()` → `update_devices()` → `reset_modified()` 이므로 device 표의 저장 안 한 편집(값, 추가, 삭제, 순서)이 묻지도 않고 사라진다. Load Virtuoso를 누르고 응답이 오기 전에 표를 고치거나, Virtuoso 쪽에서 목록을 다시 보내면 닿는다.

이것은 주장이다. 먼저 재현하라.

## 작업

### 설계 결정: 닫기 확인은 `MainWindowController` 의 이벤트 필터

dirty 상태와 저장은 컨트롤러만 안다. 뷰(`MainWindow`)가 컨트롤러를 부르게 하면 레이어 표를 어긴다. 그래서 `MainWindowController` 가 `self.ui.installEventFilter(self)` 로 창의 `QEvent.Close` 를 받는다. `views/main_window.py` 는 바꾸지 않는다. 테스트는 `ui.close()` 의 반환값(닫혔으면 True)으로 확인한다.

```python
class MainWindowController(QObject):
    def eventFilter(self, obj: QObject, event: QEvent) -> bool: ...   # self.ui 의 Close 만 본다. 나머지는 False
    def shutdown(self) -> None: ...   # 이벤트 필터를 뗀다(정리 뒤에는 저장할 수 없다). 여러 번 불러도 된다
```

- 닫기를 막을 때는 `event.ignore()` 하고 True를 돌려준다. 허락할 때는 False를 돌려줘 `QMainWindow` 의 기본 처리(닫힘)를 탄다.

### 결과 × 상태 (닫기)

| 상태 | 동작 |
|---|---|
| 편집 없음 (`device_table.is_dirty()`·`parameter_tab.is_dirty()` 모두 False) | 묻지 않고 닫는다(지금과 같다) |
| 편집 있음, Yes | `self.device_tab.save_db()`. True면 닫는다. False(저장 실패, 충돌에서 취소·다시 읽기, `Save Skipped`, 탭 저장 실패)면 창을 남긴다. `Save Skipped` 뒤에는 다시 읽기로 dirty가 지워지므로 다음 닫기는 묻지 않고 닫힌다 |
| 편집 있음, No | 저장하지 않고 닫는다 |
| `is_busy()`(저장·접속·CSV 불러오기 중. `run_blocking` 의 이벤트 처리는 사용자 입력만 막고 창 닫기 요청은 막지 않는다) | 묻지 않고 닫기를 무시한다(창이 남는다). 끝난 뒤 다시 닫으면 된다 |
| DB 없음 | `current_process_id` 가 없어 dirty가 될 수 없다 → 그냥 닫는다 |
| `shutdown()` 뒤 | 필터가 없으므로 묻지 않는다 |

- 질문 문구는 기존 것을 그대로 쓴다: `question(self.ui, "Save Changes", "You have unsaved changes. Do you want to save them?")`(process 전환의 `_save_before_process_change`, device 전환의 `_switch_device_by_index` 와 같은 문구). 새 문구를 만들지 않는다.
- Yes 뒤 알림("Saved", "Save Devices Failed" 등)은 `save_db()` 가 지금처럼 낸다. 성공하면 알림이 2~3개 뜰 수 있다(device "Save Complete"/"No changes to save.", 탭 "Saved", "All changes have been saved."). 지금 Database → Save 와 같은 동작이다.
- 닫기에는 `save_db()` 를 쓴다(승인된 G6: 저장에 성공했을 때만 닫는다). process 전환용 `_save_before_process_change` 를 가져다 쓰지 마라. 그 함수는 다시 읽기를 "넘어가도 된다"(True)로 보므로 위 표와 어긋난다.

### 결과 × 상태 (DeviceList 응답)

| 상태 | 동작 |
|---|---|
| device 표 편집 없음 | 지금과 같다(두 Virtuoso 표 갱신, `device_state_data` 갱신, `refresh_devices()`, 로그 한 줄) |
| 편집 있음, Yes | 지금과 같다(다시 읽어 편집을 버린다) |
| 편집 있음, No | 두 Virtuoso 표와 `device_state_data` 는 갱신하고 로그 한 줄도 남긴다. `refresh_devices()` 는 부르지 않는다. 모델의 편집·dirty 표시·`deleted_devices()` 가 그대로다. 새 목록은 다음 다시 읽기(저장 뒤 등)에 반영된다 |
| DB 없음 | `refresh_devices()` 가 repo 없이 돌아가고 dirty도 없다 → 지금과 같다 |
| 저장 중(`is_busy()`) 도착 | 위와 같은 규칙(편집이 남아 있으면 묻는다). 따로 다루지 않는다 |

- 질문 문구는 `DeviceTabController._on_refresh_requested` 의 것을 그대로 쓴다: 제목 `"Refresh"`, 본문 `"저장하지 않은 편집이 있습니다.\n서버 내용으로 다시 읽으면 그 편집은 사라집니다. 계속할까요?"`. `refresh_devices()` 는 정말로 서버에서 다시 읽으므로 문구가 맞다.
- 탭(파라미터) 편집은 이 경로에서 사라지지 않으므로 device 표의 dirty만 본다.
- LibraryList·그 밖의 메시지 분기는 바꾸지 않는다.

### 1. 테스트 먼저 (`tests/gui/test_window_guards.py`, 새 파일)

`main_window` fixture를 쓴다(아래 `mw` 는 MainWindowController, `mw.ui` 는 MainWindow — 실제 모양은 conftest를 보고 맞춘다). 첫 접속이 비동기이므로(step 4) 붙을 때까지 기다린 상태에서 시작한다. Virtuoso 응답은 소켓 없이 `mw.connection_controller.received.emit("[DeviceList]nfet_a,O,O,lib")` 로 넣는다.

닫기:
- **편집 없음**: `mw.ui.close()` 가 True, `dialogs.shown` 에 질문이 없다.
- **device 편집 + No**: `select_process(…, "sf2p")`, `edit_device_cell` 로 하나 고침, `dialogs.answer_question(False)` → `close()` 가 True, `dialogs.shown` 에 질문 "Save Changes" 가 있다, `store.calls` 에 `upsert_devices` 가 없다. **수정 전에는 질문이 없어 실패해야 한다.**
- **device 편집 + Yes, 성공**: `answer_question(True)` → `close()` 가 True, `upsert_devices` 가 불렸고 store에 편집이 반영됐다.
- **Yes, 저장 실패**: `store.fail_next("upsert_devices", DbUnavailableError("down"))` + Yes → `close()` 가 False, 모델에 편집이 남아 있다, 실패 알림이 `dialogs.shown` 에 있다.
- **Yes, 충돌 후 취소**: `store.touch_device(store.find_device("nfet_a")["id"], actor="bob")` 로 충돌을 만들고 `dialogs.answer_conflict(CANCEL)` → `close()` 가 False.
- **탭만 편집**: device를 고르고 `edit_tab_cell` → Yes → 탭 저장(`replace_many_for_device`)이 불리고 `close()` 가 True. (phase 3 이후 `save_db()` 는 탭을 저장한다. 탭만 고쳐도 `device_table.save_all` 이 화면의 device 전부로 `upsert_devices` 를 부르고 "No changes to save." 를 먼저 띄우므로, 이 테스트에서 `upsert_devices` 가 없다고 단언하지 마라.)
- **저장 중**: `monkeypatch.setattr("genviewer.controllers.main_window.is_busy", lambda: True)`(import 방식에 맞춰 바꾼다) + 편집 있음 → `close()` 가 False, 질문 없음, 저장 호출 없음.
- **shutdown 뒤**: 편집 있음 → `mw.shutdown()` → `mw.ui.close()` 가 질문 없이 True.

DeviceList:
- **편집 없음**: 응답 → 질문 없음, device 목록 조회가 `store.calls` 에 한 번 더 있다, `device_table.device_state_data` 가 새 목록.
- **편집 있음 + No**: `edit_device_cell` 후 `answer_question(False)` + 응답 → `dialogs.shown` 에 "Refresh" 질문, 모델이 편집을 그대로 갖고 있다(`is_modified()` True, 고친 값, dirty 셀), `device_state_data` 와 Virtuoso 표(`ui.device_tab_view.virtuoso_device_table.get_devices()`)는 새 목록, 응답 뒤 device 목록 조회가 늘지 않았다. **수정 전에는 편집이 사라져 실패해야 한다.**
- **편집 있음 + Yes**: 다시 읽어 편집이 사라진다(지금 동작).

**구조가 바뀌므로(하네스 규칙 14) fixture를 확인한다.** `main_window` 정리가 `close()` 를 `shutdown()` **보다 먼저** 부르면, 편집을 남긴 채 끝나는 테스트마다 질문이 떠 AssertionError가 난다. 지금 conftest는 이미 shutdown → close 순서다(shutdown이 필터를 떼야 한다). 이 순서를 바꾸지 않는다. 다른 GUI 테스트가 `close()` 를 직접 부르며 편집을 남기면 답을 넣거나 순서를 맞춘다.

### 2. 수정 (`controllers/main_window.py`)

- `__init__` 끝에서 `self.ui.installEventFilter(self)`. `eventFilter` 는 `obj is self.ui and event.type() == QEvent.Type.Close` 일 때만 위 표대로 판단하고, 그 밖에는 False.
- `shutdown()` 은 먼저 `self.ui.removeEventFilter(self)` 한 뒤 지금처럼 이력·DB를 정리한다.
- `_on_received_from_controller` 의 DeviceList 분기는 위 표대로: Virtuoso 표·`device_state_data` 갱신과 로그 한 줄은 늘 하고, `refresh_devices()` 는 device 표가 dirty가 아니거나 질문에 Yes일 때만 부른다.
- `controllers/main_window.py` 가 `from genviewer.utils.dialogs import question` 으로 이름을 묶으면 `tests/gui_support/dialogs.py` 의 `QUESTION_MODULES` 에 `"genviewer.controllers.main_window"` 를 더한다. 빠지면 `tests/gui/test_dialogs_fixture.py::test_every_dialogs_import_is_patched` 가 실패한다.
- `views/main_window.py` 와 `controllers/device_tab.py` 는 바꾸지 않는다.

### 3. 문서

- UI_GUIDE·README는 phase 마무리에서 고친다("창을 닫을 때 저장 여부를 묻는다"). 이 step에서는 바꾸지 않는다.

## Acceptance Criteria

```bash
uv run pytest tests/gui/test_window_guards.py -q   # 새 테스트 통과 (수정 전에는 닫기 질문·DeviceList No 테스트가 실패해야 한다)
uv run ruff check src tests
uv run pytest tests/gui -q                         # 이벤트 필터를 단 뒤에도 모든 GUI 테스트 통과
uv run pytest -q
```

## 검증 절차

1. 위 AC 커맨드를 실행한다.
2. 아키텍처 체크리스트를 확인한다:
   - `views/main_window.py` 가 controllers를 import하거나 dirty·저장을 직접 보지 않는가(레이어 표)?
   - 새 문구 없이 기존 질문 문구만 썼는가(ADR-015, UI_GUIDE 문구)?
   - 저장이 실패·취소됐을 때 창을 닫지 않는가(UI_GUIDE 원칙 4)?
3. 결과에 따라 `phases/4-gui-robustness/index.json` 의 step 5를 업데이트한다:
   - 성공 → `"status": "completed"`, `"summary": "MainWindowController: 창 Close 이벤트 필터(dirty 면 Save Changes 질문, Yes=save_db()가 True일 때만 닫음, No=닫음, is_busy 면 무시), shutdown 이 필터 제거. DeviceList 는 device 표 dirty 면 Refresh 질문, No 면 Virtuoso 표만 갱신. RED: <테스트 이름>. tests/gui/test_window_guards.py 추가"`
   - 재현 안 됨 → `"status": "completed"`, `"summary": "not reproduced: <이유>"`
   - 수정 3회 시도 후에도 실패 → `"status": "error"`, `"error_message": "구체적 에러 내용"`
   - 사용자 개입 필요 → `"status": "blocked"`, `"blocked_reason": "구체적 사유"` 후 즉시 중단

## 금지사항

- `MainWindow`(뷰)에 `closeEvent` 를 넣어 컨트롤러·repo를 부르거나 dirty를 직접 보게 하지 마라. 이유: views는 controllers를 모른다(레이어 표). 판단은 컨트롤러가 한다.
- 저장/버리기/취소 세 갈래 대화상자를 새로 만들지 마라. 이유: `question` 은 Yes/No뿐이고(UI_GUIDE), 승인된 것은 그 형태다. 닫기를 멈추는 길은 "Yes 뒤 저장 실패·충돌 취소" 와 "작업 중" 뿐이다.
- 저장이 실패하거나 취소됐는데 창을 닫지 마라. 이유: 실패를 성공처럼 다루면 편집이 사라진다(UI_GUIDE 원칙 4). 판단은 알림 문구가 아니라 `save_db()` 의 반환값으로 한다.
- `is_busy()` 중에 질문을 띄우거나 `save_db()` 를 부르지 마라. 이유: 진행 중인 `run_blocking` 안에서 저장이 겹쳐 돈다.
- DeviceList를 받고 No를 골랐을 때 Virtuoso 표·`device_state_data` 갱신까지 건너뛰지 마라. 이유: 목록은 받은 것이 맞고, 지켜야 할 것은 device 표 편집뿐이다.
- process·device 바꾸기 경로의 질문(`on_process_changed`, `_save_before_process_change`, `_switch_device_by_index`, `select_process_silently`)과 배너 새로고침을 바꾸지 마라. 이유: 이 step의 범위가 아니다.
- Virtuoso 끊김을 접속 상태에 반영하는 일(known-issues K14)을 하지 마라. 이유: 동작 변경이라 기록만 했다.
- 기존 테스트를 깨뜨리지 마라.
