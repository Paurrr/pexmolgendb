# Step 2: qtcpsocket-controller

## 배경 (phase 13 공통)

이 저장소는 이미 여러 명이 쓰는 도구다. 평소에는 **에러·버그만 고친다**(CLAUDE.md, ADR-015). phase 13은 예외로, **사용자가 2026-10-17 승인한 구조 변경**이다.

> 사용자 승인 2026-10-17: `net/` 을 QTcpSocket 으로 전환한다(제안 P6). 워커 스레드 기반 소켓을 GUI 스레드의 이벤트 기반 소켓 하나로 바꾼다.

이 구조 변경으로 없애려는 버그는 넷이다(`docs/notes/known-issues.md`).
- K14: Virtuoso 쪽이 연결을 끊거나 수신 오류가 나도 상태가 계속 Connected다. 0바이트 프레임을 끊김으로 잘못 본다.
- K24: 프레임 중간에서 상대가 멈추면 끊기·창 닫기가 굳는다.
- K39: 접속하는 동안 창을 닫으면 프로세스가 죽는다.
- K40: Connect를 아주 빠르게 두 번 누르면 프로세스가 죽는다.

phase는 step 셋으로 진행한다.
- step 0: 지금 동작을 공개 API 테스트로 고정하고, 버그 넷을 strict xfail로 재현했다.
- step 1: 바깥 코드가 `ConnectionController.client` 대신 공개 API를 쓰게 했다.
- step 2(이 step): `net/controller.py` 를 QTcpSocket 하나로 다시 쓰고, step 0의 xfail을 뗀다.

모든 step에 같은 규칙이 적용된다.
1. 버그는 **Windows 개발 PC에서** 실패하는 테스트로 먼저 보인다. 이 phase의 RED는 step 0의 strict xfail이다.
2. 버그가 아닌 구조 변경은 RED 대신 **변이 검사**를 한다. 코드를 손으로 망가뜨려 테스트가 실패하는 것을 보고, 손으로 되돌린다. `git checkout`/`git stash` 로 되돌리지 마라. 이유: 같은 step의 다른 변경까지 사라진다.
3. 프레임 형식은 바꾸지 않는다. 4바이트 big-endian 길이 다음에 UTF-8 본문이 온다. Virtuoso SKILL 쪽 코드가 이 형식을 쓴다.
4. 테스트는 실제 Virtuoso에 붙지 않는다. 127.0.0.1의 테스트 서버(`tests/gui_support/virtuoso_server.py`)에는 붙어도 된다.
5. 테스트는 **공개 API만** 쓴다. 메서드는 `connect`, `disconnect`, `send`, `shutdown` 이다. 속성은 `is_connected`(property)다. 시그널은 `received`, `statusChanged` 다.
6. pytest 프로세스 안에서 실행 중인 QThread를 놓치면 프로세스가 통째로 죽는다. 이 step 뒤로 `net/` 에는 QThread가 없다.
7. 이 파일의 행 번호는 2026-10-17 기준 대략값이다. 이름으로 찾아라.
8. PostgreSQL SQL은 바꾸지 않는다. `GENDB_TEST_PG_DSN` 이 있으면 `-rs` 로 전체를 돌리고 summary에 `DB 테스트: <N passed | 안 돎(DSN 없음)>` 을 적는다. DSN이 없어도 `blocked` 가 아니다.

GUI 테스트 관례는 CLAUDE.md "테스트 관례" 와 `tests/gui/conftest.py` 를 따른다. `waitUntil` 콜백은 bool을 돌려주고, 고정 대기로 "아무 일 없음" 을 단언하지 않는다.

## 이 step의 목적

`ConnectionController` 를 GUI 스레드의 `QTcpSocket` 하나로 다시 쓴다. 이벤트 기반으로 `connected`, `readyRead`, `disconnected`, `errorOccurred` 를 받는다. `net/workers.py` 와 `net/client.py` 는 지운다. 워커 스레드가 없어지므로 K24·K39·K40은 구조적으로 사라진다. K14는 아래 표대로 상태를 바꾼다.

공개 표면은 그대로 둔다. step 0·1의 테스트와 `controllers/main_window.py` 가 쓰는 것이다.

```python
class ConnectionController(QObject):
    received = Signal(str)
    statusChanged = Signal(bool, str)

    def __init__(self, parent: QObject | None = None): ...   # client_factory 인자는 없앤다
    @property
    def is_connected(self) -> bool: ...
    def connect(self, host: str, port: int) -> None: ...
    def disconnect(self) -> None: ...
    def send(self, msg: str) -> None: ...
    def shutdown(self) -> None: ...                           # 멱등, 상태 신호 없음
```

