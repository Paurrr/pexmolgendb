# Step 2: paste-tab-version

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

(버그, K38) device 표에 붙여넣으면 device 행을 바로 저장한 뒤 복사한 탭 행을 그 새 device에 쓴다. 그런데 그 탭 쓰기가 `expected_version=None` 으로 나가 낙관적 잠금 확인을 건너뛴다(ADR-004). 붙여넣은 device의 저장된 version을 탭 쓰기까지 넘긴다.

이 step은 **계약 step**이다. `DeviceTableController.pasteRequested` 시그널이 version을 싣게 바꾸고, 받는 쪽(`DeviceTabController.on_paste_requested`)을 같은 step에서 맞춘다. 시그널을 내는 쪽과 받는 쪽은 따로 바꿀 수 없다. 다음 step 3(붙여넣기의 탭 편집 거부)이 같은 `paste_rows` 를 바꾸므로 이 step이 먼저다.

## 읽어야 할 파일

- `/CLAUDE.md`(쓰기는 version 낙관적 잠금), `/docs/ADR.md`(ADR-004), `/docs/UI_GUIDE.md`("device 표 붙여넣기는 바로 저장되고 목록을 다시 읽는다")
- `src/genviewer/controllers/device_table.py`
  - `pasteRequested = Signal(object, str, dict)` (~37)
  - `paste_rows` (~176-211): 행마다 `save_device` → `pasteRequested.emit(id, celltype, related)`, 끝에 `refresh_devices()`
  - `save_device` (~327-335)
- `src/genviewer/controllers/device_tab.py`: `on_paste_requested` (~472-479). 모델에서 id로 version을 찾지만, 그 행은 `refresh_devices()` 전이라 모델에 id가 없다.
- `src/genviewer/controllers/parameter_tab.py`: `paste_payload` (~179-201), `_write` (~80-99), `_apply` (~101-117)
- `src/genviewer/service/repo/device.py`: `upsert_device` (~97-155). 새 행은 `RETURNING id, version` 으로 `device["version"]` 을 채운다.
- `src/genviewer/service/repo/parameter.py`: `replace_many_for_device` (~40-85). `expected_version` 이 None이면 비교하지 않는다.
- `tests/gui_support/fakes.py`: `FakeDeviceRepository.upsert_device` (새 행에 version을 채운다), `FakeParameterRepository.replace_many_for_device`
- `tests/gui/test_device_save_guards.py`: G15b 붙여넣기 절(~180-215, `open_sf2p`, `record_notifications`, `model_of`)

## 버그

```python
@Slot()
def on_paste_requested(self, device_id, device_type, payload: dict):
    version = None
    for dev in self.device_table.ui.model_safe().get_devices():
        if dev.get("id") == device_id:
            version = dev.get("version")
            break
    self.parameter_tab.paste_payload(device_id, device_type, payload, version)
```

`paste_rows` 는 `model.insert_row` 로 id 없는 행을 넣고 `save_device` 로 저장한 뒤 바로 `pasteRequested` 를 낸다. 모델 행에는 아직 id가 없다. `refresh_devices()` 는 반복이 끝난 뒤에 돈다. 그래서 위 반복은 늘 못 찾고 `version=None` 이 되고, 탭 쓰기가 version 확인 없이 나간다. 이것은 주장이다. 먼저 재현하라.

## 작업

### 계약

- `DeviceTableController.pasteRequested` 는 `(device_id, celltype, related_rows, version)` 을 싣는다. version은 그 행을 저장한 `save_device` 가 돌려준 dict의 `"version"` 이다.
  - 시그널 타입은 `Signal(object, str, dict, object)` 처럼 None을 실을 수 있게 한다.
- `DeviceTabController.on_paste_requested(device_id, device_type, payload, version)` 은 받은 version을 그대로 `parameter_tab.paste_payload(..., version)` 에 넘긴다. 모델을 뒤지는 반복은 지운다.
- `ParameterTabController.paste_payload` 의 시그니처와 동작은 바꾸지 않는다.

### 결과 × 상태 (붙여넣은 행 하나의 탭 쓰기)

| 경우 | 탭 쓰기 | 결과 |
|---|---|---|
| 성공 | `replace_many_for_device(new_id, …, expected_version=<save_device 가 돌려준 version>)` | 탭 행이 저장되고 `mark_saved`. device version +1(`deviceVersionChanged`) |
| 그 사이 남이 새 device를 고침(stale) | 지금까지는 version 확인이 없어 덮어썼다. 이제 충돌 대화상자(`_write`)가 뜬다 | RELOAD: 섹션을 다시 읽고 붙여넣은 탭 행은 저장되지 않는다 / OVERWRITE: force로 쓴다 / CANCEL: 붙여넣은 탭 행이 dirty로 남는다. 모두 `_write` 의 기존 동작이다 |
| 그 사이 남이 새 device를 지움(deleted) | 지금처럼 deleted 충돌(step 0 뒤로 덮어쓰기는 내놓지 않는다) | RELOAD·CANCEL은 `_write` 기존 동작 |
| 탭 쓰기 예외(접속 끊김 등) | 지금처럼 `paste_rows` 의 `@report("Paste Failed")` 가 받는다 | 바뀌지 않는다 |
| 여러 행을 붙여넣음 | 행마다 자기 `save_device` 의 version으로 쓴다 | 다른 행의 version이 섞이지 않는다 |

