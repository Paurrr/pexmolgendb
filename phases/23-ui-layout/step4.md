# Step 4: menus

## 배경

이 저장소는 **에러·버그만 고친다**(CLAUDE.md, ADR-015). 이 step은 사용자가 2026-10-22에 승인한 사용성 변경이다("메뉴 보강", AskUserQuestion).

**문제**
- 메뉴 줄에는 `Database(Connect... / Save / Load CSV)` 하나뿐이다.
- Undo·Redo는 단축키로만 있다. 숨은 창 동작이라 아무 메뉴에도 보이지 않는다.
- 내보내기는 Device Info 표의 오른쪽 클릭 메뉴(Export CSV / Export XLSX)에만 있다.
- `Load CSV` 는 대화상자를 여는데도 `...` 가 없다.

**승인된 동작.** 메뉴 줄은 `Database | Edit | View` 다. View는 step 1이 만들었다.

```
Database                       Edit                 View
├ Connect...                   ├ Undo   Ctrl+Z      └ ☑ Dark Theme   (step 1)
├ ─────                        └ Redo   Ctrl+Y (Linux Ctrl+Shift+Z)
├ Save
├ ─────
├ Load CSV...
└ Export Selected Devices...
```

- `Load CSV` → `Load CSV...` 로 글자만 바꾼다. 동작은 그대로 `device_tab_view._ask_load_csv` 다.
- `Export Selected Devices...` 는 오른쪽 클릭 Export와 같은 함수 `DeviceTableController.export_selected_devices("csv")` 를 부른다.
  - 저장 창은 지금처럼 CSV/XLSX 둘 다 고를 수 있다. 형식은 고른 파일의 확장자를 따른다.
  - 고른 device가 없으면 지금처럼 `Export` / `No device selected.` 경고다.
- Edit 메뉴에는 `_setup_actions` 가 이미 만드는 창 동작 `act_undo`·`act_redo`(`QKeySequence.Undo`/`.Redo`)를 **그대로** 넣는다.
  - 새 QAction을 만들지 않는다. 같은 동작이 단축키와 메뉴 양쪽을 맡는다.
  - 동작은 지금처럼 포커스를 따른다. device 표면 device 표, 탭이면 그 탭, 아니면 "Nothing to undo"/"Nothing to redo".
  - 메뉴를 열어도 창의 `focusWidget()` 은 바뀌지 않는다. 그래도 메뉴에서 눌러도 포커스 쪽을 되돌리는지 테스트로 본다.
- Database 메뉴의 `Save` 에는 단축키를 **표시하지 않는다**.
  - 이유: 메뉴 Save는 device 표와 탭을 전부 저장한다(`save_db`). Ctrl+S는 포커스에 따라 저장 범위가 다르다(UI_GUIDE "입력과 단축키").
  - Ctrl+S 창 동작(`act_save`)은 지금처럼 메뉴 밖에 둔다.

규칙:
1. 승인된 변경이라 RED 대신 변이 검사를 한다. Export 메뉴 연결을 손으로 끊으면 새 테스트가 실패해야 한다. `git checkout`/`git stash` 로 되돌리지 마라.
2. 행 번호는 2026-10-22 기준 대략값이다. step 1이 같은 `_setup_actions` 에 View 메뉴를 더했다. 그 코드를 먼저 읽어라.
3. 문서(UI_GUIDE "레이아웃" 의 메뉴 줄, README의 메뉴 이름)는 phase 마무리에서 고친다.

## 읽어야 할 파일

- `/CLAUDE.md`, `/docs/UI_GUIDE.md`: "레이아웃", "입력과 단축키"
- `src/genviewer/controllers/main_window.py`: `_setup_actions`(step 1이 View 메뉴를 더했다), `_on_undo_triggered`, `_on_redo_triggered`, `_on_save_triggered`
- `src/genviewer/controllers/device_table.py`: `export_selected_devices`(~517-557), `_on_context_menu`
- `src/genviewer/views/device_table.py`: `_ask_export_path`
- `tests/gui/test_save_entry_points.py`: `database_save_action`(~29-35). Database 메뉴의 `Save` 하나를 찾는다. 그대로 통과해야 한다.
- `tests/gui/test_export_format.py`: `ui._ask_export_path` 를 바꿔 끼우는 방식(~25)
- `tests/gui/test_main_toolbar.py`: step 1의 View 메뉴 테스트
- `tests/gui_support/helpers.py`: `select_process`, `select_device_row`, `edit_device_cell`

## 작업

### 1. 테스트 (새 파일 `tests/gui/test_menus.py`, `main_window` fixture)

