# Step 0: user-message-sites

## 배경 (phase 11 공통)

이 저장소는 이미 여러 명이 쓰는 도구다. 평소에는 **에러·버그만 고친다**(CLAUDE.md, ADR-015). phase 11은 2026-10-17에 `docs/notes/known-issues.md` 를 분류하면서 고치기로 한 GUI 오류 경로 항목을 한 step에 하나씩 다룬다. 두 종류가 섞여 있다.
- 버그: K34·K35, K22 의 일부
- **사용자가 2026-10-17 승인한 동작 변경**: K3 의 GUI 쪽, K21, K16 의 내보내기 형식, K18

승인된 step에는 승인 문장을 그대로 적었다. 그 문장 밖으로 넓히지 마라.

phase 0~10이 끝나 있다. 이 phase에 닿는 것은 다음과 같다.
- phase 7 step 2(`pool-failure-cause`): 풀에서 커넥션을 얻지 못하면 `Database.connection()` 이 한 번 직접 접속한다. 그 실제 원인(첫 줄, `scrub` 를 거침)을 `DbUnavailableError` 에 담는다. `ping()` 은 여전히 bool이다. 정확한 API는 `src/genviewer/service/pool.py` 와 `phases/7-service-fixes/index.json` 의 summary로 확인하라.
- phase 10: 저장·편집 보호. `controllers/device_tab.py`·`controllers/device_table.py`·`dialogs/conflict.py` 가 바뀌었다.
  - 삭제 충돌에서는 덮어쓰기를 내놓지 않는다.
  - 같은 행을 다시 클릭해도 탭을 다시 읽지 않는다.
  - 붙여넣기는 version을 넘기고, 탭이 dirty면 거부한다.
  - 재접속·CSV 불러오기 전에 묻는다. step 4가 `connect_db` 앞에 질문을 넣었다.
  - Remove Process 뒤에는 편집을 버린다.
  - 걸러 본 상태로 저장할 때 순서값을 다시 나눠 준다.

모든 step에 같은 규칙이 적용된다.
1. 버그는 **주장**이다. 먼저 실패하는 테스트로 재현하고, RED 출력(테스트 이름과 실패한 단언)을 summary에 적는다. 승인된 동작 변경도 테스트를 먼저 쓴다. 지금 코드에서 그 테스트가 어떻게 실패하는지(지금 동작)를 summary에 적는다.
2. RED는 **Windows 개발 PC에서** 보여야 한다. `posix_only` 테스트는 개발 PC에서 skip되므로 버그를 증명하지 못한다.
3. 재현되지 않으면 `src/` 를 고치지 않는다. 테스트는 특성 테스트로 남기고 `"status": "completed"`, `"summary": "not reproduced: <이유>"` 로 끝낸다.
4. 고친 뒤 수정을 손으로 되돌려 새 테스트가 실패하는지 확인하고 다시 고친다(변이 검사). `git checkout`/`git stash` 로 되돌리지 마라. 이유: 같은 step의 테스트 변경까지 사라진다.
5. 이 파일의 행 번호는 2026-10-17(phase 6 전) 기준 대략값이다. phase 7~10이 같은 파일을 바꿨으니 이름으로 찾아라.
6. `DeviceTabController.connect_db`/`_open_database` 는 phase 7·10·11·12가 차례로 건드린다. 이 파일들은 그 본문을 인용하지 않는다. 지금 코드를 읽고, 적힌 불변식만 지켜라.

GUI 테스트 기반은 phase 2(`2-gui-test-infra`)가 만들었다. 아래 이름을 그대로 쓰고, 같은 일을 하는 것을 새로 만들지 마라. 작업 전에 `tests/gui/conftest.py`·`tests/gui_support/` 를 읽는다. 이 파일의 서술과 다르면 실제 코드를 따른다.
- 대화상자 대역은 `tests/gui_support/dialogs.py` 의 `FakeDialogs` 이고 autouse `dialogs` fixture로 들어온다.
  - `dialogs.answer_question(*bools)` 는 Yes/No 질문에, `dialogs.answer_conflict(*choices)` 는 충돌 대화상자에 순서대로 답한다.
  - 뜬 상자는 `dialogs.shown` 에 `(kind, title, text)` 로 쌓인다. 알림 severity `warn` 은 kind `warning` 으로 남는다.
  - 답을 정하지 않은 모달은 `AssertionError` 다. `@report` 가 삼켜도 teardown에서 실패한다. 파일 대화상자와 메뉴도 막혀 있다.
