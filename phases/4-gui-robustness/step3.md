# Step 3: device-sort

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

device 표 머리글 메뉴의 "오름차순 정렬"/"내림차순 정렬" 이 저장 안 한 상태를 지우지 않게 한다. 지금은 정렬이 모델을 통째로 갈아 끼우면서 기준점까지 새로 잡아, 검색 필터에 가려진 device가 화면에서 사라지고, 저장 전에 지운 device가 "지울 목록" 에서 빠지고, 고친 셀 표시와 undo가 사라진다. 정렬을 끌어 옮기기(`moveRows`)와 같은 규칙의 "저장 안 한 변경" 으로 만든다.

## 읽어야 할 파일

- `/CLAUDE.md`(CRITICAL: 화면에 들고 있지 않은 device는 지우지 않는다, 명시적으로 지운 id만), `/docs/UI_GUIDE.md`(dirty 셀 색, 원칙 2), `/docs/ARCHITECTURE.md`(device 저장 흐름)
- `src/genviewer/controllers/device_table.py` — `_on_header_menu` (~101-115), `sort_and_commit` (~117-128), `refresh_devices` (~255-297), `save_all` (~330-363, `model.get_devices()` 전부와 `model.deleted_devices()` 를 쓴다), `_on_dirty_changed`/`is_dirty` (~206-215)
- `src/genviewer/models/device_table.py` — `deleted_devices` (~70-82, 기준점 `_original_by_id` 와 현재 목록을 비교), `set_devices`/`update_devices` (~99-110, 둘 다 `reset_modified()`), `moveRows` (~225-251, 따라야 할 규칙), `reset_modified` (~256-261), `is_modified` (~263-264, 순서까지 비교), `undo`/`redo`/`_push_undo` (~266-292), `_recompute_dirty_cells` (~310-318), `data` 의 `BackgroundRole` (~41-45)
- `src/genviewer/views/device_table.py` — `proxy_model`(`SortingProxyModel`, 필터 키 컬럼 0) (~52-55), `apply_filter` (~183-187), `_wire_model_dirty` (~199-200)
- `src/genviewer/models/sorting_proxy.py`
- `tests/gui/conftest.py`, `tests/gui_support/`
- 이전 step에서 수정된 파일: `src/genviewer/controllers/tab_section.py`, `src/genviewer/views/tab_section.py`, `src/genviewer/views/parameter_tab.py`, `src/genviewer/controllers/parameter_tab.py` (이 step과 관계없음)

## 버그

```python
def sort_and_commit(self, col: int, order: Qt.SortOrder):
    self.ui.proxy_model.sort(col, order)
    model = self.ui.model_safe()
    sorted_data = []
    for row in range(self.ui.proxy_model.rowCount()):
        proxy_index = self.ui.proxy_model.index(row, 0)
        source_index = self.ui.proxy_model.mapToSource(proxy_index)
        sorted_data.append(model.get_devices()[source_index.row()])
    model.set_devices(sorted_data)
    self.ui.proxy_model.sort(-1)
    self.ui.proxy_model.invalidate()
```

1. **보이는 행만 모은다.** 검색 필터(`apply_filter`)가 켜져 있으면 `proxy_model.rowCount()` 는 걸러진 행 수다. 숨은 device는 `sorted_data` 에 없고 `set_devices` 가 모델을 그것으로 바꾸므로 **화면에서 사라진다**. 숨은 device에 한 편집도 함께 사라진다.
2. **`set_devices` 가 `reset_modified()` 를 부른다.** 필터와 관계없이 기준점(`_original_devices`, `_original_by_id`)이 정렬된 현재 목록으로 바뀐다.
   - 저장 전에 지운 device가 `deleted_devices()` 에서 빠진다. 저장해도 DB에서 지워지지 않고, 다시 읽으면 되살아난다. 사용자가 한 삭제가 말없이 취소된다.
   - 고친 셀의 노란 표시와 undo/redo 기록이 사라진다.
   - `modified` 를 내지 않으므로 컨트롤러의 dirty(`dirty_by_process_id`)와 모델(`is_modified()` False)이 어긋난다. 편집 없이 정렬만 한 경우에는 process를 바꿔도 묻지 않아 정렬이 말없이 버려진다.

