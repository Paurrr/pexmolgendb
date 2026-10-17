# Step 6: socket-workers

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

Virtuoso 소켓(`net/`)의 QThread 워커가 프로세스를 죽이거나 워커 스레드에서 메시지 상자를 여는 경로를 막는다.
- 접속하는 동안 Connect를 또 누르면 실행 중인 `ConnectWorker` 를 덮어써 프로세스가 죽는다 → 두 번째 호출을 무시한다.
- 보내기 실패(`OSError`)가 `SendWorker.run` 밖으로 새어 워커 스레드에서 "예기치 못한 오류" 상자를 연다 → 워커가 잡아 메시지로 알린다.
- 창을 닫아도 Receive/Send 워커를 멈추지 않는다 → `ConnectionController.shutdown()` 을 만들고 `MainWindowController.shutdown()` 이 부른다.
- 마지막 예외 그물(`main.py`)이 어느 스레드에서든 상자를 연다 → 메인(GUI) 스레드에서만 연다.

끊김을 접속 상태에 반영하는 일(known-issues K14)과 `recv`/`wait()` 타임아웃(K24)은 **기록만 하고 고치지 않는다**.

## 읽어야 할 파일

- `/CLAUDE.md`(테스트 관례: 외부 의존에 붙지 않는다), `/docs/ARCHITECTURE.md`(스레딩: `net/` 은 QThread 워커 셋이 `Client` 소켓 하나를 쓴다, 레이어 표: `net/` 은 자기 안에서 닫혀 있다), `/docs/UI_GUIDE.md`("워커 스레드에서 위젯·QMessageBox 만들기" 금지), `/docs/ADR.md`(ADR-013)
- `src/genviewer/net/controller.py` — `__init__(client_factory=…)` (~13-27, fake를 넣는 입구), `connect` (~37-47), `disconnect` (~49-60), `send` (~62-66), `_on_connect_worker_done` (~68-82), `_start_io_workers` (~99-109), `_stop_io_workers` (~111-128), `_cleanup_workers`/`_teardown_client` (~130-156)
- `src/genviewer/net/workers.py` — `ConnectWorker` (~9-18, 부모 없는 QThread), `SendWorker` (~33-54, `run` ~42-48 은 `Empty` 만 잡는다, `sendWorkerSignal` 은 선언만 있고 쓰이지 않는다), `ReceiveWorker` (~57-108, 오류를 `"ERROR: recv failed - …"` 로 내는 모양 ~100)
- `src/genviewer/net/client.py` — `connect`, `send` (~40-43, `clientSocket.sendall`), `close`
- `src/genviewer/controllers/main_window.py` — `__init__` 의 `ConnectionController()` (~24), `shutdown` (~64 이후, step 5에서 이벤트 필터 제거가 들어갔다), `_on_received_from_controller`(그 밖의 메시지는 Socket 탭 수신 칸), `_on_click_connect_toggle` (~152-171)
- `src/genviewer/main.py` — `_show_unexpected` (~28-40, `QMessageBox.critical`), `install_excepthooks` (~43-70: `hook` 이 스레드를 가리지 않고 `_show_unexpected` 를 부른다, `thread_hook` 은 로그만)
- `tests/gui/conftest.py`(`main_window` 정리 순서), `tests/gui_support/`
- 이전 step에서 수정된 파일: `src/genviewer/controllers/main_window.py`(창 닫기 이벤트 필터, `shutdown` 이 필터를 뗀다, DeviceList 질문), `src/genviewer/controllers/device_tab.py`(첫 접속 비동기), `tests/gui/test_window_guards.py`, `tests/gui/conftest.py`

## 버그

