# Step 0: edit-dialog-title

## 배경

이 저장소는 **에러·버그만 고친다**(CLAUDE.md, ADR-015). phase 23은 사용자가 2026-10-22에 승인한 사용성 정리다. 이 step은 그 조사 중에 찾은 버그 하나를 고친다.

**버그 (주장)**
- device 표(Device Info)의 Edit 창 제목이 "Insert" 로 뜬다.
- `views/device_table.py` `DeviceTableView.open_edit_dialog` 가 `InsertDialog(...)` 에 `window_title` 을 넘기지 않는다. 그래서 기본값 `"Insert"` 가 쓰인다.
- 탭 표는 맞게 넘긴다(`views/tab_section.py` `open_edit_dialog` 의 `window_title="Edit"`).

**기대 동작**: device 표의 Edit 창 제목은 `"Edit"` 다(탭 표와 같다). Insert 창은 그대로 `"Insert"` 다.

규칙:
1. 버그는 **주장**이다. 먼저 실패하는 테스트로 재현하고, RED 출력(테스트 이름과 실패한 단언)을 summary에 적는다. RED는 Windows 개발 PC에서 보여야 한다.
2. 재현되지 않으면 `src/` 를 고치지 않는다. `"status": "completed"`, `"summary": "not reproduced: <이유>"` 로 끝낸다.
3. 고친 뒤 인자를 손으로 빼서 테스트가 실패하는지 본다(변이 검사). `git checkout`/`git stash` 로 되돌리지 마라.
4. 행 번호는 2026-10-22 기준 대략값이다.

## 읽어야 할 파일

- `/CLAUDE.md`, `/docs/UI_GUIDE.md`
- `src/genviewer/views/device_table.py`: `open_insert_dialog`, `open_edit_dialog`(~128-151)
- `src/genviewer/views/tab_section.py`: `open_edit_dialog`(~116-126). 참고만 한다.
- `src/genviewer/dialogs/insert.py`: `InsertDialog.__init__` 의 `window_title="Insert"`
- `tests/gui/test_tab_section_view.py`: `FakeInsertDialog` 와 `insert_dialog` fixture(~34-79). 진짜 모달을 띄우지 않고 생성 인자를 기록하는 방식이다.
- `tests/gui/conftest.py`, `tests/gui_support/helpers.py`(`select_process`, `select_device_row`)

## 작업

### 1. 실패하는 테스트 (새 파일 `tests/gui/test_device_edit_dialog.py`)

- `test_tab_section_view.py` 의 `FakeInsertDialog` 와 같은 방식의 대역을 **이 파일 안에** 둔다. 다른 테스트 모듈은 import하지 않는다(CLAUDE.md 테스트 관례).
- 대역은 `genviewer.views.device_table.InsertDialog` 자리에 monkeypatch한다.
- `device_tab_ctrl` fixture로 sf2p를 고르고 device 한 행을 고른다.
- 테스트(앞의 것은 수정 전에 실패해야 한다):
  - `test_device_edit_dialog_is_titled_edit`: device 표 view의 `open_edit_dialog(0)` 이 만든 대화상자의 `window_title` 이 `"Edit"` 이고, `prefill` 이 그 행 값이다.
  - `test_device_insert_dialog_stays_titled_insert`: `open_insert_dialog()` 는 `"Insert"` 다.

### 2. 수정 (`views/device_table.py`)

- `open_edit_dialog` 의 `InsertDialog(...)` 호출에 `window_title="Edit"` 를 넘긴다. 탭 표처럼 `prefill=old_values` 도 키워드로 넘겨도 된다. 다른 것은 바꾸지 않는다.

## Acceptance Criteria

```bash
uv run pytest tests/gui/test_device_edit_dialog.py -q
uv run pytest tests/gui -q
uv run ruff check src tests
uv run pytest -q
```

## 검증 절차

1. 위 AC 커맨드를 실행한다.
2. 아키텍처 체크리스트를 확인한다.
   - 바꾼 `src` 가 `open_edit_dialog` 의 호출 인자뿐인가?
3. 결과에 따라 `phases/23-ui-layout/index.json` 의 step 0을 업데이트한다.
   - 성공 → `"status": "completed"`, `"summary": "device 표 Edit 창 제목 Insert→Edit(views/device_table.open_edit_dialog). tests/gui/test_device_edit_dialog.py. RED: <테스트 이름: 단언>. 변이: <결과>"`
   - 재현 안 됨 → `"status": "completed"`, `"summary": "not reproduced: <이유>"`
   - 수정 3회 시도 후에도 실패 → `"status": "error"`, `"error_message": "구체적 에러 내용"`
   - 사용자 개입 필요 → `"status": "blocked"`, `"blocked_reason": "구체적 사유"` 후 즉시 중단

## 금지사항

- `InsertDialog` 의 기본값(`window_title="Insert"`)을 바꾸지 마라. 이유: Insert 창은 그 기본값을 쓴다.
- 버튼·메뉴 이름(`Insert`·`Insert Row`, `Clear Sel`·`Clear Selection`)을 통일하지 마라. 이유: 사용자가 하지 않기로 했다.
- 건드리는 파일의 기존 한국어 문구를 번역하지 마라. 이유: phase 24(영어화)의 몫이다.
- 기존 테스트를 깨뜨리지 마라.
