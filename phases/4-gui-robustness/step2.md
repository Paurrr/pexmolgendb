# Step 2: parameter-add-tab

## 배경 (phase 4 공통)

이 저장소는 이미 여러 명이 쓰는 도구다. 지금은 **에러·버그만 고친다**(CLAUDE.md, ADR-015). phase 4는 GUI가 실패·경합 상황에서 데이터를 잘못 쓰거나 죽는 버그를 한 step에 하나씩 고친다(탭 로드 실패, 탭 섹션 입력, "+" 탭, 필터 중 정렬, DB 재접속, 창 닫기, Virtuoso 소켓 워커). phase 3(`3-gui-save-fixes`)이 먼저 끝나 있다. 저장 함수가 결과를 돌려주고(`save_all() -> bool`, `DeviceTabController.save_db() -> bool`), `select_process_silently` 가 생겼다. 그 밖에 `deviceVersionBumped`/`adopt_device_version`(내 device 저장 뒤 탭이 version을 따라간다), `DeviceTabController._save_before_process_change`(process 전환 전 질문·저장), `DeviceTableModel.is_row_changed`, device 표 붙여넣기의 `Unsaved Changes` 거부, `save_all` 의 `Save Skipped` 경고가 있다. 정확한 반환 계약은 코드와 `phases/3-gui-save-fixes/index.json` 의 summary로 확인하라.

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

파라미터 탭 줄의 "+" 탭에서 탭을 고르면 "예기치 못한 오류" 가 뜬다. 컨트롤러가 부르는 `ParameterTab.add_tab` 이 없기 때문이다. **사용자 승인(2026-10-17)**: 없는 `add_tab` 을 구현해서, 고른 탭이 다른 탭과 똑같이 붙어 "+" 바로 앞에 생기게 한다.

## 읽어야 할 파일

- `/CLAUDE.md`, `/docs/UI_GUIDE.md`(파라미터 탭 순서: `Summary`, tab_config 순서, 마지막 `+`), `/docs/ARCHITECTURE.md`(레이어 표, "현재 어긋난 곳")
- `src/genviewer/views/parameter_tab.py` — `__init__` (~12-21, "Summary" 와 "+" 만 만든다), `rebuild_tabs` (~23-48, 탭 하나를 만드는 본문 ~28-44), `_set_dirty_marker` (~72-78), `find_tab` (~86-92), `on_tab_changed` (~94-102)
- `src/genviewer/controllers/parameter_tab.py` — `_attach_section` (~35-42), `section` (~44-45), `rebuild_all_sections` (~160-163), `on_tab_clicked` (~165-175, `self.ui.add_tab(selected)` 를 부르는데 그런 메서드가 없다)
- `src/genviewer/dialogs/tab_selector.py` — `TabSelectorDialog(available_tabs, parent)`, `exec_()`, `get_selected_tab()`
- `src/genviewer/controllers/device_tab.py` — `__init__` (~58, `ParameterTabController` 를 repo 없이 만든다), `apply_db` (~266-272, 접속에 성공해야만 `rebuild_all_sections()`)
- `src/genviewer/config/tab_config.json` — 탭 이름 → `{"table", "columns", "headers", …}`
- `tests/gui/conftest.py`, `tests/gui_support/`
- 이전 step에서 수정된 파일: `src/genviewer/controllers/tab_section.py`, `src/genviewer/views/tab_section.py`, `tests/gui/test_tab_section_load.py`, `tests/gui/test_tab_section_view.py` (이 step은 `TabSection` 을 만들기만 하고 그 내부는 바꾸지 않는다)

## 버그

```python
def on_tab_clicked(self, index):
    if self.ui.tabText(index) != "+":
        return
    options = [name for name in tab_config if self.ui.find_tab(name) == -1]
    if not options:
        return
    dialog = TabSelectorDialog(options, self.ui)
    if dialog.exec_():
        selected = dialog.get_selected_tab()
        if selected:
            self.ui.add_tab(selected)   # ParameterTab 에 add_tab 이 없다
```

