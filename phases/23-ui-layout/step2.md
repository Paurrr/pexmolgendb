# Step 2: db-status

## 배경

이 저장소는 **에러·버그만 고친다**(CLAUDE.md, ADR-015). 이 step은 사용자가 2026-10-22에 승인한 사용성 변경이다("DB 상태 상시 표시", AskUserQuestion).

**문제**
- 데이터베이스 접속 상태가 화면에 늘 보이지 않는다.
- 접속 결과는 상태 표시줄에 2초 뜨고 사라진다. 로그 패널 줄은 스크롤되거나 `Clear` 로 지워진다.
- 반면 Virtuoso 소켓은 툴바에 상태 라벨이 있다.
- 그래서 지금 어느 DB에 붙어 편집하는지 알 수 없다.

**승인된 동작**
- 상태 표시줄 오른쪽에 영구 라벨 하나를 둔다(`QStatusBar.addPermanentWidget`). 이름은 `db_status_label`, objectName은 `DbStatus` 다.
- 글자
  - 붙어 있으면 `DB: <service.diagnostics.target_summary(db.cfg.dsn)>` 다. 예: `DB: host=db.example port=5433 dbname=gendb user=alice`.
  - 안 붙어 있으면 `DB: not connected` 다.
- 색은 Virtuoso 상태 라벨(`QLabel#ConnectionStatus[connected=…]`)과 같은 규칙이다. 동적 속성 `connected` 가 `"true"`/`"false"` 이고, QSS는 good/bad를 쓴다.
  - `utils/palette.py` 의 그 두 규칙 선택자에 `QLabel#DbStatus[connected="true"]` 와 `[connected="false"]` 를 더한다.
  - 속성을 바꾼 뒤에는 `MainWindow._refresh_style` 처럼 다시 polish한다.
- 비밀번호는 절대 보이지 않는다. `target_summary` 는 host·port·dbname·user만 고르는 화이트리스트다(CLAUDE.md CRITICAL "비밀번호를 화면에 남기지 않는다").
  - DSN 문자열을 직접 자르거나 `scrub` 으로 만들지 마라.
  - `target_summary` 가 빈 DSN에 돌려주는 한국어 `"(libpq 기본값)"` 은 phase 24가 영어로 바꾼다. 여기서는 그대로 쓴다.

**상태 × 결과** (모두 테스트한다)

| 상황 | 라벨 |
|---|---|
| 창을 만든 직후(첫 접속 전) | `DB: not connected`, connected=false |
| 첫 접속 성공 | 접속 대상, connected=true |
| 첫 접속 실패 | `DB: not connected`, connected=false |
| 재접속 성공(Database → Connect...) | 새 대상 |
| 재접속 실패 | 옛 대상 그대로. 실패하면 옛 DB를 그대로 쓴다(`DeviceTabController.connect_db` 의 docstring) |
| `shutdown()` → `close_db()` | `DB: not connected` |

- 신호: `DeviceTabController.dbChanged(object)` 는 접속 성공 때 새 DB를, `close_db` 때 `None` 을 낸다. 접속 실패 때는 내지 않는다.
- `MainWindowController.__init__` 에서 그 신호를 라벨 갱신에 잇는다. 이으면서 지금 상태(`self.device_tab.db`)로 한 번 맞춘다.
- 첫 접속은 `DeviceTabController` 생성자가 `QTimer.singleShot(0)` 으로 예약한다. 그래서 `__init__` 안에서 이으면 놓치지 않는다. 그래도 지금 상태로 한 번 맞춘다.

규칙:
1. 승인된 변경이라 RED 대신 변이 검사를 한다. 라벨 갱신 연결을 손으로 끊으면 새 테스트가 실패해야 한다. `git checkout`/`git stash` 로 되돌리지 마라.
2. 행 번호는 2026-10-22 기준 대략값이다.
3. 문서(UI_GUIDE "레이아웃", README)는 phase 마무리에서 고친다.

## 읽어야 할 파일

- `/CLAUDE.md`(CRITICAL: 비밀번호, GUI 스레드에서 DB를 기다리지 않음), `/docs/UI_GUIDE.md`
- `src/genviewer/service/diagnostics.py`: `target_summary`(~117-134)
- `src/genviewer/controllers/device_tab.py`: `dbChanged`, `connect_db`(~192-227), `close_db`(~317-328), `connected`
- `src/genviewer/views/main_window.py`: `MainWindow.__init__`(상태 표시줄 ~132-133), `apply_connection_ui`, `_refresh_style`
- `src/genviewer/controllers/main_window.py`: `__init__`, `shutdown`
- `src/genviewer/utils/palette.py`: `QLabel#ConnectionStatus` 규칙
- `tests/gui/conftest.py`: `main_window` fixture(`MainWindowController(ui, "")`, 첫 접속을 기다린다)
- `tests/gui_support/fakes.py`: `FakeStore.open_database(dsn)`, `FakeDatabase.cfg`(`DbConfig(dsn=dsn or "fake")`), `store.fail_next`
- `tests/gui/test_connect_db.py`, `tests/gui/test_connect_failure.py`: 재접속과 접속 실패를 만드는 방식

## 작업

### 1. 테스트 (새 파일 `tests/gui/test_db_status.py`)

