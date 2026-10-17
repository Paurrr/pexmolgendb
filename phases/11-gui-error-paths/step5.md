# Step 5: drag-under-filter

## 배경 (phase 11 공통)

이 저장소는 이미 여러 명이 쓰는 도구다. 평소에는 **에러·버그만 고친다**(CLAUDE.md, ADR-015). phase 11은 2026-10-17에 `docs/notes/known-issues.md` 를 분류하면서 고치기로 한 GUI 오류 경로 항목을 한 step에 하나씩 다룬다. 버그(K34·K35, K22 일부)와 **사용자가 2026-10-17 승인한 동작 변경**(K3의 GUI 쪽, K21, K16 내보내기 형식, K18)이 섞여 있다. 승인된 step에는 승인 문장을 그대로 적었다. 그 문장 밖으로 넓히지 마라.

phase 0~10과 이 phase의 step 0~4가 끝나 있다. 이 step에 닿는 것:
- phase 4 step 3(`device-sort`): 필터 중 정렬은 모델의 모든 행을 정렬한다. 같은 원인(proxy 행과 source 행을 섞어 씀)의 끌어 옮기기가 K18로 남았다.
- phase 10 step 6(`filtered-save-order`): Virtuoso 목록으로 걸러 본 저장의 순서값. 그 필터는 `refresh_devices` 가 행을 거르는 것이고, 이 step의 필터(`apply_filter`, proxy 정규식)와는 다르다.

모든 step에 같은 규칙이 적용된다.
1. 승인된 동작 변경도 테스트를 먼저 쓰고, 지금 코드에서 그 테스트가 어떻게 실패하는지(지금 동작)를 summary에 적는다.
2. RED는 **Windows 개발 PC에서** 보여야 한다.
3. 지금 동작이 설명과 다르면(숨은 행이 옮겨지지 않는다) `src/` 를 고치지 않고 `"summary": "not reproduced: <이유>"` 로 끝낸다.
4. 고친 뒤 수정을 손으로 되돌려 새 테스트가 실패하는지 확인하고 다시 고친다(변이 검사). `git checkout`/`git stash` 로 되돌리지 마라.
5. 이 파일의 행 번호는 2026-10-17(phase 6 전) 기준 대략값이다. 이름으로 찾아라.

GUI 테스트 기반(phase 2)의 이름을 그대로 쓴다: `device_tab_ctrl`, `store`, `store.add_device(process_id, name, celltype, order=…)`, `select_process`. `tests/gui/test_device_sort.py` 의 `store` fixture(sf2p에 `nfet_0`(order 2)을 더함), `names`·`visible_names` 헬퍼를 본보기로 삼는다.

## 이 step의 목적

(**사용자 승인 2026-10-17**, K18) 승인 문장: "필터가 켜진 상태에서 고른 행들이 실제 목록에서 떨어져 있으면 놓기를 거부(아무 일 없음). 지금은 사이의 숨은 행까지 옮겨짐"

## 읽어야 할 파일

- `/CLAUDE.md`, `/docs/UI_GUIDE.md`("입력과 단축키"의 정렬 줄), `/docs/ARCHITECTURE.md`(데이터 흐름의 device 정렬)
- `src/genviewer/views/device_table.py`
  - `dropEvent` (~209-266): proxy에서 고른 행이 이어져 있는지만 보고, `relocateRow(src_from, src_to, proxy_count)` 로 source의 **연속된** `proxy_count` 행을 옮긴다.
  - `_selected_proxy_rows`, `_selected_source_rows`, `_map_to_source_row` (~106-121), `apply_filter` (~183-187)
- `src/genviewer/models/device_table.py`: `relocateRow`, `moveRows`(undo, dirty)
- `tests/gui/test_device_sort.py`

## 승인된 동작 변경

| 고른 행(화면) | source에서 | 지금 | 바뀐 뒤 |
|---|---|---|---|
| 이어져 있음 | 이어져 있음(필터 없음, 또는 필터가 사이를 숨기지 않음) | 옮김 | **그대로** 옮김 |
| 이어져 있음 | **떨어져 있음**(사이 행이 필터로 숨음) | source의 연속 구간을 옮김(숨은 행이 함께 옮겨짐) | **놓기 거부**: `event.ignore()`, 모델 불변, dirty·undo 없음 |
| 떨어져 있음 | - | 거부(지금 코드) | 그대로 거부 |

- 거부할 때 알림·로그를 더하지 않는다(승인 문장: "아무 일 없음").
- 판단은 고른 proxy 행을 **모두** source로 옮겨, 그 source 행들이 연속인지로 한다.

## 작업

### 1. 테스트 먼저 (`tests/gui/test_device_drag.py`, 새 파일)

