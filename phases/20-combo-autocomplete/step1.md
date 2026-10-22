# Step 1: load-csv-completer

## 배경 (phase 20 공통)

이 저장소는 **에러·버그만 고친다**(CLAUDE.md, ADR-015). phase 20은 phase 19(process 버전, ADR-018) 마무리 리뷰에서 재현한 K56(`docs/notes/known-issues.md`)을 고친다. 사용자가 2026-10-22에 버그로 정하고 이 phase에서 고치기로 승인했다. 사용자에게 보이는 문구와 배치는 바꾸지 않는다.

**K56.** 편집 가능한 `QComboBox` 에는 Qt가 기본 completer(대소문자 무시, inline 완성)를 붙인다. 그래서 사용자가 친 글자가 앞부분이 같은 기존 항목으로 바뀐다.
- 추가 창(`+`, `dialogs/add_process.py`)의 Process 칸
  - `sf2p` 가 있을 때 `sf2` 를 치면 `(sf2p, 버전)` 쌍이 만들어진다.
  - step 0이 고친다.
- Load CSV 버전 질문(`views/device_tab.py` `_ask_release`, `QInputDialog.getItem(editable=True)`)
  - `S00-V1.0.0.0` 이 있을 때 `S00-V1.0` 을 치면 `S00-V1.0.0.0` 으로 불러온다. 행이 기존 버전에 쌓인다.
- Enter도 같다.
  - 콤보는 Enter를 받으면 같은 글자의 항목을 찾아 그 항목으로 바꾼다. completer가 대소문자를 무시하면 이 찾기도 대소문자를 무시한다.
  - 예: `s00-v1.0.0.0` + Enter → `S00-V1.0.0.0`.
  - DB의 `UNIQUE (name, release)` 와 CLI는 대소문자를 구분하므로, 사용자가 친 것과 다른 버전이 된다.

**고치는 방법.** 그 콤보의 completer를 끈다(`setCompleter(None)`).
- inline 완성이 없어진다.
- Qt `QComboBoxPrivate::matchFlags` 는 completer가 없으면 `Qt::MatchCaseSensitive` 를 쓴다. 그래서 Enter도 대소문자까지 같은 항목만 고른다.
- 목록에서 고르기(▾, 위·아래 키)는 그대로다.

**확인한 사실** (2026-10-22, 개발 PC, offscreen, PySide6 6.9.3)
- 포커스가 없는 칸에 키를 치면 completer가 돌지 않는다. 그런 테스트는 수정 전에도 통과한다.
- 창을 활성화하고 칸에 포커스가 간 것을 기다린 뒤 쳐야 재현된다. step 0의 `type_into` 가 그렇게 한다.
- 정적 `QInputDialog.getItem` 은 C++ 안에서 창을 만들고 `exec` 를 부른다. Python에서 `QInputDialog.exec` 를 바꿔도 닿지 않는다. 그래서 지금 코드의 RED는 **진짜 모달**로만 볼 수 있다. 아래 순서로 지금 코드에서 `'S00-V1.0.0.0'` 이 나오는 것을 확인했다.
  1. 모듈 import 때 진짜 `QInputDialog.getItem` 과 `QDialog.exec` 를 잡아 둔다.
  2. 테스트 안에서 `monkeypatch.setattr` 로 둘을 되돌린다. 잡은 것을 그대로 넣으면 된다.
  3. `QTimer.singleShot(0, drive)` 를 걸고 `_ask_release()` 를 부른다.
  4. `drive` 는 모달 루프 안에서 돈다. 보이는 `QInputDialog` 를 찾아 활성화와 포커스를 기다린 뒤 친다.
  5. `finally` 에서 창을 `accept()` 로 닫는다.
- 고친 `_ask_release` 처럼 `QInputDialog` 인스턴스를 만들어 콤보의 completer를 끄면, 같은 절차에서 친 글자가 그대로 나온다(`S00-V1.0`, `s00-v1.0.0.0`).
- 부모 view가 보이지 않아도 `QInputDialog(view)` 는 활성화된다.

이 phase의 step:
- step 0 `add-window-completer`: 추가 창 Process 칸
- step 1 `load-csv-completer`: Load CSV 버전 질문 ← 이 step

모든 step에 같은 규칙이 적용된다.
1. 버그는 **주장**이다. 먼저 실패하는 테스트로 재현하고, RED 출력(테스트 이름과 실패한 단언)을 summary에 적는다.
2. RED는 **Windows 개발 PC에서** 보여야 한다.
3. 재현되지 않으면 `src/` 를 고치지 않는다. 테스트는 특성 테스트로 남기고 `"status": "completed"`, `"summary": "not reproduced: <이유>"` 로 끝낸다.
4. 고친 뒤 변이 검사를 한다.
   - completer를 끄는 줄을 손으로 지워 새 테스트가 실패하는지 확인하고 다시 고친다.
   - `git checkout`/`git stash` 로 되돌리지 마라.
