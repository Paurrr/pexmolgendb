# Step 0: conflict-deleted-only

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

(**사용자 승인 2026-10-17**, K20) "deleted" 충돌에서 덮어쓰기를 고르면 지금은 이렇게 된다.
- device 저장: 사라진 device의 편집을 조용히 버리고 "Save Complete"/"Saved" 를 띄운다(UI_GUIDE 원칙 4 위반).
- 탭 저장: 같은 `StaleWriteError` 가 다시 나 오류 상자가 뜬다. device 전환 중이면 "예기치 못한 오류" 가 된다.

덮어쓸 대상이 없는 충돌에서는 덮어쓰기를 내놓지 않는다.

**승인된 동작**: "충돌이 전부 '삭제'면 충돌 대화상자에 덮어쓰기 버튼을 안 보인다(다시 읽기/취소만)."

이 step의 해석과 범위(승인 문장의 목적 = 덮어쓸 대상이 없는 덮어쓰기를 막기):
- 판단에서 **내가 지운 행**(device 저장의 `deleted` 사전에 든 id)의 "deleted" 충돌은 뺀다. 이유는 아래와 같다.
  - 남이 먼저 지운 행을 나도 지운 것이므로 덮어쓰기가 해가 없다. 지울 행이 이미 없다.
  - 이것까지 숨기면 남는 길은 다시 읽기(화면의 다른 편집까지 버린다)와 취소(다음 저장이 같은 충돌로 또 막힌다)뿐이라 지금보다 나빠진다.
  - 그래서 내가 지운 행의 충돌을 빼고 본다. **남은 충돌이 하나 이상이고 그것이 전부 deleted 일 때** 덮어쓰기를 숨긴다.
  - 예: [내가 지운 행 5의 deleted, 남이 지운 편집 행 6의 deleted] 면 남은 것은 [6] 이고 전부 deleted 이므로 숨긴다. [내가 지운 행 5의 deleted] 만 있으면 남은 것이 없으므로 내놓는다.
  - 이 해석은 **사용자가 2026-10-17 확인했다**(phase 10 step 파일을 확정할 때).
- stale 과 deleted 가 섞인 충돌은 지금처럼 세 갈래다. 덮어쓰면 사라진 행의 편집은 여전히 조용히 버려진다. 고치지 말고 summary에 "새 known-issue" 로 적는다.
- 탭 저장의 deleted 는 항상 지금 열린 device 하나다. 그래서 탭 쪽 deleted 충돌에서는 덮어쓰기가 늘 숨는다.

## 읽어야 할 파일

- `/CLAUDE.md`, `/docs/UI_GUIDE.md`(원칙 4, "문구" 절의 저장 충돌 세 갈래), `/docs/ADR.md`(ADR-004), `/docs/ARCHITECTURE.md`(데이터 흐름 → device 저장, 탭 저장, 저장 결과)
- `src/genviewer/dialogs/conflict.py`: 전체. `ConflictDialog` (~22-68), `ask_conflict(parent, conflicts)` (~71-75)
- `src/genviewer/service/errors.py`: `Conflict` (~16-31, `reason` 은 `"stale"`/`"deleted"`, `describe()`), `StaleWriteError` (~34-39)
- `src/genviewer/service/repo/device.py`
  - `_preflight`: FOR UPDATE로 잡지 못한 행은 deleted다. `deleted` 사전의 id도 같은 검사를 받아 `Conflict(id, "", "deleted")` 가 된다.
  - `_update_existing`: force면 사라진 행은 맞는 행이 없어 조용히 지나간다.
- `src/genviewer/service/repo/parameter.py` `replace_many_for_device` (~60-80): 행이 없으면 force여도 deleted를 낸다.
- `src/genviewer/controllers/device_table.py` `_write_devices` (~413-445, `ask_conflict(self.ui, e.conflicts)`), `save_all` (~337-395)
- `src/genviewer/controllers/parameter_tab.py` `_write` (~80-99)
- `src/genviewer/controllers/device_tab.py`
  - `save_db` (~118-144)
  - `_save_before_process_change` (~434-470)
  - `_switch_device_by_index` (~487-524, try 없이 `parameter_tab.save_all()`)
  - `on_current_row_changed` (`@report` 는 `StaleWriteError` 를 다시 올린다, `utils/reporting.py` ~64)
- `tests/gui_support/dialogs.py`: `FakeDialogs.ask_conflict` (~131-137), `CONFLICT_MODULES` (~40-44), `install_dialogs`
- `tests/gui/test_dialogs_fixture.py`
  - `_conflicts()` (~34-38, stale+deleted 섞임)
  - `test_ask_conflict_returns_queued_choice` (~116, 섞인 목록에 OVERWRITE로 답한다. 그대로 통과해야 한다), `test_ask_conflict_without_answer_raises` (~131)
  - `test_every_ask_conflict_import_is_patched` (~370)
