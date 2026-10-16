# Step 5: process-change-save

## 배경 (phase 3 공통)

이 저장소는 이미 여러 명이 쓰는 도구다. 지금은 **에러·버그만 고친다**(CLAUDE.md, ADR-015). phase 3은 GUI 저장 흐름(`controllers/device_tab.py`, `device_table.py`, `parameter_tab.py`, `main_window.py`, `device_tab_toolbar.py`)의 버그를 고친다. 저장 함수가 "저장했다/사용자가 그만뒀다" 를 돌려주지 않아 취소해도 "Saved" 가 뜨고 화면이 넘어가는 문제, Database → Save 가 탭을 저장하지 않는 문제, 내 device 저장 뒤 내 탭 저장이 나 자신과 충돌하는 문제, process 전환·목록 갱신에서 편집이 말없이 사라지는 문제다. 반환 계약을 바꾸는 step(0, 1)이 먼저 끝나고 호출부 step(2, 3, 5)이 그 계약을 쓴다.

모든 step에 같은 규칙이 적용된다.
1. 아래 "버그"는 **분석 에이전트의 주장**이다. 먼저 실패하는 테스트로 재현하고, RED 출력(테스트 이름과 실패한 단언)을 summary에 적는다.
2. RED는 **Windows 개발 PC에서** 보여야 한다. `posix_only` 테스트는 개발 PC에서 skip되므로 버그를 증명하지 못한다.
3. 재현되지 않으면 `src/` 를 고치지 않는다. 테스트는 특성 테스트로 남기고 `"status": "completed"`, `"summary": "not reproduced: <이유>"` 로 끝낸다.
4. 고친 뒤 수정을 손으로 되돌려 새 테스트가 실패하는지 확인하고 다시 고친다(변이 검사). `git checkout`/`git stash` 로 되돌리지 마라. 이유: 같은 step의 테스트 변경까지 사라진다.
5. 이 파일의 행 번호는 2026-10-17 기준 대략값이다. 이름으로 찾아라.

GUI 테스트 기반은 phase `2-gui-test-infra` 가 만들었다. 아래 이름을 그대로 쓴다.
- `tests/gui/conftest.py`: offscreen. autouse `dialogs` fixture가 모달을 가로챈다. `dialogs.answer_question(*bools)` 는 Yes/No 질문(`utils/dialogs.question`)에, `dialogs.answer_conflict(*choices)` 는 충돌 대화상자에 순서대로 답한다(`genviewer.dialogs.conflict` 의 `RELOAD`/`OVERWRITE`/`CANCEL`). 뜬 것은 `dialogs.shown` 에 `(kind, title, text)` 로 쌓이고, 답을 넣지 않은 모달은 AssertionError를 낸다.
- fixture: `store`(FakeStore. process "sf2p" 에 device "nfet_a", "nfet_b", process "sf4u" 에 device 하나. device마다 탭 두 개에 행이 있다), `device_tab_ctrl`(가짜에 붙어 이미 접속한 DeviceTabController), `main_window`(가짜 위의 MainWindowController와 MainWindow. teardown이 shutdown과 close를 한다).
- `tests/gui_support/fakes.py`: `FakeStore`(`calls` 는 `(method, args)` 목록, `fail_next(method_name, exc)`), `FakeDatabase`, 실제 repo와 같은 의미의 가짜 Device/Parameter/Process/IO repository(값이 바뀐 행만 version +1, force가 아니면 version 불일치·사라진 행에 `StaleWriteError`).
- `tests/gui_support/helpers.py`: `select_process(ctrl, name)`, `select_device_row(ctrl, row)`, `edit_device_cell(ctrl, row, column, value)`, `edit_tab_cell(ctrl, tab_name, row, column, value)`. `ctrl` 은 DeviceTabController다(`main_window` 면 `.device_tab`).
- "bob 이 nfet_a 를 저장한다" 는 store에서 그 device의 version을 직접 1 올리는 것(값은 그대로, `updated_by="bob"`)이다. 다른 사용자의 탭 저장과 같다. `store.touch_device(device_id, actor="bob")` 를 쓴다(phase 2 의 FakeStore). device id·version은 화면 모델에서 읽는다(`ctrl.device_table.ui.model_safe().get_device(row)`).
- 새 GUI 테스트는 `tests/gui/test_<주제>.py` 에 둔다. "아무 일도 일어나지 않았다" 는 `qtbot.wait` 로 기다리지 말고 `store.calls` 를 `qtbot.waitUntil` 로 기다린 뒤 단언한다.
- 저장 경로에는 넓은 `except Exception`(`save_db`, `@report`)이 있어 답을 넣지 않은 모달의 AssertionError를 삼킬 수 있다. 대화상자가 떴는지·안 떴는지는 반환값, `store.calls`, `dialogs.shown` 으로 직접 단언한다.
- 알림: `main_window` 를 쓰면 `notifyRequested` 가 `MainWindow.notify` 를 거쳐 `dialogs.shown` 에 남는다(알림 상자는 답 없이 기록만 된다고 본다. 다르면 phase 2 방식을 따른다). `device_tab_ctrl` 만 쓰면 `ctrl.notifyRequested` 를 테스트 안에서 리스트에 연결해 확인한다.
- 필요한 헬퍼가 없거나 이름이 다르면(phase 2가 "not reproduced" 로 끝났거나 다르게 만들었으면) `tests/gui_support/` 에 직접 더한다. `src/` 에 테스트용 코드를 넣지 않는다.

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