- `device_tab_ctrl` 은 가짜에 붙어 이미 접속한 `DeviceTabController` 다. `notifyRequested` 가 `dialogs.record_notify` 에 이어져 있다.
- `main_window` 는 가짜에 붙은 `MainWindowController` 다. `.ui` 는 MainWindow, `.device_tab` 은 컨트롤러다. History 화면은 만들지 않는다.
- 시드(`seeded_store()`): process `sf2p`(device `nfet_a`, `nfet_b`), `sf4u`(device `pfet_a`). 탭은 `"InstTerm"`·`"InstSchParam"` 이다.
  - id는 `store.find_device("nfet_a")["id"]` 로 얻는다.
  - 접속하면 `sf2p` 가 골라진다. autouse로 `GENDB_APP_USER=tester` 다.
- `store.calls` 는 `(메서드 이름, 인자 dict의 deep copy)` 이고, 호출이 **끝난 뒤**(예외로 끝나도) 기록된다. `store.calls_of(name)`, `store.fail_next(name, exc)`, `store.add_device(process_id, name, celltype, order=…)` 를 쓴다.
- `install_fake_db(monkeypatch, store)` 는 `DeviceTabController._open_database` 를 `store.open_database` 로 바꾼다. 그래서 fixture 안에서는 `_open_database` 본문이 돌지 않는다.
- `tests/gui_support/helpers.py`: `select_process(ctrl, name)`, `select_device_row(ctrl, row)`, `edit_device_cell(...)`, `edit_tab_cell(...)`. helpers는 기다리지 않는다.
- "아무 일도 일어나지 않았다" 를 `qtbot.wait` 고정 대기로 확인하지 않는다. `store.calls` 나 컨트롤러 상태를 `qtbot.waitUntil` 로 기다린 뒤 단언한다. `waitUntil` 콜백은 bool을 돌려준다(`lambda: store.calls_of("etag") != []`).

## 이 step의 목적

화면(알림 상자, 로그 패널)으로 가는 예외 문자열 두 곳이 `user_message()` 를 거치지 않는다. 이것을 고친다.
- K34: process 조회 실패 알림
- K35: 변경 감지 폴링 중단 로그

CLAUDE.md CRITICAL 규칙은 "예외는 `str(exc)` 대신 `service.errors.user_message(exc)`" 다. 이 위반을 고치면 문구가 `user_message` 형태로 바뀐다. 2026-10-17 분류에서 이것을 버그로 정했다(승인 대상 아님).

## 읽어야 할 파일

- `/CLAUDE.md`(CRITICAL: 비밀번호를 화면·로그에 남기지 않는다), `/docs/UI_GUIDE.md`(원칙 5, "하지 않는 것" 표), `/docs/ADR.md`(ADR-013)
- `src/genviewer/service/errors.py`: `user_message` (~90-102), `_detail`, `_BY_SQLSTATE`. 제목 줄, 빈 줄, 상세 줄로 된 여러 줄 문자열을 낼 수 있다.
- `src/genviewer/utils/logs.py`: `scrub`
- `src/genviewer/controllers/device_tab_toolbar.py`: `get_process_id` (~150-157)
- `src/genviewer/controllers/device_tab.py`
  - `_poll_remote_changes` (~197-215), `_on_poll_failed` (~233-237)
  - `send_device_data` 끝의 try/except (~346-352)
  - `connect_db` 의 실패 로그 줄은 이미 `user_message` 를 쓴다(본보기).
