# Step 2: save-entry-points

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

두 저장 입구를 step 0·1의 계약 위에서 바로잡는다.
- **Database → Save**(`DeviceTabController.save_db`)가 탭도 저장하게 한다(분석 G1). 지금은 탭을 한 번도 저장하지 않으면서 "All changes have been saved." 를 띄운다.
- `save_db` 와 **Ctrl+S**(`MainWindowController._on_save_triggered`)가 저장이 취소되거나 실패했으면 "Saved"·상태 표시줄 문구를 띄우지 않게 한다(분석 G4, UI_GUIDE 원칙 4).

## 읽어야 할 파일

- `/CLAUDE.md`, `/docs/UI_GUIDE.md`(원칙 4·5, 문구 → 알림 경로), `/docs/ADR.md`(ADR-004)
- `src/genviewer/controllers/device_tab.py` — `save_db` (~111-127)
- `src/genviewer/controllers/main_window.py` — `_setup_actions` (~71-105: 창 전체 `act_save`(Ctrl+S) → `_on_save_triggered`, Database 메뉴 `save_action` → `device_tab.save_db`), `_on_save_triggered` (~173-191, 포커스로 세 갈래), `_on_status_message` (~217-220), `_on_notify_requested` (~222-230)
- `src/genviewer/views/main_window.py` — `notify` (~172-182), `show_status` (~184-185)
- `src/genviewer/utils/reporting.py` — `report_error`
- 이전 step에서 수정된 파일: `src/genviewer/controllers/device_table.py`, `src/genviewer/controllers/parameter_tab.py`(둘 다 `save_all -> bool`: True=저장·덮어쓰기·쓸 것 없음, False=취소·다시 읽기·repo 없음, 예외는 그대로), `tests/gui/test_device_save_result.py`, `tests/gui/test_tab_save_result.py`

## 버그

**G1 — Database → Save 가 탭을 저장하지 않는다.**

```python
def save_db(self):
    try:
        self.device_table.save_all()
    except Exception as e:
        report_error(self, "Save Devices Failed", e, logger=log)
        return

    current = getattr(self, "current_device", None)
    if current:
        try:
            self.parameter_tab.save_all()
        ...
    self.notifyRequested.emit("info", "Saved", "All changes have been saved.")
```

`current_device` 는 어디에서도 대입되지 않는다(`grep -rn current_device src/` 는 이 줄뿐). 그래서 탭 저장은 절대 불리지 않는다. 재현: sf2p → nfet_a를 누른다 → 탭 셀 하나를 고친다(탭 이름 뒤 ` *`) → 메뉴 Database → Save → "Save Complete: No changes to save." 와 "Saved: All changes have been saved." 가 뜬다 → 탭의 ` *` 가 그대로이고, 앱을 다시 띄우면 그 편집이 없다.

**G4 — 취소·실패 뒤에도 "Saved".**
- `save_db` 는 `device_table.save_all()` 의 결과를 보지 않는다. 재현: nfet_a Description을 고친다 → bob이 nfet_a를 저장한다 → Database → Save → "Save Conflict" 에서 "취소" → "Saved: All changes have been saved." 가 뜬다.
- `_on_save_triggered` 는 결과와 상관없이 상태 표시줄 문구를 띄운다. 재현: device 표에 포커스를 두고 같은 충돌에서 Ctrl+S → "취소" → 상태 표시줄에 "Device table saved". device 저장이 예외로 실패해도(서버 다운) 포커스가 표 밖이면 `save_db` 가 "Save Devices Failed" 를 띄운 직후 상태 표시줄에 "All device and tab data saved" 가 뜬다.

## 작업

### 1. 테스트 먼저 (`tests/gui/test_save_entry_points.py`, 새 파일)

`main_window` fixture를 쓰고 `ctrl = main_window.device_tab` 이다. Database → Save는 메뉴바의 "Database" 메뉴에서 텍스트가 "Save" 인 `QAction` 을 찾아 `trigger()` 한다(창 전체의 Ctrl+S `QAction` 도 텍스트가 "Save" 라서 메뉴 안에서 찾아야 한다). 반환값이 필요한 경우는 `ctrl.save_db()` 를 직접 부른다.