5. 이 파일의 행 번호는 2026-10-22(phase 19 직후) 기준 대략값이다. 이름으로 찾아라.
6. 다음은 바꾸지 않는다.
   - 문구: 창 제목, 라벨
   - 후보 목록과 처음 자리
   - 값 다듬기(`strip`)와 반환 규칙
7. 문서(README "process 버전" 절의 K56 문단, known-issues K56)는 phase 마무리에서 고친다. step에서는 바꾸지 않는다.
8. 셀 값 콤보(`delegates/combo_box.py`, `dialogs/insert.py` 의 편집 가능 콤보)는 범위 밖이다. 건드리지 마라. 이유: phase 19 전부터 있던 값 입력 보조이고, K56 승인 범위가 아니다.

**GUI 테스트 기반**
- 작업 전에 `tests/gui/conftest.py` 와 `tests/gui_support/` 를 읽는다. 이 파일의 서술과 다르면 실제 코드를 따른다.
- autouse `dialogs` fixture가 막는 것: `QDialog.exec`/`exec_`(서브클래스 인스턴스 포함, `QInputDialog` 도)와 `QInputDialog.getText`·`getItem` 등 정적 함수. 부르면 `AssertionError` 다.
- 테스트 안에서 `monkeypatch.setattr` 로 바꾼 것이 fixture가 바꾼 것을 이긴다.
- 고정 대기(`qtbot.wait`)는 쓰지 않는다. `waitUntil` 콜백은 bool을 돌려준다.

## 선행 step

- step 0이 만든 `tests/gui_support/keys.py` 의 `type_into(qtbot, line_edit, text)`. 창을 활성화하고 포커스를 기다린 뒤 한 글자씩 친다.
- `phases/20-combo-autocomplete/index.json` 의 step 0 summary를 읽어라.

## 읽어야 할 파일

- `/CLAUDE.md`
- `/docs/UI_GUIDE.md`: "입력과 단축키"의 Load CSV 줄
- `/docs/ADR.md`: ADR-018
- `src/genviewer/views/device_tab.py`
  - import(~1-13), `_ask_load_csv`(~139), `_ask_release`(~153-174)
- `src/genviewer/views/device_tab_toolbar.py`
  - `_ask_add_pair`(~158-166): 대화상자를 만들고 `exec`, `finally` 에서 `deleteLater` 하는 모양이다.
  - `pairs`, `current_pair`, `set_pairs`
- `tests/gui/test_load_csv_release.py`
  - `three_releases`(~181), `answer_get_item`(~193-205)
  - 이 대역을 쓰는 테스트 세 개(~208-273)
- `tests/gui/test_add_release.py`: `test_the_plus_button_opens_the_add_process_window`(~520). fixture가 답하지 않은 `exec` 를 막는지 보는 본보기다.
- `tests/gui/test_dialogs_fixture.py`: `test_file_and_input_dialogs_raise`. 바꾸지 않는다.
- `tests/gui_support/dialogs.py`, `tests/gui_support/keys.py`

## 버그

```python
text, ok = QInputDialog.getItem(
    self,
    "Load CSV",
    "불러올 버전 (비우면 버전 없음):",
    items,
    releases.index(current) if current in releases else 0,
    editable=True,
)
```

툴바 쌍이 `("sf2p","")`, `("sf2p","S00-V1.0.0.0")` 일 때 확인한 결과다(2026-10-22, 진짜 모달).

| 친 것 | 지금 `_ask_release()` | 기대 |
|---|---|---|
| `S00-V1.0` 후 OK | `'S00-V1.0.0.0'` | `'S00-V1.0'` |
| `s00-v1.0.0.0` + Enter | `'S00-V1.0.0.0'` | `'s00-v1.0.0.0'` |

이것은 주장이다. 먼저 재현하라.

## 작업

### 1. 실패하는 테스트 (`tests/gui/test_load_csv_release.py`, 진짜 모달)

위 "확인한 사실"의 절차를 쓴다.

**준비**
- 버전 목록은 다음 중 하나로 만든다. 실제 코드를 보고 고른다.
  - `DeviceTab()` 을 직접 만들고 `device_tab_toolbar_view.set_pairs([("sf2p",""), ("sf2p","S00-V1.0.0.0")])`
  - `device_tab_ctrl` + `store.add_process("sf2p", release="S00-V1.0.0.0")` + `refresh_processes()`
- 진짜 `getItem`·`exec` 는 테스트 모듈의 import 때 잡는다. 이유: autouse dialogs fixture가 테스트마다 둘을 막는다.
- 잡은 것이 fixture의 가짜가 아닌지 단언한다(예: `__module__` 이 `gui_support.dialogs` 가 아니다).

