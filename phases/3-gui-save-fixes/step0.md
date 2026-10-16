# Step 0: device-save-result

## 배경 (phase 3 공통)

이 저장소는 이미 여러 명이 쓰는 도구다. 지금은 **에러·버그만 고친다**(CLAUDE.md, ADR-015). phase 3은 GUI 저장 흐름(`controllers/device_tab.py`, `device_table.py`, `parameter_tab.py`, `main_window.py`, `device_tab_toolbar.py`)의 버그를 고친다. 저장 함수가 "저장했다/사용자가 그만뒀다" 를 돌려주지 않아 취소해도 "Saved" 가 뜨고 화면이 넘어가는 문제, Database → Save 가 탭을 저장하지 않는 문제, 내 device 저장 뒤 내 탭 저장이 나 자신과 충돌하는 문제, process 전환·목록 갱신에서 편집이 말없이 사라지는 문제다. 반환 계약을 바꾸는 step(0, 1)이 먼저 끝나고 호출부 step(2, 3, 5)이 그 계약을 쓴다.

모든 step에 같은 규칙이 적용된다.
1. 아래 "버그"는 **분석 에이전트의 주장**이다. 먼저 실패하는 테스트로 재현하고, RED 출력(테스트 이름과 실패한 단언)을 summary에 적는다.
2. RED는 **Windows 개발 PC에서** 보여야 한다. `posix_only` 테스트는 개발 PC에서 skip되므로 버그를 증명하지 못한다.
3. 재현되지 않으면 `src/` 를 고치지 않는다. 테스트는 특성 테스트로 남기고 `"status": "completed"`, `"summary": "not reproduced: <이유>"` 로 끝낸다.
4. 고친 뒤 수정을 손으로 되돌려 새 테스트가 실패하는지 확인하고 다시 고친다(변이 검사). `git checkout`/`git stash` 로 되돌리지 마라. 이유: 같은 step의 테스트 변경까지 사라진다.
5. 이 파일의 행 번호는 2026-10-17 기준 대략값이다. 이름으로 찾아라.

GUI 테스트 기반은 phase `2-gui-test-infra` 가 만들었다. 아래 이름을 그대로 쓴다.
- `tests/gui/conftest.py`: offscreen. autouse `dialogs` fixture가 모달을 가로챈다. `dialogs.answer_question(*bools)` 는 Yes/No 질문(`utils/dialogs.question`)에, `dialogs.answer_conflict(*choices)` 는 충돌 대화상자에 순서대로 답한다(`genviewer.dialogs.conflict` 의 `RELOAD`/`OVERWRITE`/`CANCEL`). 뜬 것은 `dialogs.shown` 에 `(kind, title, text)` 로 쌓이고, 답을 넣지 않은 모달은 AssertionError를 낸다.
- fixture: `store`(FakeStore. process "sf2p" 에 device "nfet_a", "nfet_b", process "sf4u" 에 device 하나. device마다 탭 두 개에 행이 있다), `device_tab_ctrl`(가짜에 붙어 이미 접속한 DeviceTabController), `main_window`(가짜 위의 MainWindowController와 MainWindow. teardown이 shutdown과 close를 한다).
- `tests/gui_support/fakes.py`: `FakeStore`(`calls` 는 `(method, args)` 목록, `fail_next(method_name, exc)`), `FakeDatabase`, 실제 repo와 같은 의미의 가짜 Device/Parameter/Process/IO repository(값이 바뀐 행만 version +1, force가 아니면 version 불일치·사라진 행에 `StaleWriteError`).
- `tests/gui_support/helpers.py`: `select_process(ctrl, name)`, `select_device_row(ctrl, row)`, `edit_device_cell(ctrl, row, column, value)`, `edit_tab_cell(ctrl, tab_name, row, column, value)`. `ctrl` 은 DeviceTabController다(`main_window` 면 `.device_tab`).
- "bob 이 nfet_a 를 저장한다" 는 store에서 그 device의 version을 직접 1 올리는 것(값은 그대로, `updated_by="bob"`)이다. 다른 사용자의 탭 저장과 같다. `store.touch_device(device_id, actor="bob")` 를 쓴다(phase 2 의 FakeStore). device id·version은 화면 모델에서 읽는다(`ctrl.device_table.ui.model_safe().get_device(row)`).
- 새 GUI 테스트는 `tests/gui/test_<주제>.py` 에 둔다. "아무 일도 일어나지 않았다" 는 `qtbot.wait` 로 기다리지 말고 `store.calls` 를 `qtbot.waitUntil` 로 기다린 뒤 단언한다.
- 저장 경로에는 넓은 `except Exception`(`save_db`, `@report`)이 있어 답을 넣지 않은 모달의 AssertionError를 삼킬 수 있다. 대화상자가 떴는지·안 떴는지는 반환값, `store.calls`, `dialogs.shown` 으로 직접 단언한다.
- 알림: `main_window` 를 쓰면 `notifyRequested` 가 `MainWindow.notify` 를 거쳐 `dialogs.shown` 에 남는다(알림 상자는 답 없이 기록만 된다고 본다. 다르면 phase 2 방식을 따른다). `device_tab_ctrl` 만 쓰면 `ctrl.notifyRequested` 를 테스트 안에서 리스트에 연결해 확인한다.
- 필요한 헬퍼가 없거나 이름이 다르면(phase 2가 "not reproduced" 로 끝났거나 다르게 만들었으면) `tests/gui_support/` 에 직접 더한다. `src/` 에 테스트용 코드를 넣지 않는다.

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

