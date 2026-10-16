# Step 1: tab-section-view

## 배경 (phase 4 공통)

이 저장소는 이미 여러 명이 쓰는 도구다. 지금은 **에러·버그만 고친다**(CLAUDE.md, ADR-015). phase 4는 GUI가 실패·경합 상황에서 데이터를 잘못 쓰거나 죽는 버그를 한 step에 하나씩 고친다(탭 로드 실패, 탭 섹션 입력, "+" 탭, 필터 중 정렬, DB 재접속, 창 닫기, Virtuoso 소켓 워커). phase 3(`3-gui-save-fixes`)이 먼저 끝나 있다. 저장 함수가 결과를 돌려주고(`save_all() -> bool`, `DeviceTabController.save_db() -> bool`), `select_process_silently` 가 생겼다. 정확한 반환 계약은 코드와 `phases/3-gui-save-fixes/index.json` 의 summary로 확인하라.

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

탭 섹션(`views/tab_section.py`)의 입력 경로 두 군데를 고친다.
- (G10) device를 고르기 전에 Insert(버튼, Ctrl+I, 오른쪽 클릭 메뉴)를 누르면 "예기치 못한 오류" 상자가 뜬다. device가 없으면 Insert는 아무것도 하지 않게 한다.
- (G12) Ctrl+E로 연 편집 창이 빈 값으로 열려, OK를 누르면 그 행이 빈 값으로 덮인다. Ctrl+E가 Edit 버튼과 같은 경로(행 값을 채운 편집 창)를 타게 한다.

## 읽어야 할 파일

- `/CLAUDE.md`, `/docs/UI_GUIDE.md`(입력과 단축키 표: Ctrl+I / Ctrl+E / Ctrl+D), `/docs/ARCHITECTURE.md`(레이어 표)
- `src/genviewer/views/tab_section.py` — `__init__` (~28-48, `device_id`/`device_celltype` 를 만들지 않는다), `on_device_changed` (~95-98, 여기서 처음 생긴다), `open_insert_dialog` (~100-107), `open_edit_dialog` (~109-126), `edit_selected_row` (~128-139, Edit 버튼), `keyPressEvent` (~170-187, Ctrl+E가 `open_edit_dialog(rows[0], {})` ~180-183)
- `src/genviewer/dialogs/insert.py` — `InsertDialog.__init__(device_celltype, table_name, field_names, headers, parent, prefill=None, window_title="Insert")`, `_make_searchable_combo`(잠기지 않은 콤보는 `setCurrentIndex(-1)`, strict 콤보는 첫 항목), `get_data`
- `src/genviewer/controllers/tab_section.py` — `set_device` (`deviceChanged` → `ui.on_device_changed`), `_on_context_menu` (~43-61, 메뉴의 Insert는 `ui.open_insert_dialog()`, Edit은 `_row_to_dict` 로 값을 채운다), `insert_row`/`update_row` (`if not self.model: return`)
- `src/genviewer/controllers/parameter_tab.py` — `_clear_tabs` (~132-135, 모든 섹션을 `set_device(None, None)`), `rebuild_all_sections` (~137-140)
- `src/genviewer/controllers/device_tab.py` — `apply_db` (~253-259: `refresh_processes()` 가 첫 process를 고르고 `_clear_tabs()` 가 돈 **뒤에** `rebuild_all_sections()` 가 새 섹션을 만든다. 그래서 접속 직후의 섹션에는 `device_celltype` 이 없다)
- `tests/gui/conftest.py`, `tests/gui_support/`
- 이전 step에서 수정된 파일: `src/genviewer/controllers/tab_section.py`(`update_model` 실패 시 모델 비움), `tests/gui/test_tab_section_load.py`

## 버그