- `src/genviewer/controllers/main_window.py`: `_on_click_connect_toggle` (~198-216)
- `tests/gui/test_smoke.py`: 폴링 테스트 본보기(~98-122). `ctrl._poll_remote_changes()` 를 직접 부르고, `etag` 호출과 `ctrl._poll_task is None` 을 기다린다.
- `tests/gui/test_process_list_refresh.py`

## 버그

**K34** (`controllers/device_tab_toolbar.py` `get_process_id`)

```python
except Exception as e:
    self.notifyRequested.emit("error", "Process Lookup Failed", str(e))
```

- process를 고를 때 `get_or_create_id` 가 55P03(lock_timeout)으로 실패할 수 있다. 다른 사람의 CLI `load` 가 process 행을 잠갔을 때(K5)다.
- 그러면 알림 본문은 psycopg 원문이다. `user_message` 였다면 "다른 사용자가 저장하는 중이다. 잠시 후 다시 시도할 것." 이 나온다.
- 예외 문자열에 conninfo(`password=…`)가 들어 있으면 그대로 화면에 찍힌다.

**K35** (`controllers/device_tab.py` `_on_poll_failed`)
- 연속 3번째 실패에서 `f"변경 감지 폴링을 중단했다: {exc}"` 를 로그 패널에 쓴다.
- 로그 패널은 파일 로그의 scrub 포매터를 지나지 않는다(ADR-013).

이것은 주장이다. 먼저 재현하라. repo가 내는 예외는 `store.fail_next` 로 만들어도 된다. 실제 repo도 psycopg 예외를 낸다.

**후보** (재현되면 같은 방식으로 고치고, 안 되면 그대로 둔다)
- `controllers/main_window.py` `_on_click_connect_toggle` 의 `f"Connection error: {e}"`. Virtuoso 소켓 접속이고 DB conninfo와는 무관하다.
- `controllers/device_tab.py` `send_device_data` 끝의 `f"Send failed: {e}"`. PySide6에서 슬롯이 낸 예외는 `emit` 호출자에게 오지 않는다. 닿는 경로가 있는지 본다.

후보는 그 try 블록 안의 **실제 코드**가 예외를 내는 입력을 찾았을 때만 재현으로 본다. 그 함수나 그 안에서 부르는 메서드를 monkeypatch 해 아무 예외나 내게 하는 것은 재현이 아니다.

다른 step 몫이라 이 step에서 건드리지 않는 것:
- `dialogs/connection.py` 의 `f"실패: {e}"`: step 1(connect-failure-cause)이 같은 줄을 고친다.
- `controllers/history_tab.py` 의 두 곳: phase 12 step 1이 고친다(History fixture가 그때 생긴다).

## 작업

### 1. 테스트 먼저 (`tests/gui/test_user_message_sites.py`, 새 파일)

- **K34, SQLSTATE 안내**
  - 준비: `store.fail_next("get_or_create_id", psycopg.errors.LockNotAvailable("canceling statement due to lock timeout"))`
  - 동작: `select_process(device_tab_ctrl, "sf4u")`
  - 단언: `dialogs.shown` 에 `("error", "Process Lookup Failed", text)` 가 있고, `text == user_message(같은 예외 객체)` 다. 단언 전에 그 예외의 `sqlstate` 가 `"55P03"` 인지 확인한다.
  - **수정 전에는 원문이라 실패해야 한다.**
- **K34, 비밀번호**
  - 준비: `psycopg.OperationalError("connection failed: host=h password=s3cret")`
  - 단언: 알림 본문에 `"s3cret"` 이 없다. **수정 전에는 실패해야 한다.**