2026-10-17 개발 PC(PySide6 6.9.3, Windows)에서 단독 스크립트로 확인한 사실:
- 실행 중인 QThread를 가리키던 마지막 Python 참조를 덮어쓰면 프로세스가 즉시 죽는다(종료 코드 `0xC0000409`, Qt의 "QThread: Destroyed while thread is still running"). 
- `QThread.run` 밖으로 샌 예외는 PySide6가 **그 워커 스레드에서** `sys.excepthook` 을 부른다("Error calling Python override of QThread::run()").

**(a) 접속 중 다시 Connect.** `connect` 는 `_connected` 만 본다. 닿지 않는 호스트면 `ConnectWorker` 가 `client.connect()` 에서 오래(Windows 약 20초) 막히는데, 그동안 Connect를 다시 누르면 `_on_click_connect_toggle` → `connect` 가 `self._client` 와 `self._connectWorker` 를 새 것으로 바꾼다. 앞 `ConnectWorker` 는 부모가 없어 마지막 참조가 사라지는 순간 지워지고, 실행 중이므로 **프로세스가 죽는다**. 살아남더라도 앞 워커의 결과가 도착해 두 번째 클라이언트로 IO 워커를 띄운다.

**(b) 보내기 실패.** `SendWorker.run`:

```python
while self._running:
    try:
        msg = self._queue.get(timeout=0.1)
        self.client.send(msg)
    except Empty:
        continue
```

상대가 끊어 `sendall` 이 `ConnectionResetError`/`BrokenPipeError`(또는 소켓이 닫혀 다른 예외)를 내면 `run` 밖으로 샌다. PySide6가 워커 스레드에서 `sys.excepthook` 을 부르고, `main.py` 의 `hook` 은 `_show_unexpected` → `QMessageBox.critical` 을 **워커 스레드에서** 연다(Qt 위젯은 GUI 스레드 것이다. 멈추거나 죽을 수 있다). SendWorker 스레드는 끝나 버려 이후 보내기는 "Not connected (send ignored)" 가 된다.

**(c) 창을 닫을 때.** `MainWindowController.shutdown()` 은 이력·DB만 정리한다. Virtuoso에 붙은 채 창을 닫으면 `run_gui` 가 돌아오면서 컨트롤러가 사라지고, 아직 도는 `ReceiveWorker`·`SendWorker` 가 지워져 (a)와 같은 이유로 종료가 크래시가 된다.

**(d) 예외 그물.** `install_excepthooks` 의 `hook` 은 메인 스레드가 아닌 곳에서 불려도 `_show_unexpected` 로 상자를 연다. (b) 같은 경로가 하나 더 생겨도 같은 일이 난다.

이것은 주장이다. 먼저 재현하라.

## 작업

### 결과 × 상태

| 상태 | 동작 |
|---|---|
| 끊김, `connect` | 지금과 같다(클라이언트 하나, ConnectWorker 하나) |
| 접속 중(ConnectWorker 실행 중), `connect` 또 | 아무것도 하지 않는다. `_client`·`_connectWorker` 그대로, `statusChanged` 없음 |
| 접속 중 결과 도착(성공/실패) | 지금과 같다(성공이면 IO 워커 시작 + "Connected", 실패면 상태 문구) |
| 접속 실패 뒤 `connect` | 지금과 같다(끝난 앞 워커를 새 것으로 바꿔도 된다) |
| 붙어 있음, 보내기 성공 | 지금과 같다 |
| 붙어 있음, `client.send` 예외 | `SendWorker` 가 잡아 파일 로그에 남기고 `sendWorkerSignal("ERROR: send failed - <e>")` 를 낸 뒤 루프를 끝낸다. 컨트롤러는 이 시그널을 `received` 로 넘겨(받기 오류와 같은 길) Socket 탭 수신 칸에 보인다. 접속 상태 표시는 바꾸지 않는다(K14). 이후 `send` 는 지금처럼 "Not connected (send ignored)" |
| 창 닫기(`MainWindowController.shutdown()`) | `connection_controller.shutdown()` 이 Receive/Send 워커를 멈추고 기다린 뒤 클라이언트를 닫는다. 붙어 있지 않으면 아무것도 하지 않는다. 여러 번 불러도 된다 |
| 창 닫기 때 ConnectWorker 실행 중 | 기다리지 않는다(접속 타임아웃만큼 창이 굳는다). K24와 같은 종류로 **기록만** 하고 summary에 적는다 |
| 메인 스레드에서 잡히지 않은 예외 | 지금과 같다(파일 로그 + "예기치 못한 오류" 상자) |
| 다른 스레드에서 `sys.excepthook` | 파일 로그만 남기고 상자를 열지 않는다 |