`ParameterTab` 은 처음에 "Summary" 와 "+" 만 갖고, 탭 섹션은 DB 접속에 성공한 뒤 `apply_db` → `rebuild_all_sections()` 에서 만들어진다. 그래서 DB 없이 떴거나(시작 접속 실패) 아직 붙지 않은 동안 "+" 를 누르면 14개 탭 이름이 전부 후보로 나오고, 하나를 고르면 `AttributeError: 'ParameterTab' object has no attribute 'add_tab'` 가 슬롯 밖으로 새어 "예기치 못한 오류" 상자가 뜬다. 접속한 뒤에는 모든 탭이 이미 있어 후보가 비므로 "+" 는 아무것도 하지 않는다(그 동작은 그대로 둔다).

이것은 주장이다. 먼저 재현하라.

## 작업

### 1. 테스트 먼저 (`tests/gui/test_parameter_add_tab.py`, 새 파일)

준비: DB 없이 `ui = ParameterTab()`, `qtbot.addWidget(ui)`, `ctrl = ParameterTabController(ui)` 를 만든다(시작 접속이 실패해 섹션이 만들어지지 않은 상태와 같다). `monkeypatch.setattr("genviewer.controllers.parameter_tab.TabSelectorDialog", FakeTabSelector)` — `FakeTabSelector` 는 받은 `available_tabs` 를 기록하고, `exec_()`·`exec()` 는 테스트가 정한 값(기본 True)을, `get_selected_tab()` 은 테스트가 정한 이름을 돌려준다. `name` 은 `tab_config` 의 아무 키 하나.

- **"+" 로 탭 추가**: `plus = ui.count() - 1`(`ui.tabText(plus) == "+"`)에서 `ctrl.on_tab_clicked(plus)` 가 예외 없이 끝난다. **수정 전에는 AttributeError로 실패해야 한다.**
- **결과**: `ui.find_tab(name)` 이 "+" 바로 앞이고 "+" 는 여전히 마지막이다. 그 위젯은 `TabSection` 이고 `columns`·`headers`·`table_name`·`title` 이 `tab_config[name]` 과 같다(`rebuild_tabs` 가 만든 것과 같은 값). `ctrl.section(name)` 이 있고 그 `.ui` 가 그 위젯이다. 현재 탭이 새 탭이다.
- **기존 섹션과 같은 연결**: 새 섹션의 `dirtyChanged.emit(True)` → 탭 이름이 `f"{name} *"`, `False` → `name`. `ctrl.section(name).logRequested` 가 `ctrl.logRequested` 로 이어진다.
- **다음 후보**: 다시 "+" 를 누르면 `FakeTabSelector` 가 받은 후보에 `name` 이 없다.
- **취소**: `exec_()` 가 False면 탭 수가 그대로다. 같은 이름을 두 번 고르면 두 번째는 새 탭을 만들지 않는다(`find_tab` 결과가 하나).
- **회귀(재구성)**: `add_tab` 뒤에 `ctrl.rebuild_all_sections()` 를 부르면 탭 순서가 `Summary`, `tab_config` 순서, `+` 이고 각 이름이 한 번씩만 있다. `ctrl._sections` 키가 `tab_config` 키와 같다. 현재 탭은 index 1(지금 `rebuild_tabs` 동작).
- **회귀(접속 후)**: `device_tab_ctrl` 에서 "+" 를 누르면 후보가 비어 `FakeTabSelector` 가 만들어지지 않는다.

### 2. 수정

```python
# views/parameter_tab.py
class ParameterTab(QTabWidget):
    def add_tab(self, name: str, cfg: dict, on_created=None) -> TabSection: ...
```

