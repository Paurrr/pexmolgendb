# Step 2: history-reload-races

## 배경 (phase 12 공통)

이 저장소는 이미 여러 명이 쓰는 도구다. 평소에는 **에러·버그만 고친다**(CLAUDE.md, ADR-015). phase 12는 2026-10-17에 `docs/notes/known-issues.md` 를 분류하면서 버그로 정한 GUI 비동기·수명 항목(History 화면의 오류 문구·다시 읽기 경합 K23a·K41, 변경 감지 폴링의 결과 묶기 K23b, Qt 객체 누수 K22 나머지)을 한 step에 하나씩 고친다. 모두 버그이고 승인 대상이 아니다. 사용자에게 보이는 문구를 새로 만들지 않는다.

phase 0~11과 이 phase의 step 0~1이 끝나 있다. 이 step에 닿는 것:
- `connect_db` 의 순서는 phase 4 그대로다: 새 DB를 연다 → 도는 폴링을 기다린다 → **옛 DB를 닫는다** → `dbChanged(새)`. `MainWindowController` 가 `dbChanged` 를 `HistoryTabController.set_db` 에 잇는다. `close_db` 는 `dbChanged(None)` 를 낸다. 창을 닫을 때는 `history_tab.shutdown()` 이 `device_tab.close_db()` 보다 먼저 불린다.
- step 0: `history_ctrl` fixture, `FakeAuditRepository.recent`, `store.add_audit`, **`store.hold_next(method) -> threading.Event`**(다음 호출을 Event가 set될 때까지 잡아 둔다. `store.lock` 밖에서 기다리고, 10초 안전장치가 있다), `store.fail_next("recent", exc)`.
- step 1: `_on_failed` 의 문구가 `user_message` 한 줄이다.

모든 step에 같은 규칙이 적용된다.
1. 버그는 **주장**이다. 먼저 실패하는 테스트로 재현하고 RED 출력(테스트 이름과 실패한 단언)을 summary에 적는다.
2. RED는 **Windows 개발 PC에서** 보여야 한다.
3. 재현되지 않으면 `src/` 를 고치지 않는다. 테스트는 특성 테스트로 남기고 `"status": "completed"`, `"summary": "not reproduced: <이유>"` 로 끝낸다.
4. 고친 뒤 수정을 손으로 되돌려 새 테스트가 실패하는지 확인하고 다시 고친다(변이 검사). `git checkout`/`git stash` 로 되돌리지 마라.
5. 이 파일의 행 번호는 2026-10-17(phase 6 전) 기준 대략값이다. 이름으로 찾아라.

테스트 기반: `history_ctrl`, `store`, `store.add_audit`, `store.hold_next`, `store.fail_next`, `store.calls_of("recent")`(인자 dict: `limit`, `since`, `actor`, `process`, `contains` …), `tests/gui_support/fakes.py` 의 `FakeDatabase(store, dsn)`. "아무 일도 없음" 은 `qtbot.wait` 고정 대기가 아니라 `store.calls`·`ctrl._task` 를 `qtbot.waitUntil` 로 기다린 뒤 단언한다. `waitUntil` 콜백은 bool을 돌려준다.

## 이 step의 목적

History 다시 읽기의 두 경합을 고친다(2026-10-17 분류: 버그). **`controllers/history_tab.py` 만** 바꾼다.
- K23a: 다시 읽기가 도는 동안 바꾼 필터가 버려진다.
- K41: 재접속할 때 도는 다시 읽기를 기다리지 않는다. 새 DB로 읽지 않는다.

## 읽어야 할 파일

- `/CLAUDE.md`(GUI 스레드에서 DB를 기다리지 않는다, 자동으로 다시 읽지 않는다), `/docs/ARCHITECTURE.md`("DB 접속", "변경 감지", "스레딩")
- `src/genviewer/controllers/history_tab.py` 전체: `set_db` (~76-93), `shutdown` (~95-100), `_tick`, `reload` (~120-149, `self._task is not None` 이면 돌아간다), `_clear_task` (~151-155, `self._task` 에 든 것을 deleteLater), `_on_result`, `_on_failed`
- `src/genviewer/utils/background.py`: `Task`(QThread, `done`/`failed`/`finished`), `is_busy`
- `src/genviewer/controllers/main_window.py`: History 배선(~53-62), `shutdown`(~95-106)
- `src/genviewer/controllers/device_tab.py`: `connect_db`, `close_db`, `_release_db`, `_clear_poll_task`(같은 뼈대). 이 파일은 읽기만 한다.
- `tests/gui/test_history_smoke.py`, `tests/gui/test_history_errors.py`