### 1. 테스트 먼저 (`tests/gui/test_socket_workers.py`, 새 파일)

실제 서버·포트에 붙지 않는다. `tests/gui_support/fakes.py` 에 `FakeVirtuosoClient` 를 더하고 `ConnectionController(client_factory=…)` 로 넣는다.
- `connect()`: `self.release`(`threading.Event`, 기본은 이미 set)를 `wait(5)` 한 뒤 `("Disconnect", "Connected", True)`. 타임아웃을 둬서 실패한 테스트가 영원히 멈추지 않게 한다.
- `send(cmd)`: `sent` 에 기록하고, `send_error` 가 있으면 그것을 낸다.
- `clientSocket`: `ReceiveWorker` 가 살아 있어야 하는 테스트는 `socket.socketpair()` 의 한쪽(로컬, 네트워크 없음)을 쓰고 다른 쪽은 테스트 끝에 닫는다. 아니면 `None`(그러면 ReceiveWorker는 곧바로 "DISCONNECTED" 를 내고 끝난다. 테스트는 이것을 무시한다).
- `close()`·`disConnect()` 는 기록만 하고 소켓이 있으면 닫는다.

**실행 중인 QThread를 테스트가 놓치면 pytest 프로세스가 통째로 죽는다.** 각 테스트는 만든 워커 객체 참조를 쥐고, `finally` 에서 `release.set()` → 모든 워커 `wait(5000)` → `ctrl._stop_io_workers()`(수정 전에도 있는 메서드) 순으로 정리한다.

- **(a) 접속 중 두 번째 connect 무시**: `release` 를 비운 fake로 `ctrl.connect("h", 1)` → `first = ctrl._connectWorker`(참조 보관) → `ctrl.connect("h", 1)` 다시. factory가 한 번만 불렸고, `ctrl._connectWorker is first`, `ctrl.client` 가 첫 fake이며, 두 번째 호출 중 `statusChanged` 가 나오지 않았다(동기 경로라 바로 단언). `release.set()` 후 `qtbot.waitUntil(lambda: ctrl.is_connected)`. **수정 전에는 factory가 두 번 불리고 `_connectWorker is not first` 라 실패해야 한다(참조를 쥐고 있어서 죽지 않고 단언에서 실패한다).**
`sys.excepthook`·`threading.excepthook` 을 바꾸는 테스트는 `monkeypatch` 대신 `old = sys.excepthook` 로 잡아 두고 `try/finally` 로 **테스트 안에서** 되돌린다. 이유: pytest-qt는 테스트 호출 구간에만 자기 hook을 걸었다 푸는데, monkeypatch 정리는 그 뒤(teardown)에 돌아 pytest-qt의 hook을 되살려 놓는다.

