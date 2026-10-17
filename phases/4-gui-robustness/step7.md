# Step 7: deleted-process-revert

## 배경 (phase 4 공통)

이 저장소는 이미 여러 명이 쓰는 도구다. 지금은 **에러·버그만 고친다**(CLAUDE.md, ADR-015). phase 4는 GUI가 실패·경합 상황에서 데이터를 잘못 쓰거나 죽는 버그를 한 step에 하나씩 고친다(탭 로드 실패, 탭 섹션 입력, "+" 탭, 필터 중 정렬, DB 재접속, 창 닫기, Virtuoso 소켓 워커, 지운 process 되돌림). phase 3(`3-gui-save-fixes`)이 먼저 끝나 있다. 저장 함수가 결과를 돌려주고(`save_all() -> bool`, `DeviceTabController.save_db() -> bool`), `select_process_silently` 가 생겼다. 그 밖에 `deviceVersionBumped`/`adopt_device_version`(내 device 저장 뒤 탭이 version을 따라간다), `DeviceTabController._save_before_process_change`(process 전환 전 질문·저장), `DeviceTableModel.is_row_changed`, device 표 붙여넣기의 `Unsaved Changes` 거부, `save_all` 의 `Save Skipped` 경고가 있다. 정확한 반환 계약은 코드와 `phases/3-gui-save-fixes/index.json` 의 summary로 확인하라.

모든 step에 같은 규칙이 적용된다.
1. 아래 "버그"는 **리뷰의 주장**이다. 먼저 실패하는 테스트로 재현하고, RED 출력(테스트 이름과 실패한 단언)을 summary에 적는다.
2. RED는 **Windows 개발 PC에서** 보여야 한다. `posix_only` 테스트는 개발 PC에서 skip되므로 버그를 증명하지 못한다.
3. 재현되지 않으면 `src/` 를 고치지 않는다. 테스트는 특성 테스트로 남기고 `"status": "completed"`, `"summary": "not reproduced: <이유>"` 로 끝낸다.
4. 고친 뒤 수정을 손으로 되돌려 새 테스트가 실패하는지 확인하고 다시 고친다(변이 검사). `git checkout`/`git stash` 로 되돌리지 마라. 이유: 같은 step의 테스트 변경까지 사라진다.
5. 이 파일의 행 번호는 2026-10-17(phase 3 직후) 기준 대략값이다. phase 4의 앞 step이 같은 파일을 바꿨을 수 있으니 이름으로 찾아라.

GUI 테스트 기반은 phase 2(`2-gui-test-infra`)가 만들었다. 아래 이름을 그대로 쓰고, 같은 일을 하는 것을 새로 만들지 마라. 작업 전에 `tests/gui/conftest.py`·`tests/gui_support/` 를 읽고, 이 파일의 서술과 다르면 실제 코드를 따른다.
- 대화상자 대역은 `tests/gui_support/dialogs.py` 의 `FakeDialogs` 이고 autouse `dialogs` fixture로 들어온다. `dialogs.answer_question(*bools)` 는 Yes/No 질문에, `dialogs.answer_conflict(*choices)` 는 충돌 대화상자에 순서대로 답한다(`genviewer.dialogs.conflict` 의 `RELOAD`/`OVERWRITE`/`CANCEL`). 뜬 상자는 `dialogs.shown` 에 `(kind, title, text)` 로 쌓인다. kind는 `info`/`warning`/`error`/`critical`/`question`, 충돌 대화상자는 `("conflict", "Save Conflict", <충돌 설명>)` 이다.
- 답을 정하지 않은 모달은 `AssertionError` 를 내고 `dialogs.unexpected` 에 남는다. `@report` 가 그 예외를 삼키므로 실패는 **teardown에서** 드러난다. 쓰이지 않고 남은 답도 teardown 실패다.
- `device_tab_ctrl` 은 가짜에 붙어 이미 접속한 `DeviceTabController` 이고 `notifyRequested` 를 `dialogs.record_notify` 에 이어 두었다(알림도 `dialogs.shown` 에서 본다).
- 시드(`seeded_store()`): process `sf2p`(device `nfet_a`, `nfet_b`), `sf4u`(device `pfet_a`). 탭은 `"InstTerm"`·`"InstSchParam"`. id는 `store.find_device("pfet_a")["id"]` 로 얻는다. 접속하면 `sf2p` 가 자동으로 선택된다. autouse로 `GENDB_APP_USER=tester` 다.
- `store.calls` 는 `(메서드 이름, 인자 dict의 deep copy)` 이고 호출이 **끝난 뒤**(예외로 끝나도) 기록된다. `store.calls_of(name)`, `store.fail_next(name, exc)`.
- 다른 사용자가 process를 지우는 흉내는 `ctrl.device_tab_toolbar.repo.delete("sf4u", actor="bob")` 다(가짜 `FakeProcessRepository.delete` 가 그 process의 device·탭 행을 지운다. `calls` 에 `delete` 로 남는다).
- `tests/gui_support/helpers.py`: `select_process(ctrl, name)`, `select_device_row(ctrl, row)`, `edit_device_cell(ctrl, row, column, value)`, `edit_tab_cell(ctrl, tab_name, row, column, value)`. helpers는 기다리지 않는다. 기다림은 테스트가 `qtbot.waitUntil` 로 한다.
- "아무 일도 일어나지 않았다" 를 `qtbot.wait` 고정 대기로 확인하지 않는다. `store.calls` 를 `qtbot.waitUntil` 로 기다린 뒤 단언한다.
- 비슷한 테스트의 본보기: `tests/gui/test_process_change_save.py`(되돌림 단언 `assert_stayed_on_sf2p`), `tests/gui/test_process_list_refresh.py`(`open_sf4u`, 다른 사용자의 process 삭제, Remove Process).

