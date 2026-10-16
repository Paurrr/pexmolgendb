# Step 0: pytest-qt-setup

## 배경 (phase 2 공통)

이 저장소는 이미 여러 명이 쓰는 도구다. 지금은 **에러·버그만 고친다**(CLAUDE.md, ADR-015). 다음 phase `3-gui-save-fixes` 와 `4-gui-robustness` 는 GUI 컨트롤러의 버그를 실패하는 테스트로 재현한 뒤 고친다. phase 2는 그 테스트를 쓸 수 있는 **GUI 테스트 기반만** 깐다. step 0은 pytest-qt와 모달 대화상자 가짜(`dialogs` fixture), step 1은 실제 repo와 같은 의미의 가짜 repo(`tests/gui_support/fakes.py`), step 2는 가짜 repo에 붙은 컨트롤러 fixture와 헬퍼다. **`src/` 는 한 줄도 바꾸지 않는다.**

모든 step에 같은 규칙이 적용된다.
1. `src/` 를 고치지 않는다. 이 phase에는 고칠 버그가 없으므로 "실패하는 테스트로 먼저 재현" 규칙 대신 **지금 코드의 동작을 그대로 드러내는 테스트만** 쓴다. 테스트를 쓰다 버그로 보이는 동작을 만나면 고치지 말고, 그 동작을 단언하지도 말고(뒤 phase가 고치면 깨질 단언을 남기지 않는다), summary에 `파일:행 — 관찰` 로 적는다.
2. 새 의존성은 pytest-qt 하나뿐이다(사용자 승인 2026-10-17). step 0이 넣는다.
3. 이 파일들에 적은 이름(fixture, 클래스, 메서드, 헬퍼, 모듈 경로)은 phase 3/4 step 파일이 그대로 쓴다. 이름·인자·의미를 바꾸지 마라. 더하는 것은 괜찮다.
4. 테스트 기반도 변이 검사를 한다. 가짜·fixture의 핵심 규칙 하나를 손으로 망가뜨려 그것을 지키는 테스트가 실패하는지 보고 되돌린다. `git checkout`/`git stash` 로 되돌리지 마라. 이유: 같은 step의 다른 변경까지 사라진다.
5. "아무 일도 일어나지 않음"은 고정 대기(`qtbot.wait`, `time.sleep`) 대신 fake가 기록한 호출이나 컨트롤러 상태를 `qtbot.waitUntil` 로 기다린 뒤 단언한다.
6. 이 파일의 행 번호는 2026-10-17 기준 대략값이다. 이름으로 찾아라.

## 이 step의 목적

pytest-qt를 dev 의존성으로 넣고, `tests/gui/` 의 Qt 테스트가 화면 없이(offscreen) 뜨게 하고, 어떤 모달 대화상자도 테스트를 멈추게 하지 못하게 한다. 예/아니오와 저장 충돌의 답은 테스트가 미리 정하고(`dialogs` fixture), 화면에 뜬 문구는 기록(`dialogs.shown`)으로 단언한다. 답을 정하지 않은 모달이 뜨면 그 자리에서 `AssertionError` 가 나고, 앱 코드가 그 예외를 삼켜도 테스트는 teardown에서 실패한다.

## 읽어야 할 파일

먼저 아래 파일들을 읽고 설계 의도를 파악하라.