- **K35**
  - 준비: 로그 줄을 리스트에 받는다(`device_tab_ctrl.logRequested.connect(lines.append)`). `store.fail_next("etag", psycopg.OperationalError("connection failed: password=s3cret"))` 를 세 번 쌓는다.
  - 동작: 세 번 되풀이한다. `ctrl._poll_remote_changes()` 를 부르고 `qtbot.waitUntil(lambda: len(store.calls_of("etag")) == n + k and ctrl._poll_task is None)` 로 기다린다.
  - 단언
    - `"변경 감지 폴링을 중단했다: "` 로 시작하는 줄이 정확히 하나다. 그 줄에 `"s3cret"` 이 없고, 줄바꿈(`"\n"`)도 없다. **수정 전에는 실패해야 한다.**
    - 폴링 타이머는 멈췄다(`not ctrl._poll_timer.isActive()`, 지금과 같다).
- **회귀**: 첫째·둘째 실패 뒤에는 그 로그 줄이 없다(지금과 같다).
- 후보마다 재현을 시도한다. 재현되면 RED 테스트를 남긴다. 안 되면 테스트를 만들지 말고, summary에 이유를 적는다.

### 2. 수정

- `get_process_id`: 알림 본문을 `user_message(e)` 로 바꾼다. 제목 `"Process Lookup Failed"` 와 severity `"error"` 는 그대로 둔다.
- `_on_poll_failed`: `user_message(exc)` 를 한 줄로 만들어(줄바꿈을 공백으로) 기존 접두어 `"변경 감지 폴링을 중단했다: "` 뒤에 붙인다.
- 재현된 후보만 같은 방식으로 고친다.

### 3. 문서

- 없다. 고친 known-issues 항목(K34·K35)은 phase 마무리에서 지운다.

## Acceptance Criteria

```bash
uv run pytest tests/gui/test_user_message_sites.py -q   # 새 테스트 통과 (수정 전에는 K34·K35 테스트가 실패해야 한다)
uv run ruff check src tests
uv run pytest -q
```

## 검증 절차

1. 위 AC 커맨드를 실행한다.
2. 아키텍처 체크리스트를 확인한다.
   - 화면·로그 패널로 가는 예외 문자열이 `user_message()` 를 거치는가(CLAUDE.md CRITICAL)?
   - 알림 제목·severity·로그 접두어를 바꾸지 않았는가(UI_GUIDE 문구)?
   - `service/errors.py` 를 바꾸지 않았는가?
3. 결과에 따라 `phases/11-gui-error-paths/index.json` 의 step 0을 업데이트한다.
   - 성공 → `"status": "completed"`, `"summary": "K34 get_process_id·K35 _on_poll_failed 를 user_message 로(로그는 한 줄). RED: <테스트 이름: 실패한 단언>. 변이: <되돌렸을 때 실패한 테스트>. 후보: main_window Connection error <재현됨/not reproduced: 이유>, device_tab Send failed <…>. tests/gui/test_user_message_sites.py"`
   - 재현 안 됨 → `"status": "completed"`, `"summary": "not reproduced: <이유>"`
   - 수정 3회 시도 후에도 실패 → `"status": "error"`, `"error_message": "구체적 에러 내용"`
   - 사용자 개입 필요 → `"status": "blocked"`, `"blocked_reason": "구체적 사유"` 후 즉시 중단

## 금지사항

- 알림 제목·severity·로그 접두어를 바꾸거나 번역하지 마라. 이유: 이 step은 예외 문자열이 `user_message` 를 거치게만 한다(UI_GUIDE "문구").
- `user_message` 자체(`service/errors.py`)를 바꾸지 마라. 이유: 모든 화면 문구가 함께 바뀐다.
- `dialogs/connection.py` 와 `controllers/history_tab.py` 를 고치지 마라. 이유: step 1과 phase 12 step 1의 몫이다. 같은 줄을 두 step이 고치면 RED가 사라진다.
- 재현되지 않은 후보를 "일관성" 을 이유로 고치지 마라. 이유: CLAUDE.md "재현되지 않으면 고치지 않는다".
- `qtbot.wait` 로 고정 대기하지 마라. 이유: 느린 PC에서 깨지고, 아무 일도 없었다는 증거가 되지 못한다.
- 기존 테스트를 깨뜨리지 마라.
