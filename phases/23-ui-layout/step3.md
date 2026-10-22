# Step 3: remove-process-confirm

## 배경

이 저장소는 **에러·버그만 고친다**(CLAUDE.md, ADR-015). 이 step은 사용자가 2026-10-22에 승인한 사용성 변경이다("Process 삭제 확인 한 번", AskUserQuestion).

**문제**: Device 탭 툴바의 `-`(Remove Process)를 누르면 확인을 두 번 연달아 묻는다.
1. view의 `DeviceTabToolBar.open_remove_process_dialog` 가 `question(self, "Confirm Delete", "Are you sure you want to delete the process:\n'<label>'?")` 를 묻는다.
2. 예이면 `removeProcessRequested` 를 낸다. 그러면 controller `DeviceTabToolBarController.remove_process` 가 `question(self.ui, "Remove Process", "Process '<label>' 을(를) 삭제하면 device N개와 …")` 를 다시 묻는다.

두 번째 질문이 device 수까지 알려 준다. 첫 번째는 같은 것을 한 번 더 묻는 것이다.

**승인된 동작**
- view는 묻지 않고 바로 `removeProcessRequested(name, release)` 를 낸다. 지금 쌍이 없으면(`("", "")`) 지금처럼 아무것도 하지 않는다.
- controller의 "Remove Process" 질문 하나만 남는다. 문구·흐름은 그대로다.

| 경로 | 결과 |
|---|---|
| 지금 쌍 없음 | 질문 없음, 시그널 없음 |
| `-` → Remove Process에 아니오 | 아무것도 지우지 않는다. `store.calls_of("delete") == []`, 쌍과 편집이 그대로다 |
| `-` → Remove Process에 예 | 그 쌍 하나를 지운다(지금과 같다) |
| 그 사이 남이 지움(`Not Found`) | 질문 없이 `Not Found` 경고(지금과 같다) |

규칙:
1. 승인된 변경이라 RED 대신 변이 검사를 한다. 첫 질문을 손으로 되살리면 고친 테스트가 실패해야 한다. `git checkout`/`git stash` 로 되돌리지 마라.
2. 행 번호는 2026-10-22 기준 대략값이다.
3. 문서(UI_GUIDE "입력과 단축키" 의 Remove Process 줄, README)는 phase 마무리에서 고친다.

## 읽어야 할 파일

- `/CLAUDE.md`, `/docs/UI_GUIDE.md`: Remove Process 줄
- `src/genviewer/views/device_tab_toolbar.py`: `open_remove_process_dialog`(~170-179), `question` import
- `src/genviewer/controllers/device_tab_toolbar.py`: `remove_process`(~146-180). 읽기만 한다.
- `tests/gui_support/dialogs.py`: `QUESTION_MODULES`. `question` 을 이름으로 묶은 모듈 목록이다. `tests/gui/test_dialogs_fixture.py` 가 빠진 것과 남은 것을 잡는다.
- `tests/gui/test_toolbar_pairs_view.py`: `test_remove_asks_about_the_current_pair_and_gives_it`(~278-290), `test_remove_without_a_pair_does_nothing`
- `tests/gui/test_process_release_switch.py`: `test_the_minus_button_confirms_and_removes_the_current_pair`(~487-504, `answer_question(True, True)`), `test_the_minus_button_question_without_a_release_is_the_old_one`(~507-515)

## 작업

### 1. 테스트를 새 동작으로 바꾼다

- `test_toolbar_pairs_view.py`
  - `test_remove_asks_about_the_current_pair_and_gives_it` 를 `test_remove_gives_the_current_pair_without_asking` 로 바꾼다.
  - 답을 미리 걸지 않는다. `dialogs.shown == []` 이고 시그널이 `("sf2p", "V1")` 이다.
- `test_process_release_switch.py`
  - `test_the_minus_button_confirms_and_removes_the_current_pair`: `answer_question(True)` 한 번만 건다. 뜬 질문은 "Remove Process" 하나다. 그 문구가 지금 controller 문구 그대로인지 단언한다(`sf2p V2`, device 수 포함).
  - `test_the_minus_button_question_without_a_release_is_the_old_one`: 아니오로 답하면 뜬 것이 "Remove Process" 질문 하나다. 문구는 이름만이다(`'sf2p'`). `delete` 가 불리지 않는다.
    - 컨트롤러 질문 전에 `exists`·`count_devices` 가 불린다. `qtbot.waitUntil` 로 질문 기록을 기다린 뒤 단언한다.
- 그 밖에 "Confirm Delete" 를 기대하는 곳을 `grep -rn "Confirm Delete" tests` 로 찾아 같이 고친다.

### 2. 수정 (`views/device_tab_toolbar.py`)

- `open_remove_process_dialog` 에서 `question(...)` 을 지운다. 쌍이 있으면 바로 `removeProcessRequested.emit(name, release)` 한다.
- `question` import가 쓰이지 않으면 지운다.
  - 그러면 `tests/gui_support/dialogs.py` 의 `QUESTION_MODULES` 에서 `"genviewer.views.device_tab_toolbar"` 를 뺀다.
  - 빼지 않으면 fixture가 없는 이름을 바꾸려다 실패한다. `test_dialogs_fixture.py` 가 그 목록을 검사하니 함께 통과해야 한다.

## Acceptance Criteria

```bash
uv run pytest tests/gui/test_toolbar_pairs_view.py tests/gui/test_process_release_switch.py tests/gui/test_dialogs_fixture.py -q
uv run pytest tests/gui -q
uv run ruff check src tests
uv run pytest -q
```

## 검증 절차

1. 위 AC 커맨드를 실행한다.
2. 아키텍처 체크리스트를 확인한다.
   - controller `remove_process` 는 그대로인가? 질문 문구, `Not Found`, `processRemoved` 순서, `refresh_processes` 가 같아야 한다.
   - 지울 것은 지금 쌍 하나뿐인가? CLAUDE.md CRITICAL: 명시적으로 지운 것만 삭제한다.
3. 결과에 따라 `phases/23-ui-layout/index.json` 의 step 3을 업데이트한다.
   - 성공 → `"status": "completed"`, `"summary": "Remove Process 확인 2회→1회(view 의 Confirm Delete 제거, controller 의 Remove Process 만). QUESTION_MODULES 에서 views.device_tab_toolbar 제거. 고친 테스트: <이름들>. 변이: <결과>"`
   - 수정 3회 시도 후에도 실패 → `"status": "error"`, `"error_message": "구체적 에러 내용"`
   - 사용자 개입 필요 → `"status": "blocked"`, `"blocked_reason": "구체적 사유"` 후 즉시 중단

## 금지사항

- controller의 "Remove Process" 질문을 지우거나 문구를 바꾸지 마라. 이유: 남기기로 한 것이 그 질문이다. device 수를 알려 준다.
- Add Process(`+`)나 Add Library 흐름을 바꾸지 마라. 이유: 범위 밖이다.
- 건드리는 파일의 기존 한국어 문구를 번역하지 마라(controller 질문 포함). 이유: phase 24(영어화)의 몫이다.
- 기존 테스트를 깨뜨리지 마라. 위에서 새 동작으로 바꾼 테스트만 예외다.
