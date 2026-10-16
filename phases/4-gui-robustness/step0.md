# Step 0: tab-section-load

## 배경 (phase 4 공통)

이 저장소는 이미 여러 명이 쓰는 도구다. 지금은 **에러·버그만 고친다**(CLAUDE.md, ADR-015). phase 4는 GUI가 실패·경합 상황에서 데이터를 잘못 쓰거나 죽는 버그를 한 step에 하나씩 고친다(탭 로드 실패, 탭 섹션 입력, "+" 탭, 필터 중 정렬, DB 재접속, 창 닫기, Virtuoso 소켓 워커). phase 3(`3-gui-save-fixes`)이 먼저 끝나 있다. 저장 함수가 결과를 돌려주고(`save_all() -> bool`, `DeviceTabController.save_db() -> bool`), `select_process_silently` 가 생겼다. 정확한 반환 계약은 코드와 `phases/3-gui-save-fixes/index.json` 의 summary로 확인하라.

모든 step에 같은 규칙이 적용된다.
1. 아래 "버그"는 **분석 에이전트의 주장**이다. 먼저 실패하는 테스트로 재현하고, RED 출력(테스트 이름과 실패한 단언)을 summary에 적는다.
2. RED는 **Windows 개발 PC에서** 보여야 한다. `posix_only` 테스트는 개발 PC에서 skip되므로 버그를 증명하지 못한다.
3. 재현되지 않으면 `src/` 를 고치지 않는다. 테스트는 특성 테스트로 남기고 `"status": "completed"`, `"summary": "not reproduced: <이유>"` 로 끝낸다.
4. 고친 뒤 수정을 손으로 되돌려 새 테스트가 실패하는지 확인하고 다시 고친다(변이 검사). `git checkout`/`git stash` 로 되돌리지 마라. 이유: 같은 step의 테스트 변경까지 사라진다.
5. 이 파일의 행 번호는 2026-10-17 기준 대략값이다. 이름으로 찾아라.

GUI 테스트 기반은 phase 2(`2-gui-test-infra`)가 만들었다. 아래 이름을 그대로 쓰고, 같은 일을 하는 것을 새로 만들지 마라.
- `tests/gui/conftest.py`: offscreen Qt. autouse `dialogs` fixture — `dialogs.answer_question(*bools)`·`dialogs.answer_conflict(*choices)` 로 다음 대화상자의 답을 미리 넣고, 뜬 상자는 `dialogs.shown` 에 `(kind, title, text)` 로 쌓인다. 답을 넣지 않은 모달이 뜨면 AssertionError다. `store`(시드된 FakeStore: process "sf2p" 에 device "nfet_a"·"nfet_b", "sf4u" 에 device 하나, 탭 행), `device_tab_ctrl`(`DeviceTabController._open_database` 가 `FakeDatabase(store)` 를 돌려주게 바꿔 접속한 컨트롤러. `qtbot.waitUntil(lambda: ctrl.connected is not None)` 까지 기다린다), `main_window`(fake 위의 MainWindowController + MainWindow. 정리 때 shutdown 후 close).
- `tests/gui_support/fakes.py`: `FakeStore`(`calls` 에 호출 기록, `fail_next(method_name, exc)` 로 그 메서드의 다음 호출 하나를 실패시킨다), `FakeDatabase`(`.cfg.dsn`, `close()`), 실제와 같은 의미의 fake repo들.
- `tests/gui_support/helpers.py`: `select_process`, `select_device_row`, `edit_device_cell`, `edit_tab_cell`.
- 새 테스트는 `tests/gui/test_<주제>.py` 에 둔다. "아무 일도 일어나지 않았다" 를 `qtbot.wait` 고정 대기로 확인하지 않는다. 비동기 경로는 fake가 기록한 호출(`store.calls`)을 `qtbot.waitUntil` 로 기다린 뒤 단언하고, 동기 경로는 호출이 돌아온 뒤 바로 단언한다. 필요한 helper·fake가 없으면 `tests/gui_support/` 에 더한다(기존 이름과 동작은 바꾸지 않는다).
- fixture가 돌려주는 객체의 정확한 모양과 helper 인자는 `tests/gui/conftest.py`·`tests/gui_support/` 를 읽고 맞춘다. 이 파일의 예시는 이름만 가리킨다.

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