이것은 주장이다. 먼저 재현하라.

## 작업

### 1. 테스트 먼저 (`tests/gui/test_device_sort.py`, 새 파일)

준비: `device_tab_ctrl`, `store`. `select_process(…, "sf2p")`. 순서가 바뀌는 정렬을 만들 수 있게 device가 둘 이상이어야 하고, 필요하면 store에 device를 더 넣는다(이름은 ASCII로). `model = ctrl.device_table.ui.model_safe()`. 정렬은 메뉴(`exec_` 로 뜨는 팝업) 대신 `ctrl.device_table.sort_and_commit(0, order)` 를 직접 부른다. 정렬 방향은 시드 순서를 보고 **순서가 실제로 바뀌는 쪽**을 고른다.

- **필터 중 정렬이 숨은 device를 지우지 않는다**: `ctrl.device_table.ui.apply_filter("nfet_b")` 후 정렬. 모델의 device id 집합이 정렬 전과 같다(숨은 nfet_a가 남아 있다). 필터는 그대로 유지된다(프록시 행 수가 정렬 전과 같다). `apply_filter("")` 로 풀면 전부 보인다. **수정 전에는 nfet_a가 모델에서 사라져 실패해야 한다.**
- **지운 device가 남는다**: device 하나를 지운 뒤(`model.remove_rows([r])` 또는 `ui.delete_rows` + `dialogs.answer_question(True)`) 정렬 → `model.deleted_devices()` 에 그 id가 남아 있다. **수정 전에는 비어서 실패해야 한다.** 이어서 `save_all()` → `store.calls` 의 `upsert_devices` 가 `deleted` 에 그 id를 담고, store에서 그 device가 지워진다.
- **고친 셀 표시와 undo가 남는다**: `edit_device_cell` 로 한 device의 description을 고친 뒤 순서가 바뀌는 정렬 → 그 device가 옮겨 간 행의 description 셀 `BackgroundRole` 이 `QColor(255, 249, 196)` 이고, `model.is_modified()` 와 `ctrl.device_table.is_dirty()` 가 True다. `model.undo()` 한 번이면 정렬 전 순서로 돌아가고 편집은 남는다. **수정 전에는 표시가 사라져 실패해야 한다.**
- **정렬만 해도 저장 안 한 변경이다**: 편집 없이 순서가 바뀌는 정렬 → `qtbot.waitSignal(model.modified)` 로 `modified` 가 나오고 `ctrl.device_table.is_dirty()` 가 True다. 이미 그 순서인 상태에서 같은 정렬을 다시 부르면 `modified` 가 나오지 않고 undo로 되돌릴 것이 생기지 않는다(동기 경로라 호출 직후 단언한다).
- **필터 중 정렬 뒤 저장**: 필터를 켠 채 정렬하고 `save_all()` → `upsert_devices` 의 저장 목록에 숨은 device도 있고, `order` 가 정렬된 순서(0..n-1)다.
- **회귀**: 필터 없이 오름차순·내림차순으로 정렬한 이름 순서가 `sorted(names)`·`sorted(names, reverse=True)` 와 같다(지금 프록시 정렬과 같은 결과).

### 2. 수정

```python
# models/device_table.py
class DeviceTableModel(QAbstractTableModel):
    def sort_rows(self, column: int, order: Qt.SortOrder) -> bool: ...   # 순서가 바뀌었으면 True
```

