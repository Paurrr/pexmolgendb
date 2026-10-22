"""모달 대화상자 가짜.

GUI 테스트에서 진짜 모달이 뜨면 offscreen 이라 누를 사람이 없어 테스트가 멈춘다.
`install_dialogs` 가 모달을 띄우는 자리를 전부 이 가짜로 바꾼다.

- 예/아니오(`question`)와 저장 충돌(`ask_conflict`)은 테스트가 미리 정한 답을 차례로 돌려준다.
  충돌 대화상자가 덮어쓰기를 내놓을지는 진짜와 같은 `can_overwrite` 로 정하고, 내놓지 않은
  OVERWRITE 답은 `unexpected` 로 간다.
- 알림(info/warning/error/critical)은 `shown` 에 (kind, title, text) 로 남기기만 한다.
- 답을 정하지 않은 모달, 파일·입력 대화상자, 컨텍스트 메뉴, GUI 스레드 밖에서 뜬 모달은
  `unexpected` 에 한 줄 남기고 `AssertionError` 를 낸다. 답이 없을 때 기본값을 돌려주지 않는다.
  묻지 말아야 할 질문이나 빠진 확인이 조용히 통과하기 때문이다.

`@report` 등이 `AssertionError` 를 알림으로 바꿔 삼킬 수 있으므로 `tests/gui/conftest.py` 의
`dialogs` fixture가 teardown에서 `problems()` 를 다시 본다.
"""

import importlib
import threading
from collections import deque
from typing import NoReturn

from PySide6.QtWidgets import QDialog, QFileDialog, QInputDialog, QMenu, QMessageBox

from genviewer.dialogs.conflict import CANCEL, OVERWRITE, RELOAD, can_overwrite

# `from genviewer.utils.dialogs import question` 으로 이름을 묶은 모듈(정의한 모듈 포함).
# 묶인 이름은 모듈마다 따로 바꿔야 한다. 새 모듈이 묶으면 여기에 더한다
# (tests/gui/test_dialogs_fixture.py 가 빠진 것을 잡는다).
QUESTION_MODULES: tuple[str, ...] = (
    "genviewer.utils.dialogs",
    "genviewer.controllers.device_tab",
    "genviewer.controllers.device_tab_toolbar",
    "genviewer.controllers.main_window",
    "genviewer.views.device_table",
    "genviewer.views.tab_section",
)
# info / warning / error / critical 을 묶은 모듈.
MESSAGE_MODULES: tuple[str, ...] = ("genviewer.utils.dialogs", "genviewer.views.main_window")
# ask_conflict 를 묶은 모듈.
CONFLICT_MODULES: tuple[str, ...] = (
    "genviewer.dialogs.conflict",
    "genviewer.controllers.device_table",
    "genviewer.controllers.parameter_tab",
)
# 컨텍스트 메뉴 builder 를 묶은 (모듈, 이름). `menu.exec(pos)` 는 QMenu.exec 를 클래스에서
# 바꿔도 막히지 않아서(PySide6 6.9.3, static/instance 오버로드) builder 를 바꾼다.
MENU_BUILDERS: tuple[tuple[str, str], ...] = (
    ("genviewer.controllers.device_table", "build_device_table_menu"),
    ("genviewer.controllers.tab_section", "build_parameter_table_menu"),
)

CONFLICT_TITLE = "Save Conflict"  # dialogs/conflict.ConflictDialog 의 창 제목
CONFLICT_CHOICES = (RELOAD, OVERWRITE, CANCEL)
MESSAGE_FUNCTIONS = ("info", "warning", "error", "critical")

# MainWindow.notify 와 같은 매핑. 모르는 severity 는 error 다.
_NOTIFY_KINDS = {"info": "info", "warn": "warning", "warning": "warning", "critical": "critical"}
# QMessageBox 정적 함수 → shown 의 kind
_MESSAGE_BOX_KINDS = {"information": "info", "warning": "warning", "critical": "critical"}
_FILE_DIALOGS = ("getOpenFileName", "getOpenFileNames", "getSaveFileName", "getExistingDirectory")
_INPUT_DIALOGS = ("getText", "getItem", "getInt", "getDouble", "getMultiLineText")