**G10.** `TabSection.__init__` 은 `device_id`·`device_celltype` 를 만들지 않는다. 두 속성은 `TabSectionController.set_device` → `deviceChanged` → `on_device_changed` 에서 처음 생긴다. 접속하면 `apply_db` 가 `rebuild_all_sections()` 로 섹션을 새로 만들고, 사용자가 device 행을 고르기 전까지 `set_device` 는 불리지 않는다. 그 사이 Insert 버튼·Ctrl+I·메뉴의 Insert는 `open_insert_dialog` 에서 `self.device_celltype` 를 읽다 `AttributeError` 를 내고, 슬롯 밖으로 샌 예외가 `sys.excepthook` → "예기치 못한 오류" 상자가 된다(접속 직후 가장 먼저 눌러 볼 버튼이다).
device를 고른 뒤 선택이 풀린 경우(`_clear_tabs()` 뒤 `device_id is None`)는 예외 없이 대화상자가 열리지만, OK를 누르면 `TabSectionController.insert_row` 가 `if not self.model: return` 으로 버린다. 입력이 말없이 사라진다.

**G12.** `keyPressEvent` 의 Ctrl+E:

```python
elif event.key() == Qt.Key_E:
    rows = self.table_view._selected_rows()
    if rows:
        self.open_edit_dialog(rows[0], {})
```

Edit 버튼(`edit_selected_row`)과 메뉴의 Edit은 행 값을 `prefill` 로 넘기는데 Ctrl+E만 빈 dict를 넘긴다. 편집 창은 빈 칸(잠기지 않은 콤보는 빈 값, strict 콤보는 첫 항목)으로 열리고, OK를 누르면 `editRequested` → `update_row` 가 그 행을 그 값으로 덮어쓴다(required가 아닌 컬럼은 빈 값도 검증을 통과한다).

이것은 주장이다. 먼저 재현하라.

## 작업

### 1. 테스트 먼저 (`tests/gui/test_tab_section_view.py`, 새 파일)

`InsertDialog` 는 진짜 모달이라 테스트에서 띄우지 않는다. `monkeypatch.setattr("genviewer.views.tab_section.InsertDialog", FakeInsertDialog)` 로 바꾼다. `FakeInsertDialog` 는 생성 인자(`device_celltype`, `table_name`, `prefill`, `window_title`)를 클래스 수준 목록에 기록하고, `exec_()`·`exec()` 는 `QDialog.Accepted` 를, `get_data()` 는 테스트가 정한 dict(기본: `prefill` 사본)를 돌려준다. 테스트 파일 안에 두거나, 다른 step도 쓸 만하면 `tests/gui_support/fakes.py` 에 둔다.

- **G10, 접속 직후**: `device_tab_ctrl` 에서 device를 고르기 전에 섹션 하나(`ctrl.parameter_tab.section(<탭 이름>).ui`)를 잡는다.
  - `sec.open_insert_dialog()` 가 예외 없이 끝나고 `FakeInsertDialog` 가 만들어지지 않는다. **수정 전에는 AttributeError로 실패해야 한다.**
  - `qtbot.keyClick(sec, Qt.Key_I, Qt.ControlModifier)` 와 `sec.insert_btn.click()` 도 같다(pytest-qt는 Qt 이벤트 처리 중에 난 예외를 잡아 테스트를 실패시킨다).
  - `sec.device_id is None`, `sec.device_celltype is None`.
- **G10, 선택이 풀린 뒤**: nfet_a를 골랐다가 `ctrl.parameter_tab._clear_tabs()` 를 부른 뒤 Insert → `FakeInsertDialog` 가 만들어지지 않는다. **수정 전에는 대화상자가 만들어져 실패해야 한다.**
- **G10, 회귀**: nfet_a를 고른 상태에서 Insert → `FakeInsertDialog` 가 nfet_a의 celltype으로 한 번 만들어지고, `get_data()` 가 돌려준 값이 행 하나로 들어간다(섹션이 dirty).
- **G12**: nfet_a 선택, 행이 있는 섹션에서 `sec.table_view.selectRow(0)` 후 `qtbot.keyClick(sec, Qt.Key_E, Qt.ControlModifier)`.
  - 기록된 `prefill` 이 그 행의 값 `{col: model.data(model.index(0, c)) for c, col in enumerate(sec.columns)}` 와 같고 `window_title == "Edit"`. **수정 전에는 `prefill == {}` 라 실패해야 한다.**
  - `get_data()` 가 `prefill` 을 그대로 돌려주면 행이 바뀌지 않고 섹션이 dirty가 아니다.
  - Edit 버튼(`sec.edit_btn.click()`)으로 연 것과 기록된 `prefill`·`window_title` 이 같다.
  - 선택이 없으면 Ctrl+E는 대화상자를 만들지 않는다(회귀).