## 버그

**K23a**
- 필터 위젯(`range_cb`/`process_cb` 의 `currentIndexChanged`, `who_field`/`find_field` 의 `returnPressed`, `refresh_btn`)이 `reload()` 를 부른다.
- 이미 다시 읽기(자동 갱신 `_tick` 이나 앞 필터)가 돌고 있으면 `reload()` 는 아무것도 하지 않고 돌아간다.
- 그래서 화면은 옛 필터의 결과를 보인다.
  - 자동 갱신이 켜져 있으면 다음 틱(10초)에 새 필터로 읽힌다. 단, 줄을 고른 동안에는 틱도 건너뛴다.
  - 꺼져 있으면 사용자가 다시 누르기 전까지 읽히지 않는다.

**K41**
- 재접속은 옛 DB를 닫은 뒤 `set_db(새)` 를 부른다.
- 그때 다시 읽기가 돌고 있으면 `set_db` 의 `reload()` 도 같은 가드에 걸려 건너뛴다.
- 결과는 다음과 같다.
  - 화면은 옛 DB의 결과(또는 옛 풀이 닫혀 난 실패 "이력을 읽지 못했다")를 보인다.
  - `set_db` 가 0으로 돌린 `_failures` 가 옛 작업의 실패로 다시 올라간다.
  - 자동 갱신이 꺼져 있으면 새 DB로 영원히 읽지 않는다.
- `set_db(None)`(접속 끊김) 뒤에 도착한 옛 결과도 "데이터베이스에 붙어 있지 않다." 를 덮어쓴다.

**고칠 때의 함정** (계획 검토에서 나온 지적. 이것도 주장이다)
- 옛 작업의 `finished` 는 큐로 온다. 그것을 받은 `_clear_task` 는 그 순간 `self._task` 에 든 것을 deleteLater 한다.
- 고치면서 새 작업을 옛 작업이 끝나기 전에 띄우면, 옛 `finished` 가 **돌고 있는 새 작업**을 지운다(QThread가 돌던 중에 지워져 크래시).
- 옛 `_on_result` 가 새 결과를 덮어쓸 수도 있다.

이것은 주장이다. 먼저 재현하라.

## 작업

### 불변식

1. 동시에 도는 다시 읽기는 최대 하나다(지금과 같다).
2. 도는 중에 `reload()` 가 오면 **보류**(pending)로 표시한다. 여러 번 와도 보류 하나다. 도는 작업이 끝나면(성공·실패 무관, `finished` 를 받은 뒤) 보류가 있으면 `reload()` 를 한 번 한다. 필터 값은 그때 화면에서 읽는다(지금 `reload` 처럼).
3. 어떤 작업이 시작된 뒤 보류가 생겼거나 `set_db` 가 불렸으면 그 작업은 **낡았다**. 낡은 작업의 결과·실패는 버린다.
   - 표·개수 칸·상세·process 콤보를 바꾸지 않는다.
   - `_failures` 를 올리지 않는다. "이력을 읽지 못했다" 도 띄우지 않는다.
   - 판단은 작업 객체 identity나 세대 번호로 한다. 시그널을 낸 작업이 지금 작업인지 본다.
4. 정리(`_clear_task` 자리)는 **끝난 그 작업만** 지운다. 돌고 있는 작업은 절대 deleteLater 하지 않는다.
5. `set_db(새)` 는 repo를 새 DB로 바꾼다. 도는 작업이 있으면 보류로 두고, 없으면 지금처럼 바로 읽는다. `_failures = 0`, 타이머 재시작은 지금과 같다.
6. `set_db(None)` 는 지금처럼 화면을 비우고 "데이터베이스에 붙어 있지 않다." 를 보인다. 보류를 지우고, 도는 작업은 낡은 것으로 만든다.
7. `shutdown()` 은 지금처럼 타이머를 멈추고 도는 작업을 기다린다. 그 뒤 보류가 있어도 새 작업을 띄우지 않는다.
8. `connect_db` 의 순서(옛 DB를 닫은 뒤 `dbChanged`)는 바꾸지 않는다. `device_tab.py` 를 건드리지 않는다. 옛 DB로 돌던 작업이 실패해도 3번에 따라 버려지므로 순서를 바꿀 필요가 없다.

