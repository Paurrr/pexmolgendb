# Step 0: socket-behavior-tests

## 배경 (phase 13 공통)

이 저장소는 이미 여러 명이 쓰는 도구다. 평소에는 **에러·버그만 고친다**(CLAUDE.md, ADR-015). phase 13은 예외로, **사용자가 2026-10-17 승인한 구조 변경**이다.

> 사용자 승인 2026-10-17: `net/` 을 QTcpSocket 으로 전환한다(제안 P6). 워커 스레드 기반 소켓을 GUI 스레드의 이벤트 기반 소켓 하나로 바꾼다.

이 구조 변경으로 없애려는 버그는 넷이다(`docs/notes/known-issues.md`).
- K14: Virtuoso 쪽이 연결을 끊거나 수신 오류가 나도 상태가 계속 Connected다. 0바이트 프레임을 끊김으로 잘못 본다.
- K24: 프레임 중간에서 상대가 멈추면 끊기·창 닫기가 굳는다. `recv` 와 `wait()` 에 타임아웃이 없다.
- K39: 접속하는 동안 창을 닫으면 실행 중인 QThread가 지워져 프로세스가 죽는다.
- K40: Connect를 아주 빠르게 두 번 누르면 IO 워커를 덮어써 프로세스가 죽는다.

phase는 step 셋으로 진행한다.
- step 0: 지금 동작을 공개 API 테스트로 고정한다. 버그 넷은 strict xfail로 재현한다. `src/` 는 바꾸지 않는다.
- step 1: `ConnectionController.client` 를 쓰는 바깥 코드를 공개 API로 옮긴다(계약 먼저). 동작은 그대로다.
- step 2: `net/controller.py` 를 QTcpSocket 하나로 다시 쓰고, step 0의 xfail을 뗀다.

모든 step에 같은 규칙이 적용된다.
1. 버그는 **Windows 개발 PC에서** 실패하는 테스트로 먼저 보인다. `posix_only` 로는 증명이 안 된다.
2. 버그가 아닌 구조 변경은 RED 대신 **변이 검사**를 한다. 코드를 손으로 망가뜨려 테스트가 실패하는 것을 보고, 손으로 되돌린다. `git checkout`/`git stash` 로 되돌리지 마라. 이유: 같은 step의 다른 변경까지 사라진다.
3. 프레임 형식은 바꾸지 않는다. 4바이트 big-endian 길이 다음에 UTF-8 본문이 온다(`net/client.py` 의 `send`/`recv_all`). Virtuoso SKILL 쪽 코드가 이 형식을 쓴다.
4. 테스트는 실제 Virtuoso에 붙지 않는다. **127.0.0.1에서 테스트가 띄운 로컬 서버(스레드)에는 붙어도 된다.** phase 4 step 6과 CLAUDE.md는 "listen하는 흉내 서버 금지, `FakeVirtuosoClient` 로 대신" 이라고 했다. QTcpSocket은 가짜 클라이언트를 끼울 자리가 없어서 이 phase가 그 관례를 바꾼다. CLAUDE.md는 step 2가 고친다.
5. 테스트는 **공개 API만** 쓴다. 메서드는 `connect(host, port)`, `disconnect()`, `send(msg)`, `shutdown()` 이다. 속성은 `is_connected`(property)다. 시그널은 `received(str)`, `statusChanged(bool, str)` 다. 이유: step 2가 내부(`_connectWorker`, `_client`, `client_factory` …)를 지우므로, private에 기댄 테스트는 그물이 되지 못한다.
6. pytest 프로세스 안에서 실행 중인 QThread를 놓치면 프로세스가 통째로 죽는다(qFatal "QThread: Destroyed while thread is still running", Windows 종료 코드 `0xC0000409`). 그 상태를 일부러 만드는 재현(K39·K40)은 **서브프로세스**에서만 돌린다.
7. 이 파일의 행 번호는 2026-10-18(phase 12 직후) 기준 대략값이다. 이름으로 찾아라.
8. PostgreSQL SQL은 바꾸지 않는다. 그래서 하네스 규칙 12(DB 테스트 필수)는 해당하지 않는다. `GENDB_TEST_PG_DSN` 이 있으면 `-rs` 로 전체를 돌리고 summary에 `DB 테스트: <N passed | 안 돎(DSN 없음)>` 을 적는다. DSN이 없어도 `blocked` 가 아니다.