- `/CLAUDE.md`(테스트 관례, 명령어), `/docs/ARCHITECTURE.md`(디렉토리 구조의 `tests/` 줄, 스레딩), `/docs/UI_GUIDE.md`(문구 절: `question`, `ask_conflict`, `notifyRequested`, "하지 않는 것" 표)
- `pyproject.toml` — `[dependency-groups] dev`, `[tool.pytest.ini_options]`(지금은 `testpaths` 뿐)
- `tests/test_background.py` — 맨 위에서 `QT_QPA_PLATFORM` 을 setdefault하고 자기 session `qapp` fixture를 쓴다. pytest-qt도 `qapp` fixture를 주는데, 모듈 안의 fixture가 이긴다. 이 파일은 고치지 않고 그대로 통과해야 한다.
- `tests/conftest.py` — `pg_dsn`/`db`(이 step과 관계없지만 `tests/gui/` 에도 적용된다)
- `src/genviewer/utils/dialogs.py` — `info`, `warning`, `critical`, `error`, `question` (~1-25)
- `src/genviewer/dialogs/conflict.py` — `RELOAD`/`OVERWRITE`/`CANCEL`, `ConflictDialog`(제목 "Save Conflict"), `ask_conflict` (~42-100)
- `question` 을 `from genviewer.utils.dialogs import question` 으로 묶은 모듈: `controllers/device_tab.py:18`, `controllers/device_tab_toolbar.py:4`, `views/device_table.py:20`, `views/device_tab_toolbar.py:12`, `views/tab_section.py:15`
- `info, warning, error, critical` 을 묶은 모듈: `views/main_window.py:22` (`MainWindow.notify` ~170-181: info→info, warn/warning→warning, critical→critical, 그 밖→error)
- `ask_conflict` 를 묶은 모듈: `controllers/device_table.py:9`, `controllers/parameter_tab.py:5`
- `QMessageBox` 정적 함수 직접 호출: `controllers/device_tab.py` ~359(`QMessageBox.warning`), `main.py` ~36(excepthook)
- `QFileDialog`: `utils/file_dialogs.py`(`open_file`, `save_file`). `QInputDialog.getText`: `views/device_tab_toolbar.py` ~125, ~149
- `QDialog.exec`/`exec_`: `dialogs/conflict.py` ~99, `views/device_tab.py` ~136(ConnectionDialog), `views/device_table.py` ~131/~145, `views/tab_section.py` ~104/~119(InsertDialog), `controllers/parameter_tab.py` ~149(TabSelectorDialog)
- 메뉴: `controllers/device_table.py` ~80(`build_device_table_menu` 결과의 `menu.exec(pos)`), ~115(헤더 메뉴 `menu.exec_(pos)`), `controllers/tab_section.py` ~45(`build_parameter_table_menu`)
- `src/genviewer/utils/reporting.py` — `@report`/`report_error` 가 `StaleWriteError` 를 뺀 **모든 `Exception`** 을 잡아 `notifyRequested` 로 바꾼다. `AssertionError` 도 여기서 삼켜진다. `DeviceTabController.connect_db`·`save_db` 도 `except Exception` 이다.
- 형제 저장소 참고: `../pexqa/tests/gui/conftest.py`(`FakePrompts`, `_collect_previous_garbage`), `../pexqa/CLAUDE.md` 테스트 관례(헬퍼 import, `qtbot.waitUntil`, teardown에서 창 닫기)

## 작업

### 1. 의존성 (`pyproject.toml`, `uv.lock`)

- `uv add --dev pytest-qt` 하나만 실행한다(사용자 승인 2026-10-17). pure-python 휠이고 dev 그룹이라 배포(`uv sync --no-dev`)에는 들어가지 않는다. 그래서 manylinux 확인은 필요 없다.
- 해석된 pytest-qt가 설치된 pytest(9.x)·PySide6 6.9.3과 맞지 않아 설치나 수집이 실패하면 버전을 이리저리 바꾸지 말고 `blocked` 로 멈춘다.

