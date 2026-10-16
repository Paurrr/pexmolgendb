# Step 7: device-save-guards

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

device 표에서 편집이 **경고 없이** 사라지는 두 경로를 막는다. 둘 다 사용자에게 보이는 동작 변경(새 경고)이다.
- **G15a** (사용자 승인 2026-10-17): 저장할 때 CellType이 목록에 없어 건너뛴 행의 편집이 저장 뒤 다시 읽기로 사라진다. 건너뛴 **편집한** 행의 이름을 경고로 알린다. 올바른 행의 저장은 그대로 한다.
- **G15b** (같은 phase 계획에 포함): 붙여넣기는 바로 저장한 뒤 목록을 다시 읽어 다른 저장 안 한 device 편집을 버린다. device 표에 저장 안 한 편집이 있으면 붙여넣지 않고 경고한다.

## 읽어야 할 파일

- `/CLAUDE.md`(문구 관례: 제목 영어, 본문 한국어), `/docs/UI_GUIDE.md`(원칙 2·4, 문구 → 알림 경로, 입력과 단축키)
- `src/genviewer/controllers/device_table.py` — `paste_rows` (~179-204: `insert_row` → `save_device` 즉시 쓰기 → `pasteRequested` → 끝에서 `refresh_devices()`), `is_dirty` (~212-215), `save_device` (~320-328), `save_all` (~330-363: `invalid_devices` 를 모으고 쓰지 않는다), `_valid_celltypes` (~448-453)
- `src/genviewer/models/device_table.py` — `_dirty_cells`, `_recompute_dirty_cells` (~310-318), `_original_for_device` (~327-340), `insert_row`
- `src/genviewer/delegates/combo_box.py` — device CellType 편집기는 `setEditable(True)` 이고 `strict` 가 아니라 목록 밖 값을 칠 수 있다
- `src/genviewer/service/repo/io.py` — CSV import(~115-122)는 CellType을 검사하지 않는다. DB에 목록 밖 CellType이 이미 있다
- `src/genviewer/config/delegate_config.json` — `device.celltype.items`
- `src/genviewer/controllers/device_tab.py` — `save_db`(step 2: device `False` 여도 탭은 저장, 둘 다 True일 때만 "All changes have been saved."), `on_process_changed`(step 5: 저장 뒤에도 dirty면 되돌림)
- 이전 step에서 수정된 파일: `controllers/device_table.py`(`save_all -> bool`, `deviceVersionBumped`), `controllers/parameter_tab.py`, `controllers/device_tab.py`, `controllers/main_window.py`, `views/device_tab_toolbar.py`, `controllers/device_tab_toolbar.py`, `tests/gui/test_*.py` 일곱 개

## 버그

**G15a — 건너뛴 행의 편집이 말없이 사라진다.**

```python
for i, d in enumerate(devices):
    d["order"] = i
    if d.get("celltype") in valid_celltypes:
        to_save.append(d)
    else:
        invalid_devices.append(d.get("name", "<Unknown>"))
...
self.notifyRequested.emit("info", "Save Complete", summary)
self.refresh_devices()
```

`invalid_devices` 는 모으기만 하고 쓰지 않는다. 건너뛴 행은 저장되지 않고, 이어진 `refresh_devices()` 가 화면을 DB 값으로 되돌린다. 재현: CSV로 들어와 CellType이 목록에 없는 device(예: `nmos_rf`)의 Description을 고친다 → Ctrl+S → "Save Complete: No changes to save." → Description이 옛 값으로 돌아가고 아무 경고도 없다. 목록에 있는 CellType을 지우고 목록 밖 값을 쳐 넣은 경우도 같다.

**G15b — 붙여넣기가 다른 편집을 버린다.**

```python
for copied_row in self._copied_rows:
    ...
    saved = self.save_device(row_data)
    ...
self.refresh_devices()
```

재현: sf2p에서 nfet_a의 Description을 고친다(노란 셀) → nfet_b 행을 Ctrl+C → Ctrl+V → 붙여넣은 행은 저장되고, nfet_a의 Description은 옛 값으로 돌아간다. 아무것도 묻지 않는다.

## 작업

### 1. 테스트 먼저 (`tests/gui/test_device_save_guards.py`, 새 파일)

`device_tab_ctrl` 로 sf2p를 고른다. 알림은 `ctrl.notifyRequested` 를 리스트에 연결해 본다.