`DeviceTableController.save_all()` 이 "저장했다(또는 저장할 것이 없었다)" 와 "사용자가 저장하지 않기로 했다" 를 `bool` 로 돌려주게 한다(분석 G4의 계약 절반). 지금은 언제나 `None` 이라서 호출부가 충돌 대화상자의 "취소" 뒤에도 "Saved" 를 띄우고 화면을 넘긴다. 이 step은 **계약만** 만든다. 호출부(`save_db`, Ctrl+S, process 전환)는 step 2·5가 바꾼다. 지금 호출부는 반환값을 무시하므로 이 step만으로는 사용자에게 보이는 동작이 바뀌지 않는다.

## 읽어야 할 파일

- `/CLAUDE.md`, `/docs/ARCHITECTURE.md`(데이터 흐름 → device 저장), `/docs/ADR.md`(ADR-004), `/docs/UI_GUIDE.md`(원칙 4, 문구 → 저장 충돌 세 갈래)
- `src/genviewer/controllers/device_table.py` — `save_all` (~330-363), `_write_devices` (~365-397, 다시 읽기·취소면 `None`), `refresh_devices` (~255-297, 끝에서 `set_dirty(False)`), `is_dirty` (~212-215)
- `src/genviewer/service/repo/device.py` — `SaveResult` (~19-37), `upsert_devices` (~157-247), `_preflight` (~273-299). 화면의 device가 전부 가고, 하나라도 version이 어긋나면 아무것도 쓰지 않고 `StaleWriteError`
- `src/genviewer/dialogs/conflict.py` — `ask_conflict`, `RELOAD`/`OVERWRITE`/`CANCEL`. 창을 닫으면 `CANCEL`(`_choice` 기본값, ~27)
- `src/genviewer/utils/reporting.py` — `report` docstring("값을 돌려주는 함수에는 쓰지 말 것")
- 호출부(이 step에서는 읽기만): `controllers/device_tab.py` `save_db` (~111-127), `on_process_changed` (~391-397), `controllers/main_window.py` `_on_save_triggered` (~173-191)
- phase 2가 만든 `tests/gui/conftest.py`, `tests/gui_support/fakes.py`, `tests/gui_support/helpers.py`
- 이전 step에서 수정된 파일: 없음(phase 3의 첫 step)

## 버그