### 2. pytest 설정 (`pyproject.toml` `[tool.pytest.ini_options]`)

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["tests"]   # GUI 테스트 헬퍼를 `from gui_support.dialogs import ...` 로 쓴다
qt_api = "pyside6"
```

있던 설정은 그대로 두고 두 줄만 더한다.

### 3. 대화상자 가짜 (`tests/gui_support/__init__.py`, `tests/gui_support/dialogs.py`, 새 파일)

`tests/gui_support/` 는 GUI 테스트 헬퍼 패키지다(step 1이 `fakes.py`, step 2가 `helpers.py` 를 더한다). `__init__.py` 는 docstring 한 줄이면 된다.

```python
QUESTION_MODULES: tuple[str, ...] = (
    "genviewer.utils.dialogs",
    "genviewer.controllers.device_tab",
    "genviewer.controllers.device_tab_toolbar",
    "genviewer.views.device_table",
    "genviewer.views.device_tab_toolbar",
    "genviewer.views.tab_section",
)
MESSAGE_MODULES: tuple[str, ...] = ("genviewer.utils.dialogs", "genviewer.views.main_window")
CONFLICT_MODULES: tuple[str, ...] = (
    "genviewer.dialogs.conflict",
    "genviewer.controllers.device_table",
    "genviewer.controllers.parameter_tab",
)
MENU_BUILDERS: tuple[tuple[str, str], ...] = (
    ("genviewer.controllers.device_table", "build_device_table_menu"),
    ("genviewer.controllers.tab_section", "build_parameter_table_menu"),
)

class FakeDialogs:
    shown: list[tuple[str, str, str]]   # (kind, title, text). 뜬 순서대로
    unexpected: list[str]               # 답을 정하지 않은 모달, 워커 스레드에서 뜬 모달
    def answer_question(self, *answers: bool) -> None: ...   # bool 이 아니면 TypeError. 여러 번 부르면 뒤에 쌓인다
    def answer_conflict(self, *choices: str) -> None: ...    # RELOAD/OVERWRITE/CANCEL 이 아니면 ValueError
    def record_notify(self, severity: str, title: str, text: str) -> None: ...
    def problems(self) -> list[str]: ...  # unexpected + 쓰이지 않고 남은 답(question, conflict)
    # 패치된 자리에 들어가는 대역. 시그니처는 원래 함수와 같다
    def question(self, parent, title: str, message: str) -> bool: ...
    def info(self, parent, title: str, message: str) -> None: ...      # warning, error, critical 도 같은 모양
    def ask_conflict(self, parent, conflicts) -> str: ...

def install_dialogs(monkeypatch) -> FakeDialogs: ...
```

`install_dialogs` 가 바꾸는 것과 기록하는 kind:

| 대체되는 것 | `shown` 의 kind | 돌려주는 값 |
|---|---|---|
| `QUESTION_MODULES` 각 모듈의 `question` | `"question"` | 큐의 다음 bool |
| `MESSAGE_MODULES` 각 모듈의 `info`/`warning`/`error`/`critical` | 함수 이름 그대로 | None |
| `QMessageBox.information` / `.warning` / `.critical` (클래스의 정적 함수) | `"info"` / `"warning"` / `"critical"` | `QMessageBox.Ok` |
| `QMessageBox.question` | `"question"` | 큐의 다음 답 → `QMessageBox.Yes`/`QMessageBox.No` |
| `CONFLICT_MODULES` 각 모듈의 `ask_conflict` | `"conflict"`, 제목 `"Save Conflict"`, 본문 = `"\n".join(c.describe() for c in conflicts)` | 큐의 다음 선택 |
| `record_notify(severity, …)` (step 2의 `device_tab_ctrl` 이 `notifyRequested` 에 잇는다) | `MainWindow.notify` 와 같은 매핑: info→`"info"`, warn/warning→`"warning"`, critical→`"critical"`, 그 밖→`"error"` | None |

답을 정하지 않은 모달은 `unexpected` 에 한 줄(종류와 제목)을 남기고 `AssertionError` 를 낸다. 메시지에 제목을 넣는다.
- `question`/`QMessageBox.question`/`ask_conflict` 를 빈 큐로 부름(`shown` 에도 남긴다).
- `QDialog.exec`, `QDialog.exec_` — ConflictDialog, ConnectionDialog, InsertDialog, TabSelectorDialog가 모두 여기로 온다. 메시지에 클래스 이름과 `windowTitle()`.
- `QFileDialog.getOpenFileName`/`getOpenFileNames`/`getSaveFileName`/`getExistingDirectory`, `QInputDialog.getText`/`getItem`/`getInt`/`getDouble`/`getMultiLineText` — 제목은 두 번째 위치 인자(caption).
- 컨텍스트 메뉴: `MENU_BUILDERS` 의 두 이름, `QMenu.exec_`.
- 위 대역이 GUI 스레드(`threading.main_thread()`)가 아닌 곳에서 불려도 `unexpected` 에 남기고 `AssertionError`. 이유: UI_GUIDE "워커 스레드에서 위젯·QMessageBox 만들기" 금지.

패치 방법(2026-10-17, PySide6 6.9.3에서 확인한 것):
- 모듈 속성은 `monkeypatch.setattr(module, name, fake.method)`. 모듈은 **먼저 `importlib.import_module` 로 import한 뒤** 바꾼다. 이유: 패치 뒤에 처음 import되는 모듈은 `from … import question` 으로 가짜를 묶어 버리고, monkeypatch가 원래 함수로 되돌려도 그 모듈에는 지난 테스트의 가짜가 남는다.
- `QMessageBox`/`QFileDialog`/`QInputDialog` 의 정적 함수는 클래스에 `staticmethod(...)` 로 바꾼다. `QDialog.exec`, `QDialog.exec_`, `QMenu.exec_` 는 클래스에 일반 함수(첫 인자 self)로 바꾸면 인스턴스 호출에도 먹는다.
- `QMenu.exec` 는 클래스 속성을 바꿔도 `menu.exec(pos)` 인스턴스 호출에 먹지 않는다(static/instance 오버로드). 그래서 메뉴는 builder 이름(`MENU_BUILDERS`)을 바꿔 막는다.

### 4. fixture (`tests/gui/conftest.py`, 새 파일)

- 맨 위(PySide6·`gui_support` import 전)에서 `os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")`. 뒤의 import에는 `# noqa: E402` 를 단다(`tests/test_background.py` 와 같은 방식).
- autouse `dialogs` fixture:

```python
@pytest.fixture(autouse=True)
def dialogs(monkeypatch) -> Iterator[FakeDialogs]:
    fake = install_dialogs(monkeypatch)
    yield fake
    problems = fake.problems()
    if problems:
        pytest.fail("\n".join(problems), pytrace=False)
```

  teardown 검사가 필요한 이유: `@report`, `connect_db` 등이 `AssertionError` 를 알림으로 바꿔 삼키고, device_tab 단독 fixture에서는 그 알림이 아무 데도 가지 않는다. 남은 답도 실패로 본다. 테스트가 기대한 질문이 뜨지 않았다는 뜻이다. 일부러 답 없는 모달을 띄워 `AssertionError` 를 확인하는 테스트는 확인한 뒤 `dialogs.unexpected.clear()` 한다.
- autouse `_collect_previous_garbage`: pexqa의 같은 이름 fixture를 옮긴다(setup에서 `QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)` → `gc.collect()` → `gc.freeze()`). 이유: `run_blocking`/`Task` 와 step 1의 가짜 repo가 워커 스레드에서 파이썬 코드를 돌리므로 순환 GC가 워커 스레드에서 돌 수 있다. 그때 부모 없는 Qt 객체(`MainWindowController` 는 부모가 없다)가 회수되면 C++ 소멸자가 GUI 스레드 밖에서 돌아 abort한다(pexqa phase 7). docstring에 이 이유를 적는다.

### 5. 자기 검사 (`tests/gui/test_dialogs_fixture.py`, 새 파일)