- **편집한 목록 밖 행**: nfet_a의 CellType 칸을 `"nmos_rf"` 로, nfet_b의 Description을 고친다 → `ctrl.device_table.save_all()` 이 `False` → `upsert_devices` 에 간 device 목록에 nfet_b는 있고 nfet_a는 없다 → 가짜 repo에 nfet_b의 새 값 → 알림에 `("warn", "Save Skipped", <nfet_a 가 들어 있는 본문>)` 이 있다. **수정 전 RED**: 경고가 없다(반환은 step 0 계약대로 `True`).
- **손대지 않은 목록 밖 행**: 가짜 DeviceRepository(`ctrl.device_table.repo`)의 `upsert_devices` 를 bob으로 직접 불러 nfet_a의 CellType을 `"nmos_rf"` 로 바꾸고 `ctrl.device_table.refresh_devices()` → 아무것도 고치지 않고 `save_all()` → `True`, "Save Skipped" 경고 없음. 지금도 통과하는 회귀 테스트다(저장할 때마다 경고가 뜨지 않는다).
- **DB에서 온 목록 밖 행을 편집**: 위처럼 만든 뒤 nfet_a의 Description을 고쳐 `save_all()` → `False`, 경고에 nfet_a. **수정 전 RED**.
- **새 행**: `insert_row` 로 CellType이 빈 새 행(name `"new1"`)을 넣고 `save_all()` → 경고에 `new1`, 그 행은 `upsert_devices` 에 가지 않는다.
- **dirty일 때 붙여넣기**: nfet_a Description 편집 → `ctrl.device_table.copy_rows([1])` → `ctrl.device_table.paste_rows([1])` → 알림에 `("warn", "Unsaved Changes", …)`, `upsert_device` 호출 없음, 행 수 그대로, nfet_a의 편집 값과 `is_dirty()` True 그대로. **수정 전 RED**: `upsert_device` 가 불리고 편집이 사라진다.
- **깨끗할 때 붙여넣기**: 편집 없이 copy → paste → `upsert_device` 가 불리고 행이 하나 늘어난다(지금과 같다).
- **Database → Save와 함께**: 편집한 목록 밖 행이 있을 때 `ctrl.save_db()` 는 `False` 이고 "All changes have been saved." 가 없다(UI_GUIDE 원칙 4: 일부만 저장됐으면 Saved를 띄우지 않는다). 탭 저장은 그대로 불린다(step 2).

### 2. 수정

```python
# models/device_table.py
def is_row_changed(self, row: int) -> bool: ...   # 새 행이거나 표시 컬럼이 불러온 값과 다르면 True (노란 셀이 있는 행과 같은 기준)
# controllers/device_table.py
def save_all(self) -> bool: ...
def paste_rows(self, rows: list[int]): ...
```

`save_all`:
- 건너뛰는 규칙(CellType이 `_valid_celltypes()` 에 없으면 저장하지 않는다)과 올바른 행의 저장은 그대로다.
- 건너뛰는 행 중 `model.is_row_changed(i)` 인 것의 이름을 **쓰기 전에** 모은다(쓰기 뒤의 `refresh_devices` 가 기준점을 지운다).
- 쓰기가 성공했고(`_write_devices` 가 `None` 이 아님) 그런 행이 있으면, 지금의 "Save Complete" 알림 뒤에 아래 경고를 내고 `False` 를 돌려준다. 없으면 지금처럼 `True`.
  - title: `Save Skipped`
  - text: `"CellType 이 목록에 없어 다음 device 의 편집은 저장하지 않았다(다시 읽으면서 사라졌다).\n" + "\n".join(f" - {name}" for name in names)`
- 다시 읽기·취소(`None`)면 경고 없이 `False`(step 0과 같다).
- docstring의 계약에 "편집한 행 일부를 CellType 때문에 저장하지 못했으면 `False`" 를 더한다. 이 `False` 로 `save_db` 는 "All changes have been saved." 를 띄우지 않고, `on_process_changed`(step 5)는 다시 읽기로 dirty가 꺼졌으므로 그대로 진행한다.
- `deviceVersionBumped`(step 6)는 올바른 행의 쓰기 결과대로 그대로 낸다.