```python
def save_all(self):
    if self.repo is None:
        return
    ...
    result = self._write_devices(to_save, deleted)
    if result is None:
        return
    ...
    self.notifyRequested.emit("info", "Save Complete", summary)
    self.refresh_devices()
```

`_write_devices` 는 충돌 대화상자에서 다시 읽기·취소(창 닫기 포함)면 `None`, 저장했으면 `SaveResult` 를 돌려준다. `save_all` 은 그 구분을 버리고 모든 경로에서 `None` 을 돌려준다. 그래서 호출부는 "저장됐다" 와 "사용자가 취소했다" 를 구별할 수 없다.

사용자 화면의 증상(호출부를 고치는 step 2 뒤에 사라진다): sf2p를 고른다 → nfet_a의 Description을 고친다 → 그 사이 bob이 nfet_a를 저장한다 → Database → Save → "Save Conflict" 에서 "취소" → 그래도 "Saved: All changes have been saved." 가 뜬다.

이 step의 RED는 반환값으로 본다. 수정 전에는 모든 경우에 `None` 이므로 `is True`/`is False` 단언이 전부 실패한다.

## 작업

### 1. 테스트 먼저 (`tests/gui/test_device_save_result.py`, 새 파일)

`device_tab_ctrl` 로 sf2p를 고르고(`select_process`), 필요하면 `edit_device_cell` 로 nfet_a(0행)의 Description을 고친 뒤 `ctrl.device_table.save_all()` 을 직접 부른다. 경우마다 반환값과 최종 상태를 단언한다.

| 경우 | 만드는 법 | 반환 | 최종 상태 |
|---|---|---|---|
| 저장 성공 | 편집 → 저장 | `True` | `upsert_devices` 1회, 가짜 repo(`fetch_devices_by_process`)에 편집 값, `is_dirty()` False, "Save Complete" 알림 |
| 바뀐 행 없음 | 편집 없이 저장 | `True` | "Save Complete" / "No changes to save." |
| 쓸 것 없음 | `ctrl.device_tab_toolbar.add_process("empty_p")` 로 device 없는 process를 만들어 고른다 | `True` | `upsert_devices` 호출 없음 |
| stale × 덮어쓰기 | 편집 → bob이 nfet_a 저장 → `answer_conflict(OVERWRITE)` | `True` | 두 번째 `upsert_devices` 가 `force=True`, 가짜 repo에 내 값 |
| stale × 취소 | 같은 충돌 → `answer_conflict(CANCEL)` | `False` | 화면에 편집 값 그대로, `is_dirty()` True, "Save Complete" 알림 없음, `upsert_devices` 1회뿐 |
| stale × 다시 읽기 | 같은 충돌 → `answer_conflict(RELOAD)` | `False` | 화면이 서버 값, `is_dirty()` False, 알림 없음 |
| 접속 전 | `ctrl.device_table.repo = None` | `False` | 아무 호출 없음 |
| 예상 밖 예외 | `store.fail_next("upsert_devices", RuntimeError("boom"))` | 예외가 그대로 난다(`pytest.raises(RuntimeError)`) | 편집 값 그대로, `is_dirty()` True |

- 접속 끊김(`DbUnavailableError`)은 예상 밖 예외와 같은 경로다. 따로 테스트하지 않아도 된다.
- `deleted` 충돌(남이 device를 지움)은 같은 분기를 탄다. 사라진 device를 만드는 헬퍼가 있으면 deleted × 취소 하나를 더한다. deleted × 덮어쓰기는 known-issues K20(범위 밖)이다. 지금 동작(`True`, 사라진 device의 편집은 버려짐)을 바꾸지 않고 테스트하지 않는다.
- 알림은 `ctrl.notifyRequested` 를 리스트에 연결해 확인한다.

### 2. 수정 (`controllers/device_table.py` 의 `save_all`)

```python
def save_all(self) -> bool: ...
```