GUI 테스트 관례는 CLAUDE.md "테스트 관례" 와 `tests/gui/conftest.py` 를 따른다.
- autouse `dialogs` fixture가 있다. 답하지 않은 모달은 teardown 실패다.
- `main_window` fixture는 `MainWindowController` 를 돌려준다(`.ui`, `.device_tab`, `.connection_controller`, `.socket_tab`).
- "아무 일도 일어나지 않았다" 는 `qtbot.wait` 고정 대기로 단언하지 않는다. 기록한 시그널을 `qtbot.waitUntil` 로 기다린 뒤 단언한다.
- `waitUntil` 콜백은 bool을 돌려준다(`lambda: statuses != []`). 리스트를 돌려주면 pytest-qt가 `ValueError` 를 낸다.
- 테스트 헬퍼는 `tests/gui_support/` 에 두고 `from gui_support.<모듈> import …` 로 쓴다. 다른 테스트 모듈이나 conftest는 import하지 않는다.

## 이 step의 목적

**`src/` 는 바꾸지 않는다.** 지금 `ConnectionController` 의 동작을 공개 API 테스트로 고정한다. step 2가 다시 써도 이 테스트들이 그물이 된다. K14·K24·K39·K40은 strict xfail로 재현한다. 지금 실패해야 하고, step 2 뒤에 XPASS가 되면 strict라서 실패한다. 그때 step 2가 xfail을 뗀다.

## 읽어야 할 파일

- `/CLAUDE.md`(테스트 관례), `/docs/ARCHITECTURE.md`(스레딩: `net/` 줄, 레이어 표: `net/` 은 자기 안에서 닫혀 있다), `/docs/ADR.md`(ADR-013)
- `src/genviewer/net/controller.py` 에서 읽을 이름
  - 진입점: `connect`, `disconnect`, `shutdown`, `send`
  - 결과 처리: `_on_connect_worker_done`, `_on_disconnect_worker_done`, `_start_io_workers`, `_stop_io_workers`, `_emit_status`
  - 상태 문구: `"Already connected: {host}:{port}"`, `"No active connection"`, `"Not connected (send ignored)"`
- `src/genviewer/net/client.py` — `connect` 의 결과 문구(`"Connected"`, `"InvalidAddress"`, `"ConnectionRefused"`, `"ConnectionTimedOut"`, `"Error: …"`), `disConnect` 의 `"Disconnected"`, 프레임 `send`/`recv_all`
- `src/genviewer/net/workers.py` — `ReceiveWorker.run`. 0바이트 프레임은 `"DISCONNECTED"`, 예외는 `"ERROR: recv failed - …"` 로 낸다. 상대가 닫으면 `recv_all` 이 `ConnectionResetError` 를 낸다. 끝날 때 `finally` 에서 소켓을 닫는다.
- `tests/gui/test_socket_workers.py` 전체. 지금 테스트가 private에 어떻게 기대는지, 정리 순서(`Virtuoso.cleanup`)가 왜 그런지 본다.
- `tests/gui_support/fakes.py` 의 `FakeVirtuosoClient`
- `docs/notes/known-issues.md` 의 K14·K24·K39·K40
- 이전 phase에서 바뀌었을 수 있는 파일: `git log --oneline -- src/genviewer/net tests/gui/test_socket_workers.py src/genviewer/controllers/main_window.py` 로 확인한다.

## 작업

### 1. 로컬 서버 헬퍼 (`tests/gui_support/virtuoso_server.py`, 새 파일)

```python
class LocalVirtuoso:
    """127.0.0.1:0 에 listen 하는 테스트용 Virtuoso 흉내. 모든 소켓 연산에 타임아웃이 있다."""
    port: int
    accepted: int                       # 지금까지 받은 연결 수
    def frames(self) -> list[bytes]: ...   # 클라이언트가 보낸 바이트를 4바이트 길이 프레임으로 나눈 본문들
    def peer_closed(self) -> bool: ...     # 마지막 연결에서 클라이언트가 닫았다(recv 가 b"")
    def send_frame(self, body: bytes | str) -> None: ...
    def send_raw(self, data: bytes) -> None: ...
    def close_peer(self) -> None: ...
    def close_peer_after(self, seconds: float) -> None: ...   # threading.Timer
    def close(self) -> None: ...           # listen 소켓과 모든 연결을 닫는다. 멱등
```

