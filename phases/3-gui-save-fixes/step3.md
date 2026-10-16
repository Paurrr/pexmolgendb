# Step 3: device-switch-save

## 배경 (phase 3 공통)

이 저장소는 이미 여러 명이 쓰는 도구다. 지금은 **에러·버그만 고친다**(CLAUDE.md, ADR-015). phase 3은 GUI 저장 흐름(`controllers/device_tab.py`, `device_table.py`, `parameter_tab.py`, `main_window.py`, `device_tab_toolbar.py`)의 버그를 고친다. 저장 함수가 "저장했다/사용자가 그만뒀다" 를 돌려주지 않아 취소해도 "Saved" 가 뜨고 화면이 넘어가는 문제, Database → Save 가 탭을 저장하지 않는 문제, 내 device 저장 뒤 내 탭 저장이 나 자신과 충돌하는 문제, process 전환·목록 갱신에서 편집이 말없이 사라지는 문제다. 반환 계약을 바꾸는 step(0, 1)이 먼저 끝나고 호출부 step(2, 3, 5)이 그 계약을 쓴다.

모든 step에 같은 규칙이 적용된다.
1. 아래 "버그"는 **분석 에이전트의 주장**이다. 먼저 실패하는 테스트로 재현하고, RED 출력(테스트 이름과 실패한 단언)을 summary에 적는다.
2. RED는 **Windows 개발 PC에서** 보여야 한다. `posix_only` 테스트는 개발 PC에서 skip되므로 버그를 증명하지 못한다.
3. 재현되지 않으면 `src/` 를 고치지 않는다. 테스트는 특성 테스트로 남기고 `"status": "completed"`, `"summary": "not reproduced: <이유>"` 로 끝낸다.
4. 고친 뒤 수정을 손으로 되돌려 새 테스트가 실패하는지 확인하고 다시 고친다(변이 검사). `git checkout`/`git stash` 로 되돌리지 마라. 이유: 같은 step의 테스트 변경까지 사라진다.
5. 이 파일의 행 번호는 2026-10-17 기준 대략값이다. 이름으로 찾아라.

GUI 테스트 기반은 phase `2-gui-test-infra` 가 만들었다. 아래 이름을 그대로 쓴다.
- `tests/gui/conftest.py`: offscreen. autouse `dialogs` fixture가 모달을 가로챈다. `dialogs.answer_question(*bools)` 는 Yes/No 질문(`utils/dialogs.question`)에, `dialogs.answer_conflict(*choices)` 는 충돌 대화상자에 순서대로 답한다(`genviewer.dialogs.conflict` 의 `RELOAD`/`OVERWRITE`/`CANCEL`). 뜬 것은 `dialogs.shown` 에 `(kind, title, text)` 로 쌓이고, 답을 넣지 않은 모달은 AssertionError를 낸다.
- fixture: `store`(FakeStore. process "sf2p" 에 device "nfet_a", "nfet_b", process "sf4u" 에 device 하나. device마다 탭 두 개에 행이 있다), `device_tab_ctrl`(가짜에 붙어 이미 접속한 DeviceTabController), `main_window`(가짜 위의 MainWindowController와 MainWindow. teardown이 shutdown과 close를 한다).
- `tests/gui_support/fakes.py`: `FakeStore`(`calls` 는 `(method, args)` 목록, `fail_next(method_name, exc)`), `FakeDatabase`, 실제 repo와 같은 의미의 가짜 Device/Parameter/Process/IO repository(값이 바뀐 행만 version +1, force가 아니면 version 불일치·사라진 행에 `StaleWriteError`).
- `tests/gui_support/helpers.py`: `select_process(ctrl, name)`, `select_device_row(ctrl, row)`, `edit_device_cell(ctrl, row, column, value)`, `edit_tab_cell(ctrl, tab_name, row, column, value)`. `ctrl` 은 DeviceTabController다(`main_window` 면 `.device_tab`).
- "bob 이 nfet_a 를 저장한다" 는 store에서 그 device의 version을 직접 1 올리는 것(값은 그대로, `updated_by="bob"`)이다. 다른 사용자의 탭 저장과 같다. `store.touch_device(device_id, actor="bob")` 를 쓴다(phase 2 의 FakeStore). device id·version은 화면 모델에서 읽는다(`ctrl.device_table.ui.model_safe().get_device(row)`).
- 새 GUI 테스트는 `tests/gui/test_<주제>.py` 에 둔다. "아무 일도 일어나지 않았다" 는 `qtbot.wait` 로 기다리지 말고 `store.calls` 를 `qtbot.waitUntil` 로 기다린 뒤 단언한다.
- 저장 경로에는 넓은 `except Exception`(`save_db`, `@report`)이 있어 답을 넣지 않은 모달의 AssertionError를 삼킬 수 있다. 대화상자가 떴는지·안 떴는지는 반환값, `store.calls`, `dialogs.shown` 으로 직접 단언한다.
- 알림: `main_window` 를 쓰면 `notifyRequested` 가 `MainWindow.notify` 를 거쳐 `dialogs.shown` 에 남는다(알림 상자는 답 없이 기록만 된다고 본다. 다르면 phase 2 방식을 따른다). `device_tab_ctrl` 만 쓰면 `ctrl.notifyRequested` 를 테스트 안에서 리스트에 연결해 확인한다.
- 필요한 헬퍼가 없거나 이름이 다르면(phase 2가 "not reproduced" 로 끝났거나 다르게 만들었으면) `tests/gui_support/` 에 직접 더한다. `src/` 에 테스트용 코드를 넣지 않는다.

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