- `rebuild_tabs` 의 "탭 하나 만들기" 본문(`TabSection` 생성, `setObjectName`, `on_created(name, section)` 호출, `dirtyChanged` → `_set_dirty_marker` 연결)을 내부 함수 하나로 빼서 `rebuild_tabs` 와 `add_tab` 이 함께 쓴다. `rebuild_tabs` 의 결과(탭 순서, 현재 탭 index 1, 연결)는 바뀌지 않는다.
- `add_tab` 은 새 섹션을 "+" 탭 **바로 앞**에 넣고(`insertTab`), 새 탭을 현재 탭으로 만들고, 그 섹션을 돌려준다. 같은 이름의 탭이 이미 있으면(`find_tab(name) != -1`) 새로 만들지 않고 그 탭의 섹션을 돌려준다.
- 뷰는 지금처럼 탭 설정을 스스로 읽지 않는다. `cfg` 는 컨트롤러가 넘긴다(`rebuild_tabs` 가 `available_tabs` 를 받는 것과 같은 방식).
- `controllers/parameter_tab.py` 의 `on_tab_clicked`: `self.ui.add_tab(selected, tab_config[selected], on_created=self._attach_section)`. 기존 섹션과 똑같이 `_attach_section` 이 `TabSectionController` 를 붙인다(`logRequested`·`notifyRequested` 연결, `_sections[name]` 등록). 그 밖의 `on_tab_clicked` 동작(후보 계산, 취소)은 그대로.
- repo가 없을 때 붙은 섹션은 repo가 None이다. 접속하면 `apply_db` → `rebuild_all_sections()` 가 탭을 전부 다시 만들므로 따로 repo를 넣지 않는다.

### 3. 문서

- UI_GUIDE의 탭 순서 설명("마지막 `+`(숨긴 탭 다시 열기)")은 그대로 맞다. 바꿀 문서는 없다.

## Acceptance Criteria

```bash
uv run pytest tests/gui/test_parameter_add_tab.py -q   # 새 테스트 통과 (수정 전에는 "+" 탭 추가 테스트가 AttributeError로 실패해야 한다)
uv run ruff check src tests
uv run pytest tests/gui -q
uv run pytest -q
```

## 검증 절차

1. 위 AC 커맨드를 실행한다.
2. 아키텍처 체크리스트를 확인한다:
   - `views/parameter_tab.py` 가 controllers·config를 import하지 않는가(레이어 표, 설정은 컨트롤러가 넘긴다)?
   - `rebuild_tabs` 를 쓰는 기존 경로(접속 → 탭 14개)의 결과가 그대로인가?
3. 결과에 따라 `phases/4-gui-robustness/index.json` 의 step 2를 업데이트한다:
   - 성공 → `"status": "completed"`, `"summary": "ParameterTab.add_tab(name, cfg, on_created) 구현(rebuild_tabs 와 탭 생성 본문 공유, '+' 앞 삽입), on_tab_clicked 가 _attach_section 으로 붙임. RED: <테스트 이름>. tests/gui/test_parameter_add_tab.py 추가"`
   - 재현 안 됨 → `"status": "completed"`, `"summary": "not reproduced: <이유>"`
   - 수정 3회 시도 후에도 실패 → `"status": "error"`, `"error_message": "구체적 에러 내용"`
   - 사용자 개입 필요 → `"status": "blocked"`, `"blocked_reason": "구체적 사유"` 후 즉시 중단

## 금지사항

- 탭 닫기(`setTabsClosable(True)`)나 탭 숨기기 기능을 더하지 마라. 이유: 승인된 것은 없는 `add_tab` 을 구현하는 것뿐이다. 기능 추가다.
- "+" 의 후보 계산이나 접속 후 "+" 가 아무것도 하지 않는 동작을 바꾸지 마라. 이유: 버그는 메서드가 없다는 것 하나다.
- 탭 섹션 생성 코드를 `add_tab` 에 복사해 두 벌로 두지 마라. 이유: 둘이 어긋나면(예: dirty 표시 연결 누락) 같은 탭이 경로에 따라 다르게 동작한다. 한 함수를 함께 쓴다.
- `rebuild_tabs` 가 옛 섹션 위젯을 지우지 않는 문제(known-issues K22)를 고치지 마라. 이유: 누수 규모가 작고 이 step의 범위가 아니다.
- 진짜 `TabSelectorDialog` 를 테스트에서 `exec` 하지 마라. 이유: 모달이 테스트를 멈춘다.
- 기존 테스트를 깨뜨리지 마라.
