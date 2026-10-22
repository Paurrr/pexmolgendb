# Step 0: add-window-completer

## 배경 (phase 20 공통)

이 저장소는 **에러·버그만 고친다**(CLAUDE.md, ADR-015). phase 20은 phase 19(process 버전, ADR-018) 마무리 리뷰에서 재현한 K56(`docs/notes/known-issues.md`)을 고친다. 사용자가 2026-10-22에 버그로 정하고 이 phase에서 고치기로 승인했다. 사용자에게 보이는 문구와 배치는 바꾸지 않는다.

**K56.** 편집 가능한 `QComboBox` 에는 Qt가 기본 completer(대소문자 무시, inline 완성)를 붙인다. 그래서 사용자가 친 글자가 앞부분이 같은 기존 항목으로 바뀐다.
- 추가 창(`+`, `dialogs/add_process.py`)의 Process 칸
  - `sf2p` 가 있을 때 `sf2` 를 치면 칸이 `sf2p` 가 된다(뒤의 `p` 가 선택된 채).
  - Version 칸으로 옮겨 OK를 누르면 `(sf2p, 버전)` 쌍이 만들어진다.
- Load CSV 버전 질문(`views/device_tab.py` `_ask_release`, `QInputDialog.getItem(editable=True)`)
  - `S00-V1.0.0.0` 이 있을 때 `S00-V1.0` 을 치면 `S00-V1.0.0.0` 으로 불러온다. 행이 기존 버전에 쌓인다.
- Enter도 같다.
  - 콤보는 Enter를 받으면 같은 글자의 항목을 찾아 그 항목으로 바꾼다. completer가 대소문자를 무시하면 이 찾기도 대소문자를 무시한다.
  - 예: `SF4U` + Enter → `sf4u`, `s00-v1.0.0.0` + Enter → `S00-V1.0.0.0`.
  - DB의 `UNIQUE (name, release)` 와 CLI는 대소문자를 구분하므로, 사용자가 친 것과 다른 쌍이 된다.

**고치는 방법.** 그 콤보의 completer를 끈다(`setCompleter(None)`).
- inline 완성이 없어진다.
- Qt `QComboBoxPrivate::matchFlags` 는 completer가 없으면 `Qt::MatchCaseSensitive` 를 쓴다. 그래서 Enter도 대소문자까지 같은 항목만 고른다.
- 목록에서 고르기(▾, 위·아래 키)는 그대로다.

**확인한 사실** (2026-10-22, 개발 PC, offscreen, PySide6 6.9.3)
- 포커스가 없는 칸에 키를 치면 completer가 돌지 않는다. 그런 테스트는 **수정 전에도 통과하므로 버그를 증명하지 못한다.**
- 다음 순서로 치면 재현된다. 모달 `exec` 가 없어도 된다.
  1. 창 `show()` → `activateWindow()` → `qtbot.waitUntil(window.isActiveWindow)`
  2. 칸 `setFocus()` → `qtbot.waitUntil(line_edit.hasFocus)`
  3. `qtbot.keyClick` 으로 한 글자씩 친다.
- 같은 순서로 completer를 끈 칸에 치면 글자가 그대로다(`sf2`, `SF4U`, `S00-V1.0`, `s00-v1.0.0.0`).

이 phase의 step:
- step 0 `add-window-completer`: 추가 창 Process 칸 ← 이 step
- step 1 `load-csv-completer`: Load CSV 버전 질문

모든 step에 같은 규칙이 적용된다.
1. 버그는 **주장**이다. 먼저 실패하는 테스트로 재현하고, RED 출력(테스트 이름과 실패한 단언)을 summary에 적는다.
2. RED는 **Windows 개발 PC에서** 보여야 한다.
3. 재현되지 않으면 `src/` 를 고치지 않는다. 테스트는 특성 테스트로 남기고 `"status": "completed"`, `"summary": "not reproduced: <이유>"` 로 끝낸다.
4. 고친 뒤 변이 검사를 한다.
   - completer를 끄는 줄을 손으로 지워 새 테스트가 실패하는지 확인하고 다시 고친다.
   - `git checkout`/`git stash` 로 되돌리지 마라.
5. 이 파일의 행 번호는 2026-10-22(phase 19 직후) 기준 대략값이다. 이름으로 찾아라.
6. 다음은 바꾸지 않는다.
   - 문구: 창 제목, 라벨, 창 안의 이유 줄
   - OK를 끄는 규칙
   - 값 다듬기(`strip`)와 반환 규칙