다른 device를 누를 때 "Save Changes?" 에 예로 답했는데 탭 저장이 충돌 "취소" 로 끝나면, 탭을 새 device로 바꾸지 않고 편집을 그대로 남긴다(분석 G4). 지금은 저장 결과를 보지 않고 새 device를 읽어 탭 편집을 버린다.

## 읽어야 할 파일

- `/CLAUDE.md`, `/docs/UI_GUIDE.md`(원칙 2·4, 저장 충돌 세 갈래), `/docs/notes/known-issues.md`(K17, K20, K25 — 범위 밖)
- `src/genviewer/controllers/device_tab.py` — `on_current_row_changed` (~355-370, `@report("Load Failed")`), `_switch_device_by_index` (~420-454). `choice is None` 분기(~441)는 닿지 않는 코드다(K25)
- `src/genviewer/controllers/device_table.py` — `_on_current_changed` (~222-227), `prev_selected_device`/`last_selected_device` (~229-241)
- `src/genviewer/controllers/parameter_tab.py` — `save_all`(step 1: `-> bool`), `_write` (다시 읽기면 모든 섹션 `update_model` 후 `False`), `discard_all`, `set_device_to_section` (~117-127)
- `src/genviewer/controllers/tab_section.py` — `set_device`/`update_model` (~63-67, ~181-192: 고를 때마다 DB에서 다시 읽고 dirty를 끈다)
- 이전 step에서 수정된 파일: `controllers/device_table.py`, `controllers/parameter_tab.py`(`save_all -> bool`), `controllers/device_tab.py`(`save_db -> bool`), `controllers/main_window.py`(`_on_save_triggered`), `tests/gui/test_device_save_result.py`, `tests/gui/test_tab_save_result.py`, `tests/gui/test_save_entry_points.py`

## 버그

```python
if self.parameter_tab.is_dirty():
    choice = question(self.ui, "Save Changes", "You have unsaved changes. Do you want to save them?")
    if choice is None:
        return
    if choice:
        self.parameter_tab.save_all()
    else:
        self.parameter_tab.discard_all()
...
self.parameter_tab.set_device_to_section(cur_dev["id"], cur_dev.get("celltype"), cur_dev.get("version"))
```

`save_all()` 의 결과를 보지 않고 `set_device_to_section` 으로 간다. 그러면 모든 탭 섹션이 새 device를 DB에서 읽고 dirty를 끈다. 이전 device의 편집은 섹션의 모델 캐시에 잠시 남지만, 그 device를 다시 고르면 `update_model` 이 DB 값으로 덮는다.

재현: sf2p → nfet_a를 누른다 → 탭 셀 하나를 고친다(` *`) → 그 사이 bob이 nfet_a를 저장한다 → nfet_b를 누른다 → "Save Changes?" 예 → "Save Conflict" 에서 "취소"(툴팁: "편집 내용은 그대로 남는다") → 탭이 nfet_b로 바뀌고 ` *` 가 없다 → nfet_a를 다시 누르면 고친 내용이 없다.

## 작업

### 1. 테스트 먼저 (`tests/gui/test_device_switch_save.py`, 새 파일)

공통 준비: `device_tab_ctrl` 로 sf2p → `select_device_row(ctrl, 0)`(nfet_a) → `edit_tab_cell` 로 탭 셀 하나를 고친다. 충돌이 필요한 경우는 그 뒤 bob이 nfet_a를 저장한다. 그다음 `answer_question(...)`/`answer_conflict(...)` 를 넣고 `select_device_row(ctrl, 1)`(nfet_b).

| 경우 | 답 | 최종 상태 |
|---|---|---|
| 충돌 × 취소 | Yes, `CANCEL` | `parameter_tab.current_device_id` 가 nfet_a id, `parameter_tab.is_dirty()` True, 그 탭 모델에 고친 값, nfet_b에 대한 `fetch_by_device` 호출 없음. **수정 전 RED**: current_device_id가 nfet_b |
| 충돌 × 다시 읽기 | Yes, `RELOAD` | 편집이 이미 버려졌으므로 nfet_b로 넘어간다. `current_device_id` 가 nfet_b, dirty 아님, 가짜 repo의 nfet_a 탭은 seed 값 그대로 |
| 충돌 × 덮어쓰기 | Yes, `OVERWRITE` | 두 번째 `replace_many_for_device` 가 `force=True`, nfet_b로 넘어간다 |
| 충돌 없음 | Yes | 저장되고 nfet_b로 넘어간다(회귀) |
| 아니오 | No | 저장 호출 없음, 편집 버림, nfet_b로 넘어간다(회귀) |
| 탭 저장 예외 | Yes, `store.fail_next("replace_many_for_device", RuntimeError("boom"))` | "Load Failed" 오류 알림(`@report`, 지금과 같음), `current_device_id` 가 nfet_a, 편집 그대로 |