준비
- `test_device_sort.py` 처럼 sf2p에 `nfet_0`(order 2)을 더한 store를 쓴다. source 순서는 `nfet_a, nfet_b, nfet_0` 이다.
- sf2p를 열고 `ui.apply_filter("nfet_a|nfet_0")` 한다. 보이는 행은 `nfet_a, nfet_0` 이고, source 행은 0과 2다.
- 보이는 두 행을 고른다(`ui.selectionModel().select(..., ClearAndSelect | Rows)`).
- 가짜 drop 이벤트 객체를 만든다.
  - 지금 `dropEvent` 가 부르는 것을 흉내 낸다: `source()` → view, `dropAction()` → `Qt.MoveAction`, 위치(`pos()` 또는 코드가 쓰는 이름).
  - 받은 처리(`ignore()`/`acceptProposedAction()`/`setDropAction()`)를 기록한다.
  - 놓는 위치는 지금 코드가 정한다(`dropIndicatorPosition()`, `indexAt`). 실제로 어디로 놓이는지는 수정 전에 한 번 돌려 summary에 적는다.

테스트
- **떨어진 source 행**: `ui.dropEvent(ev)` 뒤에도 모델 이름이 `["nfet_a", "nfet_b", "nfet_0"]` 이다. `ctrl.device_table.is_dirty()` 는 False이고, 이벤트는 ignore 됐다. **수정 전에는 nfet_b(숨은 행)가 함께 옮겨져 실패해야 한다.**
- **회귀, 필터 없음 + 이어진 두 행(nfet_a, nfet_b)**: 지금과 같은 결과로 옮겨진다. 수정 전에 돌려 얻은 순서를 기대값으로 적는다(특성 테스트). dirty가 True다.
- **회귀, 필터가 사이를 숨기지 않음**(`apply_filter("nfet_a|nfet_b")`): 위와 같은 결과다.
- **회귀**: 고른 행이 화면에서 떨어져 있으면 지금처럼 거부된다.

### 2. 수정

- `views/device_table.py` `dropEvent`: 고른 proxy 행을 모두 source로 옮겨 연속이 아니면 `event.ignore()` 하고 돌아간다. 연속이면 지금 계산 그대로 `relocateRow` 한다.
- 판단은 view 안에서 끝낸다. controller나 model은 바꾸지 않는다.

### 3. 문서

- `docs/UI_GUIDE.md` "입력과 단축키" 의 정렬 줄 근처에 한 줄을 더한다: `- 필터가 켜진 상태에서 고른 행이 실제 목록에서 떨어져 있으면(사이 행이 숨어 있으면) 끌어 놓기를 받지 않는다.`

## Acceptance Criteria

```bash
uv run pytest tests/gui/test_device_drag.py tests/gui/test_device_sort.py -q   # 새 테스트 통과 (수정 전에는 떨어진 source 행 테스트가 실패해야 한다)
uv run ruff check src tests
uv run pytest -q
```

## 검증 절차

1. 위 AC 커맨드를 실행한다.
2. 아키텍처 체크리스트를 확인한다.
   - `views/` 가 controllers를 import하지 않는가(레이어 표)?
   - source에서 이어진 끌어 옮기기(필터 없음 포함)가 그대로인가?
   - 알림·로그를 더하지 않았는가?
3. 결과에 따라 `phases/11-gui-error-paths/index.json` 의 step 5를 업데이트한다.
   - 성공 → `"status": "completed"`, `"summary": "dropEvent: 고른 행이 source 에서 떨어져 있으면 ignore (사용자 승인 2026-10-17). 지금 동작(RED): <테스트 이름: 단언>. 가짜 drop 위치: <실측>. 변이: <…>. tests/gui/test_device_drag.py"`
   - 지금 동작이 설명과 다름 → `"status": "completed"`, `"summary": "not reproduced: <이유>"`
   - 수정 3회 시도 후에도 실패 → `"status": "error"`, `"error_message": "구체적 에러 내용"`
   - 사용자 개입 필요 → `"status": "blocked"`, `"blocked_reason": "구체적 사유"` 후 즉시 중단

## 금지사항

- 떨어진 행들을 모아서 옮기는 새 동작을 만들지 마라. 이유: 승인된 동작은 "거부(아무 일 없음)" 다.
- 거부할 때 알림·로그를 더하지 마라. 이유: 승인 문장 밖이고 새 문구다.
- `models/device_table.py` 의 `relocateRow`/`moveRows` 를 바꾸지 마라. 이유: 정렬(phase 4 step 3)과 undo가 기대는 동작이다.
- 이 step에서 `_map_to_source_row` 같은 private 이름을 공개 이름으로 바꾸지 마라. 이유: 그것은 구조 제안 P4(phase 15)다.
- 기존 테스트를 깨뜨리지 마라.