process를 바꿀 때 저장하지 않은 **탭** 편집도 묻고(분석 G2), "예" 로 저장하다 충돌에서 취소하거나 저장이 실패하면 전환을 멈추고 콤보를 이전 process로 되돌린다(분석 G4). 지금은 device 표만 검사해서 탭 편집은 묻지도 않고 버리고, 저장이 취소·실패해도 새 process로 넘어가 device 편집까지 버린다.

## 읽어야 할 파일

- `/CLAUDE.md`, `/docs/UI_GUIDE.md`(원칙 2·4·5, 질문은 Yes/No 둘뿐), `/docs/notes/known-issues.md`(K20 — 범위 밖)
- `src/genviewer/controllers/device_tab.py` — `__init__` 의 `processChanged`·`clearTabRequested` 연결 (~63-68), `save_db`(step 2: 예외 제목 "Save Devices Failed"/"Save Tabs Failed"), `clear` (~265-267), `on_process_changed` (~378-403)
- `src/genviewer/controllers/device_tab_toolbar.py` — `add_process` (~81-99: `setProcessRequested.emit(name)` 다음의 `clearTabRequested.emit(True)`), `select_process_silently`(step 4)
- `src/genviewer/controllers/device_table.py` — `save_all`(step 0: `-> bool`), `is_dirty` (~212-215), `current_process`
- `src/genviewer/controllers/parameter_tab.py` — `save_all`(step 1: `-> bool`), `is_dirty`, `_clear_tabs` (~132-135)
- `src/genviewer/controllers/tab_section.py` — `set_device`/`update_model` (~63-67, ~181-192)
- `src/genviewer/utils/reporting.py` — `report_error`, `report`(`StaleWriteError` 는 다시 올린다)
- 이전 step에서 수정된 파일: `controllers/device_table.py`, `controllers/parameter_tab.py`(`save_all -> bool`), `controllers/device_tab.py`(`save_db`, `_switch_device_by_index`), `controllers/main_window.py`, `views/device_tab_toolbar.py`(`set_processes` 는 현재 process를 유지하고 바뀔 때만 한 번 알린다, `select_process_silently`), `controllers/device_tab_toolbar.py`(`remove_process`, `select_process_silently`), `tests/gui/test_*.py` 다섯 개

## 버그

```python
@Slot()
@report("Process Change Failed")
def on_process_changed(self, process_name: str):
    self.clear()
    self.ui.hide_views()
    self.ui.hide_refresh_banner()
    if not process_name:
        ...
        return
    self.logRequested.emit(f"Selected process: {process_name}.")
    if self.device_table.is_dirty():
        if question(self.ui, "Save Changes", "You have unsaved changes. Do you want to save them?"):
            self.device_table.save_all()

    process_id = self.device_tab_toolbar.get_process_id(process_name)
    ...
    self.device_table.refresh_devices()
    self.parameter_tab._clear_tabs()
```