- **(b) 보내기 실패가 메시지가 된다**: 붙은 뒤 `received` 를 리스트로 모으고, `fake.send_error = ConnectionResetError(10054, "reset")`, `sys.excepthook = recorder`(위 방식으로 되돌린다). `sw = ctrl._sendWorker`(참조 보관) → `ctrl.send("x")` → `qtbot.waitUntil(lambda: fake.sent)` → `qtbot.waitUntil(lambda: not sw.isRunning())`. `recorder` 가 비어 있고, `qtbot.waitUntil` 로 `received` 에 `"ERROR: send failed"` 로 시작하는 메시지가 온다. **수정 전에는 `recorder` 가 워커 스레드에서 ConnectionResetError를 받아 실패해야 한다.**
- **(c) shutdown이 IO 워커를 멈춘다**: socketpair fake로 붙은 뒤 `rw, sw = ctrl._receiveWorker, ctrl._sendWorker` → `ctrl.shutdown()` → `rw.isFinished()`·`sw.isFinished()` 가 True, 두 속성이 None, fake의 `close` 가 불렸다. 한 번 더 불러도 예외가 없다. 붙기 전 컨트롤러의 `shutdown()` 도 예외가 없다.
- **(c) 창 정리가 소켓도 정리한다**: `main_window` 에서 `mw.connection_controller._client_factory` 를 fake factory로 바꾸고 `connect` → 붙은 뒤 워커 참조 보관 → `mw.shutdown()` → 두 워커가 끝나 있다. **수정 전에는 워커가 아직 돌고 있어 실패해야 한다.** (fixture 정리가 `shutdown()` 을 한 번 더 부르므로 두 번 불러도 되는지 함께 확인된다.)
- **(d) 예외 그물**: `sys.excepthook`·`threading.excepthook` 을 잡아 두고(`finally` 에서 둘 다 되돌린다), `monkeypatch.setattr(genviewer.main, "_show_unexpected", recorder)`, `genviewer.main.install_excepthooks()`.
  - `threading.Thread(target=lambda: sys.excepthook(type(e), e, None))` 를 돌리고 `join()` → `recorder` 가 비어 있고 `caplog` 에 "처리되지 않은 예외" 가 있다. **수정 전에는 `recorder` 가 불려 실패해야 한다.**
  - `run` 에서 예외를 내는 작은 `QThread` 를 돌리고 `wait()` → 역시 `recorder` 가 비어 있다(실제 PySide6 경로).
  - 메인 스레드에서 `sys.excepthook(...)` → `recorder` 가 한 번 불린다(지금 동작 유지).

### 2. 수정

```python
# net/controller.py
class ConnectionController(QObject):
    def connect(self, host: str, port: int) -> None: ...   # ConnectWorker 가 돌고 있으면 바로 돌아간다
    def shutdown(self) -> None: ...                        # IO 워커 정지·대기 후 클라이언트 close. 멱등

# net/workers.py
class SendWorker(QThread):
    sendWorkerSignal = Signal(str)   # 이미 있다. 보내기 실패를 "ERROR: send failed - <e>" 로 낸다
```

- `connect`: `self._connectWorker is not None and self._connectWorker.isRunning()` 이면 아무것도 바꾸지 않고 돌아간다. 그 밖은 지금과 같다.
- `SendWorker.run`: `client.send(msg)` 에서 난 `Exception` 을 잡아 `logging.getLogger(__name__).warning(…, exc_info=e)` 로 파일 로그에 남기고, `sendWorkerSignal.emit(f"ERROR: send failed - {e}")` 한 뒤 루프를 끝낸다(`ReceiveWorker` 의 오류 처리와 같은 모양). `Empty` 처리는 그대로.
- `_start_io_workers`: `self._sendWorker.sendWorkerSignal` 을 `self._on_received` 에 잇는다.
- `shutdown`: `_stop_io_workers()` 후 `self._client` 가 있으면 `close()` 하고 `None` 으로 둔다. ConnectWorker·DisconnectWorker 는 기다리지 않는다. `statusChanged` 는 내지 않는다(창이 닫히는 중이다).
- `controllers/main_window.py` 의 `shutdown()`: 지금 정리(필터 제거, 이력, DB)에 `self.connection_controller.shutdown()` 을 더한다.
- `main.py` 의 `hook`: 지금처럼 `log.critical(…)` 은 늘 남기고, `_show_unexpected(exc)` 는 메인 스레드(`threading.current_thread() is threading.main_thread()`, 이 앱에서는 GUI 스레드와 같다)일 때만 부른다. `thread_hook` 은 그대로.