def _caption(args: tuple, kwargs: dict) -> str:
    """QFileDialog/QInputDialog 정적 함수의 제목. 두 번째 위치 인자(caption)다."""
    if len(args) > 1:
        return str(args[1])
    return str(kwargs.get("caption", kwargs.get("title", "")))


class FakeDialogs:
    """모달 대역. 뜬 것은 `shown`, 뜨면 안 되는 것은 `unexpected` 에 남는다."""

    def __init__(self) -> None:
        self.shown: list[tuple[str, str, str]] = []  # (kind, title, text). 뜬 순서대로
        self.unexpected: list[str] = []  # 답을 정하지 않은 모달, 워커 스레드에서 뜬 모달
        # 충돌 대화상자마다 내놓은 선택. (RELOAD, OVERWRITE, CANCEL) 또는 (RELOAD, CANCEL)
        self.conflict_choices: list[tuple[str, ...]] = []
        self._questions: deque[bool] = deque()
        self._conflicts: deque[str] = deque()

    # -- 테스트가 쓰는 것 --------------------------------------------------

    def answer_question(self, *answers: bool) -> None:
        """다음 question 들의 답. 여러 번 부르면 뒤에 쌓인다."""
        for answer in answers:
            if not isinstance(answer, bool):
                raise TypeError(f"question 의 답은 bool 이어야 한다: {answer!r}")
        self._questions.extend(answers)

    def answer_conflict(self, *choices: str) -> None:
        """다음 ask_conflict 들의 선택(RELOAD/OVERWRITE/CANCEL). 여러 번 부르면 뒤에 쌓인다."""
        for choice in choices:
            if choice not in CONFLICT_CHOICES:
                raise ValueError(f"충돌 선택은 {CONFLICT_CHOICES} 중 하나여야 한다: {choice!r}")
        self._conflicts.extend(choices)

    def record_notify(self, severity: str, title: str, text: str) -> None:
        """notifyRequested(severity, title, text) 를 MainWindow.notify 처럼 기록한다."""
        self._require_gui_thread("notify", title)
        self.shown.append((_NOTIFY_KINDS.get(severity, "error"), title, text))

    def problems(self) -> list[str]:
        """unexpected 와 쓰이지 않고 남은 답. 비어 있어야 테스트가 통과한다."""
        found = list(self.unexpected)
        if self._questions:
            found.append(f"쓰이지 않은 question 답: {list(self._questions)}")
        if self._conflicts:
            found.append(f"쓰이지 않은 conflict 답: {list(self._conflicts)}")
        return found

    # -- 패치된 자리에 들어가는 대역 (시그니처는 원래 함수와 같다) ------------

    def question(self, parent, title: str, message: str) -> bool:
        self._require_gui_thread("question", title)
        self.shown.append(("question", title, message))
        if not self._questions:
            self._fail("question", title)
        return self._questions.popleft()

    def info(self, parent, title: str, message: str) -> None:
        self._message("info", title, message)

    def warning(self, parent, title: str, message: str) -> None:
        self._message("warning", title, message)

    def error(self, parent, title: str, message: str) -> None:
        self._message("error", title, message)

    def critical(self, parent, title: str, message: str) -> None:
        self._message("critical", title, message)

    def ask_conflict(self, parent, conflicts, my_deletions=()) -> str:
        self._require_gui_thread("conflict", CONFLICT_TITLE)
        text = "\n".join(c.describe() for c in conflicts)
        self.shown.append(("conflict", CONFLICT_TITLE, text))
        # 판단은 진짜 함수 그대로 쓴다. 규칙을 여기 다시 쓰면 둘이 어긋나도 테스트가 통과한다.
        offered = CONFLICT_CHOICES if can_overwrite(conflicts, my_deletions) else (RELOAD, CANCEL)
        self.conflict_choices.append(offered)
        if not self._conflicts:
            self._fail("conflict", CONFLICT_TITLE)
        choice = self._conflicts.popleft()
        if choice not in offered:
            line = f"내놓지 않은 {choice.upper()} 답: {CONFLICT_TITLE!r}"
            self.unexpected.append(line)
            raise AssertionError(line)
        return choice

    # -- 내부 -------------------------------------------------------------

    def _message(self, kind: str, title: str, message: str) -> None:
        self._require_gui_thread(kind, title)
        self.shown.append((kind, title, message))

    def _require_gui_thread(self, kind: str, title: str) -> None:
        # UI_GUIDE: 워커 스레드에서 위젯·QMessageBox 를 만들지 않는다.
        if threading.current_thread() is not threading.main_thread():
            line = (
                f"GUI 스레드가 아닌 곳({threading.current_thread().name})에서 뜬 {kind}: {title!r}"
            )
            self.unexpected.append(line)
            raise AssertionError(line)

    def _fail(self, kind: str, title: str) -> NoReturn:
        self._require_gui_thread(kind, title)
        line = f"답을 정하지 않은 {kind}: {title!r}"
        self.unexpected.append(line)
        raise AssertionError(line)

    def _message_box(self, kind: str):
        def fake(parent, title, text, *_args, **_kwargs):
            self._message(kind, title, text)
            return QMessageBox.Ok

        return fake

    def _message_box_question(self, parent, title, text, *_args, **_kwargs):
        return QMessageBox.Yes if self.question(parent, title, text) else QMessageBox.No

    def _blocked_static(self, kind: str):
        def fake(*args, **kwargs):
            self._fail(kind, _caption(args, kwargs))

        return fake

    def _blocked_dialog_exec(self, method: str):
        def fake(dialog, *_args, **_kwargs):
            self._fail(f"{type(dialog).__name__}.{method}", dialog.windowTitle())

        return fake

    def _blocked_menu_exec(self):
        # 클래스 속성은 일반 함수라야 menu 가 첫 인자로 온다. 바운드 메서드를 넣으면 pos 가 온다.
        def fake(menu, *_args, **_kwargs):
            self._fail("QMenu.exec_", menu.title())

        return fake

    def _blocked_menu_builder(self, module: str, name: str):
        def fake(*_args, **_kwargs):
            self._fail("context menu", f"{module}.{name}")

        return fake


