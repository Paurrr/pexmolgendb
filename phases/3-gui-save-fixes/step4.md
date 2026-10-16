# Step 4: process-list-refresh

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

- process 목록을 다시 채울 때(CSV 불러오기, Add Process, 재접속) 지금 고른 process를 그대로 두고, 그 사이 빈 process("")나 첫 process로 잠깐 바뀌면서 dirty 검사 없이 편집을 버리지 않게 한다(분석 G3).
- process를 지우면 목록에서 그 이름이 사라지게 한다. 지금은 남아 있어서 다시 고르면 `get_or_create_id` 가 빈 process를 새로 만든다(분석 G11).
- step 5가 쓸 `select_process_silently(name)` 을 만든다.

## 읽어야 할 파일

- `/CLAUDE.md`, `/docs/UI_GUIDE.md`(원칙 2), `/docs/ARCHITECTURE.md`(스레딩: 아직 GUI 스레드에서 동기로 도는 process 호출)
- `src/genviewer/views/device_tab_toolbar.py` — `open_remove_process_dialog` (~133-145), `set_processes` (~157-160), `select_process` (~162-164), `set_libraries` (~166-174, 시그널을 막고 이전 값을 되살리는 같은 파일의 선례)
- `src/genviewer/controllers/device_tab_toolbar.py` — `__init__` 연결 (~29, 40-41: `process_selector.currentTextChanged` 만 연결되어 있다), `add_process` (~81-99), `remove_process` (~101-128), `refresh_processes` (~130-135), `get_process_id` (~143-150)
- `src/genviewer/controllers/device_tab.py` — `apply_db` (~253-259), `on_load_csv_requested` (~327-353), `on_process_changed` (~378-403, "" 경로 ~385-389)
- `src/genviewer/controllers/device_table.py` — `is_dirty` (~212-215, `current_process_id` 가 None이면 False)
- `src/genviewer/service/repo/process.py` — `get_or_create_id` (~104-121, 없으면 만든다), `delete` (~32-66)
- 이전 step에서 수정된 파일: `controllers/device_table.py`, `controllers/parameter_tab.py`(`save_all -> bool`), `controllers/device_tab.py`(`save_db`, `_switch_device_by_index`), `controllers/main_window.py`, `tests/gui/test_device_save_result.py`, `test_tab_save_result.py`, `test_save_entry_points.py`, `test_device_switch_save.py`

## 버그

**G3 — 목록을 다시 채우면 process가 두 번 바뀐다.**

```python
@Slot()
def set_processes(self, items: list[str]):
    self.process_selector.clear()
    self.process_selector.addItems(items)
```

`clear()` 가 `currentTextChanged("")` 를 낸다 → `on_process_changed("")` 가 dirty 검사 없이 `set_current_process_id(None)` 하고 `_clear_tabs()` 로 탭 편집을 버린다. 이어서 `addItems` 가 첫 항목을 골라 `currentTextChanged(items[0])` 를 낸다 → 이제 `current_process_id` 가 None이라 `device_table.is_dirty()` 가 False → 묻지 않고 첫 process를 읽는다. (2026-10-17 offscreen 확인: 빈 콤보에 `addItems` → `['sf2p']`, `clear()` → `['']`, 다시 `addItems` → `['sf2p']`.) 이 경로를 타는 곳은 `refresh_processes`(접속·재접속의 `apply_db`, CSV 불러오기)와 `add_process` 다.

재현:
- CSV: sf4u를 고른다 → 그 device를 눌러 탭 셀을 고친다 → Database → Load CSV → 끝나면 콤보가 sf2p이고 탭 편집은 묻지도 않고 사라졌다.
- Add Process: sf4u에서 device Description을 고친다 → `+` 로 "new_p" 추가 → "Save Changes?" 를 묻지 않고 편집이 사라진다.
- 재접속: sf4u를 보다가 Database → Connect... 로 다시 붙으면 sf2p로 넘어간다.

**G11 — 지운 process가 목록에 남는다.**

```python
if self.repo.delete(name, actor=current_user()):
    self.notifyRequested.emit("info", "Removed", f"Process '{name}' removed.")
    self.setProcessRequested.emit("")
```

`select_process("")` 는 비편집 `QComboBox.setCurrentText("")` 다. 일치하는 항목이 없으면 아무것도 하지 않는다(offscreen 확인: 시그널 없음, 텍스트 그대로). 재현: sf4u를 고른다 → `-` → 확인 두 번 → "Removed" → 콤보에 sf4u가 그대로다 → sf2p를 골랐다가 다시 sf4u를 고르면 `get_or_create_id("sf4u")` 가 빈 sf4u를 새로 만든다(이력에 "process 추가").

## 작업

### 1. 테스트 먼저 (`tests/gui/test_process_list_refresh.py`, 새 파일)