`client` property는 없앤다. step 1 뒤로 `src/` 에서 쓰는 곳이 없다.

## 읽어야 할 파일

- `/CLAUDE.md`(테스트 관례의 `FakeVirtuosoClient` 줄), `/docs/ARCHITECTURE.md`(디렉토리 구조의 `net/` 줄, 레이어 표 "`net/` 은 자기 안에서 닫혀 있다", 스레딩의 `net/` 줄), `/docs/UI_GUIDE.md`(툴바 상태)
- `src/genviewer/net/controller.py`, `src/genviewer/net/workers.py`, `src/genviewer/net/client.py` 전체. 지금 상태 문구와 경로는 다음과 같다.
  - 접속 결과: `"Connected"`, `"InvalidAddress"`, `"ConnectionRefused"`, `"ConnectionTimedOut"`, `"Error: <e>"`
  - 그 밖: `"Disconnected"`, `"Already connected: {host}:{port}"`, `"No active connection"`, `"Not connected (send ignored)"`
  - Socket 탭으로 가는 메시지: `"DISCONNECTED"`, `"ERROR: recv failed - …"`, `"ERROR: send failed - …"`
- `src/genviewer/controllers/main_window.py` — `_on_received_from_controller`(DeviceList/LibraryList 말고는 Socket 탭 수신 칸), `_on_status_changed`, `_on_click_connect_toggle`, `shutdown`
- `src/genviewer/service/virtuoso_protocol.py` — `parse`(`"DISCONNECTED"`·`"ERROR: …"` 는 `"Text"` 로 Socket 탭에 간다)
- step 0·1이 만든 `tests/gui_support/virtuoso_server.py`, `tests/gui/test_virtuoso_connection.py`(xfail 6개와 그 reason)
- `tests/gui/test_socket_workers.py` 전체
  - (a)~(c)는 워커·`FakeVirtuosoClient`·private에 기댄다.
  - (d) 마지막 예외 그물은 `main.py` 것이다. `net/` 과 상관없으니 그대로 둔다.
- `tests/gui_support/fakes.py` 의 `FakeVirtuosoClient`, `tests/gui/test_window_guards.py` 의 DeviceList 테스트(`connection_controller.received.emit(...)` 만 쓴다. 그대로 통과해야 한다)
- phase 6 의 `tests/test_boundaries.py`. `net/` 이 우리 다른 패키지를 import하지 않는지 검사한다.

## 작업

### 1. 상태 × 사건 (전부 테스트한다)

| 상태 | 호출/사건 | 결과 |
|---|---|---|
| 끊김 | `connect(h, p)` | `connectToHost`. 상태 신호 없음(접속 중) |
| 접속 중 | `connect` 또 | 아무것도 하지 않는다. 신호 없음, 소켓 하나(K40) |
| 접속 중 | 접속됨 | `(True, "Connected")` |
| 접속 중 | 접속 실패 | 소켓 오류에 따라 상태 신호를 낸다(아래 매핑). 소켓을 정리한다. 다시 `connect` 할 수 있다 |
| 접속 중 | `disconnect` | `abort()`, `(False, "Disconnected")`. 그 뒤 접속 결과 신호는 오지 않는다 |
| 접속 중 | `shutdown` | `abort()`, 신호 없음. 남는 스레드 없음(K39) |
| 붙음 | `connect` | `(True, f"Already connected: {host}:{port}")` |
| 붙음 | `send(msg)` | 프레임 하나를 쓴다. `write` 가 -1이면 `received("ERROR: send failed - <errorString>")`, 소켓을 닫고 `(False, "Disconnected")` |
| 붙음 | 데이터 도착 | 버퍼에 쌓는다. 완성된 프레임마다 `received(text)`. 한 번에 여러 프레임이 오거나 한 프레임이 나뉘어 와도 된다 |
| 붙음 | 0바이트 프레임 | 무시한다. 끊김이 아니다(K14) |
| 붙음 | UTF-8이 아닌 프레임 | `received("ERROR: recv failed - <e>")`, `abort()`, `(False, "Disconnected")`(K14) |
| 붙음 | 상대가 닫음 | `received("ERROR: recv failed - Server connection closed")`(지금 문구 그대로), `(False, "Disconnected")`(K14). 반쯤 받은 프레임은 버린다 |
| 붙음 | 그 밖 소켓 오류 | `received("ERROR: recv failed - <errorString>")`, `(False, "Disconnected")` |
| 붙음 | `disconnect` | 닫는다. `(False, "Disconnected")`. `received` 는 내지 않는다(내가 끊었다). 반쯤 받은 프레임이 있어도 바로 돌아온다(K24) |
| 붙음 | `shutdown` | `abort()`, 신호 없음. 여러 번 불러도 된다 |
| 끊김 | `disconnect` | `(False, "No active connection")` |
| 끊김·접속 중 | `send` | `(False, "Not connected (send ignored)")`. 아무것도 쓰지 않는다(지금과 같다) |
| 끊김 | `shutdown` | 아무것도 하지 않는다 |