- `tests/gui/test_device_save_result.py` (`test_cancelling_after_another_user_deleted_the_device_returns_false` ~110), `tests/gui/test_tab_save_result.py`, `tests/gui/test_deleted_process_revert.py`
- 지금 OVERWRITE로 답하는 테스트는 모두 stale 충돌 뒤다. 이 step 뒤에도 그대로 통과해야 한다.
  - `test_device_save_result.py:~71`, `test_tab_save_result.py:~93`
  - `test_device_switch_save.py:~129,177`, `test_save_entry_points.py:~102`
  - `test_tab_version_sync.py:~208,236,263`

## 지금 동작 (재현해서 확인하라)

- **device 저장**: nfet_a의 Description을 고친 뒤 남이 nfet_a를 지우면 `save_all()` 이 충돌을 묻는다(목록 "nfet_a: 다른 사용자 님이 삭제"). OVERWRITE를 고르면 다음과 같이 된다.
  - 로그 "Save conflict: 내 변경으로 덮어썼다."
  - 정보 상자 "Save Complete" / "No changes to save."
  - 반환은 True다. 다시 읽은 표에서 그 행이 사라지고, 편집은 말없이 사라진다.
- **탭 저장**: nfet_a 탭을 고친 뒤 남이 nfet_a를 지우면 `parameter_tab.save_all()` 이 충돌을 묻는다(목록 "<id>: 다른 사용자 님이 삭제"). OVERWRITE를 고르면 `_apply(force=True)` 가 같은 `StaleWriteError` 를 다시 낸다.
  - `save_db` 에서는 "Save Tabs Failed" 오류 상자가 뜬다.
  - device 전환(`_switch_device_by_index`) 중이면 슬롯 밖으로 새어 나간다.

## 작업

### 계약 (dialogs/conflict.py)

- 순수 함수 `can_overwrite(conflicts, my_deletions=()) -> bool` 을 둔다(Qt를 쓰지 않는다).
  - `my_deletions` 에 든 `device_id` 의 충돌을 뺀 나머지를 본다. 나머지가 비어 있지 않고 **모두** `reason == "deleted"` 이면 False다.
  - 그 밖에는 True다(빈 목록, 내가 지운 행만 겹친 경우 포함).
- `ConflictDialog(parent, conflicts, *, allow_overwrite=True)`: False면 "내 변경으로 덮어쓰기" 버튼을 만들지 않거나 숨긴다.
  - 머리말, 목록, 나머지 두 버튼의 문구·툴팁·기본 버튼(다시 읽기)은 그대로 둔다.
- `ask_conflict(parent, conflicts, my_deletions=()) -> str`: `can_overwrite` 로 판단해 대화상자에 넘긴다. 숨겼으면 RELOAD/CANCEL만 돌려준다(창 닫기는 지금처럼 CANCEL).
- 호출부
  - `controllers/device_table.py` `_write_devices`: 이번 쓰기의 `deleted` 사전의 id를 `my_deletions` 로 넘긴다.
  - `controllers/parameter_tab.py` `_write`: 지금 호출 그대로(`my_deletions` 없음).

### 테스트 대역 (tests/gui_support/dialogs.py)

- `FakeDialogs.ask_conflict(parent, conflicts, my_deletions=())`: 진짜와 같은 시그니처로 맞추고, **`genviewer.dialogs.conflict.can_overwrite` 를 그대로 import해** 판단한다. 같은 규칙을 가짜에 다시 쓰지 마라. 이유: 둘이 어긋나면 GUI 테스트가 거짓으로 통과한다.
- 내놓았을 선택지를 순서대로 `dialogs.conflict_choices: list[tuple[str, ...]]` 에 남긴다. 숨겼으면 `(RELOAD, CANCEL)`, 아니면 `(RELOAD, OVERWRITE, CANCEL)` 이다.
- `shown` 의 항목 형식(`("conflict", "Save Conflict", <설명>)`)은 바꾸지 않는다. 이유: 기존 테스트 수십 개가 그 형식을 단언한다.
- 내놓지 않은 OVERWRITE를 꺼내면 `unexpected` 에 한 줄 남기고 `AssertionError` 를 낸다. 예: `"내놓지 않은 OVERWRITE 답: 'Save Conflict'"`.

### 결과 × 상태

내가 지운 행을 뺀 나머지 충돌이 있고 모두 deleted 인 경우:

| 경로 | 선택 | 반환 | 화면·dirty | 알림·로그 |
|---|---|---|---|---|
| device `save_all` | RELOAD | False | 다시 읽음(지워진 행 사라짐), dirty 아님 | 로그 "Save conflict: 서버 내용으로 다시 읽었다.", "Save Complete" 없음 (지금과 같다) |
| device `save_all` | CANCEL | False | 편집 그대로, dirty | 로그 "Save conflict: 저장을 취소했다." (지금과 같다) |
| device `save_all` | OVERWRITE | 내놓지 않는다 | - | - |
| 탭 `save_all` | RELOAD | False | 섹션을 다시 읽음(그 device 행 없음), dirty 아님 | 로그 "Tab conflict: 서버 내용으로 다시 읽었다." |
| 탭 `save_all` | CANCEL | False | 편집 그대로, dirty | 로그 "Tab conflict: 저장을 취소했다." |
| 탭 `save_all` | OVERWRITE | 내놓지 않는다 | - | - |
| device 전환(탭 dirty → "Save Changes" 예) | RELOAD / CANCEL | - | RELOAD면 새 device로 넘어간다. CANCEL이면 머문다(phase 3) | 오류 상자·"예기치 못한 오류" 없음 |
| process 전환(`_save_before_process_change`) | RELOAD / CANCEL | True / False | RELOAD면 넘어간다. CANCEL이면 콤보를 되돌린다(phase 3·4) | 지금과 같다 |

그 밖의 경우는 지금과 같다.

| 충돌 | 내놓는 선택 | 비고 |
|---|---|---|
| stale만 | 세 갈래 | 기존 테스트가 지킨다 |
| stale + deleted(편집한 행) | 세 갈래 | 덮어쓰면 사라진 행의 편집은 조용히 버려진다. 새 known-issue |
| 내가 지운 행을 남도 지움(deleted, `my_deletions` 안)만 있음 | 세 갈래 | OVERWRITE가 해가 없다. 나머지 편집이 저장된다 |
| 내가 지운 행의 deleted + 남이 지운 편집 행의 deleted | RELOAD/CANCEL | 내가 지운 행을 빼면 전부 deleted 다 |
| 쓰기 중 예외(`fail_next`), 접속 끊김 | 대화상자 없음 | 예외가 그대로 올라간다(지금과 같다) |

### 1. 테스트 먼저

새 파일 `tests/gui/test_conflict_deleted_only.py`:
- **`can_overwrite` 단위**: 아래 여섯 경우를 확인한다.
  - `[deleted]` → False
  - `[stale]` → True
  - `[stale, deleted]` → True
  - `[deleted(id=5)]` 와 `my_deletions={5}` → True
  - `[deleted(id=5), deleted(id=6)]` 와 `my_deletions={5}` → False
  - `[]` → True
- **`ConflictDialog` 버튼**(exec 하지 말고 만들기만 한다. `QDialog.exec` 는 가짜가 막는다): `findChildren(QPushButton)` 의 보이는 버튼 텍스트로 확인한다.
  - 모든 충돌이 deleted면 "내 변경으로 덮어쓰기" 가 없다.
  - stale이 하나라도 있으면 있다.
  - "다시 읽기"·"취소" 는 둘 다 있다.
  - **수정 전에는 deleted 경우가 실패해야 한다.**
- **device 저장**: `edit_device_cell(ctrl, 0, "description", …)` → `store.remove_device(nfet_a)`. RELOAD·CANCEL 각각에 대해 위 표의 반환·dirty·로그와 `dialogs.conflict_choices[-1] == (RELOAD, CANCEL)` 를 단언한다.
- **탭 저장**: `open_nfet_a` 형태로 nfet_a를 골라 탭을 고치고 → `store.remove_device(nfet_a)` → `ctrl.parameter_tab.save_all()`. RELOAD·CANCEL 각각을 위 표대로 단언한다.
- **device 전환**: nfet_a 탭을 고치고 → nfet_a가 지워지면 → `select_device_row(ctrl, 1)` → `answer_question(True)`, `answer_conflict(RELOAD)`.
  - nfet_b로 넘어간다(`parameter_tab.current_device_id`).
  - `dialogs.shown` 에 `error`/`critical` 이 없다.
- **내가 지운 행**: nfet_b 행을 화면에서 지우고(모델 `remove_rows([1])`), nfet_a의 Description을 고친다 → 남이 nfet_b를 지운다 → `save_all()` → `conflict_choices[-1]` 에 OVERWRITE가 있다 → OVERWRITE → True이고 nfet_a의 Description이 저장됐다(수정 전에도 통과한다. 회귀 그물).
- **섞인 충돌**: nfet_a를 고치고 nfet_b도 고친 뒤 남이 nfet_a는 `touch_device`, nfet_b는 `remove_device` → 세 갈래가 다 나온다(특성 테스트).