`paste_rows`:
- 복사한 행이 있고 `self.is_dirty()` 면 아무것도 넣거나 쓰지 않고 아래 경고를 낸 뒤 return한다. 깨끗하면 지금 동작 그대로다(바로 저장, `pasteRequested`, `refresh_devices`).
  - title: `Unsaved Changes`
  - text: `"저장하지 않은 device 편집이 있어 붙여넣지 않았다.\n붙여넣기는 바로 저장하고 목록을 다시 읽으므로 그 편집이 사라진다. 먼저 저장할 것."`

### 3. 문서

- `docs/UI_GUIDE.md` "입력과 단축키" 표 아래 목록에 두 줄을 더한다:
  - device 표 붙여넣기는 바로 저장되고 목록을 다시 읽는다. 저장 안 한 device 편집이 있으면 붙여넣지 않고 경고한다.
  - CellType이 `delegate_config` 목록에 없는 device는 저장하지 않는다. 그런 행을 편집했으면 저장 뒤 경고로 이름을 알린다.
- README·known-issues는 바꾸지 않는다.

## Acceptance Criteria

```bash
uv run pytest tests/gui/test_device_save_guards.py -q   # 새 테스트 통과 (수정 전에는 경고·붙여넣기 거부 경우가 실패해야 한다)
uv run ruff check src tests
uv run pytest tests/gui -q
uv run pytest -q
```

## 검증 절차

1. 위 AC 커맨드를 실행한다.
2. 아키텍처 체크리스트를 확인한다:
   - `controllers/device_table.py`, `models/device_table.py`(공개 메서드 하나), `docs/UI_GUIDE.md` 만 바꿨는가? controller가 model의 private 멤버(`_dirty_cells`, `_original_for_device`)를 직접 부르지 않는가(ARCHITECTURE "따라 하지 않는다")?
   - 새 문구가 관례(제목 영어, 본문 한국어)를 따르고 기존 문구는 그대로인가?
   - `delegate_config.json`·`_valid_celltypes` 를 바꾸지 않았는가?
3. 결과에 따라 `phases/3-gui-save-fixes/index.json` 의 step 7을 업데이트한다:
   - 성공 → `"status": "completed"`, `"summary": "save_all: CellType 때문에 건너뛴 편집한 행을 'Save Skipped' 경고로 알리고 False. paste_rows: device dirty면 'Unsaved Changes' 경고 후 거부. DeviceTableModel.is_row_changed 추가. UI_GUIDE 두 줄. RED: <테스트 이름>. tests/gui/test_device_save_guards.py. 범위 밖: <발견한 것>"`
   - 재현 안 됨 → `"status": "completed"`, `"summary": "not reproduced: <이유>"`
   - 수정 3회 시도 후에도 실패 → `"status": "error"`, `"error_message": "구체적 에러 내용"`
   - 사용자 개입 필요 → `"status": "blocked"`, `"blocked_reason": "구체적 사유"` 후 즉시 중단

## 금지사항

- CellType이 목록 밖인 행 때문에 저장 전체를 막거나, 저장 전에 질문을 띄우지 마라. 이유: CSV import가 CellType을 검사하지 않고 DB에 목록 밖 CellType(옛 값)이 이미 있다. 막으면 그런 행이 하나라도 있는 process는 아무도 저장할 수 없다.
- 손대지 않은 목록 밖 행까지 경고하지 마라. 이유: 잃는 편집이 없는데, 옛 CellType이 있는 process에서는 저장할 때마다 경고가 떠 아무도 경고를 읽지 않게 된다.
- 건너뛰는 규칙을 없애거나(목록 밖 행도 저장) 목록을 넓히지 마라. 이유: 저장 규칙 변경이다. 이 step은 알리기만 한다.
- 붙여넣기의 동작(바로 저장, 다시 읽기)을 바꾸지 마라. 이유: 거부 조건만 더한다.
- 탭에 저장 안 한 편집이 있을 때의 붙여넣기(`paste_payload` 가 `set_device_to_section` 으로 탭을 다시 읽는다)는 고치지 마라. 이유: 승인 범위(G15b)는 device 표의 dirty다. 발견했으면 summary에 적는다.
- 건너뛴 행의 순서(`order`) 손실이나 K19(Virtuoso 필터 뒤 순서 겹침)를 고치지 마라. 이유: 범위 밖이다.
- 기존 테스트를 깨뜨리지 마라. step 0의 반환 계약 테스트(올바른 CellType만 쓰는 경우)는 그대로 통과해야 한다.