- 한 사건에 상태 신호와 `received` 는 **한 번씩만** 낸다. 상대가 닫으면 Qt는 `errorOccurred(RemoteHostClosedError)` 와 `disconnected` 를 둘 다 낼 수 있다. 내가 부른 `disconnect`/`abort` 도 `disconnected` 를 낸다. 그래서 상태는 플래그(내가 끊음, 정리 중)로 가린다.
- 접속 실패 문구는 지금 `Client.connect` 매핑을 따른다.
  - `HostNotFoundError` → `"InvalidAddress"`
  - `ConnectionRefusedError` → `"ConnectionRefused"`
  - `SocketTimeoutError` → `"ConnectionTimedOut"`
  - 그 밖 → `f"Error: {errorString()}"`
- 명시적 접속 타임아웃은 두지 않는다. 지금도 OS 기본값이다.
- 보내기 인코딩은 `str.encode()`(UTF-8), 받기 디코딩은 엄격한 UTF-8이다(지금과 같다).
- 소켓은 컨트롤러를 부모로 둔다. 새로 붙을 때 앞 소켓은 `deleteLater` 한다. `waitFor*` 메서드를 쓰지 않는다. 이유: GUI 스레드를 막는다. K24와 같은 종류다.
- 소켓 오류는 `logging.getLogger(__name__)` 로 파일 로그에 남긴다(지금 워커의 `log.warning` 과 같은 수준). `net/` 은 우리 다른 패키지를 import하지 않는다.
- 0바이트 프레임을 무시하는 것은 이 phase의 결정이다. 0바이트 프레임은 메시지가 아니다(지금은 `"DISCONNECTED"` 로 잘못 읽는다).
- 상대가 닫았을 때 Socket 탭 문구는 지금 문구 "ERROR: recv failed - Server connection closed" 를 그대로 쓴다(**사용자 확인 2026-10-17**). `"DISCONNECTED"` 로 바꾸지 마라. 바뀌는 것은 툴바 상태가 Disconnected로 바뀌는 것뿐이다(K14).

### 2. 테스트

- `tests/gui/test_virtuoso_connection.py`
  - step 0 버그 재현 6개의 `xfail` 을 뗀다. 모두 통과해야 한다.
  - 정리 fixture의 step 0 한정 줄(`getattr(ctrl, "_connectWorker", None)` 등)을 지운다.
  - 위 표에서 step 0·1 테스트가 덮지 않는 칸을 더한다: 접속 중 `disconnect`, 붙은 뒤 상대가 닫은 다음 `send` 는 `"Not connected (send ignored)"`, 상태 신호가 한 번만 오는지.
  - `send` 의 `write == -1` 칸은 공개 API로 만들기 어렵다. 만들 수 없으면 summary에 적고 넘어간다. private을 쓰는 테스트를 만들지 마라.
- `tests/gui/test_socket_workers.py`
  - (a)~(c)는 워커·`FakeVirtuosoClient`·`_connectWorker`·`client` 에 기대므로 지운다.
  - 지우기 전에 각 테스트의 성질이 `test_virtuoso_connection.py` 에 공개 API로 있는지 대조하고, 대응표를 summary에 적는다(하네스 규칙 14).
    - "접속 중 connect 무시" → K40 테스트
    - "실패 뒤 다시 connect" → 닫힌 포트 다음 접속
    - "보내기 실패가 received 로" → `write == -1` 칸 또는 "상대가 닫은 뒤 보내기"
    - "보내기 실패가 Socket 탭에" → 아래 main_window 테스트
    - "shutdown 이 정리" → shutdown 테스트들
    - "창 닫기가 소켓 정리" → `main_window` 로 붙은 뒤 `main_window.shutdown()` 하면 서버가 `peer_closed()`
  - (d)와 그 헬퍼(`app_excepthooks`, `record_unexpected`, `unhandled_logged`, `RaisingThread`)는 그대로 둔다. 모듈 docstring은 남은 내용에 맞게 고친다.
