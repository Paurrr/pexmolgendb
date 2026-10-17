# Step 4: connect-db

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

`DeviceTabController` 의 DB 접속 경로 세 가지를 고친다.
- (S8) "Database connected: …" 로그 줄의 DSN을 `scrub()` 해서 비밀번호가 로그 패널에 찍히지 않게 한다.
- (G13) 다시 접속할 때 새 DB를 **먼저** 연다. 실패하면 지금 DB와 repo를 그대로 쓴다. 성공하면 폴링을 멈추고 도는 폴링 작업을 기다린 뒤 옛 DB를 닫는다.
- (G16, **사용자 승인 2026-10-17**) 시작할 때의 접속을 `QTimer.singleShot(0, …)` 로 미뤄, 창의 로그 패널·알림이 연결된 뒤에 돌게 한다. 시작 접속 실패와 첫 조회 실패가 화면에 보인다.

## 읽어야 할 파일

- `/CLAUDE.md`(CRITICAL: 비밀번호를 화면·로그에 남기지 않는다, `scrub()`), `/docs/ADR.md`(ADR-009, ADR-013: 로그 패널로 직접 보내는 문자열은 호출자가 `scrub()`), `/docs/ARCHITECTURE.md`(스레딩, 변경 감지), `/docs/UI_GUIDE.md`(문구: `notifyRequested`/`logRequested`)
- `src/genviewer/controllers/device_tab.py` — `__init__` (~44-89, 마지막 줄에서 `self.connect_db(dsn)`), `set_repo` (~91-97), `_on_connect` (~102-109, "Connected"/"Connect Failed" 알림), `_open_database` (~129-136), `connect_db` (~138-169: ~140-142 에서 옛 DB를 먼저 닫고, ~168 에서 DSN을 그대로 로그), `_poll_remote_changes`/`_clear_poll_task` (~175-200), `close_db` (~234-251, 폴링 작업을 기다린 뒤 닫고 `dbChanged(None)`), `apply_db` (~253-259)
- `src/genviewer/controllers/main_window.py` — `__init__` (~21-62: `DeviceTabController` 를 만든 **뒤에** ~47-49 에서 `notifyRequested`·`logRequested` 를 창에 잇는다. ~59-60 이력 화면 `dbChanged` 연결)
- `src/genviewer/controllers/history_tab.py` — `set_db` (~76-93)
- `src/genviewer/controllers/device_tab_toolbar.py` — `refresh_processes` (~130-135, `@report("Process List Failed")`)
- `src/genviewer/utils/logs.py` — `scrub` (~41-48, `password=…` 와 `://user:secret@` 를 가린다)
- `src/genviewer/utils/background.py` — `run_blocking`, `Task`, `is_busy`
- `.venv/Lib/site-packages/psycopg_pool/base.py` — `_check_open`: 닫힌 풀은 `PoolClosed("pool has already been opened/closed and cannot be reused")`
- `tests/gui/conftest.py`(`device_tab_ctrl`·`main_window` 가 `_open_database` 를 어떻게 바꾸고 무엇을 기다리는지), `tests/gui_support/fakes.py`(`FakeDatabase`)
- 이전 step에서 수정된 파일: `src/genviewer/models/device_table.py`, `src/genviewer/controllers/device_table.py`(정렬), 그 앞의 탭 섹션 파일들 (이 step과 관계없음)

## 버그

**S8.** `connect_db` 끝의 `self.logRequested.emit(f"Database connected: {db.cfg.dsn}.")` 가 `--dsn`·Connect 창·`GENDB_PG_DSN` 의 DSN을 그대로 로그 패널에 쓴다. `host=… password=s3cret` 이나 `postgresql://app:s3cret@host/db` 면 비밀번호가 화면에 찍힌다. 로그 패널은 파일 로그의 `ScrubbingFormatter` 를 지나지 않는다(ADR-013).

**G13.** `connect_db` 는 새 DB를 열기 **전에** 지금 DB를 닫는다.

```python
if self.db is not None:
    self.db.close()
    self.db = None
try:
    db = run_blocking(lambda: self._open_database(dsn), self)
except Exception as e:
    self.connected = False
    ...
    return False
```

새 접속이 실패하면 `self.db = None`, `connected = False` 인데 `device_table`·`device_tab_toolbar`·`parameter_tab` 의 repo는 **닫힌** `Database` 를 그대로 쥐고 있다. 그 뒤 process 바꾸기·저장·탭 로드가 전부 psycopg_pool 의 `PoolClosed`("pool has already been opened/closed and cannot be reused")로 실패한다. 다시 붙기 전까지 앱을 쓸 수 없다. 성공하는 경우에도 폴링 `Task` 가 옛 풀의 커넥션을 쥔 채로 풀이 닫힐 수 있다(`close_db` 는 기다리지만 여기는 기다리지 않는다).