7. 문서(README "process 버전" 절의 K56 문단, known-issues K56)는 phase 마무리에서 고친다. step에서는 바꾸지 않는다.
8. 셀 값 콤보(`delegates/combo_box.py`, `dialogs/insert.py` 의 편집 가능 콤보)는 범위 밖이다. 건드리지 마라. 이유: phase 19 전부터 있던 값 입력 보조이고, K56 승인 범위가 아니다.

**GUI 테스트 기반**
- 작업 전에 `tests/gui/conftest.py` 와 `tests/gui_support/` 를 읽는다. 이 파일의 서술과 다르면 실제 코드를 따른다.
- autouse `dialogs` fixture가 막는 것: `QDialog.exec`/`exec_`(서브클래스 인스턴스 포함)와 `QInputDialog.getText`·`getItem` 등 정적 함수. 부르면 `AssertionError` 다.
- 고정 대기(`qtbot.wait`)는 쓰지 않는다. `waitUntil` 콜백은 bool을 돌려준다.

## 읽어야 할 파일

- `/CLAUDE.md`
- `/docs/UI_GUIDE.md`: "입력과 단축키"의 Add Process 줄
- `/docs/ADR.md`: ADR-018
- `src/genviewer/dialogs/add_process.py`
  - `name_box`(~36-39), `values`(~70), `_update`(~81)
- `src/genviewer/views/device_tab_toolbar.py`: `_ask_add_pair`(~158-166). 읽기만 한다.
- `tests/gui/test_add_process_dialog.py`
  - 기존 단위 테스트다.
  - `fill` 은 `setEditText` 로 넣으므로 completer를 거치지 않는다. 그래서 이 버그를 못 봤다.
- `tests/gui/test_add_release.py`: `AddProcessDialog.exec` 대역(~480-530)
- `tests/gui_support/dialogs.py`
- `tests/gui_support/helpers.py`: 사용자 동작 헬퍼는 기다리지 않는다는 규칙이 있다.

## 버그

```python
self.name_box = QComboBox()
self.name_box.setEditable(True)          # Qt 가 대소문자 무시 inline completer 를 붙인다
self.name_box.addItems(list(dict.fromkeys(n for n, _ in self._pairs)))
self.name_box.setCurrentIndex(self.name_box.findText(current[0]))
```

pairs가 `[("sf2p",""), ("sf4u","")]`, Version 칸이 `V9` 인 창에서 확인한 결과다(2026-10-22).

| 친 것 | 지금 `values()` | 기대 |
|---|---|---|
| `sf2` | `('sf2p', 'V9', None)` | `('sf2', 'V9', None)` |
| `SF4U` + Enter (창이 Accepted) | `('sf4u', 'V9', None)` | `('SF4U', 'V9', None)` |

이것은 주장이다. 먼저 재현하라.

## 작업

### 1. 테스트 지원 (`tests/gui_support/keys.py`, 새 파일)

`type_into(qtbot, line_edit: QLineEdit, text: str) -> None`
- 할 일, 순서대로:
  1. `line_edit.window()` 가 보이지 않으면 `show()` 한다.
  2. `activateWindow()` 하고 `qtbot.waitUntil(window.isActiveWindow)` 로 활성화를 기다린다.
  3. `line_edit.setFocus()` 하고 `qtbot.waitUntil(line_edit.hasFocus)` 로 포커스를 기다린다.
  4. 있던 글자를 모두 지운다(`selectAll` + `Key_Delete`).
  5. `text` 를 `qtbot.keyClick` 으로 한 글자씩 친다.
- 활성화나 포커스를 얻지 못하면 `waitUntil` 의 timeout으로 실패해야 한다. 조용히 넘어가지 마라. 이유: 포커스 없이 치면 수정 전에도 통과한다.
- docstring에 왜 기다리는지 적는다.
  - 포커스가 없으면 completer가 돌지 않아 버그가 숨는다.
  - `helpers.py` 의 "기다리지 않는다" 규칙의 예외인 이유: 결과가 아니라 전제를 기다린다.
- step 1도 이 함수를 쓴다.

### 2. 실패하는 테스트 (`tests/gui/test_add_process_dialog.py` 에 더한다)

창은 `AddProcessDialog([("sf2p",""), ("sf4u","")], ("sf2p",""))` 이고 `qtbot.addWidget` 한다. 모달 `exec` 는 쓰지 않는다. `show` 로 재현되고, 답하지 않은 `exec` 는 dialogs fixture가 막는다.