device를 바꿀 때 탭 하나의 행 읽기가 실패하면, 그 탭은 **이전 device의 행을 보여 준 채** 새 device의 탭으로 취급된다. 그 상태에서 고치고 저장하면 이전 device의 행이 새 device에 통째로 써진다. 로드가 실패한 탭은 비워서(모델 없음) 저장 대상에서 빠지게 하고, 오류는 지금처럼 "Load Failed" 로 보이게 한다.

## 읽어야 할 파일

- `/CLAUDE.md`, `/docs/ARCHITECTURE.md`(데이터 흐름의 탭 저장, 스레딩), `/docs/ADR.md`(ADR-004, ADR-009), `/docs/UI_GUIDE.md`(원칙 4·5)
- `src/genviewer/controllers/tab_section.py` — `set_device` (~63-67), `payload_fragment` (~115-121), `_on_dirty_changed`/`is_dirty`/`set_dirty` (~146-161), `get_buffer_rows` (~163-164), `get_or_create_model`·`model_by_device` (~166-177), `update_model` (~181-192, `@report("Load Failed")`), `bind_model`/`clear_model` (~194-199)
- `src/genviewer/controllers/parameter_tab.py` — `set_device_to_section` (~117-127, `current_device_id` 를 먼저 바꾼 뒤 섹션마다 `set_device`), `save_all`/`_write` (~55-91, RELOAD 분기가 `update_model` 을 부른다), `discard_all` (~111-115)
- `src/genviewer/utils/reporting.py` — `report`(예외를 잡아 `notifyRequested("error", title, user_message(exc))` 와 파일 로그)
- `src/genviewer/views/tab_section.py` — `_wire_model_dirty`, `mark_dirty_ui`
- `src/genviewer/controllers/device_tab.py` — `_switch_device_by_index` (~420-454)
- `tests/gui/conftest.py`, `tests/gui_support/fakes.py`, `tests/gui_support/helpers.py`
- 이전 step에서 수정된 파일: 이 phase의 첫 step이다. phase 3이 바꾼 저장 경로(`controllers/parameter_tab.py`, `controllers/device_table.py`, `controllers/device_tab.py`)와 그 테스트를 먼저 읽어라.

## 버그

`update_model` 은 이렇다.

```python
@report("Load Failed")
def update_model(self):
    if not self.device_id:
        self.clear_model()
        return
    model = self.get_or_create_model(self.device_id)
    model.set_device_celltype(self.device_celltype)
    rows = self.repo.fetch_by_device(self.table_name, self.columns, self.device_id)
    self.bind_model(model)
    model.set_data(rows)
    self.set_dirty(False)
```

device A를 보다가 B를 고른다. `ParameterTabController.set_device_to_section(B)` 가 `current_device_id = B` 로 바꾸고, 섹션마다 `set_device(B)` 가 `self.device_id = B` 로 바꾼 뒤 `update_model()` 을 부른다. 여기서 `fetch_by_device` 가 예외를 내면(서버 끊김, 55P03/57014 타임아웃) `@report` 가 "Load Failed" 를 띄우고 예외를 삼킨다. 그런데 `bind_model` 에 닿지 않았으므로 `self.model` 과 표는 **A의 모델 그대로**다.

- 사용자가 화면(A의 행)을 고치면 모델의 `modified` → `dirtyChanged` → `_on_dirty_changed` 가 `dirty_by_device[B] = True` 로 적는다.
- 저장하면 `payload_fragment()` 가 `self.model.get_data()`, 즉 **A의 행**을 돌려주고, `_write` 는 `current_device_id = B` 로 `replace_many_for_device` 를 부른다. B의 그 탭 행이 A의 행으로 통째로 바뀐다(데이터 손상, 이력에도 B의 변경으로 남는다).
- 덤으로 `model_by_device[B]` 에는 읽지 못한 빈 모델이 캐시되어 있다. 그것을 그대로 붙이면 "B는 행이 없다" 로 보이고, 저장하면 B의 행을 지운다. 그래서 고칠 때 빈 캐시 모델을 붙여서도 안 된다.

