# Step 6: filtered-save-order

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

(**사용자 승인 2026-10-17**, K19) Virtuoso device 목록을 받으면 device 표는 Virtuoso에 있는 이름(`S == "O"`)만 보인다(`refresh_devices` 의 필터). 이 상태에서 저장하면 `save_all` 이 **보이는 행에만** `order = 0..k-1` 을 다시 매긴다. 그래서 두 가지가 생긴다.
- 숨은 행과 순서값이 겹친다. `ORDER BY "order", id` 로 읽는 전체 목록과 내보내기 순서가 바뀐다.
- 편집 없이 저장해도 순서값이 바뀐 보이는 행의 version이 올라 남에게 충돌이 난다.

**승인된 동작**: "Virtuoso 목록으로 걸러 본 채 저장할 때 보이는 행에 0..k-1 대신 그 행들이 원래 갖던 순서값을 다시 나눠 준다."

## 읽어야 할 파일

- `/CLAUDE.md`, `/docs/ADR.md`(ADR-004), `/docs/ARCHITECTURE.md`(데이터 흐름 → device 저장, device 정렬), `/docs/UI_GUIDE.md`(정렬은 undo 가능한 저장 안 한 변경)
- `src/genviewer/controllers/device_table.py`
  - `refresh_devices` (~262-304): `fetch_devices_by_process` 의 모든 행 중 `device_state_data` 와 이름이 겹치는 것만 `visible_devices` 로 모델에 넣는다. 부분 문자열 매칭(`name in r["name"]`)은 의도로 판정했다(바꾸지 않는다).
  - `save_all` (~337-395): `for i, d in enumerate(devices): d["order"] = i`. **모델의 dict를 그 자리에서 바꾼다.** 취소된 저장 뒤에도 바뀐 값이 남는다.
  - `_write_devices` (~413-445)
- `src/genviewer/models/device_table.py`
  - `update_devices` (~105-110, 행을 복사해 넣고 기준점을 다시 잡음), `get_devices` (내부 리스트를 그대로 준다)
  - `insert_row`, `remove_rows`, `sort_rows`(~253-), `deleted_devices`, `_original_by_id`(불러올 때의 행)
- `src/genviewer/service/repo/device.py`
  - `fetch_devices_by_process` (~59-66, `ORDER BY "order", id`)
  - `_update_existing` (~302-356): `IS DISTINCT FROM` 가드로 값이 같으면 쓰지 않고 version도 올리지 않는다
- `tests/gui_support/fakes.py`: `FakeStore._devices_of`(같은 정렬), `FakeDeviceRepository.upsert_devices`(같은 가드), `FakeStore.add_device(process_id, name, celltype, order=…)`
- `src/genviewer/controllers/main_window.py` `_on_received_from_controller` (~162-184): Virtuoso 목록이 `device_state_data` 를 정하고 `refresh_devices` 를 부르는 실제 경로
- `tests/gui/test_window_guards.py`(~215-300, Virtuoso 목록 테스트), `tests/gui/test_device_sort.py`(정렬 테스트 본보기)

## 승인된 동작 변경

지금은 걸러 본 저장이 보이는 행에 0..k-1을 매긴다. 아래 불변식으로 바꾼다.

## 작업

### 불변식

"마지막 `refresh_devices` 가 숨긴 행이 있었는가" 를 기준으로 한다.

1. **숨긴 행이 없었으면** 지금과 똑같다. `order = i`(화면 모델 순서). 필터가 없을 때와, 필터가 있어도 모든 행이 보일 때가 여기에 든다.
2. **숨긴 행이 있었으면** 다음과 같이 한다.
   - **id 있는 보이는 행(슬롯)**: 마지막 refresh에서 그 행들이 가졌던 order 값을 모아 오름차순 정렬하고, 모델(화면) 순서대로 하나씩 나눠 준다.
     - 화면에서 지운 행의 값은 빠진다.
     - 옛 값은 refresh 때 읽은 값(`id → order`)을 쓴다. 모델 dict의 `"order"` 는 쓰지 마라. 이유: `save_all` 이 그 자리에서 덮어써서 취소된 저장 뒤에는 옛 값이 아니다.
   - **새 행(id 없음)**: 모델 순서에서 바로 위에 있는 가장 가까운 id 행과 같은 값을 받는다. `ORDER BY "order", id` 에서 새 id가 더 크므로 그 행 바로 뒤에 온다.
     - 위에 id 행이 없으면 가장 작은 슬롯 값보다 1 작은 값을 받는다.
     - 보이는 id 행이 하나도 없으면 refresh 때 읽은 모든 행(숨은 행 포함)의 최댓값 + 1(행이 없었으면 0)을 받는다.
   - **숨은 행**은 보내지 않는다. 지금도 모델에 없으니 보내지 않는다. 그 order·version은 그대로다.