## 이 step의 목적

(**사용자 승인 2026-10-17**, phase 3 마무리 리뷰에서 재현) 지금 process가 지워졌는데 저장하지 않은 편집이 남아 있을 때, process 전환이 저장 취소·실패로 멈추면 **콤보와 device 표가 서로 다른 process를 가리키는** 상태가 된다. 이를 막는다. 승인된 동작: **이전 process가 콤보 목록에 없으면 되돌리지 않고 새 process로 넘어간다.** 그 편집은 저장할 곳(process)이 이미 없다. 이전 process가 목록에 있으면 지금처럼 되돌린다(phase 3 step 5 동작 그대로).

## 읽어야 할 파일

- `/CLAUDE.md`, `/docs/UI_GUIDE.md`(원칙 2·4), `/docs/ARCHITECTURE.md`(데이터 흐름 → 저장 결과), `/docs/ADR.md`(ADR-004 의 "phase 3 보강")
- `src/genviewer/controllers/device_tab.py` — `on_process_changed` (~391-416: `_save_before_process_change()` 가 False면 `select_process_silently(self.device_table.current_process)` 후 return), `_save_before_process_change` (~418-454)
- `src/genviewer/controllers/device_tab_toolbar.py` — `remove_process` (~101-131, 지운 뒤 `refresh_processes()`), `refresh_processes` (~133-138), `select_process_silently` (~140-142)
- `src/genviewer/views/device_tab_toolbar.py` — `set_processes` (~157-171: 지금 process가 목록에서 사라졌을 때만 최종 이름으로 `currentTextChanged` 를 한 번 낸다), `select_process_silently` (~177-183: 목록에 없는 이름이면 아무것도 하지 않는다)
- `tests/gui/test_process_change_save.py`, `tests/gui/test_process_list_refresh.py`
- 이전 step에서 수정된 파일: phase 4 step 0~6이 바꾼 파일 전부(`git diff main...HEAD --stat` 으로 확인). 특히 step 4(connect-db)가 `controllers/device_tab.py` 의 접속 순서를 바꿨다.

## 버그

```python
def on_process_changed(self, process_name: str):
    if process_name and not self._save_before_process_change():
        self.device_tab_toolbar.select_process_silently(
            self.device_table.current_process
        )
        return
```

이전 process가 지워졌으면 `set_processes` 가 콤보를 이미 첫 process로 바꾼 뒤 `currentTextChanged` 를 낸다. 저장이 취소되거나 실패하면 위 코드가 이전 이름으로 되돌리려 하지만, 그 이름은 목록에 없어서 `select_process_silently` 가 아무것도 하지 않는다. 결과는 콤보 "sf2p", `device_table.current_process == "sf4u"`(지워진 process), 표에는 지워진 device와 그 편집이 남는다. 그 상태에서 저장하면 다시 "deleted" 충돌이 나고, 콤보에서 "sf2p" 를 다시 골라도 텍스트가 같아 신호가 나지 않는다.

