# Step 3: poll-process-binding

## 배경 (phase 12 공통)

이 저장소는 이미 여러 명이 쓰는 도구다. 평소에는 **에러·버그만 고친다**(CLAUDE.md, ADR-015). phase 12는 2026-10-17에 `docs/notes/known-issues.md` 를 분류하면서 버그로 정한 GUI 비동기·수명 항목(History 화면의 오류 문구·다시 읽기 경합 K23a·K41, 변경 감지 폴링의 결과 묶기 K23b, Qt 객체 누수 K22 나머지)을 한 step에 하나씩 고친다. 모두 버그이고 승인 대상이 아니다. 사용자에게 보이는 문구를 새로 만들지 않는다.

phase 0~11과 이 phase의 step 0~2가 끝나 있다. 이 step에 닿는 것:
- `connect_db` 의 순서는 phase 4 그대로다: 새 DB를 연다(`run_blocking`) → `_release_db`(폴링 타이머를 멈추고 도는 폴링 `Task` 를 `wait()` 한 뒤 `_poll_task = None`, 옛 DB를 닫는다) → repo 교체 → `dbChanged` → `apply_db`(device 목록을 다시 읽고 etag를 기억한다) → 폴링 타이머 시작. phase 10 step 4가 그 앞에 편집 질문을 넣었고, phase 11이 `_open_database` 를 바꿨다.
- phase 11 step 0: `_on_poll_failed` 의 로그가 `user_message` 한 줄이다.
- step 0(이 phase): **`store.hold_next(method) -> threading.Event`**(다음 호출을 Event가 set될 때까지 잡아 둔다. `store.lock` 밖에서 기다리고, 10초 안전장치가 있다).
- step 2(이 phase): History는 낡은 작업의 결과·실패·정리를 버린다. 폴링도 같은 생각을 따른다.

모든 step에 같은 규칙이 적용된다.
1. 버그는 **주장**이다. 먼저 실패하는 테스트로 재현하고 RED 출력(테스트 이름과 실패한 단언)을 summary에 적는다.
2. RED는 **Windows 개발 PC에서** 보여야 한다.
3. 재현되지 않으면 `src/` 를 고치지 않는다. 테스트는 특성 테스트로 남기고 `"status": "completed"`, `"summary": "not reproduced: <이유>"` 로 끝낸다.
4. 고친 뒤 수정을 손으로 되돌려 새 테스트가 실패하는지 확인하고 다시 고친다(변이 검사). `git checkout`/`git stash` 로 되돌리지 마라.
5. 이 파일의 행 번호는 2026-10-18(phase 11 직후) 기준 대략값이다. 이름으로 찾아라.
6. `DeviceTabController.connect_db`/`_open_database` 는 phase 7·10·11·12가 차례로 건드린다. 이 파일은 그 본문을 인용하지 않는다. 지금 코드를 읽고, 적힌 불변식만 지켜라.

테스트 기반: `device_tab_ctrl`, `main_window`, `store`(sf2p: nfet_a·nfet_b / sf4u: pfet_a), `store.touch_device(id, actor=…)`, `store.hold_next`, `store.fail_next("etag", exc)`, `store.calls_of("etag")`, `select_process`. 본보기: `tests/gui/test_smoke.py` 의 폴링 테스트(`ctrl._poll_remote_changes()` 를 직접 부르고 `etag` 호출과 `ctrl._poll_task is None` 을 기다린다), `tests/gui/test_connect_db.py` 의 `threading.Timer` 로 GUI 스레드의 `wait()` 를 풀어 주는 방식. 배너는 `ctrl.ui.refresh_banner`(`isHidden()`, `label.text()`). 고정 대기(`qtbot.wait`) 금지.

## 이 step의 목적

K23b: 변경 감지 폴링 결과가 그 폴링을 시작한 process·DB에 묶여 있지 않아 엉뚱한 배너가 뜬다. 이것을 고친다(2026-10-17 분류: 버그). `controllers/device_tab.py` 의 폴링 부분만 바꾼다.

## 읽어야 할 파일

- `/CLAUDE.md`(자동으로 다시 읽지 않는다, 남이 바꾼 것은 배너로), `/docs/ARCHITECTURE.md`("변경 감지", "DB 접속"), `/docs/ADR.md`(ADR-004)
- `src/genviewer/controllers/device_tab.py`
  - `_poll_remote_changes` (~223-242): 시작할 때 `repo`·`process_id` 를 잡는다.
  - `_clear_poll_task` (~244-248): 그 순간 `self._poll_task` 에 든 것을 deleteLater 한다.
  - `_on_poll_result` (~250-257): 도착한 순간의 `self.device_table.remembered_etag()` 와 비교한다.
  - `_on_poll_failed`, `_release_db`, `close_db`, `on_process_changed`(배너를 숨긴다)