위젯을 만드는 테스트는 `qtbot` 을 받고 `qtbot.addWidget` 으로 등록한다.
- `QUESTION_MODULES` 각 모듈의 `question` 이 큐 순서대로 답하고 `("question", title, text)` 를 남긴다(모듈별 parametrize).
- 빈 큐 `question` → `AssertionError`, 메시지에 제목, `unexpected` 1건(확인 뒤 clear).
- `answer_question("yes")` → `TypeError`, `answer_conflict("bogus")` → `ValueError`.
- `CONFLICT_MODULES` 각 모듈의 `ask_conflict` 가 큐의 선택을 돌려주고 `("conflict", "Save Conflict", Conflict(...).describe())` 를 남긴다.
- `ConflictDialog(None, []).exec()` → `AssertionError`, 메시지에 "Save Conflict".
- `genviewer.utils.file_dialogs.open_file(None, "Load CSV", "csv file (*.csv)")` → `AssertionError`, 메시지에 "Load CSV". `QInputDialog.getText(None, "Add Process", "x")` 도 같다.
- `MainWindow("localhost").notify(severity, "T", "x")` 를 info/warn/critical/error/"bogus" 로 불러 kind가 info/warning/critical/error/error다. `record_notify` 가 같은 severity에 같은 kind를 낸다. `QMessageBox.warning(None, "Database Not Loaded", "x")` 는 `("warning", "Database Not Loaded", "x")`.
- 목록 완전성: `src/genviewer/**/*.py` 를 `ast` 로 읽어 `from genviewer.utils.dialogs import …`, `from genviewer.dialogs.conflict import ask_conflict`, `from genviewer.utils.menus import build_*` 를 하는 모듈이 전부 해당 목록에 있다. 이유: 새 모듈이 `question` 을 묶으면 진짜 QMessageBox가 떠서 테스트가 멈춘다.
- `problems()`: 설치하지 않은 `FakeDialogs()` 에 답을 넣고 쓰지 않으면 비어 있지 않고, 쓰면 비어 있다.
- 워커 스레드(`threading.Thread`)에서 `dialogs.question` 을 부르면 `unexpected` 에 남는다(확인 뒤 clear).

변이 검사: 빈 큐 `question` 이 True를 돌려주게 바꾸면 위 테스트가 실패하는지, `QUESTION_MODULES` 에서 하나를 빼면 완전성 테스트가 실패하는지 확인하고 되돌린다.

### 6. 문서

- `CLAUDE.md` "테스트 관례"의 "Qt 테스트는 `QT_QPA_PLATFORM=offscreen` 으로 돈다…" 줄을 아래 세 줄로 바꾼다(문장은 다듬어도 된다. 기준선 숫자는 step 2가 고친다).
  - GUI 테스트는 `tests/gui/` 에 둔다(pytest-qt, `qt_api = "pyside6"`). `tests/gui/conftest.py` 가 PySide6 import 전에 `QT_QPA_PLATFORM=offscreen` 을 둔다. `tests/test_background.py` 는 자기 `qapp` fixture로 따로 돈다.
  - 모달은 autouse `dialogs` fixture가 대신한다. 예/아니오는 `dialogs.answer_question(...)`, 저장 충돌은 `dialogs.answer_conflict(RELOAD|OVERWRITE|CANCEL)` 로 미리 답하고, 뜬 문구는 `dialogs.shown` 의 `(kind, title, text)` 로 단언한다. 답하지 않은 모달·파일 대화상자·메뉴는 `AssertionError` 이고 앱이 삼켜도 teardown에서 실패한다(쓰지 않은 답도). 이유: `@report` 가 `AssertionError` 까지 알림으로 바꾼다.
  - GUI 테스트 헬퍼는 `tests/gui_support/` 에 두고 `from gui_support.dialogs import ...` 처럼 import한다(`pythonpath = ["tests"]`). conftest나 다른 테스트 모듈은 import하지 않는다. "아무 일도 일어나지 않음"은 고정 대기(`qtbot.wait`) 대신 fake가 기록한 호출이나 컨트롤러 상태를 `qtbot.waitUntil` 로 기다린 뒤 단언한다.
- `CLAUDE.md` "명령어"에 `uv run pytest tests/gui -q   # GUI 테스트만 (pytest-qt, offscreen)` 을 더한다.
- `docs/ARCHITECTURE.md` 디렉토리 구조의 `tests/` 줄 아래에 두 줄을 더한다.
  ```
    gui/                      #   pytest-qt GUI 테스트. conftest: offscreen, autouse dialogs(모달 가짜)
    gui_support/              #   GUI 테스트 헬퍼 패키지(pythonpath=tests): dialogs.py
  ```