### 3. 문서

- known-issues K14·K24는 그대로 둔다(phase 마무리에서 정리한다). 창을 닫을 때 ConnectWorker가 도는 경우를 발견한 대로 summary에 적는다.

## Acceptance Criteria

```bash
uv run pytest tests/gui/test_socket_workers.py -q   # 새 테스트 통과 (수정 전에는 (a)(b)(c)(d) 테스트가 실패해야 한다. 프로세스가 죽으면 안 된다)
uv run ruff check src tests
uv run pytest tests/gui -q
uv run pytest -q
```

## 검증 절차

1. 위 AC 커맨드를 실행한다.
2. 아키텍처 체크리스트를 확인한다:
   - `net/` 이 우리 다른 패키지를 import하지 않는가(레이어 표: `net/` 은 자기 안에서 닫혀 있다. stdlib `logging` 은 괜찮다)?
   - 워커 스레드에서 위젯·QMessageBox를 만들지 않는가(UI_GUIDE)?
   - 테스트가 실제 서버·포트에 붙지 않는가(CLAUDE.md 테스트 관례)?
3. 결과에 따라 `phases/4-gui-robustness/index.json` 의 step 6을 업데이트한다:
   - 성공 → `"status": "completed"`, `"summary": "ConnectionController: ConnectWorker 실행 중 connect 무시, shutdown() 추가(MainWindowController.shutdown 이 호출). SendWorker 가 send 예외를 잡아 'ERROR: send failed - …' 를 received 로. main.hook 은 메인 스레드에서만 상자. K14/K24 기록만. RED: <테스트 이름>. tests/gui/test_socket_workers.py 추가"`
   - 재현 안 됨 → `"status": "completed"`, `"summary": "not reproduced: <이유>"`
   - 수정 3회 시도 후에도 실패 → `"status": "error"`, `"error_message": "구체적 에러 내용"`
   - 사용자 개입 필요 → `"status": "blocked"`, `"blocked_reason": "구체적 사유"` 후 즉시 중단

## 금지사항

- 접속 중 두 번째 `connect` 에서 앞 워커를 `terminate()` 하거나 `wait()` 하지 마라. 이유: `terminate` 는 소켓·락 상태를 망가뜨리고, `wait` 는 접속 타임아웃만큼 창을 굳힌다.
- 두 번째 `connect` 에서 `statusChanged` 를 내지 마라. 이유: `_on_status_changed` 가 버튼·상태 문구를 바꿔 접속 중 표시가 틀어진다. "무시" 는 아무것도 바꾸지 않는 것이다.
- 보내기 실패를 새 시그널·새 대화상자·새 상태 문구로 알리지 마라. 이유: 받기 오류가 이미 쓰는 길(`received` → Socket 탭)이 있다. 같은 길을 쓴다.
- 보내기 실패 때 접속 상태(`_connected`, 버튼, 상태 표시줄)를 바꾸지 마라. 이유: 끊김을 상태에 반영하는 것은 known-issues K14(동작 변경, 기록만)다.
- `recv_all`·`select`·`wait()` 에 타임아웃을 넣거나 ReceiveWorker의 UTF-8 처리를 바꾸지 마라. 이유: known-issues K24·K14, 제안 P6의 범위다.
- 테스트에서 `127.0.0.1` 에 listen하는 흉내 서버를 띄우거나 실제 `Client` 로 접속하지 마라. 이유: 외부 의존에 붙지 않는다(CLAUDE.md). fake client를 `client_factory` 로 넣는다(`socketpair` 는 로컬 소켓 한 쌍이라 괜찮다).
- `threading.excepthook`(로그만) 동작과 "예기치 못한 오류" 상자 문구를 바꾸지 마라. 이유: 이 step의 범위가 아니다.
- 기존 테스트를 깨뜨리지 마라.
