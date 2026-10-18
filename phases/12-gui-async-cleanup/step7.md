# Step 7: own-save-banner

## 배경 (phase 12 공통)

이 저장소는 이미 여러 명이 쓰는 도구다. 평소에는 **에러·버그만 고친다**(CLAUDE.md, ADR-015). phase 12는 2026-10-17에 `docs/notes/known-issues.md` 를 분류하면서 버그로 정한 GUI 비동기·수명 항목(History 화면의 오류 문구·다시 읽기 경합 K23a·K41, 변경 감지 폴링의 결과 묶기 K23b, Qt 객체 누수 K22 나머지)을 한 step에 하나씩 고친다. 모두 버그이고 승인 대상이 아니다. 사용자에게 보이는 문구를 새로 만들지 않는다.

이 step(K43)은 2026-10-17 사용자 제보("device 를 추가하고 저장하면 '…님이 …했다' 같은 문구가 크게 뜬다")를 조사하다 찾았다. 조사 중 일회성 스크립트(FakeStore 위의 실제 `DeviceTabController`)로 한 번 재현했다. 그래도 이 step에서는 주장으로 보고 테스트로 다시 재현한다.

phase 0~11과 이 phase의 step 0~6이 끝나 있다. 이 step에 닿는 것:
- step 3(이 phase): 폴링 결과·실패를 시작할 때의 `(process_id, repo)` 에 묶었다. 전환·재접속 뒤에 도착한 결과는 버린다. 같은 process·같은 DB의 결과는 전처럼 판단한다(같으면 배너를 숨기고, 다르면 `who` 로 배너를 띄운다).
- phase 10 step 0: 충돌 대화상자가 `can_overwrite` 로 OVERWRITE를 숨길 수 있다. stale 충돌에서는 세 갈래 그대로다.
- phase 10 step 6: `save_all` 이 Virtuoso 필터 중 저장 순서를 바꿨을 수 있다. 이 step은 알림 위치만 본다.

모든 step에 같은 규칙이 적용된다.
1. 버그는 **주장**이다. 먼저 실패하는 테스트로 재현하고 RED 출력(테스트 이름과 실패한 단언)을 summary에 적는다.
2. RED는 **Windows 개발 PC에서** 보여야 한다.
3. 재현되지 않으면 `src/` 를 고치지 않는다. 테스트는 특성 테스트로 남기고 `"status": "completed"`, `"summary": "not reproduced: <이유>"` 로 끝낸다.
4. 고친 뒤 수정을 손으로 되돌려 새 테스트가 실패하는지 확인하고 다시 고친다(변이 검사). `git checkout`/`git stash` 로 되돌리지 마라.
5. 이 파일의 행 번호는 2026-10-18(phase 11 직후) 기준 대략값이다. 이름으로 찾아라.

테스트 기반: `device_tab_ctrl`, `store`(sf2p: nfet_a·nfet_b / sf4u: pfet_a, actor `tester`), `store.touch_device(id, actor=…)`, `store.calls_of("etag")`, `dialogs`(`answer_conflict`, `shown`), `edit_device_cell`. 본보기는 `tests/gui/test_smoke.py` 의 폴링 테스트다. `ctrl._poll_remote_changes()` 를 직접 부르고 `etag` 호출 수와 `ctrl._poll_task is None` 을 기다린다. 배너는 `ctrl.ui.refresh_banner`(`isHidden()`, `label.text()`)로 본다. 고정 대기(`qtbot.wait`)는 쓰지 않는다. `waitUntil` 콜백은 bool을 돌려준다.

## 읽어야 할 파일

- `/CLAUDE.md`(자동으로 다시 읽지 않는다, 남이 바꾼 것은 배너로), `/docs/ARCHITECTURE.md`("변경 감지"), `/docs/ADR.md`(ADR-004), `/docs/UI_GUIDE.md`(배너, "Save Complete")
- `src/genviewer/controllers/device_table.py`
  - `save_all` (~386-453): 쓰기 → `_emit_version_bumps` → `notifyRequested("info", "Save Complete", summary)` → `refresh_devices()` → 로그 → (있으면) "Save Skipped" 경고
  - `refresh_devices` (~309-353, `@report("Load Failed")`): 끝에서 `remember_etag()` 를 부른다
  - `remember_etag` (~355-371): docstring이 "기준점을 갱신하지 않으면 내가 방금 한 저장을 보고 '남이 바꿨다' 배너가 뜬다" 고 적고 있다
  - `_write_devices` (~471-504): 충돌 → RELOAD/OVERWRITE/CANCEL
