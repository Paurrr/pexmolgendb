# Step 6: tab-version-sync

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

내가 device 표를 저장해 어떤 device의 version이 올라가면, 그 device의 탭을 열어 둔 탭 컨트롤러도 그 version을 따라가게 한다(분석 G5). 지금은 바로 다음 탭 저장이 **나 자신**과 충돌하고, "다시 읽기" 를 고르면 탭 편집이 사라진다. 다른 사용자의 변경은 지금처럼 충돌로 보여야 한다(ADR-004).

K17(같은 행 재클릭이 탭을 다시 읽음)은 고치지 않고, 재현하는 테스트를 `xfail(strict=True)` 로 남긴다.

## 읽어야 할 파일

- `/CLAUDE.md`(쓰기는 version 낙관적 잠금), `/docs/ADR.md`(ADR-004), `/docs/ARCHITECTURE.md`(device 저장·탭 저장 흐름), `/docs/notes/known-issues.md`(K17)
- `src/genviewer/service/repo/device.py` — `SaveResult` (~19-37, "devices 는 id/version 이 채워진 그 목록 그대로"), `upsert_devices` (~157-247), `_update_existing` (~301-356: 값이 바뀐 행만 `version+1`, RETURNING한 행의 dict만 새 version으로 고친다. force면 version 조건이 빠져 남의 변경 위에 +1)
- `src/genviewer/service/repo/parameter.py` — `replace_many_for_device`(`expected_version` 이 DB와 다르면 `StaleWriteError`)
- `src/genviewer/controllers/device_table.py` — `save_all` (~330-363, 저장 뒤 `refresh_devices`), `_write_devices`, `set_device_version` (~399-404, 탭 저장 → device 표 방향은 이미 있다)
- `src/genviewer/controllers/parameter_tab.py` — `deviceVersionChanged` (~18), `_apply` (~93-109), `set_device_to_section` (~117-127). `current_version` 은 이 둘에서만 바뀐다
- `src/genviewer/controllers/device_tab.py` — `__init__` 연결 (~75-83: `parameter_tab.deviceVersionChanged → device_table.set_device_version`), `_switch_device_by_index` (~420-454, 같은 id면 `set_device_to_section`)
- `src/genviewer/controllers/device_table.py` — `_on_current_changed`, `prev_selected_device`, `last_selected_device` (~222-241, K17의 stale `QModelIndex`)
- 이전 step에서 수정된 파일: `controllers/device_table.py`, `controllers/parameter_tab.py`(`save_all -> bool`), `controllers/device_tab.py`(`save_db -> bool` 은 device와 탭을 차례로 저장, `_switch_device_by_index`, `on_process_changed`), `controllers/main_window.py`, `views/device_tab_toolbar.py`, `controllers/device_tab_toolbar.py`, `tests/gui/test_*.py` 여섯 개

## 버그

`ParameterTabController.current_version` 은 `set_device_to_section`(device를 고를 때 화면 모델의 version)과 `_apply`(내 탭 저장)에서만 바뀐다. 그런데 device 표 저장(`upsert_devices`)도 값이 바뀐 device의 `version` 을 +1 한다. 탭 컨트롤러는 그것을 모른다.

```python
version = run_blocking(lambda: self.repo.replace_many_for_device(
    self.current_device_id, payload,
    expected_version=self.current_version, ...))
```

재현: sf2p → nfet_a를 누른다 → nfet_a의 Description을 고친다 → 탭 셀 하나를 고친다 → Database → Save(step 2 뒤에는 device와 탭을 차례로 저장한다) → "Save Conflict: nfet_a: <나> 님이 수정 (…)" 이 뜬다. "다시 읽기" 를 고르면 탭 편집이 사라진다. Ctrl+S(device 표 포커스) 뒤 nfet_b를 눌러 "Save Changes?" 에 예로 답해도 같다.

K17(고치지 않음): device 저장의 `refresh_devices` 가 모델을 reset하면 선택 모델은 시그널 없이 현재 행을 지운다. 그런데 `DeviceTableController._cur_proxy_index` 는 옛 `QModelIndex` 를 그대로 들고 있고 `isValid()` 가 여전히 True다(2026-10-17 offscreen 확인). 같은 행을 다시 누르면 prev와 cur가 같은 device로 보여 `set_device_to_section` 이 탭을 DB에서 다시 읽고 저장 안 한 탭 편집이 사라진다.

## 작업

### 1. 테스트 먼저 (`tests/gui/test_tab_version_sync.py`, 새 파일)

`device_tab_ctrl` 를 쓴다. sf2p → `select_device_row(ctrl, 0)`(nfet_a)에서 시작한다.

