# Step 1: same-row-reclick

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

(버그, K17) device 저장 뒤 같은 device 행을 다시 클릭하면, 저장하지 않은 탭 편집이 서버 내용으로 덮여 사라진다(UI_GUIDE 원칙 2). phase 3 step 6이 재현 테스트를 strict xfail로 남겨 두었다. 이 step에서 고치고 xfail을 뗀다.

## 읽어야 할 파일

- `/CLAUDE.md`(테스트 관례의 xfail 문단), `/docs/UI_GUIDE.md`(원칙 2), `/docs/ADR.md`(ADR-004 "phase 3 보강": 탭은 내 device 저장이 올린 version을 +1일 때만 따라간다), `/docs/ARCHITECTURE.md`(데이터 흐름 → version 동기화)
- `src/genviewer/controllers/device_tab.py`
  - `on_current_row_changed` (~382-397)
  - `_switch_device_by_index` (~487-524). 같은 device 분기(~496-500)가 늘 `set_device_to_section` 을 부른다.
- `src/genviewer/controllers/device_table.py`
  - `_on_current_changed` (~229-234), `prev_selected_device`/`last_selected_device` (~236-248)
  - `refresh_devices` (~262-304). 모델 reset 때문에 들고 있던 proxy index가 낡는다.
- `src/genviewer/controllers/parameter_tab.py`
  - `set_device_to_section` (~140-150): `current_device_id`·`current_version` 을 바꾸고 섹션마다 `set_device`
  - `is_dirty` (~47-48), `_clear_tabs` (~155-158), `adopt_device_version` (~119-132)
- `src/genviewer/controllers/tab_section.py`
  - `set_device` (~63-67), `update_model` (~182-201): device별 모델 캐시를 서버 행으로 `set_data` 한다
  - `is_dirty` (~152-155): `device_id` 가 None이면 False
- `tests/gui/test_tab_version_sync.py`
  - 모듈 docstring의 K17 줄(~9), `open_nfet_a`, `edit_nfet_a_tab`, `tab_value`, `EDITED`/`SEED`
  - `test_clicking_the_same_row_after_a_device_save_keeps_the_tab_edits` (~315-333, strict xfail)

## 버그

```python
if prev_dev and prev_dev.get("id") == cur_dev.get("id"):
    self.parameter_tab.set_device_to_section(
        cur_dev["id"], cur_dev.get("celltype"), cur_dev.get("version")
    )
    return
```

재현 순서는 다음과 같다.
1. nfet_a를 고르고 InstTerm 0행을 `"dd"` 로 고친다.
2. `device_table.save_all()` 을 부른다. device 편집이 없어도 `refresh_devices` 가 모델을 reset한다.
3. 0행을 다시 클릭한다.

그러면 이전 index와 지금 index가 둘 다 nfet_a라 같은 device 분기로 간다. `set_device_to_section` → `update_model` 이 캐시된 모델을 서버 행으로 덮어 `"dd"` 가 `"d"` 로 돌아간다. 질문도 없다.

분석에 따르면 `QPersistentModelIndex` 로 바꾸는 것만으로는 고쳐지지 않는다. 이전 index가 무효면 `prev_dev = cur_dev` 라 어차피 같은 분기로 들어온다. 원인은 같은 device 분기가 탭 상태를 보지 않고 늘 다시 읽는 것이다. 이것은 주장이다. 먼저 재현하라.

## 작업

### 결과 × 상태 (`_switch_device_by_index`, 클릭한 행이 탭이 지금 보이는 device와 같을 때)

| 탭 상태 | 동작 |
|---|---|
| 그 device를 보이고 있고(`parameter_tab.current_device_id == cur_dev["id"]`) dirty | **다시 읽지 않는다.** 탭 모델, dirty, `current_version`(내 device 저장 뒤 따라간 값)을 그대로 둔다. 질문도 없다 |
| 그 device를 보이고 있고 깨끗함 | 지금처럼 다시 읽는다(`set_device_to_section`). 깨끗한 탭의 다시 읽기는 잃는 것이 없고, 지금은 이것이 celltype·version을 새로 받는 길이다 |
| 비어 있음(`_clear_tabs` 뒤: Refresh, process 전환, 처음 클릭) | 지금처럼 읽는다. 섹션의 `device_id` 가 None이라 `is_dirty()` 가 False다. 그래서 `current_device_id` 가 옛 값으로 남아 있어도 첫 줄에 걸리지 않는다 |
| 다른 device를 보이고 있음 | 지금처럼 다른 device 분기(dirty면 "Save Changes" 질문, phase 3)로 간다 |

- 판단은 "탭이 실제로 그 device를 보이고 있고 dirty인가" 로 한다. 이전·지금 proxy index만으로 판단하지 마라. 이유: 모델 reset 뒤에는 그 index가 낡아 있다.
- `_clear_tabs` 나 `current_device_id` 를 지우는 새 코드는 넣지 않는다. 위 표의 세 번째 행은 지금 코드로 성립한다(재현 테스트로 확인하라). 성립하지 않으면 그 사실과 최소 수정을 summary에 적는다.

### 1. 테스트 먼저 (`tests/gui/test_tab_version_sync.py`)