재현: `device_tab_ctrl` 에서 sf2p → nfet_a 선택 → `store.fail_next("fetch_by_device", DbUnavailableError("down"))` → nfet_b 선택. 처음 읽는 섹션(`_sections` 순서상 첫 탭)이 실패하고, 그 섹션의 `model` 이 nfet_a의 모델이다.

이것은 주장이다. 먼저 재현하라.

**불변식**: `update_model()` 이 끝난 뒤 `self.model` 은 `self.device_id` 에 대해 **이번 호출에서 새로 읽어 채운** 모델(`model_by_device[self.device_id]`)이거나 `None` 이다. 표(`self.ui.table_view.model()`)는 항상 `self.model` 과 같다. `self.model is None` 이면 `is_dirty()` 는 False이고, 따라서 `save_all` 이 그 섹션의 `payload_fragment()` 를 부르지 않는다.

## 작업

### 1. 테스트 먼저 (`tests/gui/test_tab_section_load.py`, 새 파일)

공통 준비: `device_tab_ctrl`, `store`. `select_process(…, "sf2p")`, `select_device_row(…, "nfet_a")`. 실패시킬 탭(첫 섹션)에서 nfet_a와 nfet_b가 **서로 다른 행**을 갖게 한다(시드에 없으면 테스트에서 store에 넣는다). 이 fixture는 창에 연결되어 있지 않으므로 알림은 `ctrl.notifyRequested` 에 리스트를 연결해 모은다. 실패시킬 예외는 `genviewer.service.errors.DbUnavailableError`.

- **로드 실패 뒤 불변식**: `fail_next("fetch_by_device", …)` 후 nfet_b 선택. 모든 섹션(`ctrl.parameter_tab._sections.values()`)에서 `sec.device_id == B`, `sec.model is None or sec.model is sec.model_by_device[B]`, `sec.ui.table_view.model() is sec.model`. 실패한 섹션이 정확히 하나 있고 그 섹션은 `model is None`, `is_dirty() is False`. 모은 알림에 `("error", "Load Failed", …)` 가 있다(오류는 여전히 보인다). 다른 섹션은 B의 행을 보여 준다. **수정 전에는 실패한 섹션의 `model` 이 A의 모델이라 실패해야 한다.**
- **데이터 무결성**: 같은 상황에서 실패한 섹션의 표에 모델이 붙어 있으면(수정 전) `edit_tab_cell` 로 셀 하나를 고친다. 그 뒤 `ctrl.parameter_tab.save_all()` 을 부른다. store의 B 행은 시드 그대로이고, `store.calls` 에 device B로 A의 행을 쓴 `replace_many_for_device` 가 없다. **수정 전에는 B의 행이 A의 행으로 바뀌어 실패해야 한다.** (수정 뒤에는 표에 모델이 없어 편집 자체가 안 된다. 테스트는 그 분기를 `if` 로 다룬다.)
- **dirty가 남아 있던 경우**: B에 편집이 남은 채로 다시 읽다 실패하는 경로(`discard_all()` 이나 RELOAD 가 `update_model()` 을 부르는데 그때 `fetch_by_device` 가 실패)에서도 실패한 섹션은 `model is None`, `is_dirty() is False` 이고, `save_all()` 이 예외 없이 끝난다(`None.get_data()` 의 AttributeError가 나지 않는다).
- **회복**: 실패 뒤 nfet_a를 골랐다가 다시 nfet_b를 고르면(이번에는 실패 없음) 그 섹션의 `model` 이 `model_by_device[B]` 이고 store의 B 행과 같다.
- **정상 경로(회귀)**: 실패가 없으면 device를 바꿀 때마다 모든 섹션의 `model` 이 `model_by_device[새 device]` 이고 행이 store와 같으며 dirty가 아니다.

### 2. 수정 (`controllers/tab_section.py` 의 `update_model`)

```python
@report("Load Failed")
def update_model(self) -> None: ...   # 시그니처·데코레이터 그대로
```

