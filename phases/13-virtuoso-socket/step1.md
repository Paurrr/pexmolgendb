# Step 1: socket-consumers

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
- step 1(이 step): `ConnectionController.client` 를 쓰는 바깥 코드를 공개 API로 옮긴다(계약 먼저).
- step 2: `net/controller.py` 를 QTcpSocket 하나로 다시 쓴다.

모든 step에 같은 규칙이 적용된다.
1. 버그는 **Windows 개발 PC에서** 실패하는 테스트로 먼저 보인다. `posix_only` 로는 증명이 안 된다.
2. 버그가 아닌 구조 변경은 RED 대신 **변이 검사**를 한다. 코드를 손으로 망가뜨려 테스트가 실패하는 것을 보고, 손으로 되돌린다. `git checkout`/`git stash` 로 되돌리지 마라. 이유: 같은 step의 다른 변경까지 사라진다.
3. 프레임 형식(4바이트 big-endian 길이 + UTF-8 본문)은 바꾸지 않는다.
4. 테스트는 실제 Virtuoso에 붙지 않는다. step 0이 만든 127.0.0.1 로컬 서버(`tests/gui_support/virtuoso_server.py`)에는 붙어도 된다.
5. 새 테스트는 `ConnectionController` 의 **공개 API만** 쓴다. 메서드는 `connect`, `disconnect`, `send`, `shutdown` 이다. 속성은 `is_connected`(property)다. 시그널은 `received`, `statusChanged` 다.
6. pytest 프로세스 안에서 실행 중인 QThread를 놓치면 프로세스가 통째로 죽는다. step 0의 정리 fixture를 그대로 쓴다.
7. 이 파일의 행 번호는 2026-10-17 기준 대략값이다. 이름으로 찾아라.
8. PostgreSQL SQL은 바꾸지 않는다. `GENDB_TEST_PG_DSN` 이 있으면 `-rs` 로 전체를 돌리고 summary에 `DB 테스트: <N passed | 안 돎(DSN 없음)>` 을 적는다. DSN이 없어도 `blocked` 가 아니다.

GUI 테스트 관례는 CLAUDE.md "테스트 관례" 와 `tests/gui/conftest.py` 를 따른다. `main_window` fixture를 쓰고, `waitUntil` 콜백은 bool을 돌려주며, 고정 대기로 "아무 일 없음" 을 단언하지 않는다.

## 이 step의 목적

step 2가 `ConnectionController.client` property와 `Client` 클래스를 지운다. 그 전에 바깥 코드가 그것에 기대지 않게 한다. **사용자가 보는 동작은 바뀌지 않는다.**

지금 `.client` 를 쓰는 곳은 하나다.

```python
# controllers/main_window.py, _on_status_changed (~189-195)
self.device_tab.set_client(
    self.connection_controller.client if connected else None
)
```

`DeviceTabController` 는 받은 객체를 `self.client` 에 두고, `show_views` 에서 참·거짓만 본다.

```python
# controllers/device_tab.py
def set_client(self, client):   # ~106-107
    self.client = client

def show_views(self):           # ~288-290
    if self.connected and self.client:
        self.ui.show_views()
```

Load Virtuoso 버튼 → `DeviceTabToolBarController.show_views` → `showViewRequested` → `DeviceTabController.show_views` 순서로 간다. **DB에 붙어 있고(`self.connected`) Virtuoso에도 붙어 있을 때만** "Device List"/"Filtered List" 를 보인다(UI_GUIDE 레이아웃: Virtuoso 목록을 받은 뒤에만 보인다). `connected` 가 True인 상태 신호에서는 `client` 가 늘 있으므로, Virtuoso 접속 여부는 bool 하나로 충분하다.

## 읽어야 할 파일

- `/CLAUDE.md`, `/docs/ARCHITECTURE.md`(레이어 표: `net/` 은 자기 안에서 닫혀 있다, "현재 어긋난 곳": 남의 private 부르기를 따라 하지 않는다), `/docs/UI_GUIDE.md`(레이아웃)
- `src/genviewer/controllers/main_window.py` — `__init__`(`ConnectionController()`, 시그널 연결), `_on_status_changed`, `_on_click_connect_toggle`(`is_connected` property 사용), `shutdown`
- `src/genviewer/controllers/device_tab.py` — `__init__` 의 `self.client = None`, `set_client`, `show_views`, `showViewRequested` 연결(`__init__`)
- `src/genviewer/controllers/device_tab_toolbar.py` — `show_views`, `showViewRequested`
- `src/genviewer/views/device_tab.py` — `show_views`/`hide_views`(`search_labeled_virtuoso_device`, `search_labeled_filter`)
- `src/genviewer/net/controller.py` — `is_connected`, `client` property, `_emit_status`(`_connected` 를 먼저 바꾸고 신호를 낸다)
- step 0이 만든 `tests/gui_support/virtuoso_server.py`, `tests/gui/test_virtuoso_connection.py`
- `grep -rn "\.client\b\|set_client" src tests` 로 다른 사용처가 없는지 확인한다. 2026-10-17 기준으로는 위 두 곳과 `tests/gui/test_socket_workers.py` 뿐이다. 그 테스트 파일은 step 2가 정리한다.

## 작업

### 1. 테스트 먼저 (`tests/gui/test_virtuoso_connection.py` 에 더한다)

