# Step 3: paste-tab-dirty

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

(**사용자 승인 2026-10-17**, K37) 탭에 저장하지 않은 편집이 있을 때 device 표에 붙여넣으면, `paste_payload` 의 `set_device_to_section` 이 탭을 붙여넣은 device로 바꾼다. 그 편집은 화면에서 사라지고, 원래 device를 다시 고르면 서버 내용으로 덮인다. 이 경우 붙여넣지 않는다.

**승인된 동작**: "탭에 저장 안 한 편집이 있으면 device 표 붙여넣기를 하지 않고 'Unsaved Changes' 경고(탭 편집용 본문)를 띄운다."

경고는 정확히 다음과 같다(severity `warn`).
- 제목: `Unsaved Changes`
- 본문: `"저장하지 않은 탭 편집이 있어 붙여넣지 않았다.\n붙여넣기는 바로 저장하고 탭을 다시 읽으므로 그 편집이 사라진다. 먼저 저장할 것."`

phase 3 step 7(G15b)이 device 표 편집이 남았을 때의 같은 거부를 만들었다. 이 step은 그 옆에 탭 편집 검사를 더한다. step 2가 같은 `paste_rows` 의 `pasteRequested` 에 version을 실었다(summary 확인).

## 읽어야 할 파일

- `/CLAUDE.md`, `/docs/UI_GUIDE.md`(원칙 2, "device 표 붙여넣기는 바로 저장되고 … 저장 안 한 device 편집이 있으면 붙여넣지 않고 경고한다"), `/docs/ARCHITECTURE.md`("현재 어긋난 곳": 컨트롤러끼리 private 멤버를 부르는 것을 따라 하지 않는다)
- `src/genviewer/controllers/device_table.py`
  - `paste_rows` (~176-211): 앞의 `if self.is_dirty():` 경고가 device 표 편집 거부다. 그 아래 행 저장과 `pasteRequested`.
  - `__init__` (~43-68)
- `src/genviewer/controllers/device_tab.py`
  - `__init__` (~45-96): 하위 컨트롤러를 만들고 시그널을 잇는다.
  - `on_paste_requested` (~472 근처, step 2가 바꿨다)
- `src/genviewer/controllers/parameter_tab.py`: `is_dirty` (~47-48), `paste_payload` (~179-201)
- `src/genviewer/controllers/device_table.py` 의 `_on_context_menu`(붙여넣기 메뉴)와 `ui.pasteRequested`(Ctrl+V). 둘 다 `paste_rows` 로 온다.
- `tests/gui/test_device_save_guards.py`: G15b 절. `test_pasting_with_unsaved_device_edits_is_refused_with_a_warning`, `test_pasting_without_unsaved_edits_saves_the_pasted_row` (~188-217), `open_sf2p`, `record_notifications`, `titled`, `model_of`
- `tests/gui/test_tab_version_sync.py`: `open_nfet_a`·`edit_nfet_a_tab` (탭 편집을 만드는 본보기)

## 승인된 동작 변경

지금은 탭에 편집이 남아 있어도 붙여넣는다. 붙여넣은 device로 탭이 바뀌고 `is_dirty()` 는 False가 된다. 편집은 원래 device의 캐시 모델에 남지만 화면에서 사라진다. 그 device를 다시 고르면 `update_model` 이 서버 행으로 덮는다(분석 결과). 승인된 동작으로 바꾼다.

## 작업

### 결과 × 상태 (`paste_rows`, 복사한 행이 있을 때)

| device 표 dirty | 탭 dirty | 동작 |
|---|---|---|
| 아니오 | 아니오 | 지금처럼 붙여넣는다(바로 저장, 탭 쓰기, 다시 읽기) |
| 예 | 아니오 | 지금처럼 device 편집 경고(기존 문구)를 띄우고 붙여넣지 않는다 |
| 예 | 예 | device 편집 경고 **하나만** 띄우고 붙여넣지 않는다(기존 검사가 먼저다) |
| 아니오 | 예 | **새 경고**(위 문구)를 띄우고 붙여넣지 않는다. `upsert_device` 호출이 없고, 탭 모델·dirty·`current_device_id`·device 표 행 수가 그대로다 |

- 복사한 행이 없거나 모델이 없으면 지금처럼 아무것도 하지 않는다(경고도 없다).
- 메뉴, Ctrl+V, 직접 호출이 모두 같은 `paste_rows` 를 지나므로 이 표 하나로 덮인다.

### 탭 dirty를 아는 방법