**`drive` 규칙**
- 보이는 `QInputDialog` 를 view의 자식에서 찾는다.
- 그 콤보(`findChild(QComboBox)`)의 line edit에 `type_into` 로 친다.
- 단언하지 말고 값을 기록만 한다.
- **`finally` 에서 떠 있는 모달을 반드시 닫는다**(`QApplication.activeModalWidget()` 또는 찾은 창을 `accept()`, 이미 닫혔으면 건너뛴다). 이유: `drive` 안에서 예외가 나면 모달이 닫히지 않아 테스트가 멈춘다.
- 단언은 `_ask_release()` 가 돌아온 뒤에 한다.
- 이 모양이 둘 이상 쓰이면 테스트 파일 안의 작은 함수로 묶는다.

**앞부분이 같은 버전** (수정 전에 실패해야 한다)
- `S00-V1.0` 을 치고 닫는다(`accept`).
- 단언: `_ask_release() == "S00-V1.0"`.

**대소문자만 다른 버전 + Enter** (수정 전에 실패해야 한다)
- `s00-v1.0.0.0` 을 치고 `Key_Return` 을 누른다. Enter가 창을 닫는다.
- 단언: `_ask_release() == "s00-v1.0.0.0"`.

**회귀** (수정 전에도 통과)
- 목록에 있는 `S00-V1.0.0.0` 을 그대로 치고 Enter → `"S00-V1.0.0.0"`.

이 진짜 모달 테스트는 고친 뒤에도 그대로 통과해야 한다. 고친 코드는 `QInputDialog` 인스턴스의 `exec` 를 부르는데, 테스트가 진짜 `QDialog.exec` 를 되돌려 두었기 때문이다.

### 2. 수정 (`views/device_tab.py` `_ask_release`)

창을 만든다.
- 정적 `getItem` 대신 `QInputDialog(self)` 를 만든다.
- Qt `getItem` 과 같은 순서로 채운다.
  1. `setWindowTitle("Load CSV")`
  2. `setLabelText("불러올 버전 (비우면 버전 없음):")`
  3. `setComboBoxItems(items)`
  4. `setTextValue(처음 글자)`
  5. `setComboBoxEditable(True)`
- 처음 글자는 지금과 같은 자리(`releases.index(current) if current in releases else 0`)의 항목이다. 항목이 없으면 `""` 다. Qt `getItem` 의 `items.value(current)` 와 같다.
  - **쌍이 하나도 없을 때(새 DB)도 지금처럼 묻는다. `IndexError` 를 내지 마라.**
  - 항목이 없으면 Qt는 콤보 대신 line edit를 보인다. 지금과 같다.

completer를 끈다.
- 콤보(`findChild(QComboBox)`)의 completer를 끈다(`setCompleter(None)`).
- `setComboBoxEditable(True)` **뒤에** 끈다. 편집 가능으로 바꿀 때 Qt가 기본 completer를 붙인다.
- 이유를 한국어 주석 한 줄로 적는다.

결과를 돌려준다.
- `exec()` 가 `QDialog.Accepted` 가 아니면 None이다.
- 맞으면 `textValue()` 를 지금처럼 `strip` 한다. `(없음)` 과 빈 글자는 `""` 다.
- 창은 `try/finally` 로 `deleteLater` 한다(`_ask_add_pair` 와 같은 모양).

그대로 둘 것: `items`·`current` 계산, 문구, 반환 규칙. 묻는 동안 DB를 부르지 않는다.

### 3. 기존 테스트 옮기기 (`tests/gui/test_load_csv_release.py`)

고친 뒤에는 `QInputDialog.getItem` 이 불리지 않는다. `answer_get_item` 을 쓰는 테스트 세 개(파라미터 8개 포함)를 **같은 성질을 단언하는** 새 대역으로 옮긴다. 지우기만 하지 마라.

**새 대역**
- `monkeypatch.setattr(QInputDialog, "exec", fake)` 이고, `fake(dialog)` 의 첫 인자는 창이다(`test_add_release.py` 의 `AddProcessDialog.exec` 대역과 같은 방식).
- 받은 창에서 기록한다: `parentWidget()`, `windowTitle()`, `labelText()`, `comboBoxItems()`, 처음 `textValue()`, `isComboBoxEditable()`, 콤보의 `completer()`.
- 답 글자를 `setTextValue(text)` 로 넣고 `QDialog.Accepted` 또는 `QDialog.Rejected` 를 돌려준다.
- 대역 이름은 바꿔도 된다.

**지킬 성질**