### 결과 × 상태

| 상황 | 작업 결과 | 최종 상태 |
|---|---|---|
| 도는 작업 없음 + `reload()` | - | 지금처럼 바로 시작한다 |
| 도는 중 + 필터 변경(`reload()`) | 성공 | 옛 결과는 버린다. 끝난 뒤 새 필터로 한 번 읽고 그 결과를 보인다 |
| 도는 중 + 필터 변경 | 실패 | 옛 실패는 버린다(`_failures` 그대로, 문구 없음). 끝난 뒤 새 필터로 한 번 읽는다 |
| 도는 중 + `reload()` 세 번(필터 셋) | - | 다시 읽기는 한 번, 마지막 필터로 |
| 도는 중 + `set_db(db2)` | 옛 DB 작업 성공 또는 실패 | 옛 결과·실패는 버린다. 끝난 뒤 db2로 한 번 읽는다. `_failures == 0` 이고 "이력을 읽지 못했다" 가 없다 |
| 도는 중 + `set_db(None)` | 성공 또는 실패 | "데이터베이스에 붙어 있지 않다." 가 남는다. 표는 비어 있고, 더 읽지 않는다 |
| 도는 중 + `shutdown()` | - | 기다린 뒤 끝낸다. 보류가 있어도 더 읽지 않는다 |
| 자동 갱신 꺼짐(`auto_cb` off) | - | 위와 같다. 보류는 타이머와 무관하다 |
| 줄을 고른 상태의 `_tick` | - | 지금처럼 건너뛴다 |
| `is_busy()` 중의 `reload()` | - | 지금처럼 돌아간다(이 step의 범위 밖) |

### 1. 테스트 먼저 (`tests/gui/test_history_reload.py`, 새 파일)

공통 준비
- `history_ctrl` 의 첫 다시 읽기가 끝난 상태에서 시작한다.
- `ev = store.hold_next("recent")` 다음 `ctrl.reload()` 를 부르면 작업이 붙잡힌 채 돈다.
- 끝까지 기다리는 조건은 `ctrl._task is None` 과 `recent` 호출 수다.

테스트(수정 전에는 첫 셋이 실패해야 한다)
- **필터 변경**
  - 동작: 붙잡은 채 `ui.who_field.setText("kim")` 와 `ui.who_field.returnPressed.emit()` 을 한 뒤 `ev.set()` 한다.
  - 단언: `qtbot.waitUntil(lambda: any(c["actor"] == "kim" for c in store.calls_of("recent")), timeout=3000)` 가 통과한다. 지금은 시간이 지나 실패한다.
- **set_db 중**
  - 준비: 붙잡은 호출이 실패하도록 `store.fail_next("recent", DbUnavailableError("pool closed"))` 도 건다. 옛 풀이 닫혀 실패한 것의 흉내다.
  - 동작: `ctrl.set_db(FakeDatabase(store, "db2"))` 다음 `ev.set()` 한다.
  - 단언
    - 붙잡힌 호출 다음에 `recent` 호출이 하나 더 있다.
    - `ctrl.repo.db.cfg.dsn == "db2"` 다.
    - 개수 칸이 `"이력을 읽지 못했다"` 로 시작하지 않는다.
    - `ctrl._failures == 0` 이다.
- **set_db(None) 중**
  - 동작: 붙잡은 채 `ctrl.set_db(None)` 다음 `ev.set()` 한다.
  - 단언: 끝난 뒤에도 개수 칸이 `"데이터베이스에 붙어 있지 않다."` 이고, 표 행이 0이다.
- **여러 번**: 붙잡은 채 필터를 세 번 바꾼다. 놓은 뒤 `recent` 호출은 정확히 하나 늘고 마지막 필터로 갔다. 단언 전에 `ctrl._task is None` 과 보류가 비었는지를 기다린다.
- **shutdown 중**
  - 동작: 붙잡은 채 필터를 바꾼다. `threading.Timer(0.2, ev.set)` 를 건 뒤 `ctrl.shutdown()` 한다. shutdown 은 GUI 스레드에서 기다린다. Timer 가 놓아 준다.
  - 단언: 그 뒤 `recent` 호출이 늘지 않는다. 판단은 `ctrl._task is None` 을 기다린 뒤 호출 수로 한다.