- `src/genviewer/controllers/device_tab.py`: `_poll_remote_changes`, `_on_poll_result`(step 3이 바꿨다), `on_load_csv_requested`(다시 읽은 **뒤에** 알린다. 이 step이 따를 순서다)
- `src/genviewer/controllers/parameter_tab.py`: `_apply`(알림 전에 `deviceVersionChanged` → `set_device_version` → `remember_etag`. 순서가 이미 맞다. 바꾸지 않는다)
- `src/genviewer/views/main_window.py` `notify` → `utils/dialogs.py` `info` → `QMessageBox.information`. 모달이라 중첩 이벤트 루프가 돈다.
- `src/genviewer/utils/background.py` `is_busy`: `run_blocking` 안에서만 True다. 모달 상자 안에서는 False라 폴링이 돈다.
- `src/genviewer/views/device_tab.py` `RefreshBanner.show_change`: "이 process 가 {actor} 님에 의해 변경되었습니다."
- `tests/gui/test_smoke.py`(`test_a_poll_without_changes_keeps_the_banner_hidden`, `test_another_users_save_shows_the_banner`), `tests/gui/test_device_save_result.py`, step 3의 `tests/gui/test_poll_binding.py`

## 버그

`DeviceTableController.save_all` 은 "Save Complete" 알림을 `refresh_devices()`(→ `remember_etag()`) **보다 먼저** 낸다. 실제 앱에서 그 알림은 모달 `QMessageBox.information` 이다. 상자가 떠 있는 동안 10초 폴링 타이머가 울리면 다음 순서로 거짓 배너가 뜬다.
- `is_busy()` 가 False이고 기억한 기준점도 있으므로 폴링이 돈다.
- 저장 **뒤**의 etag를 저장 **전** 기준점과 비교하니 다르다.
- 그래서 배너가 "이 process 가 <나> 님에 의해 변경되었습니다." 로 뜬다. `who` 는 방금 저장한 나다.
- 상자를 닫으면 `refresh_devices` 가 기준점을 새로 잡지만 배너는 그대로 남는다. 다음 폴링(최대 10초 뒤)이 같은 etag를 보고 숨긴다.

추가뿐 아니라 수정·삭제 저장, stale 충돌에서 OVERWRITE를 고른 저장도 같은 줄을 지난다. 이것은 주장이다. 먼저 재현하라.

## 작업

### 결과 × 상태 (`save_all`)

| 경로 | 지금 | 바뀐 뒤 |
|---|---|---|
| 쓰기 성공(추가·수정·삭제) | 알림 → 다시 읽기(기준점) → 로그 → (Save Skipped) | 다시 읽기(기준점) → 알림 → 로그 → (Save Skipped). **상자가 떠 있는 동안 폴링해도 배너가 없다** |
| stale 충돌 → OVERWRITE | 위 "지금"과 같다 | 위 "바뀐 뒤"와 같다 |
| stale 충돌 → RELOAD / CANCEL | "Save Complete" 없음 | 지금과 같다 |
| 쓸 것 없음(`No changes to save.`) | 쓰기가 없으므로 기준점이 그대로다. 알림 순서와 무관하게 배너가 없다 | 지금과 같다(알림 위치만 옮겨진다) |
| 쓰기 예외(`fail_next`, 접속 끊김) | 알림 없음, 예외가 올라간다 | 지금과 같다 |
| 쓰기 성공 뒤 `refresh_devices` 실패(`@report("Load Failed")`) | "Save Complete" → "Load Failed" | "Load Failed" → "Save Complete". 기준점이 갱신되지 않아 다음 폴링이 배너를 띄울 수 있다. 화면이 서버와 다르므로 맞는 알림이다. summary에 이 순서 변화를 적는다 |
| 상자가 떠 있는 동안 **남이** 저장함 | 배너(남의 이름 또는 내 이름) | 배너가 뜨고 남의 이름이 들어 있다(회귀 그물) |

`save_all` 의 반환값, 요약 문구(`_describe_save`), 로그 문구, "Save Skipped" 경고의 내용과 위치(알림 뒤)는 바꾸지 않는다.

### 1. 테스트 먼저 (`tests/gui/test_own_save_banner.py`, 새 파일)

공통 준비(헬퍼 하나로 묶어도 된다):
- `ctrl.device_table.notifyRequested` 에 슬롯을 하나 더 잇는다. 제목이 `"Save Complete"` 면 다음을 한다. 모달의 중첩 루프 안에서 폴링 틱이 한 번 도는 상황을 흉내 낸 것이다.
  - `n = len(store.calls_of("etag"))`
  - `ctrl._poll_remote_changes()`
  - `qtbot.waitUntil(lambda: len(store.calls_of("etag")) == n + 1 and ctrl._poll_task is None)`
- 슬롯이 실제로 한 번 돌았는지 단언한다(예: 호출 횟수 카운터 == 1). 안 돌았으면 테스트가 아무것도 증명하지 못한다.

