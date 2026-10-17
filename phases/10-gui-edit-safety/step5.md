# Step 5: remove-process-edits

## 배경 (phase 10 공통)

이 저장소는 이미 여러 명이 쓰는 도구다. 평소에는 **에러·버그만 고친다**(CLAUDE.md, ADR-015). phase 10은 GUI에서 저장하지 않은 편집이 말없이 사라지거나, 엉뚱한 충돌이나 잘못된 저장이 나는 경로를 한 step에 하나씩 고친다. 대상 경로는 충돌 대화상자의 덮어쓰기, 같은 행 재클릭, 붙여넣기의 version과 탭 편집, 재접속·CSV 불러오기, Remove Process, Virtuoso 필터 중 저장 순서다. 모두 2026-10-17 docs/notes 분류에서 나온 항목이다(`docs/notes/known-issues.md` K17·K19·K20·K36·K37·K38·K42).
- K17·K38은 버그다.
- K19·K20·K36·K37·K42는 **사용자가 2026-10-17 승인한 동작 변경**이다. 승인 step에는 승인된 동작 문장을 "승인된 동작"에 그대로 적었다. 그 문장을 넘는 변경(새 문구, 새 질문, 다른 경로의 동작 변경)은 하지 않는다.

phase 0~9가 먼저 끝나 있다.
- GUI 저장 경로의 계약은 phase 3·4가 만들었다.
  - `save_all() -> bool`(device·탭), `DeviceTabController.save_db() -> bool`
  - `select_process_silently(name) -> bool`
  - `deviceVersionBumped`/`adopt_device_version`, `_save_before_process_change`
  - device 표 붙여넣기의 `Unsaved Changes` 거부, `save_all` 의 `Save Skipped` 경고
- phase 6~9는 GUI 코드를 바꾸지 않았다(경계 가드 테스트, service·schema, 운영 스크립트).
- 정확한 계약은 코드와 `phases/3-gui-save-fixes/index.json`·`phases/4-gui-robustness/index.json` 의 summary로 확인하라.

모든 step에 같은 규칙이 적용된다.
1. 버그 step(K17, K38)
   - 아래 "버그"는 **분석의 주장**이다. 먼저 실패하는 테스트로 재현하고, RED 출력(테스트 이름과 실패한 단언)을 summary에 적는다.
   - 재현되지 않으면 `src/` 를 고치지 않는다. 테스트는 특성 테스트로 남기고 `"status": "completed"`, `"summary": "not reproduced: <이유>"` 로 끝낸다.
2. 승인 step(K19, K20, K36, K37, K42): 새 동작을 단언하는 테스트를 먼저 쓰고, 수정 전에 실패하는 것을 본다(RED). 그 출력도 summary에 적는다.
3. RED는 **Windows 개발 PC에서** 보여야 한다. `posix_only` 테스트는 개발 PC에서 skip되므로 증명이 아니다.
4. 고친 뒤 수정을 손으로 되돌려 새 테스트가 실패하는지 확인하고, 다시 고친다(변이 검사).
   - `git checkout`/`git stash` 로 되돌리지 마라. 이유: 같은 step의 테스트 변경까지 사라진다.
5. 이 파일의 행 번호는 2026-10-17(phase 5 직후) 기준 대략값이다. phase 10의 앞 step이 같은 파일을 바꿨을 수 있으니 이름으로 찾아라.
6. `DeviceTabController.connect_db`·`_open_database` 는 phase 7·10·11이 차례로 건드린다. 그래서 본문을 이 파일에 옮겨 적지 않았다. 지금 코드를 읽고, 이름과 아래 불변식으로 작업하라.
7. repo(`service/repo/`)와 가짜 repo(`tests/gui_support/fakes.py` 의 `Fake*Repository`)의 의미는 바꾸지 않는다.
   - 그래서 이 phase에는 DB 테스트가 필요 없다. `GENDB_TEST_PG_DSN` 이 없어도 `blocked` 가 아니다.
8. 문서(`docs/`, README)는 이 phase의 step에서 바꾸지 않는다. phase 마무리에서 고친다(ADR-004 보강, UI_GUIDE, known-issues).
   - 예외는 이 파일이 따로 적은 것뿐이다(step 1의 CLAUDE.md 한 줄).