3. 결과로 지켜야 할 성질은 다음과 같다.
   - (a) 편집도 순서 변경도 없이 저장하면 DB에 쓰이는 행이 없다(`updated == 0`, 어떤 version도 오르지 않는다).
   - (b) 숨은 행의 order·version은 바뀌지 않는다.
   - (c) 저장 뒤 전체 목록(`ORDER BY "order", id`)에서 보이던 행들끼리의 상대 순서가 화면 순서와 같다. 옛 order 값이 서로 겹치던 행은 예외다(아래 한계).
   - (d) 보이던 행들은 전체 목록에서 원래 차지하던 자리만 쓴다(숨은 행 사이로 끼어들지 않는다).
4. **한계**: refresh 때 이미 order 값이 겹친 행(옛 데이터)은 숨은 행을 쓰지 않고는 완전히 정리할 수 없다. 고치지 말고 summary에 "새 known-issue" 로 적는다.

### 결과 × 상태 (`save_all`, 걸러 본 상태)

| 경우 | 보내는 order | 결과 |
|---|---|---|
| 편집 없음 | 슬롯 = 옛 값 그대로 | 쓰기 0. "No changes to save." (`_describe_save`) |
| 보이는 행끼리 순서만 바꿈(`sort_rows` 나 끌어 옮기기) | 슬롯을 화면 순서대로 | 그 행들만 order·version이 바뀐다. 숨은 행 불변 |
| 보이는 행 하나 편집 | 슬롯 = 옛 값 | 편집한 행만 version +1 |
| 새 행 추가 | 위 규칙 | 새 행이 바로 위 행 뒤에 온다 |
| 보이는 행 삭제 | 남은 행이 자기 옛 값 | 지운 행만 사라진다 |
| 충돌 RELOAD/OVERWRITE/CANCEL, 예외 | 지금과 같다 | 취소 뒤 다시 저장해도 옛 값 기준이 유지된다(모델 dict가 아니라 refresh 때의 값) |
| `Save Skipped`(CellType 밖) | 그 행은 보내지 않는다(지금과 같다) | 슬롯 계산은 보내는 행 기준으로 해도 되고 모든 보이는 id 행 기준으로 해도 된다. 성질 (a)~(d)를 지키면 된다. 고른 것을 summary에 적는다 |

### 1. 테스트 먼저 (새 파일 `tests/gui/test_filtered_save_order.py`)

공통 준비: `device_tab_ctrl`, `store`.
- `store.add_device(<sf2p id>, "nfet_c", "NFET", order=2)` 로 세 번째 device를 넣는다. sf2p id는 `store.processes` 에서 찾는다.
- 그 뒤 `ctrl.device_table.device_state_data = {"nfet_a": {"S": "O"}, "nfet_c": {"S": "O"}}` → `ctrl.device_table.refresh_devices()`. 보이는 행은 nfet_a(0), nfet_c(2)이고 숨은 행은 nfet_b(1)다.
- 버전과 순서는 `store.devices` 에서 읽는다. 저장은 `ctrl.device_table.save_all()` 이다(info "Save Complete" 가 `dialogs.shown` 에 남는다).

테스트:
- **편집 없이 저장(RED)**: `save_all()` 이 True다. 세 device의 order가 `(0, 1, 2)` 이고 version이 저장 전과 같다. "Save Complete" 본문이 "No changes to save." 다.
  - **수정 전에는 nfet_c의 order가 1이 되고 version이 올라 실패해야 한다.**
- **보이는 행끼리 순서 바꾸기**: 모델 `sort_rows(<name 열>, Qt.DescendingOrder)` 로 nfet_c, nfet_a 순서로 만든 뒤 저장한다. 결과는 nfet_c=0, nfet_a=2, nfet_b=1이고 nfet_b의 version이 그대로다. 전체 목록(`fetch_devices_by_process` 순서)이 nfet_c, nfet_b, nfet_a다.
- **새 행**: nfet_a 아래에 새 행(CellType `NFET`)을 넣고 저장한다. 전체 목록에서 새 행이 nfet_a 바로 뒤에 오고, nfet_b의 order·version이 그대로다.
- **필터 없음**: `device_state_data = {}` 로 refresh한 뒤 저장한다. 지금처럼 order = 0..n-1이다(특성 테스트, 수정 전에도 통과).
- **모두 보이는 필터**: 세 이름을 다 넣은 필터면 숨긴 행이 없으므로 지금처럼 0..n-1이다(특성 테스트).
- **취소 뒤 다시 저장**: 순서를 바꾼 뒤 남이 nfet_a를 `touch_device` → 충돌 CANCEL → 남의 변경을 RELOAD로 받지 않고 다시 `save_all()` 을 부른다. 또 충돌이 나고, CANCEL을 고르는 동안 보내는 order가 옛 값 기준으로 같은지 본다(`store.calls_of("upsert_devices")` 두 호출의 order 비교). 이 시나리오가 가짜에서 자연스럽게 서지 않으면 이 테스트는 빼고 summary에 이유를 적는다.