닿는 경로 두 개(phase 3 마무리 때 아래 순서로 재현했다. 둘 다 `assert 'sf2p' == 'sf4u'`):
1. **다른 사용자가 지움**: sf4u를 열고 pfet_a Description을 고친다 → bob이 sf4u를 지운다 → `refresh_processes()`(CSV 불러오기·재접속·Add Process도 이것을 부른다) → "Save Changes?" 예 → 충돌 대화상자 취소.
2. **내가 지움**: sf4u를 열고 고친다 → `remove_process("sf4u")` → "Remove Process" 예 → "Save Changes?" 예 → 충돌 대화상자 취소.

phase 3 전에는 1번 경로에서 편집이 말없이 사라졌지만 콤보와 표는 일치했다. 2번 경로에서는 지운 이름이 콤보에 남았다(phase 3 step 4가 고침). 이것은 주장이다. 먼저 재현하라.

## 작업

### 결과 × 상태 (`on_process_changed`, 새 process 이름이 비어 있지 않을 때)

| 이전 process | `_save_before_process_change()` | 동작 |
|---|---|---|
| 목록에 있음 | True | 넘어간다(지금과 같다) |
| 목록에 있음 | False(취소·예외로 편집이 남음) | 콤보를 시그널 없이 이전 process로 되돌리고 멈춘다(지금과 같다. phase 3 step 5 테스트가 지킨다) |
| 목록에 없음(지워짐) | True(아니오, 다시 읽기, 저장 성공) | 넘어간다(지금과 같다) |
| 목록에 없음(지워짐) | False(취소, 저장 예외) | **넘어간다.** `clear`/배너 숨김/로그/`get_process_id`/`set_current_process*`/`refresh_devices`/`_clear_tabs` 를 평소처럼 한다. 저장 예외는 `_save_before_process_change` 가 이미 "Save Devices Failed"/"Save Tabs Failed" 로 알렸다 |

- "목록에 없음" 은 콤보에서 그 이름을 찾지 못한 것이다. 판단은 `select_process_silently` 의 결과로 한다: `select_process_silently(name) -> bool`(찾아서 골랐으면 True, 목록에 없으면 아무것도 하지 않고 False). view·controller 둘 다 bool을 돌려주게 한다. 기존 호출부와 phase 3 테스트(`test_select_process_silently_*`)의 단언은 그대로 통과해야 한다.
- 넘어갈 때 `processChanged` 를 다시 내지 않는다(콤보는 이미 새 process다).

### 1. 테스트 먼저 (`tests/gui/test_deleted_process_revert.py`, 새 파일)

공통 준비: `device_tab_ctrl`, `store`, `dialogs`. sf4u를 열고(`select_process` + `qtbot.waitUntil(lambda: ctrl.device_table.current_process == "sf4u")`, 행 1개까지 기다림) pfet_a(0행)의 `description` 을 고친다. 단언 묶음 "sf2p로 넘어갔다": 콤보 `currentText() == "sf2p"`, `ctrl.device_table.current_process == "sf2p"`, `current_process_id` 가 sf2p의 id, 모델의 device 이름이 `["nfet_a", "nfet_b"]`, `ctrl.device_table.is_dirty() is False`.

- **다른 사용자가 지움 + 취소**: bob이 sf4u를 지운다 → `dialogs.answer_question(True)`, `dialogs.answer_conflict(CANCEL)` → `ctrl.device_tab_toolbar.refresh_processes()` → `upsert_devices` 호출이 기록될 때까지 기다린 뒤 "sf2p로 넘어갔다". **수정 전에는 `current_process == "sf4u"` 로 실패해야 한다.**
- **내가 지움 + 취소**: `dialogs.answer_question(True, True)`("Remove Process", "Save Changes"), `answer_conflict(CANCEL)` → `remove_process("sf4u")` → "sf2p로 넘어갔다", 콤보 목록에 "sf4u" 가 없다. **수정 전에는 실패해야 한다.**
- **다른 사용자가 지움 + 저장 예외**: `store.fail_next("upsert_devices", RuntimeError("boom"))`, `answer_question(True)` → `refresh_processes()` → `dialogs.shown` 에 "Save Devices Failed" 오류, "sf2p로 넘어갔다". **수정 전에는 실패해야 한다.**
- **탭만 편집 + 다른 사용자가 지움 + 취소**: sf4u의 pfet_a를 골라 InstTerm 0행을 고친다(device 표는 그대로) → bob이 지운다 → `answer_question(True)` → 탭 저장이 부딪히는 충돌에 `answer_conflict(CANCEL)` → "sf2p로 넘어갔다", `ctrl.parameter_tab.is_dirty() is False`. 가짜가 이 경우 충돌 대신 다른 예외를 내면 그 실제 동작(알림 제목)에 맞춰 단언하고 summary에 적는다. **수정 전에는 실패해야 한다.**
- **회귀 — 아니오**: bob이 지운다 → `answer_question(False)` → 넘어간다(수정 전에도 통과).
- **회귀 — 이전 process가 남아 있으면 되돌린다**: `tests/gui/test_process_change_save.py` 의 되돌림 테스트가 그대로 통과한다(새로 쓰지 않는다).
- **`select_process_silently` 의 반환값**: 있는 이름이면 True, 없는 이름이면 False이고 콤보는 그대로다.
- 넘어가는 경우마다 `ctrl.device_tab_toolbar.processChanged` 를 리스트에 연결해 `refresh_processes()`/`remove_process` 뒤 신호가 `["sf2p"]` 한 번뿐인지 본다.