경우:
- **새 행 추가(RED)**: `model = ctrl.ui.device_table_view.model_safe()`, `model.insert_row(model.rowCount(), {"name": "new_dev", "celltype": <ctrl.device_table._valid_celltypes()[0]>, "description": ""})` → `assert ctrl.device_table.save_all()` → `assert ctrl.ui.refresh_banner.isHidden()`. **수정 전에는 배너가 "이 process 가 tester 님에 의해 변경되었습니다." 로 떠서 실패해야 한다.**
- **수정 저장**: `edit_device_cell(ctrl, 0, "description", "edited")` → 같은 단언.
- **삭제 저장**: 모델에서 한 행을 지운다(`model.remove_rows([1])`) → 같은 단언.
- **OVERWRITE**: nfet_a의 Description을 고친다 → `store.touch_device(nfet_a, actor="kim")` → `dialogs.answer_conflict(OVERWRITE)` → `save_all()` → 같은 단언.
- **회귀 그물(남의 저장)**: 슬롯이 폴링 전에 `store.touch_device(nfet_b, actor="kim")` 을 하게 한 변형이다. 내 저장 뒤 상자가 떠 있는 동안 남이 저장한 것이다. 배너가 보이고 `"kim" in label.text()` 다. 수정 전에도 통과할 수 있다(특성 테스트).
- **그다음 틱**: 첫 경우 뒤에 `_poll_remote_changes()` 를 한 번 더 돌려도 배너가 숨어 있다(특성 테스트).

### 2. 수정

- `controllers/device_table.py` `save_all` 에서 `self.notifyRequested.emit("info", "Save Complete", summary)` 를 `self.refresh_devices()` 뒤로 옮긴다. 옆에 한두 줄로 이유를 적는다. 예: "알림은 모달이다. 기준점을 먼저 잡지 않으면 상자가 떠 있는 동안의 폴링이 내 저장을 남의 변경으로 본다".
- 다른 것은 바꾸지 않는다.

### 3. 변이 검사

알림을 손으로 원래 자리(`refresh_devices()` 앞)로 되돌려 "새 행 추가" 테스트가 실패하는지 본다. 다시 고친다.

## Acceptance Criteria

```bash
uv run pytest tests/gui/test_own_save_banner.py -q   # 새 테스트 통과 (수정 전에는 '새 행 추가' 테스트가 실패해야 한다)
uv run pytest tests/gui/test_device_save_result.py tests/gui/test_smoke.py tests/gui/test_poll_binding.py tests/gui/test_save_entry_points.py -q
uv run ruff check src tests
uv run pytest tests/gui -q
uv run pytest -q
```

## 검증 절차

1. 위 AC 커맨드를 실행한다.
2. 아키텍처 체크리스트를 확인한다.
   - 자동으로 다시 읽지 않는가(ADR-004)? 이 step은 알림 위치만 옮겼는가?
   - 문구(요약·로그·"Save Skipped")와 `save_all` 반환 계약이 그대로인가?
   - 폴링 코드(`_poll_remote_changes`, `_on_poll_result`, `_on_poll_failed`, `_clear_poll_task`)를 건드리지 않았는가?
3. 결과에 따라 `phases/12-gui-async-cleanup/index.json` 의 step 7을 업데이트한다.
   - 성공 → `"status": "completed"`, `"summary": "K43: DeviceTableController.save_all 이 'Save Complete'(모달)를 refresh_devices(remember_etag) 뒤에 냄. 모달 중 폴링이 내 저장을 남의 변경으로 보던 배너 없앰. RED: <테스트 이름: 단언>. 변이: <결과>. 순서 변화: refresh 실패 시 'Load Failed' 가 'Save Complete' 보다 먼저. tests/gui/test_own_save_banner.py"`
   - 재현 안 됨 → `"status": "completed"`, `"summary": "not reproduced: <이유>"`
   - 수정 3회 시도 후에도 실패 → `"status": "error"`, `"error_message": "구체적 에러 내용"`
   - 사용자 개입 필요 → `"status": "blocked"`, `"blocked_reason": "구체적 사유"` 후 즉시 중단

## 금지사항

- 폴링 쪽(`device_tab.py` 의 `_poll_remote_changes`·`_on_poll_result` 등)을 고쳐서 이 버그를 막지 마라. 예를 들어 "모달이 떠 있으면 폴링하지 않음", "내 이름이면 배너 숨김" 같은 것이다. 이유: 원인은 `save_all` 의 순서이고, 폴링은 step 3이 정리한 영역이다. `who` 가 내 이름이어도 다른 PC에서 같은 계정으로 저장한 진짜 변경일 수 있다.
- 쓰기가 시작되기 직전에 출발한 폴링 결과가 기준점을 잡은 뒤에 도착하는 경합(known-issues K45, 기록만)을 이 step에서 고치지 마라. 이유: 범위 밖이고 확률이 매우 낮다. 발견하면 summary에 적기만 한다.
- 다른 저장 경로(탭 저장 `parameter_tab`, 붙여넣기 `paste_rows`, CSV 불러오기)의 순서를 바꾸지 마라. 이유: 이미 기준점을 먼저 잡거나 범위 밖이다.
- 알림 문구·배너 문구·폴링 주기를 바꾸지 마라.
- `qtbot.wait` 로 고정 대기하지 마라.
- 기존 테스트를 깨뜨리지 마라.
