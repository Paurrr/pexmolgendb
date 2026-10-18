# Step 5: tab-section-model-leaks

## 배경 (phase 12 공통)

이 저장소는 이미 여러 명이 쓰는 도구다. 평소에는 **에러·버그만 고친다**(CLAUDE.md, ADR-015). phase 12는 2026-10-17에 `docs/notes/known-issues.md` 를 분류하면서 버그로 정한 GUI 비동기·수명 항목(History 화면의 오류 문구·다시 읽기 경합 K23a·K41, 변경 감지 폴링의 결과 묶기 K23b, Qt 객체 누수 K22 나머지)을 한 step에 하나씩 고친다. 모두 버그이고 승인 대상이 아니다. 사용자에게 보이는 동작은 그대로다.

phase 0~11과 이 phase의 step 0~4가 끝나 있다. 이 step에 닿는 것:
- phase 10 step 1(`same-row-reclick`): 탭이 이미 그 device를 보이고 있으면 같은 행을 다시 클릭해도 탭을 다시 읽지 않는다. 그래서 탭을 다시 읽게 하려면 **다른** device를 골라야 한다.
- phase 4 step 0(`tab-section-load`): 행을 읽지 못하면 `update_model` 이 섹션을 모델 없이 비운다(`clear_model` → `bind_model(None)`).

모든 step에 같은 규칙이 적용된다.
1. 버그는 **주장**이다. 먼저 실패하는 테스트로 재현하고 RED 출력(테스트 이름과 실패한 단언)을 summary에 적는다.
2. RED는 **Windows 개발 PC에서** 보여야 한다.
3. 재현되지 않으면 `src/` 를 고치지 않는다. 테스트는 특성 테스트로 남기고 `"status": "completed"`, `"summary": "not reproduced: <이유>"` 로 끝낸다.
4. 고친 뒤 수정을 손으로 되돌려 새 테스트가 실패하는지 확인하고 다시 고친다(변이 검사). `git checkout`/`git stash` 로 되돌리지 마라.
5. 이 파일의 행 번호는 2026-10-18(phase 11 직후) 기준 대략값이다. 이름으로 찾아라.

테스트 기반:
- fixture: `device_tab_ctrl`, `store`
  - 시드: sf2p(nfet_a, nfet_b), sf4u(pfet_a)
  - `store.add_device(process_id, name, celltype, order=…)`
- 헬퍼: `select_process`, `select_device_row`, `edit_tab_cell`
- 탭 섹션 컨트롤러: `ctrl.parameter_tab.section("InstTerm")`. `.ui` 가 `TabSection`, `.ui.table_view` 가 표다.
- 고정 대기(`qtbot.wait`)는 쓰지 않는다. 탭 로드를 기다릴 때는 `qtbot.waitUntil` 에 `sec.device_id` 와 `fetch_by_device` 호출 수를 쓴다.

## 이 step의 목적

K22 중 탭 섹션의 누수 두 가지를 고친다(2026-10-17 분류: 버그). `controllers/tab_section.py` 만 바꾼다.
- setModel마다 새로 생기는 selection model
- device 모델마다 새로 만드는 delegate

## 읽어야 할 파일

- `/CLAUDE.md`, `/docs/ARCHITECTURE.md`("탭 로드 실패", 모델 소유), `/docs/UI_GUIDE.md`(값 후보·검증은 `delegate_config.json`)
- `src/genviewer/controllers/tab_section.py` 전체
  - `get_or_create_model` (~166-177): 새 device마다 모델을 만들고 `apply_delegates_and_constraints(m)` 을 부른다.
  - `update_model`, `bind_model` (~203-205, `self.ui.table_view.setModel(model)`), `clear_model`
  - `apply_delegates_and_constraints` (~222-241): 콤보 컬럼마다 `ComboBoxDelegate(..., parent=self.ui)` 를 새로 만들어 `install_delegate` 한다.
- `src/genviewer/views/tab_section.py`: `install_delegate`(같은 컬럼에 `setItemDelegateForColumn`), `_wire_model_dirty`, `table_view`
- `src/genviewer/delegates/combo_box.py`: `_items_for_index` 가 `index.model()` 의 `device_celltype` 을 읽는다. 그래서 컬럼당 delegate 하나로 모든 device 모델에 쓸 수 있다.
- `src/genviewer/config/delegate_config.json`: 어느 탭 컬럼이 콤보(`items`/`items_by_celltype`)이고 `required` 인지
- `src/genviewer/models/generic_table.py`: `set_required_column`, `set_device_celltype`

## 버그

1. `bind_model` 은 `update_model` 마다(device를 고를 때마다, 14개 섹션 각각) `table_view.setModel(model)` 을 부른다. Qt의 `setModel` 은 새 `QItemSelectionModel` 을 만들고 옛 것을 지우지 않는다(Qt 문서). 표마다 device를 고른 횟수만큼 selection model이 쌓인다.
2. 새 device 모델이 생길 때마다 콤보 컬럼마다 `ComboBoxDelegate` 를 새로 만들어 같은 표 컬럼에 다시 설치한다. 밀려난 delegate는 섹션의 자식으로 남는다. 본 device 수 × 콤보 컬럼 수만큼 쌓인다.

이것은 주장이다. 먼저 재현하라.

## 작업

### 불변식