- `DeviceTableController` 가 `ParameterTabController` 를 알게 하거나 남의 private 멤버를 부르지 마라.
- `DeviceTabController.__init__` 이 검사 함수를 넘겨 준다. 예: `self.device_table.set_unsaved_tabs_check(self.parameter_tab.is_dirty)`.
- 넘겨 주지 않았을 때의 기본값은 "탭 편집 없음"(False)이다. `DeviceTableController` 를 단독으로 만드는 코드가 있으면 지금처럼 동작해야 한다.
- 이름은 정해도 되지만 공개 메서드여야 한다(밑줄로 시작하지 않는다).

### 1. 테스트 먼저 (`tests/gui/test_device_save_guards.py`, G15b 절)

- **RED**: `open_sf2p(ctrl)` → `select_device_row(ctrl, 0)` → 탭이 nfet_a를 읽을 때까지 기다린다 → `edit_tab_cell(ctrl, "InstTerm", 0, "cds_inst_term_name", "dd")` → `ctrl.device_table.copy_rows([1])` → `ctrl.device_table.paste_rows([1])`. 단언은 다음과 같다.
  - `titled(notes, "Unsaved Changes")` 가 위 경고 하나다.
  - `store.calls_of("upsert_device") == []`, `store.calls_of("replace_many_for_device") == []`
  - device 표 행이 2개다.
  - `ctrl.parameter_tab.current_device_id` 가 nfet_a이고, `is_dirty()` 이며, 탭 값이 `"dd"` 다.
  - **수정 전에는 `upsert_device` 가 불려 실패해야 한다.**
- **둘 다 dirty**: device Description과 탭을 둘 다 고친 뒤 붙여넣는다 → `Unsaved Changes` 가 하나뿐이고 본문이 기존 device 편집 문구다.
- 기존 두 G15b 테스트는 그대로 통과한다.

### 2. 수정

- `controllers/device_table.py`: 검사 함수를 받는 공개 메서드를 두고, `paste_rows` 의 device 편집 검사 **뒤에** 탭 편집 검사와 새 경고를 더한다.
- `controllers/device_tab.py`: 생성자에서 `parameter_tab.is_dirty` 를 넘긴다.
- 주석 한 줄로 이유를 적는다. 예: "붙여넣기는 탭을 붙여넣은 device로 바꿔 저장하지 않은 탭 편집이 사라진다(K37)".

### 3. 변이 검사

탭 편집 검사를 손으로 지워 RED 테스트가 실패하는지 본다. 검사 순서를 바꿔(탭 먼저) "둘 다 dirty" 테스트가 실패하는지도 본다. 둘 다 되돌린다.

## Acceptance Criteria

```bash
uv run pytest tests/gui/test_device_save_guards.py -q   # 새 테스트 통과 (수정 전에는 탭 dirty 붙여넣기 테스트가 실패해야 한다)
uv run ruff check src tests
uv run pytest tests/gui -q
uv run pytest -q
```

## 검증 절차

1. 위 AC 커맨드를 실행한다.
2. 아키텍처 체크리스트를 확인한다.
   - 새 문구는 승인된 제목·본문 하나뿐인가? 기존 device 편집 경고 문구는 그대로인가?
   - `DeviceTableController` 가 `ParameterTabController` 를 import하거나 그 private 멤버를 부르지 않는가?
   - 탭 편집이 없을 때의 붙여넣기는 그대로인가?
3. 결과에 따라 `phases/10-gui-edit-safety/index.json` 의 step 3을 업데이트한다.
   - 성공 → `"status": "completed"`, `"summary": "K37(승인): 탭에 저장 안 한 편집이 있으면 device 표 붙여넣기를 거부하고 Unsaved Changes(탭 편집 본문) 경고. DeviceTabController 가 parameter_tab.is_dirty 를 <메서드 이름> 으로 넘김(device 편집 검사가 먼저). RED: <테스트 이름과 단언>. 변이: <결과>"`
   - 수정 3회 시도 후에도 실패 → `"status": "error"`, `"error_message": "구체적 에러 내용"`
   - 사용자 개입 필요 → `"status": "blocked"`, `"blocked_reason": "구체적 사유"` 후 즉시 중단

## 금지사항

- 경고 대신 질문(저장할까요?)을 띄우거나 탭을 먼저 저장하지 마라. 이유: 승인된 동작은 "붙여넣지 않고 경고" 다.
- 기존 device 편집 경고의 문구와 순서를 바꾸지 마라. 이유: phase 3 step 7에서 고정된 동작이다.
- 탭 붙여넣기(`TabSectionController.paste_rows`, 탭 표 안의 Ctrl+V)를 건드리지 마라. 이유: 그것은 탭을 바꾸지 않는 다른 경로이고 승인 범위 밖이다.
- `ParameterTabController.paste_payload` 의 동작을 바꾸지 마라. 이유: 거부는 붙여넣기를 시작하기 전에 한다.
- 기존 테스트를 깨뜨리지 마라.