**앞부분이 같은 이름** (수정 전에 실패해야 한다)
- 준비: Version 칸에 `V9` 을 넣는다.
- 동작: `type_into(qtbot, dialog.name_box.lineEdit(), "sf2")`.
- 단언:
  - 칸 글자가 `"sf2"` 다.
  - `values() == ("sf2", "V9", None)` 다.
  - OK가 켜져 있다.

**대소문자만 다른 이름 + Enter** (수정 전에 실패해야 한다)
- 준비: Version 칸에 `V9` 을 넣는다.
- 동작: `SF4U` 를 치고 `qtbot.keyClick(line_edit, Qt.Key_Return)`.
- 단언:
  - `dialog.result() == QDialog.Accepted` 다. Enter가 OK(기본 버튼)를 누른다.
  - `values() == ("SF4U", "V9", None)` 다.

**회귀** (수정 전에도 통과)
- 있는 이름을 그대로 친 `sf4u` + Enter → `("sf4u", "V9", None)`, Accepted.
- `name_box.setCurrentIndex(1)` 로 목록에서 고르면 `values()[0] == "sf4u"`.

### 3. 수정 (`dialogs/add_process.py`)

- `name_box` 의 completer를 끈다(`self.name_box.setCompleter(None)`).
  - `setEditable(True)` 뒤에 둔다. 편집 가능으로 바꿀 때 Qt가 line edit와 기본 completer를 만든다.
  - 이유를 한국어 주석 한 줄로 적는다.
- 다른 것은 바꾸지 않는다: 항목, 시작 자리, `insertPolicy`, OK 규칙, 이유 줄, `values`, `Copy from` 콤보(편집 불가).

### 4. 변이 검사

- `setCompleter(None)` 줄을 지우고 새 RED 테스트 두 개가 실패하는지 본다. 다시 넣는다.

## Acceptance Criteria

```bash
uv run pytest tests/gui/test_add_process_dialog.py tests/gui/test_add_release.py -q
uv run pytest tests/gui -q
uv run ruff check src tests
uv run pytest -q
```

## 검증 절차

1. 위 AC 커맨드를 실행한다.
2. 아키텍처 체크리스트를 확인한다.
   - 추가 창의 문구, OK 규칙, 시작 상태가 그대로인가? 기존 `test_add_process_dialog.py`·`test_add_release.py` 가 바뀌지 않고 통과하는가?
   - `_ask_release`(step 1 몫), `delegates/combo_box.py`, `dialogs/insert.py` 를 건드리지 않았는가?
3. 결과에 따라 `phases/20-combo-autocomplete/index.json` 의 step 0을 업데이트한다.
   - 성공 → `"status": "completed"`, `"summary": "add_process.name_box.setCompleter(None). tests/gui_support/keys.type_into(qtbot, line_edit, text)(창 활성화·포커스를 기다린 뒤 한 글자씩 친다, step 1 도 씀). RED: <테스트 이름: 단언>. 변이: <결과>"`
   - 재현 안 됨 → `"status": "completed"`, `"summary": "not reproduced: <이유>"`
   - 수정 3회 시도 후에도 실패 → `"status": "error"`, `"error_message": "구체적 에러 내용"`
   - 사용자 개입 필요 → `"status": "blocked"`, `"blocked_reason": "구체적 사유"` 후 즉시 중단

## 금지사항

- `delegates/combo_box.py`·`dialogs/insert.py` 의 콤보를 바꾸지 마라. 이유: 범위 밖이다(셀 값 입력 보조, K56 승인 범위가 아니다).
- `insertPolicy`·`setDuplicatesEnabled` 등 다른 콤보 속성을 바꾸지 마라. 이유: Enter 때 목록에 없는 이름이 목록 끝에 더해지는 것은 phase 19 전부터의 동작이다. 창이 닫히면 사라진다.
- Process 칸을 `QLineEdit` 로 바꾸지 마라. 이유: 목록에서 이름을 고르는 동작이 그대로여야 한다.
- 문구와 OK 규칙을 바꾸지 마라.
- `views/device_tab.py` 의 `_ask_release` 를 바꾸지 마라. 이유: step 1이 재현부터 한다.
- 이 step에서 진짜 모달 `exec` 를 기다리는 테스트를 만들지 마라. 이유: `show` 로 재현된다. 모달은 단언이 실패하면 닫히지 않아 테스트가 멈출 수 있다.
- `tests/gui_support/dialogs.py`(autouse 막기)를 바꾸지 마라. 이유: 모든 GUI 테스트의 안전장치다.
- 기존 테스트를 깨뜨리지 마라.
