# Step 1: tab-save-result

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

`ParameterTabController.save_all()` 이 step 0의 device 쪽과 같은 계약으로 `bool` 을 돌려주게 한다(분석 G4의 계약 나머지 절반). 지금은 언제나 `None` 이라서 device 전환(`_switch_device_by_index`)이 충돌 "취소" 뒤에도 다음 device로 넘어가 탭 편집을 버린다. 이 step은 **계약만** 만든다. 호출부는 step 2·3·5가 바꾼다.

## 읽어야 할 파일

- `/CLAUDE.md`, `/docs/ARCHITECTURE.md`(데이터 흐름 → 탭 저장), `/docs/ADR.md`(ADR-004), `/docs/UI_GUIDE.md`(원칙 4, 저장 충돌 세 갈래)
- `src/genviewer/controllers/parameter_tab.py` — `is_dirty` (~47-48), `save_all` (~55-70), `_write` (~72-91, repo나 `current_device_id` 가 없으면 False, 다시 읽기는 모든 섹션 `update_model`), `_apply` (~93-109, `current_version` 갱신과 `deviceVersionChanged`), `paste_payload` (~154-172, `_write` 를 쓴다)
- `src/genviewer/controllers/tab_section.py` — `is_dirty` (~152-155), `mark_saved` (~123-128), `update_model` (~181-192, DB에서 다시 읽고 dirty를 끈다)
- `src/genviewer/service/repo/parameter.py` — `replace_many_for_device` (~42-, `expected_version` 비교, 사라진 device는 force여도 `StaleWriteError`)
- `src/genviewer/dialogs/conflict.py` — `ask_conflict`
- 호출부(읽기만): `controllers/device_tab.py` `save_db` (~118-124), `_switch_device_by_index` (~435-446), `controllers/main_window.py` `_on_save_triggered` (~183-185)
- 이전 step에서 수정된 파일: `src/genviewer/controllers/device_table.py`(`save_all -> bool`), `tests/gui/test_device_save_result.py`. 같은 계약 문구를 docstring에 맞춘다.

## 버그

```python
def save_all(self):
    dirty = [sec for sec in self._sections.values() if sec.is_dirty()]
    if not dirty:
        return
    if not self._write(dict(sec.payload_fragment() for sec in dirty)):
        return
    ...
```

`_write` 는 저장했으면 `True`, 다시 읽기·취소·repo 없음이면 `False` 를 돌려준다. `save_all` 은 그것을 버리고 모든 경로에서 `None` 을 돌려준다.

사용자 화면의 증상(step 3에서 사라진다): sf2p → nfet_a를 누른다 → 탭 셀 하나를 고친다(탭 이름 뒤 ` *`) → 그 사이 bob이 nfet_a를 저장한다 → nfet_b를 누른다 → "Save Changes?" 예 → "Save Conflict" 에서 "취소"(툴팁: "편집 내용은 그대로 남는다") → 탭은 nfet_b로 바뀌고, nfet_a를 다시 누르면 고친 내용이 없다.

이 step의 RED는 반환값으로 본다. 수정 전에는 모든 경우에 `None` 이다.

## 작업

### 1. 테스트 먼저 (`tests/gui/test_tab_save_result.py`, 새 파일)

`device_tab_ctrl` 로 sf2p → `select_device_row(ctrl, 0)`(nfet_a) → 필요하면 `edit_tab_cell` 로 seed가 행을 넣은 탭 하나의 셀을 고친 뒤 `ctrl.parameter_tab.save_all()` 을 직접 부른다.

| 경우 | 만드는 법 | 반환 | 최종 상태 |
|---|---|---|---|
| dirty 탭 없음 | 편집 없이 | `True` | `replace_many_for_device` 호출 없음, 알림 없음 |
| 저장 성공 | 편집 → 저장 | `True` | 1회 호출(`expected_version` = 화면의 nfet_a version), 탭 dirty 아님, `current_version` = 새 version, `deviceVersionChanged` 1회, "Saved" 알림 |
| stale × 덮어쓰기 | 편집 → bob이 nfet_a 저장 → `answer_conflict(OVERWRITE)` | `True` | 두 번째 호출이 `force=True`, 가짜 repo(`fetch_by_device`)에 내 값 |
| stale × 취소 | 같은 충돌 → `answer_conflict(CANCEL)` | `False` | 탭에 편집 값 그대로, `is_dirty()` True, "Saved" 알림 없음 |
| stale × 다시 읽기 | 같은 충돌 → `answer_conflict(RELOAD)` | `False` | 탭이 서버 값(seed 값), `is_dirty()` False |
| 접속 전 | 편집 뒤 `ctrl.parameter_tab.repo = None` | `False` | 호출 없음, 편집 그대로 |
| 예상 밖 예외 | `store.fail_next("replace_many_for_device", RuntimeError("boom"))` | 예외가 그대로 난다 | 편집 그대로, `is_dirty()` True |