### 2. 수정 (`controllers/device_tab.py` 의 `_switch_device_by_index`)

- 예로 답했을 때 `parameter_tab.save_all()` 이 `False` 를 돌려주고 **아직 `parameter_tab.is_dirty()` 이면**(취소·창 닫기·repo 없음) `set_device_to_section` 전에 return한다. 지금 있는 `choice is None: return` 과 같은 자리의 조기 반환이다.
- `False` 여도 dirty가 아니면(다시 읽기: `_write` 가 이미 모든 섹션을 서버 내용으로 되돌렸다) 아니오와 같이 새 device로 넘어간다. 이유: 버릴 편집이 남지 않았는데 멈추면 표는 nfet_b를 고르고 탭은 nfet_a를 보여주는 어긋난 화면이 된다.
- 멈춘 뒤의 상태: 표의 선택은 새 행(nfet_b)에 있고, 탭은 이전 device(nfet_a)와 그 편집, ` *` 를 그대로 보여준다. 다음에 다른 행을 누르면 다시 묻고, 그때 저장은 `parameter_tab.current_device_id`(탭이 들고 있는 nfet_a)로 간다. 이 불변식을 깨지 마라.
- 예외는 지금처럼 `on_current_row_changed` 의 `@report("Load Failed")` 까지 올라간다. `set_device_to_section` 에 닿기 전이라 편집은 남는다.
- deleted × 덮어쓰기에서 나는 두 번째 `StaleWriteError`(K20)는 `@report` 가 다시 올린다. 지금 동작이고 바꾸지 않는다.

### 3. 문서

- 바꿀 문서는 없다. UI_GUIDE 원칙 2("편집 중인 내용을 말없이 버리지 않는다")와 충돌 대화상자의 "취소" 툴팁에 맞추는 수정이다.

## Acceptance Criteria

```bash
uv run pytest tests/gui/test_device_switch_save.py -q   # 새 테스트 통과 (수정 전에는 충돌 × 취소 경우가 실패해야 한다)
uv run ruff check src tests
uv run pytest tests/gui -q
uv run pytest -q
```

## 검증 절차

1. 위 AC 커맨드를 실행한다.
2. 아키텍처 체크리스트를 확인한다:
   - `controllers/device_tab.py` 의 `_switch_device_by_index` 만 바꿨는가?
   - 선택을 코드로 바꾸는 호출(`setCurrentIndex`, `selectRow`, `clearSelection`)을 더하지 않았는가?
   - 질문 제목·문구("Save Changes", "You have unsaved changes. Do you want to save them?")가 그대로인가?
3. 결과에 따라 `phases/3-gui-save-fixes/index.json` 의 step 3을 업데이트한다:
   - 성공 → `"status": "completed"`, `"summary": "_switch_device_by_index: 예 + 탭 저장 False + 아직 dirty면 set_device_to_section 전에 멈춤(다시 읽기는 진행). RED: <테스트 이름>. tests/gui/test_device_switch_save.py"`
   - 재현 안 됨 → `"status": "completed"`, `"summary": "not reproduced: <이유>"`
   - 수정 3회 시도 후에도 실패 → `"status": "error"`, `"error_message": "구체적 에러 내용"`
   - 사용자 개입 필요 → `"status": "blocked"`, `"blocked_reason": "구체적 사유"` 후 즉시 중단

## 금지사항

- 멈출 때 이전 행을 코드로 다시 선택하지 마라(`setCurrentIndex`, `selectRow`, `blockSignals` 로 감싼 선택 포함). 이유: `currentRowChanged` 가 다시 들어와 `_switch_device_by_index` 가 재진입하고, `DeviceTableController._on_current_changed` 의 prev/cur 추적이 꼬인다. 시그널을 막으면 추적이 실제 선택과 어긋난다(K17과 같은 부류).
- `choice is None` 분기를 지우지 마라. 이유: 닿지 않는 코드지만 동작에 영향이 없어 기록만 했다(K25, 범위 밖).
- K17(모델 reset 뒤 같은 행 재클릭이 탭을 다시 읽음)을 고치지 마라. 이유: 선택 추적 구조 문제로 step 6이 재현만 한다.
- 예외 경로를 `report_error` 로 바꾸거나 제목("Load Failed")을 바꾸지 마라. 이유: 지금도 전환이 멈추고 편집이 남는다. 문구 변경은 범위 밖이다.
- 기존 테스트를 깨뜨리지 마라.