1. **탭 편집(G2)**: `parameter_tab.is_dirty()` 를 보지 않는다. `_clear_tabs()` 가 섹션을 device 없음으로 돌리고, 그 device를 다시 고르면 `TabSectionController.update_model` 이 DB 값으로 덮는다. 재현: sf2p → nfet_a → 탭 셀 편집(` *`) → 콤보에서 sf4u → 아무것도 묻지 않는다 → sf2p로 돌아와 nfet_a를 누르면 편집이 없다.
2. **저장 결과(G4)**: `save_all()` 이 `False`(충돌 취소)여도 다음 줄로 가고 `refresh_devices()` 가 편집을 버린다. 재현: sf2p에서 nfet_a Description 편집 → bob이 nfet_a를 저장 → sf4u 선택 → "Save Changes?" 예 → "Save Conflict" 에서 "취소"(툴팁: "편집 내용은 그대로 남는다") → sf4u로 넘어가고 편집은 사라졌다.
3. **예외**: `save_all()` 이 예외를 내면 `@report("Process Change Failed")` 가 알리지만 이미 `clear()`·`hide_views()` 를 했고, 콤보는 sf4u인데 device 표는 sf2p다.
4. **Add Process 뒤의 탭 비우기**: `add_process` 는 `setProcessRequested.emit(name)` 으로 새 process를 고른 뒤 `clearTabRequested.emit(True)` → `parameter_tab._clear_tabs()` 를 한다. 전환이 일어나면 `on_process_changed` 가 이미 탭을 비우므로 이 줄은 아무 일도 더하지 않는다. 아래 수정으로 전환이 되돌려진 경우에만 효과가 있고, 그때 남겨 둔 탭 편집을 버린다.

## 작업

### 1. 테스트 먼저 (`tests/gui/test_process_change_save.py`, 새 파일)

`device_tab_ctrl` 를 쓴다. sf2p에서 시작하고, 전환은 `select_process(ctrl, "sf4u")` 로 한다. 콤보는 `ctrl.device_tab_toolbar.ui.process_selector`.

| 경우 | 준비와 답 | 최종 상태 |
|---|---|---|
| 탭만 편집 × 예 | nfet_a 탭 셀 편집, `answer_question(True)` | nfet_a id로 `replace_many_for_device`, 콤보·`device_table.current_process` 가 sf4u. **수정 전 RED**: 질문이 없고 호출이 없다 |
| 탭만 편집 × 아니오 | `answer_question(False)` | `dialogs.shown` 에 "Save Changes" 질문, 저장 호출 없음, sf4u로 넘어가고 `parameter_tab.is_dirty()` False. **수정 전 RED**: 질문이 없다 |
| device 충돌 × 취소 | nfet_a Description 편집, bob이 nfet_a 저장, `answer_question(True)`, `answer_conflict(CANCEL)` | 콤보 "sf2p", `device_table.current_process == "sf2p"`, 편집 값 그대로, `device_table.is_dirty()` True, `get_or_create_id("sf4u")` 없음, 질문은 한 번뿐. **수정 전 RED**: sf4u로 넘어가고 편집이 없다 |
| 탭 충돌 × 취소 | nfet_a 탭 셀 편집, bob이 nfet_a 저장, 예, `CANCEL` | 콤보 "sf2p", 탭이 nfet_a의 편집 값과 dirty를 그대로 가진다, `upsert_devices` 호출 없음(device는 dirty가 아니라 저장하지 않는다) |
| device 저장 예외 | nfet_a Description 편집, `store.fail_next("upsert_devices", RuntimeError("boom"))`, 예 | 오류 알림 title "Save Devices Failed", 콤보 "sf2p", 편집 그대로. **수정 전 RED**: "Process Change Failed", 콤보 sf4u |
| device 충돌 × 다시 읽기 | device 편집, bob, 예, `RELOAD` | device 편집이 이미 버려졌으므로 sf4u로 넘어간다 |
| 둘 다 편집 × 예 | **nfet_b** Description 편집 + **nfet_a** 탭 편집, 예 | `upsert_devices` 다음 `replace_many_for_device`, sf4u로 넘어간다. 같은 device의 행과 탭을 함께 고치면 step 6 전까지 나 자신과 충돌하므로(G5) 서로 다른 device로 한다 |
| Add Process 중 탭 충돌 × 취소 | nfet_a 탭 편집, bob, `answer_question(True)`, `answer_conflict(CANCEL)`, `ctrl.device_tab_toolbar.add_process("new_p")` | 콤보 "sf2p", 콤보 항목에 "new_p" 있음(process는 만들어졌다), 탭 편집과 dirty 그대로. **수정 전 RED** |