### 1. 테스트 먼저 (`tests/gui/test_device_save_guards.py`, G15b 절 근처)

- **RED**: `open_sf2p(ctrl)` → `ctrl.device_table.copy_rows([1])` → `ctrl.device_table.paste_rows([1])` → `store.calls_of("replace_many_for_device")[-1]` 를 본다.
  - 그 호출의 `device_id` 는 새 device(가장 큰 id)다.
  - `expected_version` 은 None이 아니고, 그 값 + 1 == `store.devices[new_id]["version"]` 이다(탭 쓰기가 한 번 올렸다).
  - **수정 전에는 `expected_version is None` 으로 실패해야 한다.**
- **두 행 붙여넣기**: `copy_rows([0, 1])` → `paste_rows([1])` → 두 탭 쓰기의 `expected_version` 이 각 새 device의 저장 직후 version과 같다.
- **stale 경로가 이제 닿는다**: `store.fail_next("replace_many_for_device", StaleWriteError([Conflict(<id>, "nfet_b", "stale", "bob", None)]))` + `dialogs.answer_conflict(CANCEL)` → 붙여넣기가 끝난다. `dialogs.shown` 에 충돌이 한 번 있고, `@report` 오류 상자는 없다.
  - 가짜 `fail_next` 는 store를 건드리지 않고 예외만 낸다. 그래서 새 device의 id를 미리 알 수 없으면 `Conflict` 의 id는 아무 정수여도 된다. 단언은 충돌이 떴다는 것과 붙여넣은 탭 섹션이 dirty로 남았다는 것으로 한다.
  - 실제 동작이 이 서술과 다르면 실제 동작대로 단언하고 summary에 적는다.

### 2. 수정

위 "계약" 대로 `controllers/device_table.py` 와 `controllers/device_tab.py` 를 고친다.

### 3. 변이 검사

`paste_rows` 가 version 자리에 None을 싣게 손으로 바꾼다. RED 테스트가 실패하는지 본다. 그리고 되돌린다.

## Acceptance Criteria

```bash
uv run pytest tests/gui/test_device_save_guards.py -q   # 새 테스트 통과 (수정 전에는 expected_version 테스트가 실패해야 한다)
uv run ruff check src tests
uv run pytest tests/gui -q
uv run pytest -q
```

## 검증 절차

1. 위 AC 커맨드를 실행한다.
2. 아키텍처 체크리스트를 확인한다.
   - 시그널을 내는 쪽과 받는 쪽이 같이 바뀌었는가? `pasteRequested` 를 잇는 다른 곳이 없는가(`grep -rn pasteRequested src`)?
   - `paste_payload`·`_write`·repo·가짜 repo의 동작은 그대로인가?
   - 새 사용자 문구가 없는가?
3. 결과에 따라 `phases/10-gui-edit-safety/index.json` 의 step 2를 업데이트한다.
   - 성공 → `"status": "completed"`, `"summary": "K38: DeviceTableController.pasteRequested 가 (id, celltype, related, version) 을 싣고 on_paste_requested 가 그 version 을 paste_payload 에 넘김(모델 조회 삭제). RED: <테스트 이름과 단언>. 변이: <결과>. 다음 step 3 은 같은 paste_rows 에 탭 dirty 거부를 더한다"`
   - 재현 안 됨 → `"status": "completed"`, `"summary": "not reproduced: <이유>"`
   - 수정 3회 시도 후에도 실패 → `"status": "error"`, `"error_message": "구체적 에러 내용"`
   - 사용자 개입 필요 → `"status": "blocked"`, `"blocked_reason": "구체적 사유"` 후 즉시 중단

## 금지사항

- 붙여넣기 순서(행 저장 → 탭 쓰기 → 마지막에 `refresh_devices`)를 바꾸지 마라. 예를 들어 반복 안에서 `refresh_devices` 를 부르지 마라. 이유: 이 버그는 version을 넘기면 고쳐진다. 순서를 바꾸면 화면 선택·dirty·etag 기준점이 함께 바뀐다.
- 탭 쓰기를 `force=True` 로 바꾸거나 version 확인을 다른 방법으로 끄지 마라. 이유: 확인을 되살리는 것이 이 step의 목적이다.
- step 3의 일(탭 편집이 남았을 때 붙여넣기 거부)을 미리 하지 마라. 이유: 별도 승인 항목이고 step 3이 테스트와 함께 한다.
- repo와 가짜 repo의 `upsert_device`·`replace_many_for_device` 를 바꾸지 마라. 이유: 의미를 바꾸면 contract test와 DB 테스트가 필요하다.
- 기존 테스트를 깨뜨리지 마라.