### 2. 수정 (`views/tab_section.py`)

- `__init__` 에서 `self.device_id: int | None = None`, `self.device_celltype: str | None = None` 으로 시작한다.
- `open_insert_dialog()`: `self.device_id is None` 이면 대화상자를 만들지 않고 돌아간다. 버튼·Ctrl+I·메뉴(컨트롤러가 `ui.open_insert_dialog()` 를 부른다)가 모두 이 한 곳을 지나므로 여기만 고친다. device가 있으면 지금과 같다.
- `keyPressEvent` 의 Ctrl+E는 `self.edit_selected_row()` 를 부른다(Edit 버튼과 같은 경로). 선택이 없을 때 아무것도 안 하는 동작은 `edit_selected_row` 가 이미 한다.
- `open_edit_dialog`·`edit_selected_row`·`InsertDialog` 의 동작은 바꾸지 않는다.

### 3. 문서

- UI_GUIDE의 단축키 표(Ctrl+I / Ctrl+E)는 그대로 맞다. 바꿀 문서는 없다.

## Acceptance Criteria

```bash
uv run pytest tests/gui/test_tab_section_view.py -q   # 새 테스트 통과 (수정 전에는 접속 직후 Insert와 Ctrl+E prefill 테스트가 실패해야 한다)
uv run ruff check src tests
uv run pytest tests/gui -q
uv run pytest -q
```

## 검증 절차

1. 위 AC 커맨드를 실행한다.
2. 아키텍처 체크리스트를 확인한다:
   - `views/tab_section.py` 가 controllers·service를 import하지 않는가(레이어 표, 티어 3)?
   - 버튼·단축키·메뉴의 이름과 배치, 대화상자 문구가 그대로인가(ADR-015)?
3. 결과에 따라 `phases/4-gui-robustness/index.json` 의 step 1을 업데이트한다:
   - 성공 → `"status": "completed"`, `"summary": "TabSection: device_id/device_celltype None 으로 시작, device 없으면 Insert 무시, Ctrl+E 는 edit_selected_row. RED: <테스트 이름>. tests/gui/test_tab_section_view.py 추가"`
   - 재현 안 됨 → `"status": "completed"`, `"summary": "not reproduced: <이유>"`
   - 수정 3회 시도 후에도 실패 → `"status": "error"`, `"error_message": "구체적 에러 내용"`
   - 사용자 개입 필요 → `"status": "blocked"`, `"blocked_reason": "구체적 사유"` 후 즉시 중단

## 금지사항

- `InsertDialog` 가 `prefill` 이 비었을 때 다르게 동작하게 바꾸지 마라(예: 선택한 행을 스스로 읽기). 이유: 원인은 호출부의 빈 prefill이고, 대화상자는 Insert와 Edit이 함께 쓴다.
- device가 없을 때 Insert 버튼을 비활성화하거나 숨기거나, 안내 상자를 새로 띄우지 마라. 이유: 보이는 동작·문구가 바뀐다(ADR-015). "아무것도 하지 않음" 까지만 한다.
- `TabSectionController` 에 같은 검사를 중복으로 넣지 마라. 이유: 모든 Insert 경로가 `TabSection.open_insert_dialog` 를 지난다. 이 step은 `views/tab_section.py` 하나만 고친다.
- Ctrl+C / Ctrl+V / Ctrl+D / Delete 처리와 키 조합 판정(`event.modifiers() == Qt.ControlModifier`)을 바꾸지 마라. 이유: 이 step의 범위가 아니다.
- 진짜 `InsertDialog` 를 테스트에서 `exec` 하지 마라. 이유: 모달이 테스트를 멈춘다(CLAUDE.md 테스트 관례).
- 기존 테스트를 깨뜨리지 마라.