되돌림 경우에는 `ctrl.device_tab_toolbar.processChanged` 를 리스트에 연결해 되돌리는 동안 새 신호가 없는지도 본다(`select_process_silently` 가 `on_process_changed` 를 다시 부르지 않는다).

### 2. 수정

```python
# controllers/device_tab.py
def on_process_changed(self, process_name: str): ...
# controllers/device_tab_toolbar.py
def add_process(self, name: str): ...   # clearTabRequested.emit(True) 를 뺀다
```

`process_name` 이 비어 있지 않으면 `clear()`·`hide_views()`·배너 숨기기·"Selected process" 로그보다 **먼저** 아래를 한다. `previous = self.device_table.current_process`.

1. `device_table.is_dirty()` 도 `parameter_tab.is_dirty()` 도 아니면 지금처럼 진행한다.
2. 하나라도 dirty면 지금 질문(같은 제목·문구)을 **한 번** 한다.
   - 아니오: 지금처럼 진행한다(device 편집은 `refresh_devices`, 탭 편집은 `_clear_tabs` 가 버린다).
   - 예: **dirty인 쪽만** 저장한다. device 먼저, 탭 다음.
     - device: `device_table.save_all()`. 예외면 `report_error(self, "Save Devices Failed", e, logger=log)`. 예외이거나, `False` 인데 아직 `device_table.is_dirty()` 면 되돌린다. `False` 지만 dirty가 아니면(다시 읽기로 편집이 이미 버려졌다) 탭 단계로 간다.
     - 탭: `parameter_tab.save_all()`. 예외면 `report_error(self, "Save Tabs Failed", e, logger=log)`. 예외이거나 `False` 인데 아직 `parameter_tab.is_dirty()` 면 되돌린다. 그 밖에는 진행한다.
3. **되돌림**: `self.device_tab_toolbar.select_process_silently(previous)` 후 return. `clear()`, `hide_views()`, 배너, 로그, `get_process_id`, `set_current_process*`, `refresh_devices`, `_clear_tabs` 를 하나도 하지 않는다.
4. **진행**: 지금 코드 그대로(`clear`, `hide_views`, 배너, 로그, `get_process_id`, …, `refresh_devices`, `_clear_tabs`).

- 빈 process("") 경로는 바꾸지 않는다(step 4 뒤에는 목록이 비었을 때만 온다).
- 저장 예외는 `report_error` 로 여기서 잡는다. `@report("Process Change Failed")` 까지 올려보내면 되돌릴 수 없다. 저장이 아닌 곳의 예외(`get_process_id` 등)는 지금처럼 `@report` 가 받는다.
- `add_process` 의 `clearTabRequested.emit(True)` 를 뺀다(버그 4). `clearTabRequested` 시그널과 그 연결은 남겨도 된다.

최종 상태:

| 경우 | 콤보 | device 표 | 탭 | 알림 |
|---|---|---|---|---|
| 편집 없음 / 아니오 | 새 process | 새 process(편집 버림) | 비움 | 없음 |
| 예, 저장 성공 | 새 | 새 | 비움 | 저장한 쪽의 기존 알림("Save Complete", "Saved") |
| 예, device 충돌 × 취소(창 닫기) | 이전 | 이전, 편집·dirty 그대로 | 그대로(탭 저장 시도 안 함) | 없음 |
| 예, device 충돌 × 다시 읽기 / 덮어쓰기 | 탭 단계 결과를 따른다 | 다시 읽음(편집 버림) / 저장됨 | 탭 단계 결과를 따른다 | 덮어쓰기면 "Save Complete" |
| 예, device 예외(접속 끊김 포함) | 이전 | 이전, 편집 그대로 | 그대로 | "Save Devices Failed" |
| 예, 탭 충돌 × 취소 | 이전 | 이전(device는 저장됐을 수 있다) | 이전 device, 편집·` *` 그대로 | 저장된 device의 "Save Complete" 만 |
| 예, 탭 예외 | 이전 | 이전 | 그대로 | "Save Tabs Failed" |