`device_tab_ctrl` 를 쓴다. 콤보는 `ctrl.device_tab_toolbar.ui.process_selector` 다. 호출 기록은 동작 직전의 `len(store.calls)` 이후만 본다.

- **CSV 불러오기**: sf4u → 그 device 행 → 탭 셀 편집 → `ctrl.on_load_csv_requested(<path>)`(가짜 `import_data` 가 요구하는 대로 파일을 준다) → 콤보 텍스트 "sf4u", `device_table.current_process == "sf4u"`, `parameter_tab.is_dirty()` True, 불러오기 뒤 `get_or_create_id` 호출 없음. 수정 전 RED: 콤보가 "sf2p".
  - device 편집은 단언하지 마라. `on_load_csv_requested` 가 끝에서 `device_table.refresh_devices()` 를 직접 불러 다시 읽는다(이 step 범위 밖. summary에 적는다).
- **Add Process**: sf4u → device Description 편집 → `answer_question(True)` → `ctrl.device_tab_toolbar.add_process("new_p")` → `upsert_devices` 가 sf4u의 편집 값으로 불렸고, 그 뒤 콤보는 "new_p". 수정 전 RED: 질문이 뜨지 않고 `upsert_devices` 가 불리지 않는다(지금 `on_process_changed` 는 device dirty만 보므로 device 편집으로 확인한다).
- **재접속**: sf4u → fixture가 접속한 방법대로 `ctrl.connect_db(...)` 를 한 번 더 부른다(방법이 없으면 헬퍼를 더한다) → 콤보 "sf4u", `device_table.current_process_id` 가 sf4u의 id. 수정 전 RED: "sf2p". device·탭 편집은 단언하지 마라(`apply_db` 의 `refresh_devices()`·`rebuild_all_sections()` 가 다시 읽는 것은 의도된 동작이다).
- **처음 접속**: fixture 직후 콤보가 "sf2p" 이고, 그때까지 `get_or_create_id` 호출이 "sf2p" 한 번뿐이다. 지금도 통과하는 회귀 테스트다(불변식 3).
- **현재 process가 남에 의해 사라짐**: sf4u를 고른 뒤 가짜 ProcessRepository(`ctrl.device_tab_toolbar.repo`)의 `delete("sf4u", actor="bob")` 를 직접 부르고 `ctrl.device_tab_toolbar.refresh_processes()` → 콤보 "sf2p", 그 사이 `get_or_create_id` 가 "sf2p" 로 정확히 한 번, ""로 가는 전환 없음(`device_table.current_process` 가 한 번도 "" 가 되지 않았는지는 `processChanged` 를 리스트에 연결해 `["sf2p"]` 로 확인).
- **지우기**: sf4u → `answer_question(True)` → `ctrl.device_tab_toolbar.remove_process("sf4u")`(controller의 질문 하나. view의 "Confirm Delete" 는 거치지 않는다) → 콤보 항목에 "sf4u" 없음(`findText("sf4u") == -1`), 콤보 "sf2p", `device_table.current_process == "sf2p"`. 이어서 `setCurrentText("sf2p")`, `setCurrentText("sf4u")` → `get_or_create_id("sf4u")` 호출 없음, 가짜 `list_all()` 에 sf4u 없음. 수정 전 RED: "sf4u" 가 항목에 남고, 다시 고르면 되살아난다.
- **`select_process_silently`**: `ctrl.device_tab_toolbar.select_process_silently("sf4u")` → 콤보 "sf4u", `processChanged` 없음, `get_or_create_id` 호출 없음, `device_table.current_process` 그대로. 목록에 없는 이름이면 콤보 그대로.

### 2. 수정

```python
# views/device_tab_toolbar.py
def set_processes(self, items: list[str]) -> None: ...
def select_process_silently(self, name: str) -> None: ...
# controllers/device_tab_toolbar.py
def select_process_silently(self, name: str) -> None: ...   # view에 맡긴다
def remove_process(self, name: str): ...                    # 지운 뒤 목록을 다시 채운다
```

`set_processes` 불변식:
1. 목록 내용은 `items` 순서 그대로다.
2. 지금 텍스트가 `items` 에 있으면 그것을 그대로 두고 `currentTextChanged` 를 **한 번도** 내지 않는다.
3. 없으면(처음 채울 때, 지운 process, 남이 지운 process) 첫 항목(목록이 비면 "")이 되고, 최종 텍스트가 이전과 다를 때만 그 텍스트로 **정확히 한 번** 낸다. `""` 나 중간 값으로는 내지 않는다.
4. `set_libraries` 처럼 시그널을 막고 다시 채우되, 막기만 하고 끝내지 않는다(3번 때문이다).