- `current_device_id is None` 인데 dirty인 경우는 `_write` 의 같은 분기(`False`)다. 따로 테스트하지 않아도 된다.
- deleted × 덮어쓰기는 known-issues K20(범위 밖)이다. `_apply(force=True)` 가 같은 `StaleWriteError` 를 다시 내고 그것이 그대로 올라간다. 바꾸지 않고 테스트하지 않는다.
- 알림과 `deviceVersionChanged` 는 테스트 안에서 리스트에 연결해 확인한다.

### 2. 수정 (`controllers/parameter_tab.py` 의 `save_all`)

```python
def save_all(self) -> bool: ...
```

- `True`: dirty 탭이 없었다, 또는 저장했다(덮어쓰기 포함).
- `False`: `_write` 가 `False` 다(충돌에서 취소·창 닫기·다시 읽기, repo 없음, `current_device_id` 없음).
- 예외는 잡지 않는다(K20의 두 번째 `StaleWriteError` 포함).
- `_write`/`_apply` 의 계약과 `mark_saved`·알림·로그 순서는 그대로 둔다. `paste_payload` 는 바꾸지 않는다.
- docstring에 step 0과 같은 형식으로 계약을 적는다.

### 3. 문서

- 바꿀 문서는 없다. 사용자에게 보이는 동작이 바뀌지 않는다.

## Acceptance Criteria

```bash
uv run pytest tests/gui/test_tab_save_result.py -q   # 새 테스트 통과 (수정 전에는 반환값 단언이 실패해야 한다)
uv run ruff check src tests
uv run pytest tests/gui -q
uv run pytest -q
```

## 검증 절차

1. 위 AC 커맨드를 실행한다.
2. 아키텍처 체크리스트를 확인한다:
   - `controllers/parameter_tab.py` 만 바꿨는가? 호출부(`device_tab.py`, `main_window.py`)는 그대로인가?
   - 탭 저장이 여전히 한 번의 `replace_many_for_device`(한 트랜잭션, version 한 번)인가?
3. 결과에 따라 `phases/3-gui-save-fixes/index.json` 의 step 1을 업데이트한다:
   - 성공 → `"status": "completed"`, `"summary": "ParameterTabController.save_all -> bool (True=dirty 없음·저장·덮어쓰기, False=취소·다시 읽기·repo 없음, 예외는 그대로). 호출부 불변. RED: <테스트 이름>. tests/gui/test_tab_save_result.py"`
   - 재현 안 됨 → `"status": "completed"`, `"summary": "not reproduced: <이유>"`
   - 수정 3회 시도 후에도 실패 → `"status": "error"`, `"error_message": "구체적 에러 내용"`
   - 사용자 개입 필요 → `"status": "blocked"`, `"blocked_reason": "구체적 사유"` 후 즉시 중단

## 금지사항

- 호출부(`save_db`, `_switch_device_by_index`, `_on_save_triggered`)를 바꾸지 마라. 이유: 계약 step과 호출부 step을 나눈다(harness 규칙 10). 호출부는 step 2·3·5가 바꾼다.
- 예외를 잡아 `False` 로 바꾸지 마라. 이유: `False` 는 사용자의 선택이다. 예상 밖 예외는 호출부가 알린다.
- K20(deleted × 덮어쓰기의 두 번째 `StaleWriteError`)을 고치지 마라. 이유: 문구 정리가 필요한 별도 문제로 기록만 했다(known-issues).
- 탭마다 따로 저장하게 바꾸지 마라. 이유: version이 device 단위라 첫 탭 저장이 둘째 탭을 충돌시킨다(`payload_fragment` docstring).
- 기존 테스트를 깨뜨리지 마라. 단 phase 2 테스트가 지금 반환값(`None`)을 고정하고 있으면 그 단언만 새 계약으로 바꾸고 summary에 적는다.