- accept와 연결별 읽기는 daemon 스레드에서 돈다. 스레드 사이에서 넘기는 기록은 리스트에 덧붙이기만 한다.
- accept·recv에는 짧은 타임아웃을 두고 루프를 돈다. 어떤 실패도 테스트를 멈추게 해서는 안 된다.
- fixture(예: `virtuoso_server`)는 테스트 모듈이나 `tests/gui/conftest.py` 에 둔다. 정리 때 `close()` 한다.

### 2. 지금 동작 고정 (`tests/gui/test_virtuoso_connection.py`, 새 파일)

컨트롤러는 fixture(예: `make_controller`)가 만든다. 정리 순서는 다음과 같다.

1. 서버의 `close()`. 연결이 닫혀야 막혀 있는 `recv` 가 풀린다.
2. 각 컨트롤러의 `shutdown()`.
3. **step 0 한정** 남은 워커 대기: `getattr(ctrl, "_connectWorker", None)`·`getattr(ctrl, "_disconnectWorker", None)` 가 있으면 `wait(5000)` 한다. 이 줄은 정리용이고 private이다. 테스트 본문에는 넣지 않는다. `getattr` 기본값 때문에 step 2 뒤에도 깨지지 않지만, step 2가 지운다.
4. 5초 안에 끝나지 않은 스레드는 모듈 수준 리스트에 참조를 남겨 프로세스가 죽지 않게 한다. 그 테스트는 `pytest.fail` 로 실패시킨다(`test_socket_workers.py` 의 `_STUCK` 과 같은 이유).

시그널은 리스트로 모은다(`statuses`, `received`). 접속을 기다릴 때는 `qtbot.waitUntil(lambda: ctrl.is_connected, timeout=…)` 를 쓴다. Windows에서 닫힌 포트로의 접속 거부는 약 2초 걸리므로, 그 테스트는 `timeout=10000` 이다.

아래 테스트는 **지금 통과해야 하고**, step 2 뒤에도 그대로 통과해야 한다. 이름은 예시다. 성질은 바꾸지 마라.

| 테스트 | 단언 |
|---|---|
| 접속 성공 | `statuses == [(True, "Connected")]`, `ctrl.is_connected`, `server.accepted == 1` |
| 닫힌 포트(127.0.0.1:1) | `statuses == [(False, "ConnectionRefused")]`, `not ctrl.is_connected` |
| 붙은 채 다시 connect | 마지막 상태가 `(True, f"Already connected: 127.0.0.1:{port}")`, `server.accepted == 1` |
| 보내기 | `send("abc")`, `send("가나")` → 서버의 `frames()` 가 `[b"abc", "가나".encode()]`. 원시 바이트도 `b"\x00\x00\x00\x03abc"` 로 시작한다 |
| 받기 | `send_frame("hello")`, 한글 프레임, 한 번의 쓰기에 프레임 둘, 한 프레임을 두 번에 나눠 쓰기(사이에 짧은 시간). `received` 가 순서대로 정확히 그 문자열들이다 |
| 끊기 | `disconnect()` → `qtbot.waitUntil` 로 `(False, "Disconnected")`, `not ctrl.is_connected`, `received == []`(내가 끊으면 Socket 탭으로 아무것도 보내지 않는다), 서버가 `peer_closed()` |
| 붙기 전 끊기 | `statuses == [(False, "No active connection")]` |
| 붙지 않고 보내기 | `statuses[-1] == (False, "Not connected (send ignored)")`, 서버가 받은 것 없음 |
| 붙은 뒤 shutdown | 상태 신호 없음(`statuses == [(True, "Connected")]` 그대로), 서버가 `peer_closed()`. 두 번 불러도 예외 없음 |
| 붙기 전 shutdown | 예외 없음, 상태 신호 없음 |
| 끊은 뒤 다시 접속 | 두 번째 `(True, "Connected")`, `server.accepted == 2`, 새 연결로 보내고 받는다 |

한 테스트라도 지금 통과하지 않으면 그 단언이 지금 동작과 다른 것이다. 단언을 지금 동작에 맞추고, 그 차이를 summary에 적는다. `src/` 는 고치지 않는다.

### 3. 버그 재현 (strict xfail)