- `src/genviewer/controllers/device_table.py`: `remember_etag`, `remembered_etag`, `current_process_id`, `repo`
- `src/genviewer/service/repo/device.py`: `etag_key`
- `tests/gui/test_smoke.py`, `tests/gui/test_connect_db.py`

## 버그

1. **process 전환 뒤 도착**: sf2p를 폴링하는 중에 sf4u로 바꾸면, 도착한 sf2p의 etag가 sf4u의 기준과 비교된다.
   - 다르므로 배너가 뜬다: "이 process 가 X 님에 의해 변경되었습니다."(X는 sf2p 마지막 수정자)
   - 반대로 sf4u의 진짜 변경 배너를 숨길 수도 있다.
2. **재접속 뒤 도착**: `_release_db` 는 도는 폴링 작업을 `wait()` 하고 `_poll_task = None` 으로 둔다. 하지만 그 작업의 `done` 은 이미 큐에 있다.
   - 재접속이 끝난 뒤 옛 DB의 etag가 새 DB의 기준과 비교된다.
   - 사이에 누가 저장했으면 거짓 배너가 뜬다.
   - 같은 식으로 큐에 있던 `failed` 는 새 DB의 실패 횟수를 올린다.
3. **낡은 정리**(계획 검토의 지적, 주장): 큐에 있던 옛 `finished` → `_clear_poll_task` 는 그 순간의 `self._poll_task` 를 지운다. 그사이 새 폴링이 시작됐으면 돌고 있는 작업을 지운다.

이것은 주장이다. 먼저 재현하라.

## 작업

### 불변식

- 폴링 결과·실패는 **시작할 때의 (process_id, repo)** 가 도착할 때의 (`device_table.current_process_id`, `device_table.repo`)와 같을 때만 쓴다. 다르면 버린다: 배너를 바꾸지 않고 `_poll_failures` 를 바꾸지 않는다.
  - repo는 identity로 비교한다. 재접속하면 `set_repo` 가 새 repo 객체를 만든다.
- `connected` 가 False거나 `db` 가 None이면(close_db 뒤) 버린다.
- 정리는 **끝난 그 작업만** 지운다. 돌고 있는 작업을 deleteLater 하지 않는다. `_poll_task` 가 끝난 그 작업일 때만 None으로 돌린다.
- 같은 process·같은 DB의 결과는 지금처럼 판단한다(같으면 배너 숨김, 다르면 `who` 로 배너). 자동으로 다시 읽지 않는다.
- `_release_db` 의 기다림과 `connect_db` 순서는 바꾸지 않는다.

### 결과 × 상태

| 도착할 때 | 결과 성공 | 결과 실패 |
|---|---|---|
| 같은 process, 같은 DB | 지금과 같다 | 지금과 같다(3회면 멈춤, 로그) |
| 다른 process로 바뀜 | 버림(배너는 전환 때 숨긴 그대로) | 버림(`_poll_failures` 그대로) |
| 같은 process로 돌아옴(전환 후 복귀, 같은 DB) | 지금과 같다(같은 키) | 지금과 같다 |
| 재접속 뒤(옛 DB, 이미 큐에 있음) | 버림 | 버림 |
| `close_db` 뒤(connected False) | 버림 | 버림 |
| 창 닫는 중(`shutdown` → `close_db` 가 기다린다) | 버림 | 버림 |
| process 전환 중 저장 질문(`_save_before_process_change`)으로 결과가 먼저 도착 | 그 시점의 process가 같으면 지금과 같다 | 같다 |

### 1. 테스트 먼저 (`tests/gui/test_poll_binding.py`, 새 파일)

- **process 전환**
  - 동작: `ctrl._poll_remote_changes()` 직후, 이벤트를 돌리기 전에 `select_process(ctrl, "sf4u")` 를 부른다(동기. 결과 시그널은 큐에서 기다린다). 그다음 `qtbot.waitUntil(lambda: len(store.calls_of("etag")) == n + 1 and ctrl._poll_task is None)` 로 기다린다.
  - 단언: `ctrl.ui.refresh_banner.isHidden()` 이다. **수정 전에는 sf2p의 etag와 sf4u 기준이 달라 배너가 떠서 실패해야 한다.**
- **process 전환 + 실패**
  - 준비: `store.fail_next("etag", RuntimeError("x"))`
  - 동작: 위와 같다.
  - 단언: `ctrl._poll_failures == 0` 이다. **수정 전에는 1이라 실패해야 한다.**