- 공통 DSN: `DSN = "host=db.example port=5433 dbname=gendb user=alice password=s3cret"`.
- 접속은 `main_window.device_tab.connect_db(DSN)` 으로 한다. 가짜 DB의 `cfg.dsn` 이 그 값이 된다.
- 테스트
  - `test_new_window_says_not_connected`: 컨트롤러 없이 `MainWindow("localhost")` 를 만든다. `db_status_label.text() == "DB: not connected"` 이고 `property("connected") == "false"` 다.
  - `test_connect_shows_the_target_without_password`: `connect_db(DSN)` 뒤 라벨이 `"DB: host=db.example port=5433 dbname=gendb user=alice"` 이고, `"s3cret"` 와 `"password"` 가 글자에 없고, connected가 `"true"` 다.
  - `test_failed_reconnect_keeps_the_old_target`: 먼저 DSN으로 붙는다. `store.fail_next(...)` 로 접속을 실패시키고(어느 메서드인지는 `test_connect_failure.py` 의 방식을 따른다) 다른 DSN으로 `connect_db` 한다. 라벨은 옛 대상 그대로다.
  - `test_first_connect_failure_says_not_connected`: 첫 접속이 실패하는 창을 직접 만든다. `install_fake_db` 뒤 `store.fail_next` 를 걸고 `MainWindowController` 를 만든다. `connected is not None` 을 기다린 뒤 라벨이 `DB: not connected` 다.
  - `test_close_db_says_not_connected`: 붙은 뒤 `device_tab.close_db()` 하면 `DB: not connected` 다.
- "아무 일도 일어나지 않음"은 `qtbot.wait` 대신 `store.calls`/`connected` 를 `qtbot.waitUntil` 로 기다린 뒤 단언한다. 콜백은 bool을 돌려준다.

### 2. 수정

- `views/main_window.py`
  - `db_status_label` 을 만들어 상태 표시줄 영구 위젯으로 둔다.
  - `apply_db_status(target: str | None)` 같은 메서드를 둔다(이름은 재량). None이면 not connected다. 글자와 `connected` 속성을 바꾸고 다시 polish한다.
- `controllers/main_window.py`
  - `device_tab.dbChanged` 를 받는 슬롯에서 `db` 가 있으면 `target_summary(db.cfg.dsn)`, 없으면 None으로 뷰를 갱신한다.
  - `__init__` 에서 한 번 지금 상태로 맞춘다.
- `utils/palette.py`
  - `QLabel#ConnectionStatus[connected="true"]`/`[="false"]` 규칙의 선택자에 `QLabel#DbStatus[...]` 를 더한다.
  - phase 22의 mist 스타일시트 고정 테스트(`tests/gui/test_theme_colors.py` 의 `MIST_STYLESHEET_SHA256`, sha256 해시)를 새 결과로 갱신한다. 더한 선택자 말고는 같아야 한다.
    - 해시로는 차이를 볼 수 없다. 옛 결과는 `git show HEAD:src/genviewer/utils/palette.py` 를 scratchpad 에 꺼내 `importlib` 로 불러 만든다. `difflib.unified_diff` 로 새 결과와 비교한다.
    - 바뀐 줄이 `QLabel#ConnectionStatus[connected=…]` 두 규칙의 선택자 줄뿐이어야 한다. 그 결과를 summary 에 적는다.
    - 상수 위 주석의 출처도 이 step 결과로 고친다. `MIST`, `MIST_PALETTE` 는 바꾸지 마라.

## Acceptance Criteria

```bash
uv run pytest tests/gui/test_db_status.py tests/gui/test_connect_db.py tests/gui/test_connect_failure.py tests/gui/test_theme_colors.py -q
uv run pytest tests/gui -q
uv run ruff check src tests
uv run pytest -q
```

## 검증 절차

1. 위 AC 커맨드를 실행한다.
2. 아키텍처 체크리스트를 확인한다.
   - 라벨 글자에 `target_summary` 말고 DSN에서 나온 글자가 들어가지 않는가?
   - 라벨 갱신이 DB를 부르지 않는가? `db.cfg.dsn` 은 메모리 값이라 GUI 스레드에서 기다릴 일이 없다.
   - 접속 흐름(`connect_db`, `close_db`, 폴링)은 그대로인가?
3. 결과에 따라 `phases/23-ui-layout/index.json` 의 step 2를 업데이트한다.
   - 성공 → `"status": "completed"`, `"summary": "상태 표시줄 영구 라벨 db_status_label(objectName DbStatus): DB: <target_summary> / DB: not connected, connected 속성 good/bad. dbChanged 로 갱신. tests/gui/test_db_status.py(6경로). 변이: <결과>"`
   - 수정 3회 시도 후에도 실패 → `"status": "error"`, `"error_message": "구체적 에러 내용"`
   - 사용자 개입 필요 → `"status": "blocked"`, `"blocked_reason": "구체적 사유"` 후 즉시 중단

## 금지사항

- DSN을 직접 화면에 쓰거나 잘라 쓰지 마라. `target_summary` 만 쓴다. 이유: psycopg conninfo에는 비밀번호가 들어 있다(CLAUDE.md CRITICAL).
- `DeviceTabController.connect_db`/`close_db` 의 동작이나 `dbChanged` 를 내는 시점을 바꾸지 마라. 이유: History 화면도 그 신호를 쓰고, 재접속 실패 때 옛 DB를 지키는 계약이 있다.
- 시작 때의 `show_status("No database loaded")` 를 지우거나 바꾸지 마라. 이유: 범위 밖이다.
- 라벨을 폴링으로 갱신하지 마라(주기적 ping 등). 이유: 사용자가 요청하지 않았다. 신호로만 바꾼다.
- 새 문구(`DB: not connected` 등)는 영어로 쓴다.
- 건드리는 파일의 기존 한국어 문구를 번역하지 마라. 이유: phase 24(영어화)의 몫이다.
- 기존 테스트를 깨뜨리지 마라.