### 2. 수정

- `views/device_tab_toolbar.py`, `controllers/device_tab_toolbar.py`: `select_process_silently(name) -> bool`.
- `controllers/device_tab.py` `on_process_changed`: 저장이 False면 `select_process_silently(이전 process)` 를 부르고, True(되돌렸다)일 때만 return한다. False(목록에 없음)면 아래 평소 경로로 넘어간다. 주석은 지금 주석 옆에 한두 줄로 이유를 적는다("지워진 process에는 되돌릴 곳도, 편집을 저장할 곳도 없다").

### 3. 문서

- 이 step에서는 docs를 바꾸지 않는다(phase 마무리에서 ADR-004 "phase 3 보강" 에 한 줄 더한다).

## Acceptance Criteria

```bash
uv run pytest tests/gui/test_deleted_process_revert.py -q   # 새 테스트 통과 (수정 전에는 취소·예외 테스트가 실패해야 한다)
uv run pytest tests/gui/test_process_change_save.py tests/gui/test_process_list_refresh.py -q   # phase 3 되돌림·목록 테스트 그대로 통과
uv run ruff check src tests
uv run pytest -q
```

## 검증 절차

1. 위 AC 커맨드를 실행한다.
2. 아키텍처 체크리스트를 확인한다:
   - `views/` 가 controllers를 import하지 않는가(레이어 표)? 판단은 `DeviceTabController` 가 한다.
   - 새 사용자 문구(알림·로그·질문)를 더하지 않았는가(ADR-015, UI_GUIDE 문구)?
   - 이전 process가 목록에 있는 경우의 되돌림(phase 3 step 5)이 그대로인가?
3. 결과에 따라 `phases/4-gui-robustness/index.json` 의 step 7을 업데이트한다:
   - 성공 → `"status": "completed"`, `"summary": "on_process_changed: 저장 취소·실패 뒤 이전 process가 목록에 없으면(지워짐) 되돌리지 않고 넘어간다. select_process_silently -> bool. RED: <테스트 이름과 단언>. tests/gui/test_deleted_process_revert.py"`
   - 재현 안 됨 → `"status": "completed"`, `"summary": "not reproduced: <이유>"`
   - 수정 3회 시도 후에도 실패 → `"status": "error"`, `"error_message": "구체적 에러 내용"`
   - 사용자 개입 필요 → `"status": "blocked"`, `"blocked_reason": "구체적 사유"` 후 즉시 중단

## 금지사항

- 지워진 이름을 콤보에 다시 넣거나 지워진 process를 다시 만들지 마라(`get_or_create_id` 로 이전 이름을 부르지 마라). 이유: 지운 process가 되살아난다(phase 3 step 4가 막은 버그).
- 이전 process가 목록에 있을 때의 동작(되돌림)을 바꾸지 마라. 이유: phase 3 step 5에서 승인·고정된 동작이다.
- "Save Changes" 질문을 건너뛰거나 문구를 바꾸지 마라. 지워졌다는 새 알림·로그도 더하지 마라. 이유: 승인된 범위는 "넘어간다" 뿐이다(ADR-015). 사용자는 충돌 대화상자의 "deleted" 설명으로 이미 안다.
- Remove Process 뒤에 "Save Changes" 를 묻는 흐름 자체를 바꾸지 마라. 이유: 이 step의 범위가 아니다. 이상하다고 보면 summary에 적는다.
- device 표 선택을 코드로 바꾸지 마라(`setCurrentIndex`, `selectRow`). 이유: 전환 처리가 다시 들어온다(ADR-004 phase 3 보강).
- 기존 테스트를 깨뜨리지 마라.