`pytest.mark.xfail(strict=True, reason="K<번호>: …")` 로 표시한다. `uv run pytest tests/gui/test_virtuoso_connection.py -q --runxfail` 에서 **지금 실패해야 한다**. 각 실패 단언을 summary에 적는다.

- **K14 상대가 닫음**: 붙은 뒤 `server.close_peer()`
  - 기대: `received` 에 지금과 같은 "ERROR: recv failed - Server connection closed" 이 한 번 오고(문구는 바꾸지 않는다, 사용자 확인 2026-10-17), 마지막 상태가 `(False, "Disconnected")`, `not ctrl.is_connected`
  - 지금: 그 문구는 오지만 상태가 그대로다
- **K14 UTF-8이 아닌 프레임**: `send_frame(b"\xff\xfe")`
  - 기대: `received` 에 `"ERROR: recv failed - "` 로 시작하는 것이 하나 오고, 마지막 상태가 `(False, "Disconnected")`, 서버가 `peer_closed()`
  - 지금: 메시지는 오지만 상태가 그대로다
- **K14 0바이트 프레임**: `send_raw(b"\x00\x00\x00\x00")` 다음에 `send_frame("hello")`
  - 기대: `qtbot.waitUntil` 로 `received == ["hello"]` 이고 여전히 `ctrl.is_connected`
  - 지금: `"DISCONNECTED"` 가 오고 수신이 멈춘다
- **K24 반쯤 받은 프레임**
  - 서버가 한 번의 `send_raw` 로 완전한 프레임 하나(`"first"`)와, N=100바이트라고 적은 머리 + 10바이트를 보낸다.
  - 곧바로 `close_peer_after(3.0)` 을 건다. 3초 뒤 연결이 닫히므로 지금 코드도 영원히 멈추지 않는다.
  - `qtbot.waitUntil(lambda: received == ["first"])` 다음에 `time.sleep(0.2)` 를 둔다. 이벤트를 돌리지 않고 수신 워커가 프레임 중간의 `recv` 에서 막히게 하려는 것이다. 단언용 고정 대기가 아니다.
  - `t = time.monotonic(); ctrl.disconnect(); elapsed = time.monotonic() - t`
  - 기대: `elapsed < 1.0`, 그 뒤 `qtbot.waitUntil` 로 `(False, "Disconnected")`
  - 지금: `_stop_io_workers` 의 `wait()` 가 약 3초 막힌다
- **K39 접속 중 창 닫기** (서브프로세스)
  - 자식: `socket.socket.connect` 를 2초 잔 뒤 원래 것을 부르게 바꾼다. `QCoreApplication` 을 만들고 `ctrl.connect("127.0.0.1", 1)`, 곧바로 `ctrl.shutdown()`, `del ctrl`, `gc.collect()`, 이벤트를 0.5초 돌린 뒤 `print("OK")`, `sys.exit(0)`
  - 기대: `rc == 0` 이고 stdout에 `OK`
  - 지금: qFatal로 죽는다(`rc != 0`)
- **K40 결과가 오기 전 두 번째 Connect** (서브프로세스)
  - 자식이 자기 안에서 listen 소켓을 열고, accept 스레드가 받은 연결 수를 센다.
  - `ctrl.connect(...)`, 이벤트를 돌리지 않고 `time.sleep(0.5)`, `ctrl.connect(...)` 다시, 이벤트를 최대 3초 돌린다.
  - 기대: 받은 연결이 정확히 1개이고 `ctrl.is_connected`. 상태 목록은 고정하지 않는다. 새 구현에서는 첫 접속이 동기로 끝나 `"Already connected: …"` 가 붙을 수 있다.
  - 그 뒤 `ctrl.shutdown()`, `print("OK")`, `rc == 0`
  - 지금: 앞 결과가 늦게 도착해 `_start_io_workers` 가 두 번 돌고, 실행 중인 SendWorker를 덮어써 죽는다

서브프로세스 규칙
- `subprocess.run([sys.executable, …], timeout=30, capture_output=True, text=True, encoding="utf-8")` 로 돌린다.
- 환경: `QT_QPA_PLATFORM=offscreen` 을 둔다. 자식이 `gui_support` 를 import하면 `PYTHONPATH` 에 `tests` 를 더한다.
- Windows 자식은 맨 처음에 `ctypes.windll.kernel32.SetErrorMode(0x8003)` 를 부른다. 크래시 대화상자가 떠서 30초를 다 쓰지 않게 하려는 것이다.
- 자식 코드는 테스트 모듈의 문자열 상수나 `tests/gui_support/` 의 작은 모듈에 둔다. 실패 메시지에는 `rc` 와 stderr 끝 몇 줄을 넣는다.