def install_dialogs(monkeypatch) -> FakeDialogs:
    """모달을 띄우는 자리를 FakeDialogs 로 바꾼다. monkeypatch 가 테스트 끝에 되돌린다."""
    fake = FakeDialogs()

    # 먼저 전부 import 한다. 패치 뒤에 처음 import 되는 모듈은 `from … import question` 으로
    # 가짜를 묶어 버리고, monkeypatch 가 되돌려도 그 모듈에는 지난 테스트의 가짜가 남는다.
    names = {*QUESTION_MODULES, *MESSAGE_MODULES, *CONFLICT_MODULES}
    names.update(module for module, _ in MENU_BUILDERS)
    modules = {name: importlib.import_module(name) for name in sorted(names)}

    for name in QUESTION_MODULES:
        monkeypatch.setattr(modules[name], "question", fake.question)
    for name in MESSAGE_MODULES:
        for func in MESSAGE_FUNCTIONS:
            monkeypatch.setattr(modules[name], func, getattr(fake, func))
    for name in CONFLICT_MODULES:
        monkeypatch.setattr(modules[name], "ask_conflict", fake.ask_conflict)
    for name, builder in MENU_BUILDERS:
        monkeypatch.setattr(modules[name], builder, fake._blocked_menu_builder(name, builder))

    # 클래스의 정적 함수는 staticmethod 로 바꾼다.
    for method, kind in _MESSAGE_BOX_KINDS.items():
        monkeypatch.setattr(QMessageBox, method, staticmethod(fake._message_box(kind)))
    monkeypatch.setattr(QMessageBox, "question", staticmethod(fake._message_box_question))
    for method in _FILE_DIALOGS:
        monkeypatch.setattr(
            QFileDialog, method, staticmethod(fake._blocked_static(f"QFileDialog.{method}"))
        )
    for method in _INPUT_DIALOGS:
        monkeypatch.setattr(
            QInputDialog, method, staticmethod(fake._blocked_static(f"QInputDialog.{method}"))
        )

    # 인스턴스 메서드는 일반 함수(첫 인자 self)로 바꾸면 서브클래스 인스턴스 호출에도 먹는다.
    # ConflictDialog, ConnectionDialog, InsertDialog, TabSelectorDialog 가 모두 여기로 온다.
    for method in ("exec", "exec_"):
        monkeypatch.setattr(QDialog, method, fake._blocked_dialog_exec(method))
    monkeypatch.setattr(QMenu, "exec_", fake._blocked_menu_exec())

    return fake