**G16.** `DeviceTabController.__init__` 의 마지막 줄이 `connect_db(dsn)` 를 바로 부른다. 그때는 `MainWindowController.__init__` 이 아직 `device_tab.notifyRequested`·`logRequested` 를 창에 잇기 전이다. 그래서 시작할 때 접속 실패("Database connect failed: …"), 접속 성공 줄, 첫 조회 실패(`refresh_processes` 의 "Process List Failed", `apply_db` 의 "Load Failed")가 화면 어디에도 나오지 않는다(파일 로그에만 남는다). 사용자는 DB가 왜 비었는지 모른다.

이것은 주장이다. 먼저 재현하라.

## 작업

### 결과 × 상태 (최종 상태)

| 상태 \ 결과 | 성공 | 실패 (`DbUnavailableError` 등 예상 오류, `RuntimeError` 등 예상 밖 예외 모두) |
|---|---|---|
| 시작 (DB 없음, `singleShot` 으로 첫 접속) | `db` = 새 것, `connected=True`, `dbChanged(새)` 한 번, `apply_db` 로 화면 채움(그 안의 실패는 "Process List Failed"/"Load Failed" 알림으로 **화면에 뜬다**), 폴링 시작, 로그 패널 "Database connected: <가린 DSN>." | `db=None`, `connected=False`, 로그 패널 "Database connect failed: <user_message>", 파일 로그 경고. 새 대화상자 없음 |
| 붙어 있는 중에 다시 접속 (Connect…) | 폴링 타이머 정지 → 도는 폴링 `Task` 끝날 때까지 대기 → 옛 DB `close()` → `db` = 새 것, repo 교체, `dbChanged(새)` 한 번(None 없음), `apply_db`, 폴링 재시작, "Connected" 알림 | 옛 DB가 열린 채 그대로, repo 그대로, `connected=True`, 폴링 그대로, "Connect Failed" 알림 + 로그 패널 "Database connect failed: …" |
| 시작 접속 실패 뒤 다시 접속 | 시작 성공과 같다 + "Connected" 알림 | `db=None`, `connected=False` 유지, "Connect Failed" 알림 |
| 접속하는 동안 또 Connect | `run_blocking` 이 사용자 입력을 막아 닿지 않는다. 테스트하지 않는다 | |
| 첫 접속이 돌기 전에 정리(`shutdown`) | `close_db()` 는 `db is None` 이라 아무것도 닫지 않는다. 예약된 접속은 context 객체가 사라지거나 이벤트 루프가 끝나 돌지 않는다 | |

- 폴링 결과가 재접속 뒤에 도착해 엉뚱한 배너가 뜰 수 있는 문제는 known-issues K23과 같은 종류다. 고치지 않는다.
- 접속에 실패한 새 `Database` 의 풀을 닫지 않는 누수는 known-issues K22다. 고치지 않는다.
- 재접속 순간 이력 화면(`--history`)의 진행 중 `Task` 는 기다리지 않는다(이력은 `dbChanged(새)` 를 받아 다시 읽는다). 발견하면 summary에 적는다.

### 1. 테스트 먼저 (`tests/gui/test_connect_db.py`, 새 파일)

fake 접속: `monkeypatch.setattr(DeviceTabController, "_open_database", staticmethod(opener))`. `opener(dsn)` 는 큐에 넣어 둔 예외가 있으면 그것을 내고, 없으면 `cfg.dsn == dsn` 인 `FakeDatabase(store)` 를 만들어 기록한 뒤 돌려준다. `FakeDatabase` 에 dsn을 넣을 방법이나 닫힘 기록(`closed`, 닫힌 횟수)이 없으면 `tests/gui_support/fakes.py` 에 더한다. `main_window` fixture가 `_open_database` 를 이미 바꾼다면, 재접속 테스트는 fixture 뒤에 다시 바꾸면 된다. 시작 접속을 바꿔야 하는 테스트는 fixture와 같은 방식으로 `MainWindow` + `MainWindowController` 를 직접 만들거나, fixture에 opener를 넘길 수 있는 인자를 더한다(기존 사용처의 동작은 그대로). 로그 패널은 `ui.log_te.toPlainText()` 로 읽는다.