### 4. 기존 테스트

- `tests/gui/test_socket_workers.py` 는 이 step에서 바꾸지 않는다. step 2가 정리한다.
- K39·K40 재현이 phase 4 step 6의 테스트(`test_connect_while_connecting_is_ignored` 등)와 겹쳐도 둘 다 둔다.

## Acceptance Criteria

```bash
uv run pytest tests/gui/test_virtuoso_connection.py -q                 # 고정 테스트 통과, 버그 재현은 xfailed
uv run pytest tests/gui/test_virtuoso_connection.py -q --runxfail      # 버그 재현 6개가 실패해야 한다 (프로세스가 죽으면 안 된다)
uv run ruff check src tests
for i in 1 2 3; do uv run pytest tests/gui -q || break; done           # 로컬 서버·스레드 테스트가 흔들리지 않는지 세 번
uv run pytest -q                                                       # 전체 (DSN 이 있으면 -rs)
git diff --stat -- src                                                 # 비어 있어야 한다
```

## 검증 절차

1. 위 AC 커맨드를 실행한다.
2. 아키텍처 체크리스트를 확인한다.
   - `src/` 가 바뀌지 않았는가?
   - 새 테스트 본문이 private 속성(`_` 로 시작)을 쓰지 않는가? 정리 fixture의 `getattr(…, "_connectWorker", None)` 만 예외다.
   - 실제 Virtuoso나 바깥 호스트에 붙지 않는가? 127.0.0.1의 테스트 서버와 닫힌 포트 1만 쓰는가?
   - 서브프로세스에 timeout이 있는가? 로컬 서버의 모든 소켓 연산에 타임아웃이 있는가?
3. 결과에 따라 `phases/13-virtuoso-socket/index.json` 의 step 0을 업데이트한다.
   - 성공 → `"status": "completed"`, `"summary": "tests/gui_support/virtuoso_server.py(LocalVirtuoso) + tests/gui/test_virtuoso_connection.py: 지금 동작 고정 <N>개(공개 API만), strict xfail 6개(K14 상대 닫음·비 UTF-8·0바이트, K24, K39·K40 서브프로세스). --runxfail 실패 단언: <테스트별 한 줄>. 지금 동작과 달라 고친 단언: <없음|목록>. src 불변. DB 테스트: <N passed | 안 돎(DSN 없음)>"`
   - 버그가 재현되지 않음(--runxfail 에서도 통과) → 그 테스트는 xfail 없이 특성 테스트로 남긴다. `"status": "completed"` 로 두고 summary에 `"not reproduced: K<n> <이유>"` 를 적는다.
   - 수정 3회 시도 후에도 실패 → `"status": "error"`, `"error_message": "구체적 에러 내용"`
   - 사용자 개입 필요 → `"status": "blocked"`, `"blocked_reason": "구체적 사유"` 후 즉시 중단

## 금지사항

- `src/` 를 바꾸지 마라. 이유: 이 step은 그물만 친다. 고치는 것은 step 2다.
- 새 테스트 본문에서 `_connectWorker`·`_client`·`client`·`client_factory`·`_receiveWorker` 같은 내부나 `FakeVirtuosoClient` 를 쓰지 마라. 이유: step 2가 지운다. 그러면 테스트가 성질 대신 구현을 지키게 된다.
- K39·K40처럼 실행 중인 QThread를 놓치는 재현을 pytest 프로세스 안에서 돌리지 마라. 이유: qFatal은 예외가 아니라 프로세스 종료라서 전체 테스트가 죽는다.
- K24 재현에서 서버가 연결을 영원히 붙잡게 두지 마라(`close_peer_after` 필수). 이유: 지금 코드의 `wait()` 에 타임아웃이 없어 테스트가 멈춘다.
- 실제 Virtuoso 주소나 127.0.0.1 밖의 주소에 붙지 마라. 이유: 외부 의존(CLAUDE.md).
- 기존 테스트를 깨뜨리지 마라.