- **재접속 뒤 도착**
  - 준비: `main_window.device_tab` 을 쓴다.
    - `ev = store.hold_next("etag")`
    - 폴링 repo의 `etag` 를 감싼다. 원래 값을 계산한 뒤 `store.touch_device(nfet_a, actor="kim")` 을 하고, 그 값(변경 **전** etag)을 돌려주게 한다. 폴링이 시작할 때 repo를 잡으므로 `_poll_remote_changes()` 전에 감싼다.
    - `_release_db` 가 시작될 때 `ev.set()` 하도록 인스턴스 속성으로 감싼다. 이유: `run_blocking` 이 도는 동안 결과가 도착하면 이 경우가 재현되지 않는다.
  - 동작: `_poll_remote_changes()` 를 부른 뒤 `main_window.ui.device_tab_view.dbConnectRequested.emit("host=other")` 를 낸다.
  - 단언: 접속이 끝나고 큐가 비워진 뒤(`qtbot.waitUntil` 로 `etag` 호출 수와 `_poll_task is None`) 배너가 숨어 있다. 그 etag는 옛 DB의 것이다. **수정 전에는 변경 전 etag가 새 기준(kim의 변경 반영)과 달라 배너가 떠서 실패해야 한다.**
  - 재현 장치가 지금 코드와 맞지 않으면(예: phase 11이 `_release_db` 이름을 바꿈) 같은 시점에 놓아 주는 다른 지점을 찾고 summary에 적는다.
- **회귀**
  - `tests/gui/test_smoke.py` 의 "변화 없음" 과 "다른 사용자의 저장은 배너" 가 그대로 통과한다.
  - 같은 process에서 실패 3회면 지금처럼 멈추고 로그가 남는다.
- **정리**: 정리가 끝난 그 작업만 지우는지 단언한다(예: 끝난 작업의 `finished` 가 처리될 때 다른 돌고 있는 작업이 `_poll_task` 에 있으면 그 작업은 살아 있다). 구조상 만들 수 없으면 그 이유를 summary에 적는다.

### 2. 수정

- `controllers/device_tab.py` 의 `_poll_remote_changes`·`_on_poll_result`·`_on_poll_failed`·`_clear_poll_task` 만 바꾼다. 결과·실패·정리를 그 작업의 키와 identity에 묶는다. 방법(클로저로 키를 넘기기, `sender()` 비교 등)은 재량이다.
- 배너 문구, 폴링 주기, 실패 한도, `_release_db`·`connect_db` 는 바꾸지 않는다.

### 3. 문서

- `docs/ARCHITECTURE.md` "변경 감지" 문장에 이어 쓴다: "결과는 폴링을 시작한 process·DB가 그대로일 때만 쓴다(전환·재접속 뒤 도착한 결과는 버린다)."

## Acceptance Criteria

```bash
uv run pytest tests/gui/test_poll_binding.py tests/gui/test_smoke.py tests/gui/test_connect_db.py -q   # 새 테스트 통과 (수정 전에는 전환·재접속 테스트가 실패해야 한다)
uv run ruff check src tests
uv run pytest -q
```

## 검증 절차

1. 위 AC 커맨드를 실행한다.
2. 아키텍처 체크리스트를 확인한다.
   - 자동으로 다시 읽지 않는가(ADR-004)? 배너만 바꾸는가?
   - 돌고 있는 `Task` 를 deleteLater 하는 경로가 없는가?
   - `connect_db`·`_release_db` 순서와 기다림이 그대로인가?
3. 결과에 따라 `phases/12-gui-async-cleanup/index.json` 의 step 3을 업데이트한다.
   - 성공 → `"status": "completed"`, `"summary": "폴링 결과·실패를 시작 시 (process_id, repo) 에 묶고 다르면 버림, 정리는 끝난 작업만. RED: <테스트 이름: 단언>. 재현 장치: <hold_next + _release_db 감쌈 등>. 변이: <…>. tests/gui/test_poll_binding.py"`
   - 재현 안 됨 → `"status": "completed"`, `"summary": "not reproduced: <이유>"`
   - 수정 3회 시도 후에도 실패 → `"status": "error"`, `"error_message": "구체적 에러 내용"`
   - 사용자 개입 필요 → `"status": "blocked"`, `"blocked_reason": "구체적 사유"` 후 즉시 중단

## 금지사항

- 버린 결과 때문에 device 목록을 다시 읽거나 폴링을 바로 다시 띄우지 마라. 이유: 자동으로 다시 읽지 않는다(ADR-004). 다음 틱이 새 process·DB를 본다.
- `connect_db`·`_release_db`·`close_db` 의 순서를 바꾸지 마라. 이유: phase 4·10·11이 고정했고 History(step 2)가 기대한다.
- 배너 문구나 폴링 주기·실패 한도를 바꾸지 마라. 이유: 이 step의 범위가 아니다.
- `qtbot.wait` 로 고정 대기하지 마라. 이유: 결과가 "도착하지 않았다" 를 증명하지 못한다. 호출 수와 `_poll_task` 를 기다린다.
- 기존 테스트를 깨뜨리지 마라.