`tests/gui/test_dialogs_fixture.py` 에 가짜 테스트를 더한다(기존 테스트처럼 끝에서 `dialogs.unexpected` 를 비워 teardown이 실패하지 않게 한다. 기존 `test_ask_conflict_without_answer_raises` 가 어떻게 하는지 보고 따른다).
- 모든 충돌이 deleted인 목록에 `answer_conflict(OVERWRITE)` 로 답하면 `AssertionError` 가 나고 `unexpected` 에 남는다.
- RELOAD는 그대로 돌려준다.
- `conflict_choices` 가 쌓인다.
- 섞인 목록에 대한 기존 `test_ask_conflict_returns_queued_choice` 는 그대로 통과한다.
- `CONFLICT_MODULES` 의 모든 모듈에서 바뀐 시그니처로 불러도 같다.

### 2. 수정

위 "계약" 대로 고친다. 주석은 바꾼 자리 옆에 한두 줄로 이유를 적는다. 예: "덮어쓸 행이 없다. 덮어쓰기를 고르면 편집이 조용히 사라지거나 같은 충돌이 다시 난다".

### 3. 변이 검사

- `can_overwrite` 가 늘 True를 돌려주게 손으로 바꾼다. 버튼 테스트, 가짜 거부 테스트, `conflict_choices` 단언이 실패하는지 본다. 되돌린다.
- `_write_devices` 가 `my_deletions` 를 넘기지 않게 바꾼다. "내가 지운 행" 테스트가 실패하는지 본다. 되돌린다.

## Acceptance Criteria

```bash
uv run pytest tests/gui/test_conflict_deleted_only.py tests/gui/test_dialogs_fixture.py -q   # 새 테스트 통과 (수정 전에는 버튼·가짜 거부 테스트가 실패해야 한다)
uv run pytest tests/gui/test_device_save_result.py tests/gui/test_tab_save_result.py tests/gui/test_device_switch_save.py tests/gui/test_save_entry_points.py tests/gui/test_tab_version_sync.py -q   # stale 뒤 OVERWRITE 테스트 그대로 통과
uv run ruff check src tests
uv run pytest tests/gui -q
uv run pytest -q
```

## 검증 절차

1. 위 AC 커맨드를 실행한다.
2. 아키텍처 체크리스트를 확인한다.
   - `can_overwrite` 가 Qt 없이 도는 순수 함수인가? 가짜가 같은 함수를 import해 쓰는가?
   - 대화상자의 기존 문구·툴팁·기본 버튼이 그대로인가(UI_GUIDE 문구)?
   - repo·가짜 repo의 충돌 의미(`_preflight`, force)를 바꾸지 않았는가?
3. 결과에 따라 `phases/10-gui-edit-safety/index.json` 의 step 0을 업데이트한다.
   - 성공 → `"status": "completed"`, `"summary": "K20(승인): 내가 지운 행을 뺀 나머지 충돌이 있고 전부 deleted 면 덮어쓰기를 내놓지 않음. dialogs/conflict.can_overwrite(conflicts, my_deletions) + ask_conflict(..., my_deletions), device_table 이 deleted id 를 넘김. FakeDialogs 가 같은 함수로 OVERWRITE 답을 거부하고 conflict_choices 를 남김. RED: <테스트 이름과 단언>. 변이: <결과>. 해석: 내가 지운 행의 deleted 는 판단에서 뺌(사용자 확인 2026-10-17). 새 known-issue: stale+deleted 섞인 충돌의 덮어쓰기는 사라진 행 편집을 조용히 버림"`
   - 수정 3회 시도 후에도 실패 → `"status": "error"`, `"error_message": "구체적 에러 내용"`
   - 사용자 개입 필요 → `"status": "blocked"`, `"blocked_reason": "구체적 사유"` 후 즉시 중단

## 금지사항

- 덮어쓰기를 고르면 조용히 다시 읽기나 취소로 바꾸는 식으로 구현하지 마라. 이유: 승인된 동작은 "버튼을 안 보인다" 이다. 보이는 버튼이 다른 일을 하면 실패를 성공처럼 알리는 것과 같다.
- 대화상자의 머리말·버튼·툴팁 문구를 바꾸거나 새 설명 문구를 더하지 마라. 이유: 승인 범위 밖이다(UI_GUIDE 문구, ADR-015).
- `service/repo/device.py`·`parameter.py` 의 충돌 판단(`_preflight`, `force`)과 가짜 repo를 바꾸지 마라. 이유: 이 step은 대화상자가 내놓는 선택만 바꾼다. repo의 의미를 바꾸면 contract test와 DB 테스트가 필요하다.
- stale+deleted 섞인 충돌의 덮어쓰기 동작을 바꾸지 마라. 이유: 승인 범위 밖이다. summary에 known-issue로 적는다.
- `dialogs.shown` 의 충돌 항목 형식을 바꾸지 마라. 이유: 기존 GUI 테스트가 그 형식을 단언한다.
- 기존 테스트를 깨뜨리지 마라.
