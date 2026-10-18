# Step 3: send-unsaved-rows

## 배경 (phase 11 공통)

이 저장소는 이미 여러 명이 쓰는 도구다. 평소에는 **에러·버그만 고친다**(CLAUDE.md, ADR-015). phase 11은 2026-10-17에 `docs/notes/known-issues.md` 를 분류하면서 고치기로 한 GUI 오류 경로 항목을 한 step에 하나씩 다룬다. 버그(K34·K35, K22 일부)와 **사용자가 2026-10-17 승인한 동작 변경**(K3의 GUI 쪽, K21, K16 내보내기 형식, K18)이 섞여 있다. 승인된 step에는 승인 문장을 그대로 적었다. 그 문장 밖으로 넓히지 마라.

phase 0~10과 이 phase의 step 0~2가 끝나 있다. 이 step에 닿는 것:
- phase 7 step 9(`skill-escape`): SKILL 문자열의 `\`·`"` 를 이스케이프하는 헬퍼가 `utils/lisp.py` 에 생겼다. `to_lisp_list_string` 의 출력이 그 값들에서 바뀌었다.
- phase 10: device 표 붙여넣기·저장 경로가 바뀌었다(`controllers/device_table.py`, `controllers/device_tab.py`).

모든 step에 같은 규칙이 적용된다.
1. 승인된 동작 변경도 테스트를 먼저 쓰고, 지금 코드에서 그 테스트가 어떻게 실패하는지(지금 동작)를 summary에 적는다.
2. RED는 **Windows 개발 PC에서** 보여야 한다.
3. 지금 동작이 설명과 다르면(이미 경고하고 보내지 않는다 등) `src/` 를 고치지 않고 `"summary": "not reproduced: <이유>"` 로 끝낸다.
4. 고친 뒤 수정을 손으로 되돌려 새 테스트가 실패하는지 확인하고 다시 고친다(변이 검사). `git checkout`/`git stash` 로 되돌리지 마라.
5. 이 파일의 행 번호는 2026-10-18(phase 10 직후) 기준 대략값이다. 이름으로 찾아라.

GUI 테스트 기반(phase 2)의 이름을 그대로 쓴다. 작업 전에 `tests/gui/conftest.py`·`tests/gui_support/` 를 읽는다.
- `dialogs.shown`(`(kind, title, text)`, severity `warn` → kind `warning`)
- `device_tab_ctrl`, `store`(sf2p: nfet_a·nfet_b / sf4u: pfet_a), `store.calls_of`
- `select_device_row(ctrl, row)`: 화면 순서 행을 `setCurrentIndex` 로 고른다.
- 고정 대기(`qtbot.wait`) 금지.

## 이 step의 목적

(**사용자 승인 2026-10-17**, K21) 승인 문장: "Run Selected 등 보내기에 저장 안 한 새 행이 있으면 새 경고 문구로 알리고 보내지 않음. 지금은 'Send Failed: 'id''"

정한 문구(2026-10-17 계획): severity `warn`, 제목 `Unsaved Devices`, 본문 `저장하지 않은 device 가 있어 보내지 않았다. 먼저 저장할 것.`

## 읽어야 할 파일

- `/CLAUDE.md`, `/docs/UI_GUIDE.md`(원칙 4, "문구", "입력과 단축키")
- `src/genviewer/controllers/device_tab.py`: `send_device_data`(~306-362, `@report("Send Failed")`. `device_info` 를 만들 때 `dev["id"]` 에서 KeyError가 난다)
- `src/genviewer/controllers/device_table.py`: `get_selected_devices`(~302-307, `fallback_to_all`)
- `src/genviewer/controllers/device_tab_toolbar.py`: `run_selected`/`run_all`(`runModeRequested` 로 `"selected"`/`"all"`)
- `src/genviewer/models/device_table.py`: `insert_row(row, values)`(id 없는 새 행), `get_device`, `get_devices`
- `src/genviewer/utils/reporting.py`: `report`, `report_error`

## 승인된 동작 변경

지금은 저장하지 않은 새 행(id 없음)이 보낼 대상에 있으면 이렇게 된다.
1. `device_info` 를 만들다 `KeyError('id')` 가 난다.
2. `@report` 가 그것을 "Send Failed" 오류 상자로 띄운다. `user_message(KeyError('id'))` 라 본문은 `'id'` 다.
3. 로그 패널에도 같은 줄이 남는다.

바뀐 뒤:

| 보낼 대상(`mode`, 선택) | 동작 |
|---|---|
| 하나라도 id가 없다 | **아무것도 보내지 않는다.** `sendDataRequested` 를 내지 않고 `fetch_export_data` 를 부르지 않는다. `notifyRequested("warn", "Unsaved Devices", "저장하지 않은 device 가 있어 보내지 않았다. 먼저 저장할 것.")` 를 한 번 낸다 |
| 모두 id가 있다 | 지금과 같다(`fetch_export_data` → `pydata = list(...)` 를 `sendDataRequested` 로) |
| 대상이 없다 | 지금과 같다(상태 표시줄 `No device selected`) |