GUI 테스트 기반은 phase 2(`2-gui-test-infra`)가 만들었다. 아래 이름을 그대로 쓰고, 같은 일을 하는 것을 새로 만들지 마라. 작업 전에 `tests/gui/conftest.py`·`tests/gui_support/` 를 읽고, 이 파일의 서술과 다르면 실제 코드를 따른다.
- **대화상자 대역**: `tests/gui_support/dialogs.py` 의 `FakeDialogs` 이고, autouse `dialogs` fixture로 들어온다.
  - `dialogs.answer_question(*bools)` 는 Yes/No 질문에, `dialogs.answer_conflict(*choices)` 는 충돌 대화상자에 순서대로 답한다. 충돌 답은 `genviewer.dialogs.conflict` 의 `RELOAD`/`OVERWRITE`/`CANCEL` 이다.
  - 뜬 상자는 `dialogs.shown` 에 `(kind, title, text)` 로 쌓인다. kind는 `info`/`warning`/`error`/`critical`/`question` 이고, 충돌 대화상자는 `("conflict", "Save Conflict", <충돌 설명>)` 이다.
  - 답을 정하지 않은 모달은 `AssertionError` 를 내고 `dialogs.unexpected` 에 남는다. `@report` 가 그 예외를 삼키므로 실패는 **teardown에서** 드러난다. 쓰이지 않고 남은 답도 teardown 실패다.
- **`device_tab_ctrl`**: 가짜에 붙어 이미 접속한 `DeviceTabController` 다. `notifyRequested` 를 `dialogs.record_notify` 에 이어 두었으므로 알림도 `dialogs.shown` 에서 본다.
  - `main_window` fixture는 `MainWindowController` 다(`.device_tab` 이 같은 컨트롤러).
- **시드**(`seeded_store()`)
  - process `sf2p`(device `nfet_a` order 0, `nfet_b` order 1), `sf4u`(device `pfet_a`). 탭은 `"InstTerm"`·`"InstSchParam"`.
  - id는 `store.find_device("pfet_a")["id"]` 로 얻는다.
  - 접속하면 `sf2p` 가 자동으로 선택된다. autouse로 `GENDB_APP_USER=tester` 다.
- **store**
  - `store.calls` 는 `(메서드 이름, 인자 dict의 deep copy)` 이고, 호출이 **끝난 뒤**(예외로 끝나도) 기록된다.
  - `store.calls_of(name)`, `store.fail_next(name, exc)`(repo 메서드 이름 또는 `"open_database"`)
  - 남의 변경: `store.touch_device(id, actor="bob", **changes)`, 남의 삭제: `store.remove_device(id)`
  - 시드 추가: `store.add_device(process_id, name, celltype, order=…)`
  - 다른 사용자가 process를 지우는 흉내는 `ctrl.device_tab_toolbar.repo.delete("sf4u", actor="bob")` 다.
- **`tests/gui_support/helpers.py`**: `select_process(ctrl, name)`, `select_device_row(ctrl, row)`, `edit_device_cell(ctrl, row, column, value)`, `edit_tab_cell(ctrl, tab_name, row, column, value)`.
  - helpers는 기다리지 않는다. 기다림은 테스트가 `qtbot.waitUntil` 로 한다.
- "아무 일도 일어나지 않았다" 를 `qtbot.wait` 고정 대기로 확인하지 않는다. `store.calls` 를 `qtbot.waitUntil(lambda: <bool>)` 로 기다린 뒤 단언한다.
  - 콜백은 bool을 돌려줘야 한다(`lambda: store.calls_of("upsert_devices") != []`). 리스트를 돌려주면 pytest-qt가 `ValueError` 를 낸다.
  - 시그널 emit이나 직접 호출처럼 동기로 끝나는 동작은 돌아온 뒤 바로 단언해도 된다.
- 비슷한 테스트의 본보기: `tests/gui/test_device_save_result.py`, `tests/gui/test_tab_save_result.py`, `tests/gui/test_tab_version_sync.py`(`open_nfet_a`, `edit_nfet_a_tab`), `tests/gui/test_deleted_process_revert.py`, `tests/gui/test_process_list_refresh.py`, `tests/gui/test_device_save_guards.py`.

## 이 step의 목적