- `True`: 저장했다(덮어쓰기 포함), 또는 쓸 것이 없었다(`_write_devices` 가 빈 `SaveResult` 를 돌려줬거나 바뀐 행이 0).
- `False`: 사용자가 충돌 대화상자에서 취소(창 닫기 포함)나 다시 읽기를 골랐다, 또는 `repo is None`.
- 예외는 잡지 않는다. `run_blocking` 이 다시 낸 예외(접속 끊김, 덮어쓰기 재시도의 실패 포함)가 그대로 올라간다.
- 알림·로그 문구, `refresh_devices` 호출 위치는 그대로 둔다. 반환값만 더한다.
- docstring에 이 계약을 적고, 호출부가 이 값을 보고 "Saved" 를 띄울지 정한다고 한 줄 적는다.

### 3. 문서

- 바꿀 문서는 없다. 사용자에게 보이는 동작이 바뀌지 않는다. ARCHITECTURE의 저장 흐름은 phase 마무리에서 고친다.

## Acceptance Criteria

```bash
uv run pytest tests/gui/test_device_save_result.py -q   # 새 테스트 통과 (수정 전에는 반환값 단언이 실패해야 한다)
uv run ruff check src tests
uv run pytest tests/gui -q
uv run pytest -q
```

## 검증 절차

1. 위 AC 커맨드를 실행한다.
2. 아키텍처 체크리스트를 확인한다:
   - `controllers/device_table.py` 만 바꿨는가? 호출부(`device_tab.py`, `main_window.py`)는 그대로인가?
   - `service/repo/` 의 SQL을 건드리지 않았는가(DB 테스트가 필요 없는 step이다)?
   - `save_all` 에 `@report` 를 붙이지 않았는가?
3. 결과에 따라 `phases/3-gui-save-fixes/index.json` 의 step 0을 업데이트한다:
   - 성공 → `"status": "completed"`, `"summary": "DeviceTableController.save_all -> bool (True=저장·덮어쓰기·쓸 것 없음, False=취소·다시 읽기·repo 없음, 예외는 그대로). 호출부 불변. RED: <테스트 이름>. tests/gui/test_device_save_result.py"`
   - 재현 안 됨 → `"status": "completed"`, `"summary": "not reproduced: <이유>"`
   - 수정 3회 시도 후에도 실패 → `"status": "error"`, `"error_message": "구체적 에러 내용"`
   - 사용자 개입 필요 → `"status": "blocked"`, `"blocked_reason": "구체적 사유"` 후 즉시 중단

## 금지사항

- 호출부(`save_db`, `_on_save_triggered`, `on_process_changed`)를 바꾸지 마라. 이유: 반환 계약 step과 호출부 step을 나눈다(harness 규칙 10). 호출부는 step 2·5가 바꾼다.
- 예외를 잡아 `False` 로 바꾸지 마라. 이유: `False` 는 "사용자가 저장하지 않기로 했다" 는 뜻이다. 예상 밖 예외는 호출부의 `report_error`/`@report` 가 이유와 함께 알린다. 삼키면 접속 끊김이 취소처럼 조용해진다.
- `save_all` 에 `@report` 를 붙이지 마라. 이유: 값을 돌려주는 함수에 붙이면 예외가 `None` 이 되어 호출부가 분기를 잘못 탄다(`utils/reporting.py` docstring).
- `_write_devices` 의 계약(다시 읽기·취소면 `None`)과 충돌 처리(다시 읽기 → `refresh_devices`, 로그 문구)를 바꾸지 마라. 이유: 이 step은 이미 있는 구분을 위로 올리기만 한다.
- CellType이 목록에 없는 행을 건너뛰는 동작(`invalid_devices`)을 손대지 마라. 이유: step 7 범위다.
- 알림 문구("Save Complete", `_describe_save`)를 바꾸지 마라. 이유: 버그 수정 중에 기존 문구를 바꾸지 않는다(CLAUDE.md).
- 기존 테스트를 깨뜨리지 마라. 단 phase 2 테스트가 `save_all() is None` 같은 지금 동작을 그대로 고정하고 있으면 그 단언만 새 계약으로 바꾸고 summary에 적는다.