- `"selected"` 는 고른 행만, `"all"` 은 고른 행이 없으면 모든 행이 대상이다(`get_selected_devices(fallback_to_all=...)`, 지금 그대로).
- 일부만 저장된 경우 저장된 것만 보내지 않는다(승인 문장: "보내지 않음").

## 작업

### 1. 테스트 먼저 (`tests/gui/test_send_device_data.py`, 새 파일)

공통 준비
- `device_tab_ctrl` 의 `sendDataRequested` 를 리스트에 연결한다.
- 새 행은 `ctrl.device_table.ui.model_safe().insert_row(row, {"name": "new_dev", "celltype": "NFET", "description": ""})` 로 만든다. 값 검증을 통과하는지 먼저 확인한다.
- 행을 고르는 방법(`select_device_row` 또는 view의 selectionModel)은 `get_selected_devices` 가 실제로 그 행을 돌려주는지 단언하고 쓴다.

테스트
- **고른 새 행 + selected**
  - 동작: `ctrl.send_device_data("selected")`
  - 단언
    - 보낸 것이 없다.
    - `store.calls_of("fetch_export_data") == []`
    - `dialogs.shown == [("warning", "Unsaved Devices", "저장하지 않은 device 가 있어 보내지 않았다. 먼저 저장할 것.")]`
  - **수정 전에는 `("error", "Send Failed", "'id'")` 라 실패해야 한다.**
- **저장된 행과 새 행을 함께 고름 + selected**: 위와 같다.
- **고른 것 없음 + all, 새 행이 목록에 있음**: 위와 같다.
- **회귀, 저장된 행만**: 보낸 것이 하나이고 `"pydata = list("` 로 시작한다. `fetch_export_data` 가 한 번 불렸고 경고가 없다.
- **회귀, 대상 없음 + selected**: 경고 상자가 없다(상태 표시줄 경로, 지금 그대로).

### 2. 수정

- `controllers/device_tab.py` `send_device_data`: 대상을 정한 직후, `device_info` 를 만들기 전에 id가 없는 행이 있는지 본다. 있으면 위 경고를 내고 돌아간다.
- 경고는 `notifyRequested` 로 낸다(UI_GUIDE "알림은 controller가 notifyRequested 로"). 로그 줄은 더하지 않는다.

### 3. 문서

- `docs/UI_GUIDE.md` "입력과 단축키" 의 목록(붙여넣기 줄 근처)에 한 줄을 더한다: `- Virtuoso 로 보내기(Run Selected / Run All)는 저장하지 않은 device 가 있으면 보내지 않고 경고한다(`Unsaved Devices`).`

## Acceptance Criteria

```bash
uv run pytest tests/gui/test_send_device_data.py -q   # 새 테스트 통과 (수정 전에는 새 행 테스트가 실패해야 한다)
uv run ruff check src tests
uv run pytest -q
```

## 검증 절차

1. 위 AC 커맨드를 실행한다.
2. 아키텍처 체크리스트를 확인한다.
   - 문구가 위에 정한 것과 글자까지 같은가(제목 영어, 본문 한국어. UI_GUIDE 문구)?
   - 저장된 행만 있을 때의 보내기가 그대로인가?
   - 새 경고 말고 다른 문구(상태 표시줄, 로그)를 바꾸지 않았는가?
3. 결과에 따라 `phases/11-gui-error-paths/index.json` 의 step 3을 업데이트한다.
   - 성공 → `"status": "completed"`, `"summary": "send_device_data: id 없는 행이 대상에 있으면 보내지 않고 warn/Unsaved Devices (사용자 승인 2026-10-17). 지금 동작(RED): <테스트 이름: 단언>. 변이: <…>. tests/gui/test_send_device_data.py"`
   - 지금 동작이 설명과 다름 → `"status": "completed"`, `"summary": "not reproduced: <이유>"`
   - 수정 3회 시도 후에도 실패 → `"status": "error"`, `"error_message": "구체적 에러 내용"`
   - 사용자 개입 필요 → `"status": "blocked"`, `"blocked_reason": "구체적 사유"` 후 즉시 중단

## 금지사항

- 저장된 행만 골라 보내지 마라. 이유: 승인된 동작은 "보내지 않음" 이다.
- 보내기 전에 자동으로 저장하지 마라. 이유: 승인 범위 밖이고, 저장에는 충돌 질문이 따른다.
- 문구를 바꾸거나 다듬지 마라. 이유: 계획에서 정한 승인 문구다.
- `fetch_export_data` 를 워커로 옮기는 등 다른 정리를 하지 마라. 이유: 그것은 구조 제안 P5(phase 17)다.
- 기존 테스트를 깨뜨리지 마라.