(**사용자 승인 2026-10-17**, K42) 지금 process에 저장하지 않은 편집이 있는 채로 Remove Process를 하면 다음과 같이 된다.
1. 지운 뒤 목록을 다시 채운다. 콤보가 첫 process로 바뀌면서 "Save Changes?" 가 뜬다.
2. 예라고 답하면 방금 지운 process의 device를 저장하려다 **반드시** "deleted" 충돌이 난다.

사용자가 process 삭제를 확인한 순간 그 process의 편집은 저장할 곳이 없다. 그러니 묻지 않는다.

**승인된 동작**: "Remove Process 를 확인하면 그 process 의 저장 안 한 편집은 버리고 'Save Changes?'·충돌 대화상자를 띄우지 않는다."

이 step의 해석:
- 편집을 버리는 시점은 **삭제가 성공한 뒤, 목록을 다시 채우기(`refresh_processes`) 전**이다.
  - 삭제가 실패하면 편집을 그대로 둔다. process가 남아 있으니 저장할 곳이 있다.
- 지운 process가 지금 process가 아니면 지금 process의 편집을 건드리지 않는다.
- 다른 사용자가 process를 지운 경로(phase 4 step 7, `refresh_processes` 뒤 "Save Changes" 질문)는 바꾸지 않는다. 그쪽은 사용자가 삭제를 확인한 적이 없다.
- 새 문구(알림·로그)를 더하지 않는다. "Remove Process" 질문이 이미 "device와 그 파라미터가 모두 함께 삭제됩니다" 라고 알렸다.

## 읽어야 할 파일

- `/CLAUDE.md`, `/docs/UI_GUIDE.md`(원칙 2), `/docs/ADR.md`(ADR-004 "phase 3 보강"·"phase 4 보강": 되돌릴 process가 지워졌으면 넘어간다), `/docs/ARCHITECTURE.md`(데이터 흐름 → 저장 결과)
- `src/genviewer/controllers/device_tab_toolbar.py`
  - 시그널 목록 (~10-22)
  - `remove_process(name)` (~104-131): `exists` → `count_devices` → "Remove Process" 질문 → `repo.delete` → True면 "Removed" info → `refresh_processes()` → 로그. 예외는 "Remove Failed: <name>".
  - `refresh_processes` (~133-138)
- `src/genviewer/views/device_tab_toolbar.py`
  - `open_remove_process_dialog` (~133-145): "Confirm Delete" 질문 뒤 `removeProcessRequested.emit(name)`. name은 지금 콤보 텍스트다.
  - `set_processes` (~157-171): 지금 process가 목록에서 사라졌을 때만 최종 이름으로 `currentTextChanged` 를 한 번 낸다.
- `src/genviewer/controllers/device_tab.py`
  - `__init__` 시그널 연결 (~64-87)
  - `on_process_changed` (~405-432), `_save_before_process_change` (~434-470)
- `src/genviewer/controllers/device_table.py`: `is_dirty`/`set_dirty` (~219-227, `dirty_by_process_id` 기준)
- `src/genviewer/controllers/parameter_tab.py`: `is_dirty`, `_clear_tabs` (~155-158), `discard_all` (~134-138)
- `tests/gui/test_deleted_process_revert.py`
  - 전체. 특히 `test_cancelling_after_removing_the_process_moves_to_the_first_process` (~178-196): 지금 동작을 고정한다(`answer_question(True, True)` + `CANCEL`, `upsert_devices` 한 번, 충돌 한 번).
  - `edit_pfet_a_description`, `edit_pfet_a_tab`, `assert_moved_to_sf2p`, `record_process_changes`, `SAVE_CHANGES`, `conflicts`, `errors`
- `tests/gui/test_process_list_refresh.py`: Remove Process 테스트(~151-179, 편집 없음. 그대로 통과해야 한다)

## 승인된 동작 변경

지금은 `remove_process("sf4u")` 가 다음 순서로 진행된다.
1. "Remove Process" 예
2. 삭제
3. `refresh_processes` → `set_processes` 가 "sf2p" 로 `currentTextChanged`
4. `on_process_changed` → `_save_before_process_change` 가 "Save Changes" 를 묻는다
5. 예 → `upsert_devices` 가 deleted 충돌
6. 취소하면 phase 4 step 7 규칙대로 sf2p로 넘어간다

이것을 승인된 동작으로 바꾼다.