- 모델의 **모든** 행(`_devices`)을 그 컬럼의 표시 값(`DisplayRole` 과 같은 값, None은 "")으로 정렬한다. 안정 정렬이고(같은 값끼리는 지금 순서), `Qt.DescendingOrder` 면 반대 방향이다.
- `moveRows` 와 같은 규칙을 따른다. 순서가 실제로 바뀔 때만 `_push_undo()` → 재배열 → `_recompute_dirty_cells()` → 배경 갱신 → `_emit_modified()` 하고 True. 순서가 그대로면 아무것도 바꾸지 않고(undo 기록도 남기지 않고) False.
- 기준점(`_original_devices`, `_original_by_id`)과 `known_names` 는 건드리지 않는다. 그래서 `deleted_devices()`, dirty 셀, `is_modified()` 가 정렬 뒤에도 맞는다.
- 뷰 갱신은 `beginResetModel`/`endResetModel` 이나 `layoutAboutToBeChanged`/`layoutChanged` 중 하나를 쓴다. 선택·현재 행 처리는 지금 `set_devices` 의 reset과 같은 수준이면 된다.
- `controllers/device_table.py` 의 `sort_and_commit(col, order)` 는 `model.sort_rows(col, order)` 를 부른다. `set_devices` 호출과 "프록시에서 보이는 행 모으기" 를 없앤다. 프록시를 정렬된 상태로 남기지 않는다(지금처럼 원본 순서를 그대로 보여 준다). 필터는 건드리지 않는다.

### 3. 문서

- 바꿀 문서는 없다. 필터 중 여러 행 끌어 옮기기(known-issues K18)는 그대로 둔다.

## Acceptance Criteria

```bash
uv run pytest tests/gui/test_device_sort.py -q   # 새 테스트 통과 (수정 전에는 필터·삭제·dirty 표시 테스트가 실패해야 한다)
uv run ruff check src tests
uv run pytest tests/gui -q
uv run pytest -q
```

## 검증 절차

1. 위 AC 커맨드를 실행한다.
2. 아키텍처 체크리스트를 확인한다:
   - `models/device_table.py` 가 `utils.validators` 밖의 우리 모듈을 import하지 않는가(레이어 표: models는 `utils.validators` 만 안다)?
   - CLAUDE.md CRITICAL "명시적으로 지운 id만 삭제" 를 지키는가(정렬 뒤 `deleted_devices()` 가 지운 것만 담는다)?
3. 결과에 따라 `phases/4-gui-robustness/index.json` 의 step 3을 업데이트한다:
   - 성공 → `"status": "completed"`, `"summary": "DeviceTableModel.sort_rows(col, order) 추가(전체 행 안정 정렬, moveRows 규칙: undo·dirty 재계산·modified, 기준점 유지). sort_and_commit 이 set_devices 대신 사용. RED: <테스트 이름>. tests/gui/test_device_sort.py 추가"`
   - 재현 안 됨 → `"status": "completed"`, `"summary": "not reproduced: <이유>"`
   - 수정 3회 시도 후에도 실패 → `"status": "error"`, `"error_message": "구체적 에러 내용"`
   - 사용자 개입 필요 → `"status": "blocked"`, `"blocked_reason": "구체적 사유"` 후 즉시 중단

## 금지사항

- 정렬에 `set_devices`·`update_devices` 를 쓰지 마라. 이유: 둘 다 `reset_modified()` 로 기준점·undo·dirty 표시·지울 목록을 지운다. 바로 이 버그다.
- 프록시(`QSortFilterProxyModel`)가 보여 주는 행으로 모델을 다시 만들지 마라. 이유: 필터에 걸린 행만 남는다.
- 정렬하면서 `reset_modified()`·`clear_dirty()` 를 부르거나 `_original_*` 를 고치지 마라. 이유: 정렬은 저장 안 한 변경이고, 기준점은 서버에서 읽은 상태여야 한다.
- 머리글 클릭 정렬(`setSortingEnabled`)을 켜거나 메뉴 문구("오름차순 정렬"/"내림차순 정렬")를 바꾸지 마라. 이유: 보이는 동작 변경이다(ADR-015).
- 필터 중 여러 행 끌어 옮기기(known-issues K18)와 저장 시 `order` 다시 매기기(K19)를 고치지 마라. 이유: 별도 재현·확인이 필요하다고 기록된 문제다.
- 기존 테스트를 깨뜨리지 마라.
