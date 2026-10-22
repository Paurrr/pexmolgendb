# Step 1: virtuoso-toolbar

## 배경

이 저장소는 **에러·버그만 고친다**(CLAUDE.md, ADR-015). 이 step은 사용자가 2026-10-22에 승인한 사용성 변경이다("Virtuoso 묶음 정리", AskUserQuestion).

**문제**
- 창 위 툴바(`QToolBar("Main Toolbar")`)는 전부 오른쪽에 붙어 있다. 순서는 `(빈칸) [Theme: Graphite] Server: [ ] Port: [ ] [Connect] Disconnected` 다.
- Server·Port·Connect는 **Virtuoso 소켓**이다. 데이터베이스가 아니다. 그런데 화면 어디에도 "Virtuoso" 가 없다.
- 메뉴 Database → Connect... 는 DB 접속이다. 그래서 두 Connect가 헷갈린다.
- Theme 단추는 Virtuoso와 상관없는데 같은 묶음에 있다.

**승인된 동작**
- 위 툴바는 `(빈칸) Virtuoso  Server: [ ] Port: [ ] [Connect] Disconnected` 가 된다.
  - "Virtuoso" 는 굵은 라벨이고 Server 라벨 바로 앞에 둔다.
  - Connect 단추에 툴팁 `"Connect to the Virtuoso socket"` 을 단다.
- Theme 단추를 없앤다. 그 자리에 메뉴 줄의 새 **View** 메뉴와, 그 안의 체크 가능한 동작 **"Dark Theme"** 를 만든다.
  - 체크됨 = graphite, 체크 안 됨 = mist다.
  - 시작할 때는 체크됨이다. 시작 테마가 graphite이기 때문이다(`main.py`, `MainWindowController.theme_name`).
  - 누르면 지금의 `_toggle_theme` 와 같은 일을 한다. `apply_theme` 를 부르고 로그 패널에 `Theme changed to <Name>.` 를 쓴다.
- View 메뉴는 Database 메뉴 **뒤**에 둔다. step 4가 그 사이에 Edit 메뉴를 넣는다.

규칙:
1. 승인된 변경이라 RED 대신 변이 검사를 한다. "Virtuoso" 라벨을 손으로 빼면 새 테스트가 실패해야 한다. `git checkout`/`git stash` 로 되돌리지 마라.
2. 행 번호는 2026-10-22 기준 대략값이다.
3. 문서(UI_GUIDE "레이아웃" 그림, README)는 phase 마무리에서 고친다.

## 읽어야 할 파일

- `/CLAUDE.md`, `/docs/UI_GUIDE.md`: "레이아웃", "스타일과 색"
- `src/genviewer/views/main_window.py`: `MainWindow.__init__`(툴바 ~70-113), `set_theme_name`, `apply_connection_ui`, `_refresh_style`
- `src/genviewer/controllers/main_window.py`: `__init__`(`theme_btn.clicked`, `set_theme_name`), `_setup_actions`(메뉴), `_toggle_theme`
- `src/genviewer/utils/palette.py`: `QPushButton#ThemeButton` QSS 규칙, `apply_theme`, `THEMES`
- `tests/gui_support/theme.py`: phase 22가 만든 `preserved_theme`. `apply_theme` 를 부르는 테스트는 이 안에서 돈다.
- `tests/gui/test_toolbar_min_width.py`: 컨트롤러 없이 `MainWindow("localhost")` 를 띄우는 방식(CLAUDE.md 레이아웃 관례)
- `tests/gui/test_virtuoso_connection.py`: Connect/Disconnect·상태 라벨 문구를 고정한다. 그대로 통과해야 한다.

## 작업

### 1. 테스트 (새 파일 `tests/gui/test_main_toolbar.py`)

- 툴바 순서:
  - `MainWindow("localhost")` 를 직접 띄운다(`qtbot.addWidget`).
  - 위 툴바의 `QWidgetAction` 기본 위젯을 순서대로 읽는다.
  - 순서가 `[빈칸, QLabel("Virtuoso"), QLabel("Server:"), server_field, QLabel("Port:"), port_field, connect_btn, status_label]` 다.
  - `theme_btn` 속성이 없다.
- Connect 툴팁이 `"Connect to the Virtuoso socket"` 이다.
- View 메뉴:
  - `main_window` fixture로 띄운다.
  - 메뉴 줄에 제목 `"View"` 인 메뉴가 하나 있다. 그 안에 `"Dark Theme"` 동작이 있고, `isCheckable()` 이고 `isChecked()` 다.