- **Database → Save로 나 자신과 충돌하지 않음**: nfet_a Description 편집 + nfet_a 탭 셀 편집 → `ctrl.save_db()` 가 `True`, `dialogs.shown` 에 충돌이 없음, `replace_many_for_device` 의 `expected_version` 이 device 저장 뒤의 nfet_a version(이전 + 1), 탭 dirty 아님. **수정 전 RED**: 탭 충돌(답이 없어 AssertionError가 `save_db` 의 except에 잡히고 "Save Tabs Failed" 로 `False`).
- **device 저장 뒤 전환**: 같은 편집 → `ctrl.device_table.save_all()` → `answer_question(True)` → `select_device_row(ctrl, 1)` → 충돌 없이 nfet_a 탭이 저장되고 nfet_b로 넘어간다. **수정 전 RED**.
- **신호는 내 쓰기가 올린 행만**: `ctrl.device_table.deviceVersionBumped` 를 리스트에 연결 → **nfet_b** Description만 고쳐 `save_all()` → 기록이 `[(nfet_b_id, v, v + 1)]` 하나뿐(nfet_a는 같이 보내졌지만 값이 같아 오르지 않았다).
- **다른 사용자의 변경은 여전히 충돌**(최신 version을 복사하는 구현을 잡는다): nfet_a 탭 셀 편집 → bob이 nfet_a 저장 → nfet_b Description 편집 → `answer_conflict(OVERWRITE, CANCEL)` → `ctrl.device_table.save_all()` 은 `True`(device 충돌을 덮어씀. nfet_a는 값이 같아 오르지 않는다) → `ctrl.parameter_tab.save_all()` 은 `False` 이고 탭 충돌이 실제로 떴다(두 번째 답이 쓰였다), 탭 편집 그대로.
- **덮어쓰기로 +2가 된 경우**: nfet_a Description과 탭 셀을 고친다 → bob이 nfet_a 저장 → `answer_conflict(OVERWRITE, CANCEL)` → device `save_all()` 이 force로 nfet_a를 `v + 2` 로 만든다 → 탭 저장은 bob 때문에 충돌한다(따라가지 않는다).
- **`adopt_device_version` 단위 테스트**: `current_device_id`=A, `current_version`=v 일 때 `(B, v, v+1)`, `(A, v, v+2)`, `(A, v-1, v)` 는 무시하고 `(A, v, v+1)` 만 받아들인다.
- **K17 재현(고치지 않음)**:
  ```python
  @pytest.mark.xfail(strict=True, reason="K17: 모델 reset 뒤 stale QModelIndex 때문에 같은 행 재클릭이 탭을 다시 읽는다 (docs/notes/known-issues.md K17)")
  ```
  nfet_a 탭 셀 편집 → `ctrl.device_table.save_all()`(device 편집 없이. 그래도 `refresh_devices` 가 모델을 reset한다) → `select_device_row(ctrl, 0)` 다시 → 탭에 고친 값이 남아 있고 `parameter_tab.is_dirty()` True 라고 단언한다. 지금은 실패해서 XFAIL이어야 한다. 이 step의 수정 뒤에도 XFAIL이어야 한다. 만약 XPASS가 나면 아무것도 고치지 말고, 헬퍼의 선택 방식이 실제 클릭과 다른지 확인한다. 정말 재현되지 않으면 xfail 표시를 빼고 일반 특성 테스트로 남긴 뒤 summary에 "K17 not reproduced: <이유>" 를 적는다.

### 2. 수정

```python
# controllers/device_table.py
class DeviceTableController(QObject):
    deviceVersionBumped = Signal(int, int, int)   # device_id, old_version, new_version
# controllers/parameter_tab.py
def adopt_device_version(self, device_id: int, old_version: int, new_version: int) -> None: ...
# controllers/device_tab.py (__init__)
self.device_table.deviceVersionBumped.connect(self.parameter_tab.adopt_device_version)
```

- `save_all` 은 쓰기 **전에** 보낼 device들의 `{id: version}` 을 잡아 둔다(id가 있는 것만).
- 쓰기가 성공하면(덮어쓰기 포함) **쓰기가 돌려준 `SaveResult.devices`** 를 그것과 비교해 version이 달라진 행마다 `deviceVersionBumped(id, old, new)` 를 한 번 낸다. 새로 넣은 행(쓰기 전에 id 없음)과 지운 행은 내지 않는다. 다시 읽기·취소(`_write_devices` 가 `None`)면 하나도 내지 않는다.
- 가짜 DeviceRepository가 실제 repo처럼 `SaveResult.devices` 의 바뀐 행에 새 version을 채우지 않으면 `tests/gui_support/fakes.py` 를 실제 repo의 계약(`_update_existing` 이 RETURNING한 행만 고친다)에 맞춘다. `src/` 를 가짜에 맞추지 않는다.
- `adopt_device_version` 은 `device_id == current_device_id` 이고 `current_version == old_version` 이고 `new_version == old_version + 1` 일 때만 `current_version = new_version` 으로 바꾼다. 그 밖에는 아무것도 하지 않는다. 탭 모델·dirty·화면은 건드리지 않는다.
- 신호 형태는 이미 있는 `deviceVersionChanged = Signal(int, int)` 과 맞춘다.