### 2. 수정

- `controllers/device_table.py` 만 고친다.
  - `refresh_devices` 가 "숨긴 행이 있었는가" 와 `id → order`(모든 fetched 행), 모든 fetched 행의 최대 order를 기억한다.
  - `save_all` 의 `d["order"] = i` 자리를 위 불변식으로 바꾼다.
- 계산은 Qt 없이 테스트할 수 있는 작은 함수로 빼도 된다(같은 모듈 안). 빼면 그 함수의 단위 테스트를 더한다.
- 주석 한두 줄로 이유를 적는다. 예: "걸러 본 화면은 일부만 들고 있다. 0..k-1을 매기면 숨은 행과 순서값이 겹친다(K19)".

### 3. 변이 검사

`save_all` 을 손으로 `d["order"] = i` 로 되돌린다. 편집 없음·순서 바꾸기 테스트가 실패하는지 본다. 옛 값을 모델 dict에서 읽게 바꿔 "취소 뒤 다시 저장" 테스트(남겼다면)가 실패하는지 본다. 둘 다 되돌린다.

## Acceptance Criteria

```bash
uv run pytest tests/gui/test_filtered_save_order.py -q   # 새 테스트 통과 (수정 전에는 편집 없음 테스트가 실패해야 한다)
uv run pytest tests/gui/test_device_sort.py tests/gui/test_device_save_result.py tests/gui/test_window_guards.py -q   # 정렬·저장 결과·Virtuoso 목록 테스트 그대로 통과
uv run ruff check src tests
uv run pytest tests/gui -q
uv run pytest -q
```

## 검증 절차

1. 위 AC 커맨드를 실행한다.
2. 아키텍처 체크리스트를 확인한다.
   - 필터가 없거나 숨긴 행이 없을 때 `order = i` 가 그대로인가?
   - 숨은 행을 저장 목록에 넣지 않았는가?
   - repo·가짜 repo·필터 매칭 규칙을 바꾸지 않았는가?
3. 결과에 따라 `phases/10-gui-edit-safety/index.json` 의 step 6을 업데이트한다.
   - 성공 → `"status": "completed"`, `"summary": "K19(승인): 숨긴 행이 있던 refresh 뒤 save_all 은 보이는 id 행에 그 행들의 옛 order 를 정렬해 화면 순서대로 나눠 줌(새 행은 위 id 행 값, 없으면 최소-1, id 행이 없으면 max+1), 숨긴 행이 없으면 order=i 그대로. RED: <테스트 이름과 단언>. 변이: <결과>. Save Skipped 행 처리: <선택>. 새 known-issue: refresh 때 이미 겹친 order 는 숨은 행을 쓰지 않고는 정리 못 함"`
   - 수정 3회 시도 후에도 실패 → `"status": "error"`, `"error_message": "구체적 에러 내용"`
   - 사용자 개입 필요 → `"status": "blocked"`, `"blocked_reason": "구체적 사유"` 후 즉시 중단

## 금지사항

- 숨은 행을 저장 목록에 넣거나 숨은 행의 order를 다시 매기지 마라. 이유: 화면에 들고 있지 않은 행을 쓰게 된다(CLAUDE.md CRITICAL: 화면에 없는 device를 건드리지 않는다). 남의 편집과도 충돌한다.
- Virtuoso 필터 매칭(`name in r["name"]`)을 바꾸지 마라. 이유: 사용자가 2026-10-17 의도로 판정했다.
- 필터가 없을 때의 `order = i` 를 바꾸지 마라. 이유: 승인 범위는 걸러 본 저장뿐이다.
- `service/repo/device.py`·가짜 repo를 바꾸지 마라. 이유: 의미를 바꾸면 contract test와 DB 테스트가 필요하다. `IS DISTINCT FROM` 가드가 이미 "값이 같으면 쓰지 않는다" 를 해 준다.
- 기존 테스트를 깨뜨리지 마라.