- 전환: `preserved_theme(app)` 안에서 그 동작을 `trigger()` 한다.
  - `app.property("themeName") == "mist"` 이고 동작은 체크 안 됨이다.
  - 다시 누르면 `"graphite"` 이고 체크됨이다.
  - 로그 패널 끝 줄이 `Theme changed to Mist.` / `Theme changed to Graphite.` 로 끝난다.

### 2. 수정

- `views/main_window.py`
  - 툴바에서 `theme_btn` 을 지운다. `set_theme_name` 은 단추가 없으니 지우거나 동작을 갱신하는 것으로 바꾼다. 재량이지만 쓰는 곳을 모두 맞춘다.
  - Server 라벨 앞에 굵은 `QLabel("Virtuoso")` 를 둔다. 굵게 하는 방법(`<b>` 또는 QSS objectName)은 재량이다. 색은 박지 않는다.
  - `connect_btn.setToolTip("Connect to the Virtuoso socket")` 을 단다.
  - 위젯 너비·간격은 지금 관례를 따른다.
- `controllers/main_window.py`
  - `theme_btn.clicked` 연결을 지운다.
  - `_setup_actions` 에서 Database 메뉴 다음에 `View` 메뉴와 체크 가능한 `QAction("Dark Theme")` 를 만든다.
  - `toggled`(또는 `triggered`)를 `_toggle_theme` 와 같은 동작으로 잇는다.
  - 체크 상태와 `self.theme_name` 이 늘 같게 한다. 메뉴로 바꾸든 다른 길로 바꾸든 같아야 한다.
- `utils/palette.py`
  - `QPushButton#ThemeButton` 규칙을 지운다. 이 objectName을 쓰는 위젯이 없어진다.
  - 이 규칙 하나를 지우면 phase 22의 "mist stylesheet 바이트 고정" 테스트가 실패한다. 그 테스트의 기대값(리터럴 또는 해시)을 새 결과로 갱신한다. 지운 규칙 말고는 같아야 한다.

## Acceptance Criteria

```bash
uv run pytest tests/gui/test_main_toolbar.py tests/gui/test_virtuoso_connection.py tests/gui/test_theme_colors.py -q
uv run pytest tests/gui -q
uv run ruff check src tests
uv run pytest -q
```

## 검증 절차

1. 위 AC 커맨드를 실행한다.
2. 아키텍처 체크리스트를 확인한다.
   - Virtuoso 소켓 동작(Connect/Disconnect, 상태 라벨 문구·색)이 그대로인가?
   - `apply_theme` 를 부르는 새 테스트가 모두 `preserved_theme` 안에서 도는가?
   - Database 메뉴의 내용은 그대로인가? step 4가 바꾼다.
3. 결과에 따라 `phases/23-ui-layout/index.json` 의 step 1을 업데이트한다.
   - 성공 → `"status": "completed"`, `"summary": "위 툴바: Virtuoso 라벨+Connect 툴팁, Theme 단추 제거 → View 메뉴 Dark Theme(체크=graphite). ThemeButton QSS 제거(mist 고정값 갱신). tests/gui/test_main_toolbar.py. 변이: <결과>"`
   - 수정 3회 시도 후에도 실패 → `"status": "error"`, `"error_message": "구체적 에러 내용"`
   - 사용자 개입 필요 → `"status": "blocked"`, `"blocked_reason": "구체적 사유"` 후 즉시 중단

## 금지사항

- Server·Port·Connect·상태 라벨의 문구와 동작을 바꾸지 마라. 이유: `test_virtuoso_connection.py` 가 고정하고, 사용자가 고른 것은 묶음 표시뿐이다.
- 테마 선택을 설정 파일에 저장하지 마라. OS 색 구성도 따르지 마라. 이유: 사용자가 요청하지 않았다.
- Device 탭 툴바(`views/device_tab_toolbar.py`)를 고치지 마라. 이유: 이 step은 창 위 툴바만 다룬다.
- 새 문구는 영어로 쓴다("Virtuoso", "View", "Dark Theme", 툴팁).
- 건드리는 파일의 기존 한국어 문구를 번역하지 마라. 이유: phase 24(영어화)의 몫이다.
- 기존 테스트를 깨뜨리지 마라.