최종 상태:

| 경우 | 탭의 `current_version` | 다음 탭 저장 |
|---|---|---|
| 내 device 저장이 그 device를 v → v+1 | v+1 | 충돌 없음 |
| 내 device 저장이 그 device를 건드리지 않음(값 같음) | v | bob이 그 사이 바꿨으면 충돌, 아니면 없음 |
| 덮어쓰기로 v → v+2 이상(남의 변경 위) | v | 충돌(남의 변경) |
| device 저장 취소·다시 읽기 | v | 그 사이 남이 바꿨으면 충돌 |
| 다른 device가 열려 있음 | 그대로 | 영향 없음 |

### 3. 문서

- 바꿀 문서는 없다. 사용자에게 보이는 문구가 없다. known-issues K17은 이미 "phase 3 step 6이 재현만 한다" 고 적혀 있으므로 그대로 둔다.

## Acceptance Criteria

```bash
uv run pytest tests/gui/test_tab_version_sync.py -q   # 새 테스트 통과, K17 테스트는 xfail (수정 전에는 나 자신과의 충돌 경우가 실패해야 한다)
uv run ruff check src tests
uv run pytest tests/gui -q
uv run pytest -q
```

## 검증 절차

1. 위 AC 커맨드를 실행한다. K17 테스트가 `XFAIL` 로 보이는지 확인한다(`-rx`).
2. 아키텍처 체크리스트를 확인한다:
   - `controllers/` 셋(`device_table.py`, `parameter_tab.py`, `device_tab.py`)만 바꿨는가? `service/repo/` 의 SQL은 그대로인가(DB 테스트가 필요 없는 step이다)?
   - 탭이 받아들이는 version이 "내 쓰기가 정확히 한 번 올린 것" 뿐인가(ADR-004: 남의 변경은 충돌로 보인다)?
   - 선택 추적 코드(`_on_current_changed`, `prev_selected_device`, `last_selected_device`)를 건드리지 않았는가?
3. 결과에 따라 `phases/3-gui-save-fixes/index.json` 의 step 6을 업데이트한다:
   - 성공 → `"status": "completed"`, `"summary": "DeviceTableController.deviceVersionBumped(id, old, new): 내 쓰기가 올린 행만(SaveResult.devices 비교). ParameterTabController.adopt_device_version 은 같은 device + old 일치 + new == old+1 일 때만. RED: <테스트 이름>. K17 xfail(strict): <테스트 이름>. tests/gui/test_tab_version_sync.py"`
   - 재현 안 됨 → `"status": "completed"`, `"summary": "not reproduced: <이유>"`
   - 수정 3회 시도 후에도 실패 → `"status": "error"`, `"error_message": "구체적 에러 내용"`
   - 사용자 개입 필요 → `"status": "blocked"`, `"blocked_reason": "구체적 사유"` 후 즉시 중단

## 금지사항

- 다시 읽은 version(`refresh_devices` 뒤의 모델, `fetch_devices_by_process`)을 탭에 복사하지 마라. 이유: 내 저장과 다시 읽기 사이에 다른 사용자가 같은 device의 탭을 저장했으면 그 변경이 충돌 없이 덮인다. 낙관적 잠금이 막으려던 바로 그 동작이다(ADR-004).
- `set_device_to_section` 을 다시 불러 version을 맞추지 마라. 이유: 탭을 DB에서 다시 읽어 저장 안 한 편집이 사라진다.
- 탭 저장에서 `expected_version=None` 을 넘기거나 충돌 시 자동으로 force하지 마라. 이유: 버전 검사를 끄는 것이다.
- K17을 고치지 마라(`QPersistentModelIndex` 로 바꾸기, 같은 id면 다시 읽지 않기 등). 이유: 선택 추적 구조 문제로 기록만 했다(known-issues K17, 제안 P3). 이 step은 xfail 재현만 한다.
- `service/repo/device.py` 의 반환 형태(`SaveResult`)나 SQL을 바꾸지 마라. 이유: 필요한 정보(`SaveResult.devices` 의 새 version)가 이미 있다. SQL을 바꾸면 DB 테스트가 필요해진다(harness 규칙 12).
- 기존 테스트를 깨뜨리지 마라.