## 작업

### 결과 × 상태 (`DeviceTabToolBarController.remove_process(name)`)

| 경우 | 질문 | 최종 상태 |
|---|---|---|
| name = 지금 process, device 표 dirty, "Remove Process" 예, 삭제 성공 | "Remove Process" 하나뿐("Save Changes"·충돌 없음) | 편집을 버린다 → 목록 다시 채움 → 첫 process(sf2p)로 넘어간다. `upsert_devices`·`replace_many_for_device` 호출 없음. "Removed" info와 로그 "Process removed: sf4u." 는 지금처럼 |
| 〃, 탭만 dirty | 〃 | 〃 (탭 dirty 아님) |
| 〃, 둘 다 dirty | 〃 | 〃 |
| "Remove Process" 아니오 | 그 하나 | 아무것도 바뀌지 않는다(지금과 같다) |
| 삭제 예외(`store.fail_next("delete", RuntimeError("boom"))`) | "Remove Process" | 편집과 process가 그대로다. error "Remove Failed: sf4u" (지금과 같다) |
| `repo.delete` 가 False(이미 없음) | "Remove Process" | 지금처럼 아무것도 하지 않는다. 편집도 그대로 |
| name ≠ 지금 process(컨트롤러를 직접 부른 경우) | "Remove Process" | 지금 process의 편집은 그대로다. 목록만 다시 채운다(지금 process가 남아 있어 전환 없음) |
| 편집 없음 | "Remove Process" | 지금과 같다(`test_process_list_refresh.py` 의 Remove 테스트) |
| 목록 다시 채우기 실패(`fail_next("list_all", …)`, `@report("Process List Failed")`) | "Remove Process" | 편집은 이미 버렸다(그 process는 지워졌다). 콤보는 지운 이름에 머문다(지금과 같다). 이 경우의 결과를 테스트로 확인하고 summary에 적는다 |

### 편집을 버리는 방법

- `DeviceTabToolBarController` 에 공개 시그널을 더한다. 예: `processRemoved = Signal(str)`. 삭제가 True를 돌려준 뒤, `refresh_processes()` **전에** 낸다.
- `DeviceTabController` 가 그 시그널을 받아, 이름이 `device_table.current_process` 와 같을 때만 버린다.
  - device 표: `set_dirty(False)` 등으로 `is_dirty()` 가 False가 되게 한다.
  - 탭: `parameter_tab._clear_tabs()` 처럼 섹션을 비워 `is_dirty()` 가 False가 되게 한다. 이 private 호출은 같은 컨트롤러가 이미 여러 번 쓰는 방식이고, phase 15가 공개 이름으로 바꾼다. 새로운 private 교차 호출을 만들지는 마라.
  - 지워진 device의 탭을 서버에서 다시 읽는 호출(`discard_all` → `update_model`)은 피한다. 읽을 행이 없다.
- 시그널은 같은 스레드의 직접 연결이라 `refresh_processes()` 전에 처리가 끝난다. 그 순서를 테스트가 확인한다("Save Changes" 가 뜨지 않음).

### 1. 테스트 먼저 (`tests/gui/test_deleted_process_revert.py`)

- **기존 테스트를 승인된 동작으로 바꾼다(RED)**: `test_cancelling_after_removing_the_process_moves_to_the_first_process` 를 새 동작에 맞는 이름으로 바꾼다(예: `test_removing_the_process_drops_its_edits_without_asking`). 내용은 다음과 같다.
  - `dialogs.answer_question(True)`("Remove Process" 만), `answer_conflict` 없음 → `remove_process("sf4u")`
  - `qtbot.waitUntil(lambda: ctrl.device_table.current_process == "sf2p")` → `assert_moved_to_sf2p`
  - `store.calls_of("upsert_devices") == []`, `conflicts(dialogs) == []`, `SAVE_CHANGES not in dialogs.shown`
  - `changes == ["sf2p"]`, "sf4u" 가 콤보·`list_all()` 에 없다, `errors(dialogs) == []`
  - **수정 전에는 답하지 않은 "Save Changes" 로 실패해야 한다.**
