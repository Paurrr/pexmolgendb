# Step 6: parameter-tab-page-leaks

## 배경 (phase 12 공통)

이 저장소는 이미 여러 명이 쓰는 도구다. 평소에는 **에러·버그만 고친다**(CLAUDE.md, ADR-015). phase 12는 2026-10-17에 `docs/notes/known-issues.md` 를 분류하면서 버그로 정한 GUI 비동기·수명 항목(History 화면의 오류 문구·다시 읽기 경합 K23a·K41, 변경 감지 폴링의 결과 묶기 K23b, Qt 객체 누수 K22 나머지)을 한 step에 하나씩 고친다. 모두 버그이고 승인 대상이 아니다. 사용자에게 보이는 동작은 그대로다.

phase 0~11과 이 phase의 step 0~5가 끝나 있다. 이 step에 닿는 것:
- phase 4 step 2(`parameter-add-tab`): "+" 탭에서 고른 탭은 "+" 바로 앞에 붙는다(`add_tab` 과 `rebuild_tabs` 가 `_insert_section` 을 함께 쓴다).
- step 5(이 phase): 탭 섹션 안의 selection model·delegate 누수를 고쳤다(`controllers/tab_section.py`).
- 접속과 재접속마다 `DeviceTabController.apply_db` 가 `parameter_tab.rebuild_all_sections()` 를 부른다. phase 10 step 4가 재접속 전에 편집을 묻는다.

모든 step에 같은 규칙이 적용된다.
1. 버그는 **주장**이다. 먼저 실패하는 테스트로 재현하고 RED 출력(테스트 이름과 실패한 단언)을 summary에 적는다.
2. RED는 **Windows 개발 PC에서** 보여야 한다.
3. 재현되지 않으면 `src/` 를 고치지 않는다. 테스트는 특성 테스트로 남기고 `"status": "completed"`, `"summary": "not reproduced: <이유>"` 로 끝낸다.
4. 고친 뒤 수정을 손으로 되돌려 새 테스트가 실패하는지 확인하고 다시 고친다(변이 검사). `git checkout`/`git stash` 로 되돌리지 마라.
5. 이 파일의 행 번호는 2026-10-18(phase 11 직후) 기준 대략값이다. 이름으로 찾아라.

테스트 기반: `device_tab_ctrl`, `main_window`, `store`, `dialogs`, `select_device_row`. 고정 대기(`qtbot.wait`) 금지. Qt 객체가 지워졌는지는 지연 삭제를 처리한 뒤(`QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)`) `shiboken6.isValid(obj)` 로 본다.

## 이 step의 목적

K22 중 "다시 만들 때 지워지지 않는 탭 섹션" 을 고친다(2026-10-17 분류: 버그). `views/parameter_tab.py` 만 바꾼다.

## 읽어야 할 파일

- `/CLAUDE.md`, `/docs/UI_GUIDE.md`(레이아웃: 파라미터 탭 순서 Summary, tab_config 순서, 마지막 `+`), `/docs/ARCHITECTURE.md`(모델 소유)
- `src/genviewer/views/parameter_tab.py` 전체
  - `__init__`: `summary_view` 와 "+" `QWidget()`
  - `rebuild_tabs` (~23-32): `self.clear()` 후 Summary를 다시 넣고 섹션들과 새 "+" 를 넣는다.
  - `add_tab`, `_insert_section`(TabSection의 부모는 이 위젯), `on_tab_changed`(`current_tab_section`), `iter_sections`, `find_tab`
- `src/genviewer/controllers/parameter_tab.py`
  - `_attach_section`: `TabSectionController` 를 만들고 `ctrl.setParent(tab_view)` 한다. 섹션이 지워지면 컨트롤러도 함께 지워진다.
  - `rebuild_all_sections`: `clear_sections()` 뒤 `ui.rebuild_tabs(tab_config, on_created=...)`
  - `_current_section_controller`(`ctrl.ui is section` 비교)
- `src/genviewer/controllers/device_tab.py`: `apply_db`(읽기만)

## 버그

`ParameterTab.rebuild_tabs` 는 `QTabWidget.clear()` 로 페이지를 뗀다. Qt 문서에 따르면 `clear()` 는 페이지 위젯을 지우지 않는다.
- 접속·재접속마다 옛 `TabSection` 14개(와 각각의 `TabSectionController`, 그 모델 캐시)가 숨은 자식으로 남는다.
- 옛 "+" 위젯도 남는다.
- 옛 컨트롤러는 `logRequested`/`notifyRequested` 연결도 그대로 들고 있다.

이것은 주장이다. 먼저 재현하라.

## 작업

### 불변식