`main_window` fixture와 step 0의 로컬 서버를 쓴다. 지금 코드에서도 **통과해야 한다**(동작 고정).

- **Virtuoso에 붙기 전**: `main_window.device_tab.device_tab_toolbar.show_views()` 를 부른다. `ui = main_window.device_tab.ui` 일 때 `ui.search_labeled_virtuoso_device.isHidden()` 이 True다.
- **붙은 뒤**: `main_window.connection_controller.connect("127.0.0.1", server.port)` 를 부르고, `qtbot.waitUntil(lambda: main_window.connection_controller.is_connected)` 로 기다린다. 다시 `show_views()` 를 부르면 두 위젯이 숨겨져 있지 않다.
- **끊은 뒤**: `disconnect()` 하고 `(False, "Disconnected")` 상태 신호를 기다린다. `ui.hide_views()` 다음에 `show_views()` 를 부르면 다시 숨겨져 있다.
- 정리는 step 0의 순서를 따른다(서버 close → `shutdown`). `main_window` fixture 정리가 `shutdown()` 을 한 번 더 부르는 것은 괜찮다.

### 2. 수정

```python
# controllers/device_tab.py
class DeviceTabController(QObject):
    def set_virtuoso_connected(self, connected: bool) -> None: ...   # set_client 대신
    # show_views: self.connected and <Virtuoso 접속 여부>
```

- `set_client` 와 `self.client` 를 `set_virtuoso_connected(bool)` 와 bool 속성(예: `self.virtuoso_connected`, 초기값 False)으로 바꾼다.
- `MainWindowController._on_status_changed` 는 시그널의 `connected` 인자를 그대로 넘긴다. `connection_controller.client` 를 읽지 않는다.
- `ConnectionController` 는 이 step에서 바꾸지 않는다. `client` property도 남긴다. 그 property를 쓰는 테스트(`test_socket_workers.py`)는 step 2가 정리한다.
- `MainWindowController` 의 `self.is_connected = False` 속성(쓰이지 않음)은 건드리지 않는다. 범위 밖이다.

### 3. 변이 검사

각각 손으로 바꿔 1의 테스트가 실패하는 것을 보고 손으로 되돌린다. 실패 단언을 summary에 적는다.
- `_on_status_changed` 가 늘 `False` 를 넘기게 한다. "붙은 뒤" 단언이 실패해야 한다.
- `set_virtuoso_connected` 의 초기값을 True로 둔다. "붙기 전" 단언이 실패해야 한다.

### 4. 문서

- 없다. ARCHITECTURE의 `net/` 줄은 step 2가 고친다.

## Acceptance Criteria

```bash
uv run pytest tests/gui/test_virtuoso_connection.py -q     # 새 테스트 통과 (step 0 의 xfail 은 그대로 xfailed)
uv run ruff check src tests
grep -rn "\.client\b\|set_client" src                     # net/ 안의 Client 정의·사용 밖에는 없어야 한다
uv run pytest tests/gui -q
uv run pytest -q                                           # 전체 (DSN 이 있으면 -rs)
```

## 검증 절차

1. 위 AC 커맨드를 실행한다.
2. 아키텍처 체크리스트를 확인한다.
   - 바깥 코드(`controllers/`)가 `ConnectionController` 의 공개 API(`is_connected`, 시그널 인자)만 쓰는가?
   - 남의 private 멤버를 새로 부르지 않았는가(ARCHITECTURE "현재 어긋난 곳")?
   - 사용자가 보는 동작(버튼, 상태 문구, 목록 표시 조건)이 그대로인가?
3. 결과에 따라 `phases/13-virtuoso-socket/index.json` 의 step 1을 업데이트한다.
   - 성공 → `"status": "completed"`, `"summary": "DeviceTabController.set_client/client → set_virtuoso_connected(bool)/<속성 이름>, MainWindowController._on_status_changed 가 connected 인자를 넘김. src 에서 ConnectionController.client 사용 0. 테스트: <이름들>(지금 코드에서도 통과). 변이: 늘 False → <단언>, 초기값 True → <단언>. DB 테스트: <N passed | 안 돎(DSN 없음)>"`
   - 수정 3회 시도 후에도 실패 → `"status": "error"`, `"error_message": "구체적 에러 내용"`
   - 사용자 개입 필요 → `"status": "blocked"`, `"blocked_reason": "구체적 사유"` 후 즉시 중단

## 금지사항

- `net/` 을 바꾸지 마라. 이유: 계약을 쓰는 쪽을 먼저 옮기고, 구현은 step 2가 바꾼다(하네스 규칙 10의 계약 → 호출부 순서).
- `ConnectionController` 에 새 public 메서드를 더하지 마라. 이유: `is_connected` property와 `statusChanged(bool, str)` 로 충분하고, step 2가 지켜야 할 표면이 넓어진다.
- "Device List"/"Filtered List" 를 보이는 조건이나 끊길 때 숨기는 동작을 바꾸지 마라. 이유: 지금은 끊어도 숨기지 않는다. 바꾸면 동작 변경이고 승인 범위 밖이다.
- `tests/gui/test_socket_workers.py` 를 고치지 마라. 이유: step 2가 다시 쓴다.
- 기존 테스트를 깨뜨리지 마라.