- RED: xfail 표시를 떼기 전에 `uv run pytest tests/gui/test_tab_version_sync.py -q --runxfail -k same_row` 로 실패를 본다. 분석이 본 실패는 `assert 'd' == 'dd'` 다. 그 출력을 summary에 적는다.
- 같은 파일에 더한다.
  - **깨끗한 탭은 지금처럼 다시 읽는다**: nfet_a를 골라 편집 없이 `device_table.save_all()` 뒤 0행을 다시 클릭한다. `store.calls_of("fetch_by_device")` 가 늘어났는지 `qtbot.waitUntil(lambda: len(store.calls_of("fetch_by_device")) > n)` 으로 확인한다(특성 테스트, 수정 전에도 통과).
  - **Refresh 뒤 클릭은 읽는다**: nfet_a 탭을 고친다 → 서버 쪽 값을 `store.set_rows("inst_terms", nfet_a, …)` 로 바꾼다 → `ctrl.ui.refresh_banner.refreshRequested.emit()` 에 `answer_question(True)` → 0행 클릭 → 탭이 서버의 새 값을 보이고 dirty가 아니다.
  - **재클릭 뒤 탭 저장이 내 device 저장과 충돌하지 않는다**: 위 xfail 테스트의 흐름 뒤 `ctrl.parameter_tab.save_all()` 이 True이고, 충돌 대화상자가 없고, 서버 값이 `"dd"` 다.

### 2. 수정

- `controllers/device_tab.py` 의 `_switch_device_by_index` 같은 device 분기만 고친다. 위 표의 첫 행이면 return한다.
- 주석 한두 줄로 이유를 적는다. 예: "모델 reset 뒤 같은 행을 다시 눌러도 저장 안 한 탭 편집을 서버 내용으로 덮지 않는다(K17)".

### 3. xfail 떼기와 문서

- `test_clicking_the_same_row_after_a_device_save_keeps_the_tab_edits` 의 `@pytest.mark.xfail(...)` 를 지운다.
- 그 위의 `# -- K17 (고치지 않음) ---` 구분 주석은 내용에 맞게 고친다(예: `# -- K17 ---`).
- 모듈 docstring의 "K17(…)은 고치지 않고 xfail 로 재현만 한다." 줄을 지금 상태에 맞게 고친다.
- `/CLAUDE.md` 테스트 관례의 "(지금은 K17 하나)" 를 "(지금은 없다)" 로 고친다. 이 문장 말고는 CLAUDE.md를 바꾸지 마라.
- `docs/notes/known-issues.md` 의 K17은 이 step에서 지우지 않는다. phase 마무리의 docs 동기화가 지운다(phase 0~5의 관례).

### 4. 변이 검사

수정한 조건을 손으로 지워(늘 다시 읽게) xfail을 뗀 테스트가 `'d' == 'dd'` 로 실패하는지 본다. 그리고 되돌린다.

## Acceptance Criteria

```bash
uv run pytest tests/gui/test_tab_version_sync.py -q   # xfail 없이 전부 통과 (수정 전에는 --runxfail 로 같은 행 테스트가 실패해야 한다)
uv run pytest tests/gui/test_device_switch_save.py tests/gui/test_tab_section_load.py -q   # device 전환·탭 로드 테스트 그대로 통과
uv run ruff check src tests
uv run pytest tests/gui -q
uv run pytest -q                      # xfailed 가 0 이 된다 (기준선의 1 xfailed 가 passed 로)
```

## 검증 절차

1. 위 AC 커맨드를 실행한다.
2. 아키텍처 체크리스트를 확인한다.
   - 새 질문·알림·로그 문구를 더하지 않았는가(ADR-015)?
   - 깨끗한 탭의 같은 행 재클릭, 다른 device로의 전환, Refresh 뒤 클릭은 지금 동작 그대로인가?
   - device 표 선택을 코드로 바꾸지 않았는가?
3. 결과에 따라 `phases/10-gui-edit-safety/index.json` 의 step 1을 업데이트한다.
   - 성공 → `"status": "completed"`, `"summary": "K17: _switch_device_by_index 같은 device 분기에서 탭이 그 device 를 보이고 dirty 면 다시 읽지 않음. RED(--runxfail): test_clicking_the_same_row_after_a_device_save_keeps_the_tab_edits <단언>. strict xfail 제거, CLAUDE.md '(지금은 없다)'. 추가 테스트: <이름>. 변이: <결과>. known-issues K17 은 마무리에서 지움"`
   - 재현 안 됨 → `"status": "completed"`, `"summary": "not reproduced: <이유>"` (xfail은 그대로 둔다)
   - 수정 3회 시도 후에도 실패 → `"status": "error"`, `"error_message": "구체적 에러 내용"`
   - 사용자 개입 필요 → `"status": "blocked"`, `"blocked_reason": "구체적 사유"` 후 즉시 중단

## 금지사항

- device 선택 추적 구조(`_prev_proxy_index`/`_cur_proxy_index`, `QPersistentModelIndex` 도입 등)를 바꾸지 마라. 이유: 원인은 분기 조건이고, 선택 구조를 바꾸면 phase 3·4가 고정한 전환 동작이 함께 흔들린다. 구조 정리는 phase 16(SaveCoordinator)의 일이다.
- 깨끗한 탭에서 같은 행 재클릭의 다시 읽기를 없애지 마라. 이유: 버그 범위 밖이고, 지금은 그것이 celltype·version을 새로 받는 길이다.
- `_switch_device_by_index` 의 다른 분기(다른 device 전환의 질문·저장)와 `choice is None` 분기(K25)를 건드리지 마라. 이유: 범위 밖이다. K25는 phase 16에서 지운다.
- xfail을 떼지 않고 남겨 두지 마라. 이유: strict xfail이라 고치면 XPASS로 실패한다.
- 기존 테스트를 깨뜨리지 마라.