- `test_menu_bar_order`: 메뉴 줄 제목 순서가 `["Database", "Edit", "View"]` 다(`menubar.actions()` 의 `menu()` 제목).
- `test_database_menu_items`: 구분선을 뺀 글자 순서가 `["Connect...", "Save", "Load CSV...", "Export Selected Devices..."]` 다. 구분선 위치는 `Connect...` 뒤와 `Save` 뒤다.
- `test_save_menu_item_shows_no_shortcut`: Database 메뉴 `Save` 의 `shortcut().isEmpty()` 다.
- `test_export_menu_exports_selected_devices`
  - sf2p를 고르고 device 한 행을 고른다.
  - `ui._ask_export_path` 를 `tmp_path / "out.csv"` 를 돌려주는 함수로 바꾼다(`test_export_format.py` 방식).
  - 메뉴 동작을 `trigger()` 하면 파일이 생기고 `("info", "Save CSV", ...)` 알림이 뜬다.
- `test_export_menu_without_selection_warns`: 선택이 없으면 `("warning", "Export", "No device selected.")` 이고 파일 창을 열지 않는다.
- `test_edit_menu_holds_the_window_undo_redo`
  - Edit 메뉴의 두 동작이 창 동작과 **같은 객체**다(`ui.actions()` 에 있는 것).
  - 단축키는 `QKeySequence.Undo`/`QKeySequence.Redo` 다.
- `test_edit_menu_undo_reverts_the_focused_device_table`
  - device 셀을 고친다(`edit_device_cell`). device 표에 포커스를 준다(`ui.show()`, `qtbot.waitExposed`, `setFocus`, 포커스를 기다린다).
  - Edit → Undo를 `trigger()` 하면 그 편집이 되돌아간다.
- `test_load_csv_menu_text`: `Load CSV...` 동작이 있고, 누르면 `device_tab_view._ask_load_csv` 를 부른다. 그 함수를 기록용 대역으로 바꿔 본다.

### 2. 수정 (`controllers/main_window.py` `_setup_actions`)

- Database 메뉴
  - `Load CSV` 글자를 `Load CSV...` 로 바꾼다.
  - 그 뒤에 `Export Selected Devices...` 를 둔다. `self.device_tab.device_table.export_selected_devices("csv")` 를 부른다. `triggered(bool)` 인자가 fmt로 들어가지 않게 lambda로 감싼다.
- Database와 View 사이에 Edit 메뉴를 만들고, 이미 만든 `act_undo`, `act_redo` 를 넣는다(`addAction`). `self.ui.addAction(...)` 은 그대로 둔다. 메뉴가 닫혀 있어도 단축키가 돌아야 한다.
- 메뉴 줄의 순서가 Database, Edit, View가 되게 만든다.

## Acceptance Criteria

```bash
uv run pytest tests/gui/test_menus.py tests/gui/test_save_entry_points.py tests/gui/test_main_toolbar.py tests/gui/test_export_format.py -q
uv run pytest tests/gui -q
uv run ruff check src tests
uv run pytest -q
```

## 검증 절차

1. 위 AC 커맨드를 실행한다.
2. 아키텍처 체크리스트를 확인한다.
   - Ctrl+S·Ctrl+Z·Ctrl+Y의 동작이 그대로인가(포커스별)? `test_save_entry_points.py` 가 바뀌지 않고 통과하는가?
   - 오른쪽 클릭 Export CSV / Export XLSX가 그대로인가?
   - 메뉴 동작이 새 DB 호출 경로를 만들지 않는가? Export는 기존 함수를 부를 뿐이다.
3. 결과에 따라 `phases/23-ui-layout/index.json` 의 step 4를 업데이트한다.
   - 성공 → `"status": "completed"`, `"summary": "메뉴 줄 Database|Edit|View. Database: Load CSV..., Export Selected Devices...(export_selected_devices('csv')). Edit: 기존 act_undo/act_redo. Save 단축키 표시 없음. tests/gui/test_menus.py. 변이: <결과>"`
   - 수정 3회 시도 후에도 실패 → `"status": "error"`, `"error_message": "구체적 에러 내용"`
   - 사용자 개입 필요 → `"status": "blocked"`, `"blocked_reason": "구체적 사유"` 후 즉시 중단

## 금지사항

- Database 메뉴 `Save` 에 단축키를 붙이거나 `act_save` 를 메뉴에 넣지 마라. 이유: 같은 글자의 두 동작이 다른 범위를 저장하게 된다. 메뉴 Save를 찾는 테스트도 깨진다.
- Ctrl+S의 포커스별 저장을 바꾸지 마라. 이유: UI_GUIDE에 적힌 설계이고 사용자가 바꾸지 않기로 했다.
- Insert·Delete·Copy·Paste 같은 표 동작을 Edit 메뉴에 더하지 마라. 이유: 사용자가 고른 것은 Undo/Redo다. 표마다 활성 조건이 달라 범위가 커진다.
- 메뉴 동작의 활성/비활성 조건을 새로 만들지 마라. 이유: 지금 메뉴는 늘 켜져 있고, 각 함수가 안 될 때 스스로 알린다.
- 오른쪽 클릭 메뉴의 글자를 바꾸지 마라. 이유: 범위 밖이다.
- 새 문구는 영어로 쓴다.
- 건드리는 파일의 기존 한국어 문구를 번역하지 마라. 이유: phase 24(영어화)의 몫이다.
- 기존 테스트를 깨뜨리지 마라.