- **탭만 dirty**: `edit_pfet_a_tab` 뒤 같은 흐름 → `parameter_tab.is_dirty() is False`, `replace_many_for_device` 호출 없음.
- **삭제 예외**: `fail_next("delete", RuntimeError("boom"))` → "Remove Failed: sf4u" error. 콤보·device 표가 sf4u이고 편집이 남는다.
- **"Remove Process" 아니오**: 편집이 남고 delete 호출이 없다(특성 테스트).
- **다른 process를 지움**: sf2p를 열고 nfet_a Description을 고친 뒤 `remove_process("sf4u")` + `answer_question(True)` → sf2p 편집이 남고, "Save Changes" 가 없다.
- 다른 사용자가 지운 경로의 기존 테스트(같은 파일 앞부분)는 그대로 통과한다.
- 모듈 docstring에 이 step의 동작을 한 줄 더한다.

### 2. 수정

- `controllers/device_tab_toolbar.py`: 시그널을 더하고, 삭제 성공 뒤 `refresh_processes()` 전에 낸다.
- `controllers/device_tab.py`: 생성자에서 연결하고 위 규칙대로 버린다. 주석 한두 줄로 이유를 적는다. 예: "사용자가 process 삭제를 확인했다. 그 편집은 저장할 곳이 없어 물으면 반드시 deleted 충돌이 난다(K42)".

### 3. 변이 검사

- 시그널을 `refresh_processes()` **뒤로** 옮긴다. RED 테스트가 실패하는지 본다("Save Changes" 가 먼저 뜬다). 되돌린다.
- 이름 비교를 지워(늘 버리게) "다른 process를 지움" 테스트가 실패하는지 본다. 되돌린다.

## Acceptance Criteria

```bash
uv run pytest tests/gui/test_deleted_process_revert.py -q   # 바꾼·새 테스트 통과 (수정 전에는 Remove 테스트가 실패해야 한다)
uv run pytest tests/gui/test_process_list_refresh.py tests/gui/test_process_change_save.py -q   # phase 3·4 목록·전환 테스트 그대로 통과
uv run ruff check src tests
uv run pytest tests/gui -q
uv run pytest -q
```

## 검증 절차

1. 위 AC 커맨드를 실행한다.
2. 아키텍처 체크리스트를 확인한다.
   - 새 문구가 없는가? "Remove Process"·"Confirm Delete" 질문과 "Removed" 알림이 그대로인가?
   - 다른 사용자가 지운 경로(phase 4 step 7)와 이전 process가 남아 있을 때의 되돌림(phase 3 step 5)이 그대로인가?
   - 삭제가 실패하면 편집이 남는가?
3. 결과에 따라 `phases/10-gui-edit-safety/index.json` 의 step 5를 업데이트한다.
   - 성공 → `"status": "completed"`, `"summary": "K42(승인): remove_process 가 삭제 성공 뒤 refresh_processes 전에 processRemoved(name) 를 내고 DeviceTabController 가 지금 process 면 device·탭 편집을 버림(Save Changes·충돌 없음). 기존 test_cancelling_after_removing_the_process_moves_to_the_first_process → <새 이름>. RED: <단언>. 변이: <결과>. 목록 다시 채우기 실패 시: <관찰>"`
   - 수정 3회 시도 후에도 실패 → `"status": "error"`, `"error_message": "구체적 에러 내용"`
   - 사용자 개입 필요 → `"status": "blocked"`, `"blocked_reason": "구체적 사유"` 후 즉시 중단

## 금지사항

- 삭제 **전에** 편집을 버리지 마라. 이유: 삭제가 실패하면 process가 남는데 편집만 사라진다.
- "Remove Process" 질문 문구를 바꾸거나 "편집이 사라진다" 는 새 문구를 더하지 마라. 이유: 승인 범위는 "버리고 묻지 않는다" 다.
- `_save_before_process_change`·`on_process_changed` 의 일반 규칙(질문, 되돌림, 지워진 process면 넘어감)을 바꾸지 마라. 이유: 다른 사용자가 지운 경로와 일반 process 전환이 그 규칙을 쓴다(phase 3·4).
- `views/device_tab_toolbar.py` 의 "Confirm Delete" 흐름과 `set_processes` 를 바꾸지 마라. 이유: 범위 밖이다.
- 기존 테스트를 깨뜨리지 마라. 이 step이 바꾸는 것은 Remove + Save Changes 흐름을 고정한 테스트 하나뿐이다.