## Acceptance Criteria

```bash
uv lock --locked                             # lock 이 pyproject 와 맞다
uv run ruff check src tests                  # 린트 (import 정렬은 uv run ruff check --fix tests 로 고쳐도 된다)
uv run pytest tests/gui -q                   # 자기 검사 통과
uv run pytest tests/test_background.py -q    # 자기 qapp 로 그대로 통과
uv run pytest -q                             # 전체 통과 (DB 테스트는 skip)
git status --porcelain -- src                # 출력이 비어 있어야 한다 (src 불변)
```

## 검증 절차

1. 위 AC 커맨드를 실행한다.
2. 아키텍처 체크리스트를 확인한다:
   - `src/` 가 바뀌지 않았는가?
   - 새 의존성이 dev 그룹의 pytest-qt 하나뿐인가(`git diff pyproject.toml`)?
   - `tests/gui/` 의 어떤 테스트도 진짜 모달을 띄우거나 `qtbot.wait` 로 기다리지 않는가?
3. 결과에 따라 `phases/2-gui-test-infra/index.json` 의 step 0을 업데이트한다:
   - 성공 → `"status": "completed"`, `"summary": "pytest-qt <버전> dev 추가(qt_api=pyside6, pythonpath=tests). tests/gui/conftest.py: offscreen, autouse dialogs, _collect_previous_garbage. tests/gui_support/dialogs.py: FakeDialogs(answer_question/answer_conflict/shown/unexpected/record_notify/problems), install_dialogs. 자기 검사 N개. 관찰: <없음 또는 파일:행 — 관찰>"`
   - 수정 3회 시도 후에도 실패 → `"status": "error"`, `"error_message": "구체적 에러 내용"`
   - 사용자 개입 필요(pytest-qt 설치·호환 실패 등) → `"status": "blocked"`, `"blocked_reason": "구체적 사유"` 후 즉시 중단

## 금지사항

- `src/` 를 고치지 마라. 이유: 이 phase는 테스트 기반만 깐다. 테스트를 쓰다 찾은 버그는 summary에 적고 phase 3/4가 실패하는 테스트로 재현해 고친다.
- pytest-qt 말고 다른 의존성(pytest-timeout, pytest-xvfb, pytest-mock 등)을 넣지 마라. 이유: 사용자가 승인한 것은 pytest-qt 하나다. 테스트가 멈출 위험은 `dialogs` fixture가 막는다.
- 답이 없는 모달에 기본값(True, CANCEL 등)을 돌려주게 만들지 마라. 이유: 묻지 말아야 할 질문이나 빠진 확인 같은 버그가 조용히 통과한다.
- `tests/test_background.py` 를 고치거나 그 `qapp` fixture를 지우지 마라. 이유: 그 파일이 그대로 통과하는 것이 이 step의 AC다.
- `--import-mode` 등 기존 pytest 설정을 바꾸지 마라(두 줄 추가만). 이유: 기존 테스트의 수집 방식이 바뀐다.
- `QMenu.exec` 를 클래스에서 바꾸고 메뉴가 막혔다고 믿지 마라. 이유: PySide6 6.9.3에서 인스턴스 호출에 먹지 않는다. builder 이름을 바꾼다.
- 테스트 모듈에서 conftest나 다른 테스트 모듈을 import하지 마라. 헬퍼는 `tests/gui_support/` 에 둔다. 이유: conftest는 모듈 이름이 겹치고(pexqa 관례), phase 3/4가 같은 import 경로를 쓴다.
- "아무 일도 일어나지 않음"을 `qtbot.wait(ms)` 나 `time.sleep` 으로 단언하지 마라. 이유: 느린 PC에서는 아직 안 일어난 것을, 빠른 PC에서는 아무것도 증명하지 못한다.
- 기존 테스트를 깨뜨리지 마라.