| 성질 | 기대 |
|---|---|
| 부모, 제목, 라벨 | `ctrl.ui`, `"Load CSV"`, `"불러올 버전 (비우면 버전 없음):"` |
| 후보 | 지금 쌍이 `("sf2p","V1")` 이면 `["(없음)", "V1", "V2"]`, 처음 글자 `"V1"` |
| 빈 버전 | 지금 쌍이 빈 버전이면 처음 글자 `"(없음)"` |
| 편집 | 편집 가능, 콤보 completer가 `None` |
| DB | 묻는 동안 `store.calls[since:] == []` |
| 다듬기 8줄 | `(없음)`·` (없음) `·빈칸·공백 → `""`, `V2` → `"V2"`, `  V3 ` → `"V3"`, 취소(두 줄) → `None` |

**새로 더한다**
- 쌍이 하나도 없는 툴바(`set_pairs([])`)에서도 묻는다.
  - 기록한 후보가 `[]`, 처음 글자가 `""` 다.
  - 답 `V1` → `"V1"`.
- 대역 없이 `_ask_release()` 를 부르면 dialogs fixture가 막는다.
  - `pytest.raises(AssertionError, match="QInputDialog.exec: 'Load CSV'")` 뒤 `dialogs.unexpected.clear()`.
  - 본보기: `test_add_release.py::test_the_plus_button_opens_the_add_process_window`.
  - 이유: 정적 함수에서 인스턴스로 바뀌어도, 답하지 않은 질문이 조용히 지나가지 않음을 고정한다.

이 옮긴 테스트들은 수정 전에 fixture가 `getItem` 을 막아서 실패한다. 버그 RED가 아니다. summary에서 진짜 모달 RED와 나눠 적는다.

### 4. 변이 검사

- completer를 끄는 줄을 지운다 → 진짜 모달 RED 테스트 두 개와 대역 테스트의 `completer() is None` 이 실패하는지 본다. 다시 넣는다.
- 처음 글자를 `items[0]` 으로 바꾼다 → 처음 자리 테스트가 실패하는지 본다. 되돌린다.

## Acceptance Criteria

```bash
uv run pytest tests/gui/test_load_csv_release.py tests/gui/test_dialogs_fixture.py -q
uv run pytest tests/gui -q
uv run ruff check src tests
uv run pytest -q
```

## 검증 절차

1. 위 AC 커맨드를 실행한다.
2. 아키텍처 체크리스트를 확인한다.
   - 묻는 창의 제목, 라벨, 후보, 처음 자리, 반환 규칙이 그대로인가?
   - 버전 묻기가 GUI 스레드에서 DB 호출 없이 끝나는가?
   - `_ask_load_csv`, 컨트롤러의 `on_load_csv_requested`, 알림·로그 문구를 건드리지 않았는가?
   - `dialogs/add_process.py`(step 0 몫), `delegates/combo_box.py`, `dialogs/insert.py`, `tests/gui_support/dialogs.py` 를 건드리지 않았는가?
3. 결과에 따라 `phases/20-combo-autocomplete/index.json` 의 step 1을 업데이트한다.
   - 성공 → `"status": "completed"`, `"summary": "_ask_release 가 QInputDialog(self) 인스턴스(getItem 과 같은 순서로 채움, 항목 없으면 처음 글자 '')의 콤보 completer 를 끄고 exec. RED(진짜 모달): <테스트 이름: 단언>. 옮긴 테스트: getItem 대역 → QInputDialog.exec 대역 <이름들>. 새: 쌍 없음, fixture 막기. 변이: <결과>"`
   - 재현 안 됨 → `"status": "completed"`, `"summary": "not reproduced: <이유>"`
   - 수정 3회 시도 후에도 실패 → `"status": "error"`, `"error_message": "구체적 에러 내용"`
   - 사용자 개입 필요 → `"status": "blocked"`, `"blocked_reason": "구체적 사유"` 후 즉시 중단

## 금지사항

- 정적 `QInputDialog.getItem` 을 다시 쓰지 마라. 이유: 그 안의 콤보에 손댈 수 없어 completer를 끌 수 없다.
- 새 대화상자 클래스나 `utils/dialogs.py` 공용 함수를 만들지 마라. 이유: 이 한 곳의 버그 수정이다.
- 문구(제목, 라벨), 후보 순서, 처음 자리, 반환 규칙을 바꾸지 마라.
- `insertPolicy` 등 다른 콤보 속성을 바꾸지 마라. 이유: 범위 밖이다.
- 진짜 모달 테스트의 `drive` 안에서 단언하지 마라. `finally` 의 닫기를 빼지 마라. 이유: 모달이 닫히지 않으면 테스트가 멈춘다.
- `tests/gui_support/dialogs.py` 와 `tests/gui/test_dialogs_fixture.py` 를 바꾸지 마라. 이유: 모든 GUI 테스트의 안전장치다.
- `dialogs/add_process.py` 를 바꾸지 마라. 이유: step 0의 몫이다.
- 기존 테스트를 깨뜨리지 마라. `getItem` 대역 테스트는 같은 성질로 옮긴다.