- `fetch_by_device` 가 예외를 내면 `clear_model()` 로 `self.model` 과 표를 비우고, `set_dirty(False)` 로 그 device의 dirty와 탭 이름의 ` *` 표시를 지운 뒤, **예외를 다시 올린다**. `@report` 가 지금처럼 "Load Failed" 알림과 파일 로그를 남긴다.
- 성공 경로의 결과는 지금과 같다(그 device의 모델을 붙이고, 읽은 행을 넣고, dirty 해제).
- 순서는 재량이다(먼저 읽고 성공했을 때만 붙여도 되고, 실패하면 되돌려도 된다). 위 불변식만 지켜라.
- `device_id` 가 없을 때의 `clear_model()` 동작은 그대로 둔다.
- `discard_all()` 과 `_write` 의 RELOAD 분기는 `update_model()` 을 그대로 부르므로 따로 고치지 않는다. 테스트로만 확인한다.

### 3. 문서

- 바꿀 문서는 없다. `docs/notes/known-issues.md` 는 phase 마무리에서 정리하므로 건드리지 않는다.

## Acceptance Criteria

```bash
uv run pytest tests/gui/test_tab_section_load.py -q   # 새 테스트 통과 (수정 전에는 불변식·무결성 테스트가 실패해야 한다)
uv run ruff check src tests                           # 린트 통과
uv run pytest tests/gui -q                            # GUI 테스트 통과
uv run pytest -q                                      # 전체 통과 (DB 테스트는 skip 가능)
```

## 검증 절차

1. 위 AC 커맨드를 실행한다.
2. 아키텍처 체크리스트를 확인한다:
   - `controllers/` 안에서만 고쳤는가(레이어 표)?
   - 화면 문구가 `user_message()` 를 거치는가(`@report` 가 한다)?
   - CLAUDE.md CRITICAL 규칙(화면에 들고 있지 않은 것을 지우지 않는다 등)을 위반하지 않았는가?
3. 결과에 따라 `phases/4-gui-robustness/index.json` 의 step 0을 업데이트한다:
   - 성공 → `"status": "completed"`, `"summary": "TabSectionController.update_model: 읽기 실패 시 clear_model+set_dirty(False) 후 재발생(Load Failed 유지). 불변식: model 은 새로 읽은 것 또는 None. RED: <테스트 이름>. tests/gui/test_tab_section_load.py 추가"`
   - 재현 안 됨 → `"status": "completed"`, `"summary": "not reproduced: <이유>"`
   - 수정 3회 시도 후에도 실패 → `"status": "error"`, `"error_message": "구체적 에러 내용"`
   - 사용자 개입 필요 → `"status": "blocked"`, `"blocked_reason": "구체적 사유"` 후 즉시 중단

## 금지사항

- 실패를 삼키고 `return` 만 하지 마라(`@report` 를 떼거나 `try/except: pass`). 이유: 로드가 실패했다는 사실이 화면과 파일 로그에 남아야 한다(UI_GUIDE 원칙 4·5). 다시 올려야 "Load Failed" 가 뜬다.
- 실패했을 때 `model_by_device[B]` 의 빈 캐시 모델을 표에 붙이지 마라. 이유: "B는 행이 없다" 로 보이고, 그 상태로 저장하면 B의 행이 지워진다. 불변식은 "새로 읽은 모델 또는 None" 이다.
- `ParameterTabController.set_device_to_section` 의 순서나 `current_device_id` 를 바꾸지 마라. 이유: 다른 탭은 B를 제대로 읽었고 그 저장 대상은 B가 맞다. 이 step은 `controllers/tab_section.py` 하나만 고친다.
- 탭 로드를 워커 스레드(`run_blocking`/`Task`)로 옮기지 마라. 이유: GUI 스레드의 동기 탭 로드는 알려진 상태(ARCHITECTURE 스레딩 절)이고 이 step의 범위가 아니다.
- 같은 device를 다시 클릭할 때 탭이 다시 읽히는 문제(known-issues K17)를 고치지 마라. 이유: 선택 추적 구조 문제라 따로 다룬다.
- 기존 테스트를 깨뜨리지 마라.