- **탭 저장(G1)**: sf2p → `select_device_row(ctrl, 0)` → 탭 셀 편집 → 메뉴 Database → Save → `store.calls` 에 nfet_a id로 `replace_many_for_device` 가 있고, `dialogs.shown` 에 `("info", "Saved", "All changes have been saved.")` 가 있고, `parameter_tab.is_dirty()` 가 False. 수정 전 RED: `replace_many_for_device` 가 없다.
- **device 충돌 취소**: nfet_a Description 편집(탭은 그대로) → bob이 nfet_a 저장 → `answer_conflict(CANCEL)` → `ctrl.save_db()` 가 `False`, `dialogs.shown` 의 어느 text에도 "All changes have been saved." 가 없다. 수정 전 RED.
- **탭 충돌 취소**: nfet_a 탭 셀 편집 → bob이 nfet_a 저장 → `answer_conflict(OVERWRITE, CANCEL)` → `ctrl.save_db()` 가 `False`, "All changes have been saved." 없음, `parameter_tab.is_dirty()` True. 답이 둘인 이유: device 저장은 화면의 device를 전부 보내고 `_preflight` 가 전부의 version을 보므로, bob의 nfet_a 저장은 device 저장에서 먼저 충돌한다. 덮어쓰기를 골라도 nfet_a의 값이 같아 version은 오르지 않고, 이어진 탭 저장이 bob과 충돌해 취소를 받는다. 수정 전 RED: 탭 저장이 불리지 않아 "All changes" 가 뜬다.
- **device 저장 예외**: `store.fail_next("upsert_devices", RuntimeError("boom"))` → `ctrl.save_db()` 가 `False`, `dialogs.shown` 에 title "Save Devices Failed" 인 error 기록, `replace_many_for_device` 호출 없음, "All changes" 없음.
- **Ctrl+S 상태 표시줄**: `monkeypatch.setattr(main_window.ui, "focusWidget", lambda: ctrl.ui.device_table_view)` 로 포커스를 정한다(offscreen에서 실제 포커스는 창 활성화에 달려 불안정하다. `isAncestorOf` 는 자기 자신에도 True다). `main_window._on_save_triggered()` 를 부른다.
  - 성공 → `main_window.ui.statusBar().currentMessage() == "Device table saved"` (회귀).
  - device 충돌 취소 → 그 문구가 아니다. 수정 전 RED.
  - 포커스가 `ctrl.ui.parameter_tab_view` 이고 탭 충돌 취소 → "Tab section data saved" 가 아니다.
  - 포커스가 둘 다 아니고(`lambda: None`) device 저장 예외 → "All device and tab data saved" 가 아니다. 수정 전 RED.
- 주의: 같은 device(nfet_a)의 device 행과 탭을 **함께** 고친 저장은 step 6 전까지 나 자신과 충돌한다(device 저장이 nfet_a version을 올리는데 탭은 옛 version을 들고 있다, 분석 G5). 이 step의 테스트는 둘을 같은 device에서 함께 고치지 않는다.

### 2. 수정

```python
# controllers/device_tab.py
def save_db(self) -> bool: ...
# controllers/main_window.py
def _on_save_triggered(self) -> None: ...
```

`save_db`:
1. `device_table.save_all()`. 예외면 지금처럼 `report_error(self, "Save Devices Failed", e, logger=log)` 후 `False` 를 돌려준다(탭 저장으로 가지 않는다. 지금과 같다).
2. `getattr(self, "current_device", None)` 검사를 지우고, device 결과가 `True` 든 `False` 든 `parameter_tab.save_all()` 을 부른다. 탭 편집은 device 충돌과 별개로 저장을 요청받은 것이다. 예외면 `report_error(self, "Save Tabs Failed", e, logger=log)` 후 `False`.
3. 둘 다 `True` 일 때만 `("info", "Saved", "All changes have been saved.")` 알림과 "Saved all device/tab changes." 로그를 내고 `True` 를 돌려준다. 그 밖에는 `False` 이고 이 알림·로그를 내지 않는다.

최종 상태:

| device `save_all` | 탭 `save_all` | 화면 알림 | 반환 |
|---|---|---|---|
| True | True | device "Save Complete" (+ 탭이 dirty였으면 탭 "Saved: <요약>") + "Saved: All changes have been saved." | True |
| True | False(취소·다시 읽기) | device "Save Complete" 만 | False |
| False(취소·다시 읽기) | True / False | 탭 쪽 알림만(있으면) | False |
| 예외(접속 끊김 포함) | 부르지 않음 | "Save Devices Failed: <user_message>" | False |
| True / False | 예외 | "Save Tabs Failed: <user_message>" | False |

`_on_save_triggered`: 세 갈래 모두 저장 함수가 `True` 를 돌려줄 때만 지금 문구("Device table saved", "Tab section data saved", "All device and tab data saved")를 상태 표시줄에 낸다. `False` 면 아무것도 내지 않는다. device·탭 갈래의 예외 처리(`"Save Failed"` + `user_message`)는 그대로 둔다.

### 3. 문서

- 바꿀 문서는 없다. UI_GUIDE 원칙 4("저장이 취소되거나 일부만 됐으면 Saved 를 띄우지 않는다")에 맞추는 수정이고 새 문구가 없다.

## Acceptance Criteria

```bash
uv run pytest tests/gui/test_save_entry_points.py -q   # 새 테스트 통과 (수정 전에는 탭 저장·취소 경우가 실패해야 한다)
uv run ruff check src tests
uv run pytest tests/gui -q
uv run pytest -q
```

## 검증 절차

1. 위 AC 커맨드를 실행한다.
2. 아키텍처 체크리스트를 확인한다:
   - `controllers/device_tab.py` 의 `save_db` 와 `controllers/main_window.py` 의 `_on_save_triggered` 만 바꿨는가?
   - 오류 문구가 `report_error`/`user_message` 를 거치는가(`str(exc)` 금지, CLAUDE.md)?
   - 기존 문구("Saved", "All changes have been saved.", 상태 표시줄 세 문구, "Save Devices Failed", "Save Tabs Failed")를 바꾸지 않았는가?
3. 결과에 따라 `phases/3-gui-save-fixes/index.json` 의 step 2를 업데이트한다:
   - 성공 → `"status": "completed"`, `"summary": "save_db -> bool: 탭도 항상 저장(device 예외만 중단), 둘 다 True일 때만 'All changes have been saved.'. Ctrl+S 상태 문구는 True일 때만. RED: <테스트 이름>. tests/gui/test_save_entry_points.py"`
   - 재현 안 됨 → `"status": "completed"`, `"summary": "not reproduced: <이유>"`
   - 수정 3회 시도 후에도 실패 → `"status": "error"`, `"error_message": "구체적 에러 내용"`
   - 사용자 개입 필요 → `"status": "blocked"`, `"blocked_reason": "구체적 사유"` 후 즉시 중단

## 금지사항

- `current_device` 를 어딘가에서 대입해 기존 검사를 살리지 마라. 이유: 탭이 dirty인지는 `parameter_tab.save_all()` 이 스스로 본다(dirty가 없으면 `True`). 상태를 하나 더 두면 또 어긋난다.
- device 저장이 예외로 실패했을 때 탭 저장을 이어서 하지 마라. 이유: 지금 동작이고, 접속 끊김이면 탭 저장도 실패해 오류 상자가 두 번 뜬다.
- `save_db` 에서 질문이나 새 알림을 더하지 마라. 이유: 동작 변경이다. 결과에 따라 기존 알림을 낼지 말지만 정한다.
- `_on_save_triggered` 의 포커스 판단(`isAncestorOf`)과 예외 처리를 바꾸지 마라. 이유: 이 step 범위가 아니다.
- G5(같은 device의 device 행과 탭을 함께 고친 저장이 나 자신과 충돌)를 여기서 고치지 마라. 이유: step 6 범위다.
- 기존 테스트를 깨뜨리지 마라. 단 phase 2 테스트가 "save_db 는 탭을 저장하지 않는다" 같은 지금 동작을 고정하고 있으면 그 단언만 새 동작으로 바꾸고 summary에 적는다.