- **S8, 비밀번호가 로그 패널에 없다**: 붙은 `main_window` 에서 `ui.device_tab_view.dbConnectRequested.emit("host=127.0.0.1 dbname=molgen user=app password=s3cret")` → 성공 후 로그 패널에 `"Database connected:"` 가 있고 `"s3cret"` 은 없다. URL 형식 `"postgresql://app:s3cret@127.0.0.1/molgen"` 도 같다. **수정 전에는 `s3cret` 이 보여 실패해야 한다.**
- **G13, 재접속 실패가 옛 DB를 지킨다**: 붙은 상태(db1)에서 opener가 `DbUnavailableError("down")` 를 내게 하고 다시 접속 → `device_tab.db is db1`, db1이 닫히지 않았다, `device_tab.connected is True`, `dialogs.shown` 에 "Connect Failed". 이어서 `select_process(…, "sf2p")` 가 오류 없이 device를 보여 준다. **수정 전에는 db1이 닫히고 `db is None` 이라 실패해야 한다.** (FakeDatabase가 닫힌 뒤의 호출을 실패시키지 않으면 `db is db1`·닫힘 기록으로 단언한다.)
- **G13, 재접속 성공**: db1 → db2. `device_tab.dbChanged` 에 연결한 리스트가 정확히 `[db2]`(None 없음), db1은 한 번 닫혔고 db2는 열려 있다, `device_tab.db is db2`, `connected is True`, 로그 패널에 접속 줄.
- **G13, 폴링 작업을 기다린 뒤 닫는다**: `threading.Event` 를 기다리는 `Task(lambda: ev.wait(5))` 를 시작해 `device_tab._poll_task` 에 넣고, `threading.Timer(0.2, ev.set)` 를 건다. db1의 `close()` 가 불리는 순간 그 Task가 끝나 있었는지(`isFinished()`)를 기록하게 하고 재접속 → 기록이 True. **수정 전에는 기다리지 않고 닫아 False라 실패해야 한다.** 테스트 끝에 Task를 반드시 `wait()` 한다(실행 중인 QThread가 지워지면 프로세스가 죽는다).
- **G16, 시작 접속 실패가 화면에 보인다**: opener가 처음부터 `DbUnavailableError("down")` 를 내게 하고 창을 만든다 → `qtbot.waitUntil(lambda: ctrl.device_tab.connected is not None)` → `connected is False`, 로그 패널에 `"Database connect failed:"` 가 있다. `dialogs.shown` 에 새 상자가 없다. **수정 전에는 로그 패널에 없어 실패해야 한다.**
- **G16, 시작 첫 조회 실패가 화면에 보인다**: opener는 성공하고 `store.fail_next("list_all", DbUnavailableError("down"))`(`FakeProcessRepository.list_all`) → 기다린 뒤 `dialogs.shown` 에 제목 "Process List Failed" 가 있다. **수정 전에는 없어 실패해야 한다.**
- **G16, 시작 성공**: 기다린 뒤 `connected is True`, 로그 패널에 `"Database connected:"`, `dbChanged` 가 한 번.

### 2. 수정 (`controllers/device_tab.py`)

```python
class DeviceTabController(QObject):
    def __init__(self, ui: DeviceTab, dsn: str = ""): ...   # 첫 접속을 예약만 한다
    def connect_db(self, dsn: str) -> bool: ...             # 반환 계약 그대로: 새 DB에 붙었으면 True
```

- `__init__` 은 `connect_db` 를 직접 부르지 않고 `QTimer.singleShot(0, self, lambda: self.connect_db(dsn))` 로 예약한다. context 객체(`self`)를 넘겨 컨트롤러가 먼저 사라지면 불리지 않게 한다. 그때까지 `connected` 는 `None`(아직 시도 전)이다. 첫 접속은 `_on_connect` 가 아니라 `connect_db` 를 부른다 — 새 대화상자는 띄우지 않고, 지금 내는 로그·알림이 화면에 닿게만 한다.
- `connect_db(dsn)`:
  1. 새 DB를 연다(`run_blocking(lambda: self._open_database(dsn), self)`). 이때 지금 DB·repo·폴링은 그대로 둔다.
  2. 실패: 지금 상태를 **하나도 바꾸지 않는다**(`db`, repo, 폴링). 지금 DB가 없을 때만 `connected = False` 로 둔다. 지금처럼 `log.warning(…, exc_info=e)` 와 `logRequested(f"Database connect failed: {user_message(e)}")` 후 False.
  3. 성공: 폴링 타이머를 멈추고, 도는 폴링 `Task` 가 있으면 끝날 때까지 기다린 뒤(`close_db` 와 같은 방식) 옛 DB를 닫는다. 그다음 `self.db = 새 것`, `connected = True`, `set_repo(새 것)`, `dbChanged.emit(새 것)` **한 번**, `apply_db()`(실패는 지금처럼 `report_error(self, "Load Failed", …)`), `_poll_failures = 0`, 폴링 재시작, `logRequested(f"Database connected: {scrub(db.cfg.dsn)}.")`, True.