- **낡은 정리가 새 작업을 지우지 않음**: 두 번째 작업이 도는 동안 첫 작업의 `finished` 가 처리돼도 두 번째 작업이 살아 있다(`shiboken6.isValid(task)`, `isRunning()`). 구조가 이 경우를 만들 수 없게 고쳤다면 그 이유를 summary에 적고, 이 테스트는 그 구조를 지키는 형태로 쓴다.
- **회귀**: `tests/gui/test_history_smoke.py`, `tests/gui/test_history_errors.py` 가 그대로 통과한다.

### 2. 수정

- `controllers/history_tab.py` 만 바꾼다. 위 불변식을 지키는 최소 변경으로 한다(보류 플래그 + 작업 identity/세대 검사).
- 문구·필터 위젯·자동 갱신 주기를 바꾸지 않는다.

### 3. 문서

- `docs/ARCHITECTURE.md` "변경 감지" 의 History 문장 뒤에 한 문장을 더한다: "다시 읽는 중에 필터를 바꾸거나 DB가 바뀌면 끝난 뒤 한 번 더 읽고, 그사이 도착한 옛 결과는 버린다."

## Acceptance Criteria

```bash
uv run pytest tests/gui/test_history_reload.py tests/gui/test_history_smoke.py tests/gui/test_history_errors.py -q   # 새 테스트 통과 (수정 전에는 필터·set_db·set_db(None) 테스트가 실패해야 한다)
uv run ruff check src tests
uv run pytest -q
git diff --stat -- src/genviewer/controllers/device_tab.py   # 비어 있어야 한다
```

## 검증 절차

1. 위 AC 커맨드를 실행한다.
2. 아키텍처 체크리스트를 확인한다.
   - 자동으로 다시 읽지 않는다는 원칙과 충돌하지 않는가? 보류된 다시 읽기는 사용자의 필터 변경·DB 변경이 요청한 것이고, 남의 변경 때문이 아니다.
   - 돌고 있는 `Task` 를 deleteLater 하는 경로가 없는가?
   - `connect_db` 순서와 `device_tab.py` 가 그대로인가?
   - 워커 스레드에서 위젯을 만지지 않는가(슬롯은 GUI 스레드)?
3. 결과에 따라 `phases/12-gui-async-cleanup/index.json` 의 step 2를 업데이트한다.
   - 성공 → `"status": "completed"`, `"summary": "history_tab: 도는 중 reload/set_db 는 보류 후 한 번 다시 읽음, 낡은 작업의 결과·실패·정리는 버림(<identity|세대>). RED: <테스트 이름: 단언>. 변이: <…>. connect_db 순서 불변. tests/gui/test_history_reload.py"`
   - 재현 안 됨 → `"status": "completed"`, `"summary": "not reproduced: <이유>"`
   - 수정 3회 시도 후에도 실패 → `"status": "error"`, `"error_message": "구체적 에러 내용"`
   - 사용자 개입 필요 → `"status": "blocked"`, `"blocked_reason": "구체적 사유"` 후 즉시 중단

## 금지사항

- `connect_db`·`_release_db`·`close_db`(`controllers/device_tab.py`)의 순서를 바꾸지 마라. 이유: ARCHITECTURE "DB 접속" 과 phase 4 테스트가 고정한 순서다. 이 step은 History 쪽에서 낡은 작업을 버리는 것으로 해결한다.
- 작업 둘을 동시에 돌리지 마라. 이유: 같은 화면에 결과가 엇갈려 도착한다(불변식 1).
- `set_db` 나 `reload` 에서 `Task.wait()` 로 GUI 스레드를 막지 마라(`shutdown` 제외). 이유: CLAUDE.md "GUI 스레드에서 DB를 기다리지 않는다".
- 보류를 이유로 자동 갱신을 켜거나 타이머 주기를 바꾸지 마라. 이유: 사용자가 정한 자동 갱신 상태를 바꾼다.
- 문구를 바꾸거나 새 문구를 더하지 마라. 이유: 버그 수정 범위다(UI_GUIDE 문구).
- 기존 테스트를 깨뜨리지 마라.