- `previous` 가 목록에 없으면(그 process가 막 지워졌으면) `select_process_silently` 는 아무것도 하지 않는다. 그 경우는 이 step에서 다루지 않고 테스트하지 않는다.

### 3. 문서

- 바꿀 문서는 없다. 질문 문구가 그대로이고 UI_GUIDE 원칙 2·4에 맞추는 수정이다.

## Acceptance Criteria

```bash
uv run pytest tests/gui/test_process_change_save.py -q   # 새 테스트 통과 (수정 전에는 탭 질문·취소·예외·Add Process 경우가 실패해야 한다)
uv run ruff check src tests
uv run pytest tests/gui -q
uv run pytest -q
```

## 검증 절차

1. 위 AC 커맨드를 실행한다.
2. 아키텍처 체크리스트를 확인한다:
   - `controllers/device_tab.py` 의 `on_process_changed` 와 `controllers/device_tab_toolbar.py` 의 `add_process` 만 바꿨는가?
   - 질문이 여전히 Yes/No 하나이고(`utils/dialogs.question`) 문구가 그대로인가? 오류는 `report_error`(→ `user_message`)로 알리는가?
   - 되돌림이 `select_process_silently` 뿐이고 선택을 코드로 바꾸면서 `processChanged` 를 다시 내지 않는가?
3. 결과에 따라 `phases/3-gui-save-fixes/index.json` 의 step 5를 업데이트한다:
   - 성공 → `"status": "completed"`, `"summary": "on_process_changed: device·탭 dirty 둘 다 묻고 dirty인 쪽만 저장, 저장 뒤에도 dirty(취소·예외)면 select_process_silently(previous)로 되돌림. add_process 의 clearTabRequested 제거. RED: <테스트 이름>. tests/gui/test_process_change_save.py"`
   - 재현 안 됨 → `"status": "completed"`, `"summary": "not reproduced: <이유>"`
   - 수정 3회 시도 후에도 실패 → `"status": "error"`, `"error_message": "구체적 에러 내용"`
   - 사용자 개입 필요 → `"status": "blocked"`, `"blocked_reason": "구체적 사유"` 후 즉시 중단

## 금지사항

- 질문을 device용·탭용 두 번 하거나 세 갈래(저장/버림/취소) 질문을 만들지 마라. 이유: 질문은 Yes/No 둘뿐이다(UI_GUIDE). 새 대화상자는 승인되지 않은 동작 변경이다.
- `save_db()` 를 불러 저장하지 마라. 이유: "Saved: All changes have been saved." 상자가 하나 더 떠 지금 전환 흐름의 알림이 바뀐다. 두 `save_all()` 을 직접 부른다.
- dirty가 아닌 쪽의 `save_all()` 을 부르지 마라. 이유: device 쪽은 바뀐 것이 없어도 "Save Complete: No changes to save." 상자를 띄운다.
- 되돌릴 때 `select_process(previous)`(시그널이 나는 선택)나 `setCurrentText` 를 쓰지 마라. 이유: `on_process_changed` 가 다시 들어와 질문이 또 뜨거나 이전 process를 다시 읽는다.
- 빈 process("") 경로에 dirty 검사를 넣지 마라. 이유: 이 step 범위가 아니고, step 4 뒤에는 목록이 비었을 때만 온다.
- K20(deleted × 덮어쓰기)을 고치거나 따로 문구를 만들지 마라. 이유: 범위 밖. 탭 쪽에서 나는 두 번째 `StaleWriteError` 는 위의 저장 예외 처리에 잡혀 "Save Tabs Failed" 로 알리고 되돌린다(step 2의 `save_db` 와 같다).
- 기존 테스트를 깨뜨리지 마라. step 4의 Add Process 테스트(device 편집 → 질문 → 저장)는 그대로 통과해야 한다.