- 옛 DB를 닫으려고 `close_db()` 를 그대로 부르지 않는다(`dbChanged(None)` 이 한 번 더 나간다). 기다리고 닫는 부분을 함께 쓰고 싶으면 `dbChanged` 를 내지 않는 내부 함수로 나눈다.
- 화면 문구는 그대로다("Database connected: …", "Database connect failed: …", `_on_connect` 의 "Connected"/"Connect Failed").

**구조가 바뀌므로(하네스 규칙 14) 기존 테스트를 확인한다.** 첫 접속이 비동기가 되었으므로, `DeviceTabController`·`MainWindowController` 를 만든 직후 접속된 상태를 가정하는 테스트는 `connected is not None` 을 기다려야 한다. `device_tab_ctrl` 은 이미 기다린다. `main_window` fixture와 `grep -rn "DeviceTabController(\|MainWindowController(" tests` 로 찾은 곳이 기다리지 않으면 `qtbot.waitUntil(lambda: <controller>.connected is not None)` 를 더한다. 기다리지 않은 채 fixture가 정리되면 예약된 접속이 다음 테스트 도중에 돌 수 있다.

### 3. 문서

- ARCHITECTURE·README는 phase 마무리에서 고친다. 이 step에서는 바꾸지 않는다.

## Acceptance Criteria

```bash
uv run pytest tests/gui/test_connect_db.py -q   # 새 테스트 통과 (수정 전에는 S8·재접속 실패·폴링 대기·시작 실패 테스트가 실패해야 한다)
uv run ruff check src tests
uv run pytest tests/gui -q                      # 첫 접속이 비동기가 된 뒤에도 phase 2·3·4 GUI 테스트가 모두 통과
uv run pytest -q
```

## 검증 절차

1. 위 AC 커맨드를 실행한다.
2. 아키텍처 체크리스트를 확인한다:
   - 로그 패널로 가는 접속 문자열이 `scrub()` 을 거치고, 예외 문구는 `user_message()` 를 거치는가(CLAUDE.md CRITICAL)?
   - DB 열기가 여전히 `run_blocking`(워커 스레드)에서 도는가(ADR-009)?
   - `controllers/device_tab.py` 밖의 앱 코드를 바꾸지 않았는가?
3. 결과에 따라 `phases/4-gui-robustness/index.json` 의 step 4를 업데이트한다:
   - 성공 → `"status": "completed"`, `"summary": "connect_db: 새 DB 먼저 열기(실패 시 옛 DB·repo 유지), 성공 시 폴링 대기 후 옛 DB close, dbChanged(새) 1회, 접속 로그 scrub. 첫 접속은 QTimer.singleShot(0, self, ...). 테스트는 connected is not None 대기 필요. RED: <테스트 이름>. tests/gui/test_connect_db.py 추가"`
   - 재현 안 됨 → `"status": "completed"`, `"summary": "not reproduced: <이유>"`
   - 수정 3회 시도 후에도 실패 → `"status": "error"`, `"error_message": "구체적 에러 내용"`
   - 사용자 개입 필요 → `"status": "blocked"`, `"blocked_reason": "구체적 사유"` 후 즉시 중단

## 금지사항

- 새 DB를 열기 전에 지금 DB를 닫지 마라. 이유: 새 접속이 실패하면 앱 전체가 닫힌 풀을 쥔다(이 버그).
- 시작 접속에 `_on_connect` 를 쓰거나 실패 대화상자를 새로 띄우지 마라. 이유: 승인된 것은 "이미 내는 로그·알림이 화면에 닿게" 하는 것이다. 시작할 때마다 뜨는 새 상자는 승인되지 않았다.
- 재접속에서 `dbChanged(None)` 을 내지 마라. 이유: 이력 화면이 비워졌다가 다시 읽어 깜빡이고, "새 DB로 정확히 한 번" 계약이 깨진다.
- `QTimer.singleShot` 을 context 객체 없이 쓰지 마라. 이유: 컨트롤러가 정리된 뒤(테스트 fixture 정리 등)에 접속이 돌 수 있다.
- `_open_database` 의 ping·예외 변환, `scrub()` 의 패턴, `DbConfig` 를 바꾸지 마라. 이유: 이 step의 범위가 아니다(ADR-008, ADR-013).
- 접속 실패한 새 풀 닫기(known-issues K22)를 고치지 마라. 이유: 기록만 하기로 한 문제다.
- 기존 테스트를 깨뜨리지 마라.