- 섹션마다 표의 `QItemSelectionModel` 자식 수가 device를 고른 횟수와 상관없이 일정하다(지연 삭제를 처리한 뒤).
- 섹션마다 `ComboBoxDelegate` 수가 콤보 컬럼 수를 넘지 않는다. 본 device 수와 상관없다.
- 동작은 그대로다.
  - 콤보 후보는 그 모델의 celltype을 따른다.
  - `required` 컬럼 표시는 모델마다 적용된다(`set_required_column` 은 모델 단위다. 새 모델마다 계속 부른다).
  - dirty 표시와 표의 선택·편집도 같다.
- 옛 selection model은 새 모델을 설치한 **뒤** 지운다. 그것이 표의 지금 selection model이 아닐 때만 지운다.
- 이 표의 selection model 시그널에 누가 연결하는지 찾는다(`grep selectionModel`). 연결이 있으면 새 selection model에도 이어지는지 확인한다.
- 모델 캐시(`model_by_device`)는 의도된 것이다(device를 오가도 저장 안 한 탭 편집이 남는다). 그것은 줄이지 않는다.

### 1. 테스트 먼저 (`tests/gui/test_tab_section_leaks.py`, 새 파일)

- 준비: `delegate_config` 에서 콤보 컬럼이 있는 시드 탭(`InstTerm` 또는 `InstSchParam`)을 고른다. 없으면 시드 행을 더한 다른 탭을 쓰고 summary에 적는다.
- **selection model**
  - 동작: nfet_a와 nfet_b를 열 번 번갈아 고른다. 고를 때마다 `qtbot.waitUntil(lambda: sec.device_id == 기대 id)` 로 기다린다.
  - 단언: `QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)` 뒤 `len(sec.ui.table_view.findChildren(QItemSelectionModel))` 가 처음 한 번 고른 뒤의 수와 같다. **수정 전에는 늘어서 실패해야 한다.**
- **delegate**
  - 준비: sf2p에 device를 다섯 개 더한다(`store.add_device`). 접속 뒤라면 다시 읽어 목록에 보이게 한다.
  - 동작: 각각을 한 번씩 고른다.
  - 단언: `len(sec.ui.findChildren(ComboBoxDelegate))` 가 그 섹션의 콤보 컬럼 수 이하다. **수정 전에는 본 device 수만큼 늘어 실패해야 한다.**
- **회귀**
  - 각 device를 고른 뒤 콤보 컬럼의 delegate가 그 컬럼에 설치돼 있다(`table_view.itemDelegateForColumn(i)` 가 `ComboBoxDelegate`).
  - `required` 컬럼 동작이 그대로다(모델이 required로 표시).
  - `tests/gui/test_tab_section_load.py`·`test_tab_section_view.py` 가 그대로 통과한다.
- **읽기 실패 경로**: `store.fail_next("fetch_by_device", RuntimeError("x"))` 로 모델 없이 비운 뒤(`bind_model(None)`) 다시 정상 device를 고르면 selection model 수가 늘지 않는다.

### 2. 수정

- `controllers/tab_section.py` 만 바꾼다.
  - `bind_model`: 새 모델을 설치한 뒤 옛 selection model을 지운다.
  - delegate: 섹션마다 컬럼당 한 번만 만들어 설치하거나, 밀려나는 delegate를 지운다. 더 단순한 쪽을 고른다.
- `views/tab_section.py` 의 `install_delegate` 를 바꿔야 하면 바꾸지 말고 summary에 적은 뒤 controller 쪽에서 해결한다(이 step은 한 모듈).

### 3. 문서

- 없다.

## Acceptance Criteria

```bash
uv run pytest tests/gui/test_tab_section_leaks.py tests/gui/test_tab_section_load.py tests/gui/test_tab_section_view.py -q   # 새 테스트 통과 (수정 전에는 개수 단언이 실패해야 한다)
uv run ruff check src tests
uv run pytest -q
```

## 검증 절차

1. 위 AC 커맨드를 실행한다.
2. 아키텍처 체크리스트를 확인한다.
   - 콤보 후보·검증이 여전히 `delegate_config.json` 에서 오는가(UI_GUIDE)?
   - 모델 캐시(`model_by_device`)를 건드리지 않았는가?
   - 지금 쓰는 selection model을 지우는 경로가 없는가?
3. 결과에 따라 `phases/12-gui-async-cleanup/index.json` 의 step 5를 업데이트한다.
   - 성공 → `"status": "completed"`, `"summary": "tab_section: setModel 뒤 옛 selection model 삭제, ComboBoxDelegate 는 <섹션당 컬럼당 하나|밀려난 것 삭제>. RED: <테스트 이름: 단언(전/후 개수)>. 변이: <…>. tests/gui/test_tab_section_leaks.py"`
   - 재현 안 됨 → `"status": "completed"`, `"summary": "not reproduced: <이유>"`
   - 수정 3회 시도 후에도 실패 → `"status": "error"`, `"error_message": "구체적 에러 내용"`
   - 사용자 개입 필요 → `"status": "blocked"`, `"blocked_reason": "구체적 사유"` 후 즉시 중단

## 금지사항

- `model_by_device` 캐시를 비우거나 줄이지 마라. 이유: device를 오가도 저장 안 한 탭 편집이 남는 것이 지금 동작이다(phase 3).
- 지금 표에 설치된 selection model이나 delegate를 지우지 마라. 이유: 선택·편집이 바로 깨진다(Qt는 지운 delegate를 계속 부를 수 있다).
- `views/parameter_tab.py` 의 탭 페이지 누수를 여기서 고치지 마라. 이유: step 6의 몫이다.
- 콤보 후보나 검증 규칙을 코드에 하드코딩하지 마라. 이유: UI_GUIDE "값 후보와 검증은 delegate_config.json 이 정한다".
- 기존 테스트를 깨뜨리지 마라.