- `main_window` 수준 테스트를 하나 더한다. 붙은 뒤 서버가 연결을 닫으면 Socket 탭 수신 칸(`main_window.socket_tab.ui.recv_msg_te`)이 "ERROR: recv failed - Server connection closed" 이고, 툴바 상태(`main_window.ui.status_label.text()`)가 `"Disconnected"`, Connect 버튼 글자가 `"Connect"` 다.
- `tests/gui_support/fakes.py` 의 `FakeVirtuosoClient` 는 쓰는 곳이 없어지면 지운다.

### 3. 수정

- `src/genviewer/net/controller.py` 를 위 표대로 다시 쓴다.
- `git rm src/genviewer/net/workers.py src/genviewer/net/client.py`
- `controllers/main_window.py` 는 바꿀 것이 없어야 한다(step 1이 끝냈다). 바꿔야 하면 이유를 summary에 적는다.

### 4. 변이 검사

각각 손으로 바꿔 해당 테스트가 실패하는 것을 보고 손으로 되돌린다. 실패 단언을 summary에 적는다.
- 상대가 닫을 때 상태 신호를 내지 않게 한다 → K14 상대 닫음 테스트
- 0바이트 프레임을 끊김으로 처리한다 → K14 0바이트 테스트
- `connect` 의 "접속 중이면 무시" 가드를 뺀다 → K40 테스트(서버가 받은 연결 2)
- 프레임 버퍼를 지우고 `readAll()` 을 바로 디코드한다 → "한 프레임을 두 번에 나눠 쓰기" 또는 "한 번에 프레임 둘" 테스트
- `disconnect` 에서 "내가 끊음" 플래그를 빼서 상대가 닫은 것처럼 처리하게 한다 → 끊기 테스트의 `received == []`

### 5. 문서

- `CLAUDE.md` 테스트 관례의 "Virtuoso 소켓은 `tests/gui_support/fakes.py` 의 `FakeVirtuosoClient` 로 대신한다" 를 고친다. 새 문장: Virtuoso 소켓 테스트는 `tests/gui_support/virtuoso_server.py` 의 127.0.0.1 로컬 서버에 공개 API로 붙는다. 실제 Virtuoso에는 붙지 않는다. 실행 중인 스레드를 놓칠 수 있는 재현은 서브프로세스에서 돌린다. "접속 실패 경로는 닫힌 포트(`127.0.0.1:1`)" 는 그대로 둔다.
- `docs/ARCHITECTURE.md`
  - 디렉토리 구조의 `net/` 줄: `controller(ConnectionController: GUI 스레드의 QTcpSocket 하나, 4바이트 길이 + UTF-8 프레임)`
  - 스레딩 절의 `net/` 줄: 워커 스레드 없음. 접속 중의 Connect는 무시. 상대가 끊거나 수신 오류가 나면 Socket 탭에 알리고 상태를 Disconnected로. 창을 닫으면 `shutdown()` 이 소켓을 abort한다. K39 언급은 지운다.
  - 레이어 표의 "`net/` 은 자기 안에서 닫혀 있다" 는 그대로 둔다.
- `README.md`: Virtuoso 소켓을 설명하는 곳(메인 툴바 `Server`/`Port`/`Connect` 안내 근처)에 한 줄을 더한다. "Virtuoso 쪽이 연결을 끊으면 상태 표시가 Disconnected로 바뀐다(Socket 탭에는 지금처럼 `ERROR: recv failed - Server connection closed` 가 보인다)."
- `docs/notes/known-issues.md` 의 K14·K24·K39·K40은 이 step에서 지우지 않는다. phase 마무리에서 지운다. summary에 "마무리 때 K14·K24·K39·K40 삭제" 라고 적는다.

## Acceptance Criteria