- `rebuild_tabs` 뒤 이 위젯 아래의 `TabSection` 수가 지금 탭 페이지의 `TabSection` 수와 같다(지연 삭제를 처리한 뒤).
- 옛 "+" 위젯은 지워진다. "+" 페이지는 하나다.
- `summary_view` 는 지우지 않고 다시 쓴다. 0번 페이지이고 `shiboken6.isValid` 다.
- 옛 섹션의 `TabSectionController` 도 함께 지워진다(부모가 섹션).
- 탭 순서와 현재 탭은 지금과 같다(섹션이 있으면 1번).
- `current_tab_section` 이 지워진 섹션을 가리킨 채 남지 않는다.
  - 지금 코드는 `setCurrentIndex(1)` 이 `currentChanged` → `on_tab_changed` 를 불러 새로 잡는다.
  - 섹션이 하나도 없을 때도 지워진 객체를 가리키지 않게 한다.
- `add_tab`("+" 에서 탭 다시 열기)의 동작은 그대로다.

### 1. 테스트 먼저 (`tests/gui/test_parameter_tab_leaks.py`, 새 파일)

- **다시 만들기**
  - 준비: `device_tab_ctrl` 에서 `view = ctrl.ui.parameter_tab_view` 다. 옛 섹션 하나와 옛 "+" 위젯(`view.widget(view.count() - 1)`)을 잡아 둔다.
  - 동작: `ctrl.parameter_tab.rebuild_all_sections()` 를 세 번 부른 뒤 지연 삭제를 처리한다.
  - 단언
    - `len(view.findChildren(TabSection)) == len(list(view.iter_sections()))`
    - 잡아 둔 옛 섹션·옛 "+" 가 `shiboken6.isValid` 에서 False다.
    - **수정 전에는 남아서 실패해야 한다.**
- **컨트롤러**: 같은 뒤에 `view.findChildren(TabSectionController)` 의 수가 지금 섹션 수와 같다. **수정 전에는 네 배라 실패해야 한다.**
- **회귀**
  - Summary 페이지가 0번이고 살아 있다.
  - 마지막 페이지 이름이 "+" 이고, 섹션이 있으면 현재 탭이 1번이다.
  - 다시 만든 뒤 device를 고르면 탭 행이 읽힌다(`fetch_by_device` 호출, 섹션 모델 존재).
  - 다시 만든 뒤 `current_tab_section` 이 살아 있는 섹션이거나 None이다.
  - `tests/gui/test_parameter_add_tab.py` 가 그대로 통과한다.
- **재접속 경로**: `main_window.ui.device_tab_view.dbConnectRequested.emit("host=other")` 를 두 번 한다(편집 없음, 질문 없음). 그 뒤 위와 같은 개수 단언을 한다.

### 2. 수정

- `views/parameter_tab.py` `rebuild_tabs`: `clear()` 로 떼어 낸 페이지 중 `summary_view` 가 아닌 것(옛 섹션, 옛 "+")을 지운다(`deleteLater`). 지우기 전에 `current_tab_section` 이 그것을 가리키면 비운다.
- `controllers/` 는 바꾸지 않는다.

### 3. 문서

- 없다.

## Acceptance Criteria

```bash
uv run pytest tests/gui/test_parameter_tab_leaks.py tests/gui/test_parameter_add_tab.py tests/gui/test_tab_section_view.py -q   # 새 테스트 통과 (수정 전에는 개수·isValid 단언이 실패해야 한다)
uv run ruff check src tests
uv run pytest -q
```

## 검증 절차

1. 위 AC 커맨드를 실행한다.
2. 아키텍처 체크리스트를 확인한다.
   - `views/` 가 controllers를 import하지 않는가(레이어 표)?
   - Summary 페이지와 탭 순서·현재 탭이 그대로인가(UI_GUIDE 레이아웃)?
   - "+" 로 탭을 다시 여는 동작(phase 4 step 2)이 그대로인가?
3. 결과에 따라 `phases/12-gui-async-cleanup/index.json` 의 step 6을 업데이트한다.
   - 성공 → `"status": "completed"`, `"summary": "ParameterTab.rebuild_tabs 가 떼어 낸 옛 섹션·옛 + 를 deleteLater(summary_view 유지, current_tab_section 정리). RED: <테스트 이름: 단언>. 변이: <…>. tests/gui/test_parameter_tab_leaks.py"`
   - 재현 안 됨 → `"status": "completed"`, `"summary": "not reproduced: <이유>"`
   - 수정 3회 시도 후에도 실패 → `"status": "error"`, `"error_message": "구체적 에러 내용"`
   - 사용자 개입 필요 → `"status": "blocked"`, `"blocked_reason": "구체적 사유"` 후 즉시 중단

## 금지사항

- `summary_view` 를 지우거나 새로 만들지 마라. 이유: `summarySourceActivated` 연결이 생성자에서 한 번만 걸린다.
- 섹션을 다시 만들지 않고 재사용하도록 구조를 바꾸지 마라. 이유: 리팩터다. 누수만 고친다.
- 탭 순서·현재 탭·탭 이름(` *` 표시)을 바꾸지 마라. 이유: UI_GUIDE 레이아웃이다.
- `controllers/parameter_tab.py`·`controllers/tab_section.py` 를 바꾸지 마라. 이유: 이 step은 view 한 모듈이다(컨트롤러는 부모인 섹션과 함께 지워진다).
- 기존 테스트를 깨뜨리지 마라.