`select_process_silently`: 시그널 없이 그 이름을 고른다. 목록에 없으면 아무것도 하지 않는다.

`remove_process`: 지우기에 성공하면 `setProcessRequested.emit("")`(비편집 콤보에서 아무 일도 하지 않는다) 대신 `refresh_processes()` 로 목록을 다시 채운다. 콤보는 불변식 3에 따라 남은 첫 process(없으면 "")로 가고 `on_process_changed` 가 한 번 돈다. 알림·로그 문구는 그대로다.

- 현재 process가 유지되면 `on_process_changed` 가 불리지 않으므로 그 안의 `clear()`(Virtuoso 목록 비우기), `hide_views()`, 배너 숨기기도 일어나지 않는다. process가 바뀌지 않았으니 맞다. 따로 부르지 마라.
- `refresh_processes()` 의 `list_all()` 은 이 파일의 다른 process 호출처럼 GUI 스레드에서 동기로 돈다(ARCHITECTURE 스레딩 절의 "아직 남은" 경로). 새 DB 호출이 아니라 기존 경로를 다시 쓰는 것이다.
- 지운 process에 저장 안 한 device 편집이 있었다면 이어지는 전환에서 기존 "Save Changes" 질문이 뜬다. 이 step은 그 경우를 바꾸지 않고 테스트하지 않는다.

### 3. 문서

- 바꿀 문서는 없다. 문구가 그대로이고, process를 지운 뒤 남은 첫 process로 가는 것은 버그 수정이다.

## Acceptance Criteria

```bash
uv run pytest tests/gui/test_process_list_refresh.py -q   # 새 테스트 통과 (수정 전에는 CSV·Add Process·재접속·지우기 경우가 실패해야 한다)
uv run ruff check src tests
uv run pytest tests/gui -q
uv run pytest -q
```

## 검증 절차

1. 위 AC 커맨드를 실행한다.
2. 아키텍처 체크리스트를 확인한다:
   - `views/device_tab_toolbar.py` 와 `controllers/device_tab_toolbar.py` 만 바꿨는가? `controllers/device_tab.py` 는 그대로인가?
   - view가 repo나 controller를 부르지 않는가(view는 위젯과 시그널만, ARCHITECTURE 레이어)?
   - 새 DB 호출을 GUI 스레드에 더하지 않았는가(기존 `refresh_processes` 재사용만)?
3. 결과에 따라 `phases/3-gui-save-fixes/index.json` 의 step 4를 업데이트한다:
   - 성공 → `"status": "completed"`, `"summary": "set_processes: 현재 process 유지, 바뀔 때만 currentTextChanged 한 번. remove_process 뒤 refresh_processes. select_process_silently(view+controller) 추가. RED: <테스트 이름>. tests/gui/test_process_list_refresh.py. 범위 밖: CSV 불러오기·재접속의 refresh_devices 가 device 편집을 버림"`
   - 재현 안 됨 → `"status": "completed"`, `"summary": "not reproduced: <이유>"`
   - 수정 3회 시도 후에도 실패 → `"status": "error"`, `"error_message": "구체적 에러 내용"`
   - 사용자 개입 필요 → `"status": "blocked"`, `"blocked_reason": "구체적 사유"` 후 즉시 중단

## 금지사항

- `set_processes` 에서 시그널을 막기만 하고 끝내지 마라. 이유: 처음 접속이나 현재 process가 사라진 경우 콤보는 새 이름인데 device 표는 이전 process(또는 빈 목록)를 보여준다.
- `on_process_changed`("" 경로 포함)와 그 dirty 검사를 바꾸지 마라. 이유: step 5 범위다.
- `on_load_csv_requested`·`apply_db` 의 `refresh_devices()`/`rebuild_all_sections()` 를 빼거나 옮기지 마라. 이유: 불러오기·재접속 뒤 다시 읽는 것은 의도된 동작이다. 거기서 device 편집이 사라지는 것은 별도 문제다(summary에 적는다).
- `get_process_id` 의 `get_or_create_id` 를 `get_id` 로 바꾸지 마라. 이유: 동작 변경이고, Add Process 직후와 처음 접속이 그 경로를 쓴다. 목록에서 이름을 지우면 되살아날 길이 없어진다.
- 콤보를 편집 가능하게 바꾸거나 빈 항목("")을 넣지 마라. 이유: 화면 동작 변경이다.
- `add_process` 를 바꾸지 마라(`clearTabRequested` 포함). 이유: step 5 범위다. 이 step의 `set_processes` 수정만으로 Add Process의 이중 전환이 사라진다.
- 기존 테스트를 깨뜨리지 마라. 단 phase 2 테스트가 "목록 갱신 뒤 첫 process로 간다" 같은 지금 동작을 고정하고 있으면 그 단언만 새 동작으로 바꾸고 summary에 적는다.