```bash
uv run pytest tests/gui/test_virtuoso_connection.py -q            # xfail 없이 전부 통과 (XPASS strict 실패가 없어야 한다)
uv run pytest tests/gui/test_socket_workers.py -q                  # 남은 (d) 통과
uv run ruff check src tests
uv run pytest tests/test_boundaries.py -q                          # net/ 이 자기 안에서 닫혀 있다 (phase 6)
test ! -e src/genviewer/net/workers.py && test ! -e src/genviewer/net/client.py
grep -rn "QThread\|threading\|waitFor" src/genviewer/net         # 비어 있어야 한다
grep -rn "FakeVirtuosoClient\|client_factory\|_connectWorker" src tests   # 비어 있어야 한다
for i in 1 2 3; do uv run pytest tests/gui -q || break; done      # 소켓 테스트가 흔들리지 않는지 세 번
uv run pytest -q                                                  # 전체 (DSN 이 있으면 -rs)
```

## 검증 절차

1. 위 AC 커맨드를 실행한다.
2. 아키텍처 체크리스트를 확인한다.
   - `net/` 이 PySide6와 stdlib만 import하는가(레이어 표, phase 6 가드)?
   - GUI 스레드를 막는 호출(`waitFor*`, `QThread.wait`, 블로킹 `socket`)이 `net/` 에 없는가?
   - 공개 표면(`connect`/`disconnect`/`send`/`shutdown`/`is_connected`/`received`/`statusChanged`)과 상태 문구가 위 표와 같은가?
   - 테스트가 private을 쓰지 않는가? 실제 Virtuoso에 붙지 않는가?
3. **실제 Virtuoso 확인은 이 세션이 하지 않는다.** phase 마무리 때 사용자가 실제 Virtuoso에 붙여 Connect, Load Virtuoso(DeviceList), Run Selected, 끊기, 창 닫기를 손으로 확인한 뒤 main에 합친다. summary에 "실제 Virtuoso 수동 확인 필요(미확인)" 라고 적는다. 확인했다고 쓰지 마라.
4. 결과에 따라 `phases/13-virtuoso-socket/index.json` 의 step 2를 업데이트한다.
   - 성공 → `"status": "completed"`, `"summary": "net/controller.py 를 QTcpSocket 하나로 재작성(GUI 스레드, 스레드 없음), workers.py·client.py git rm, client property·client_factory 제거. step 0 xfail 6개 해제(K14 3·K24·K39·K40 통과). test_socket_workers.py (a)~(c) 삭제, 성질 대응: <표>. FakeVirtuosoClient 제거. 추가 테스트: <이름>. write==-1 칸: <테스트|못 만듦: 이유>. 변이: <5개 결과>. CLAUDE.md·ARCHITECTURE·README 갱신. 마무리 때 known-issues K14·K24·K39·K40 삭제. 실제 Virtuoso 수동 확인 필요(미확인). DB 테스트: <N passed | 안 돎(DSN 없음)>"`
   - 수정 3회 시도 후에도 실패 → `"status": "error"`, `"error_message": "구체적 에러 내용"`
   - 사용자 개입 필요 → `"status": "blocked"`, `"blocked_reason": "구체적 사유"` 후 즉시 중단

## 금지사항

- 프레임 형식(4바이트 big-endian 길이 + UTF-8), 상태 문구, Socket 탭으로 가는 `"ERROR: … failed - …"` 접두사를 바꾸지 마라. 이유: Virtuoso SKILL 쪽 코드와 사용자가 보는 문구다. 표에 적은 결정만 바뀐다.
- `waitForConnected`/`waitForReadyRead`/`waitForBytesWritten`/`waitForDisconnected` 를 쓰지 마라. 이유: GUI 스레드를 막는다(K24와 같은 종류).
- 새 QThread나 Python `threading` 을 `net/` 에 두지 마라. 이유: 스레드를 없애는 것이 이 phase의 목적이다(K39·K40).
- 명시적 접속 타임아웃이나 자동 재접속을 넣지 마라. 이유: 지금 동작이 아니고 승인 범위 밖이다.
- 끊길 때 "Device List"/"Filtered List" 를 숨기거나 버튼·상태 표시 말고 다른 UI를 바꾸지 마라. 이유: 승인 범위 밖이다.
- 테스트에서 private 속성이나 Qt 소켓 객체를 직접 건드리지 마라. 이유: 다음 구조 변경(P2·P4) 때 다시 그물이 되어야 한다.
- `test_socket_workers.py` 의 (d) 마지막 예외 그물 테스트를 바꾸지 마라. 이유: `main.py` 의 범위다.
- 기존 테스트를 깨뜨리지 마라. 지우는 (a)~(c)는 성질 대응표를 남긴 경우만 지운다.
