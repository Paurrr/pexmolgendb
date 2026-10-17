"""`dialogs` fixture(모달 가짜) 자기 검사.

여기가 틀리면 GUI 테스트가 진짜 모달에서 멈추거나, 묻지 말아야 할 질문이 조용히 통과한다.
"""

import ast
import importlib
import threading
from datetime import datetime
from pathlib import Path

import pytest
from gui_support.dialogs import (
    CONFLICT_MODULES,
    MENU_BUILDERS,
    MESSAGE_FUNCTIONS,
    MESSAGE_MODULES,
    QUESTION_MODULES,
    FakeDialogs,
    install_dialogs,
)
from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QInputDialog, QMenu, QMessageBox

import genviewer
from genviewer.dialogs.conflict import CANCEL, OVERWRITE, RELOAD, ConflictDialog
from genviewer.service.errors import Conflict
from genviewer.utils import file_dialogs
from genviewer.utils.reporting import report

SRC = Path(genviewer.__file__).resolve().parent


def _conflicts() -> list[Conflict]:
    return [
        Conflict(1, "nfet_b", "stale", "kim", datetime(2026, 10, 17, 9, 30)),
        Conflict(2, "pfet_b", "deleted"),
    ]


# -- question -------------------------------------------------------------


@pytest.mark.parametrize("module_name", QUESTION_MODULES)
def test_question_answers_in_queue_order(dialogs, module_name):
    module = importlib.import_module(module_name)
    dialogs.answer_question(True)
    dialogs.answer_question(False)  # 여러 번 부르면 뒤에 쌓인다

    assert module.question(None, "Delete Device", "first") is True
    assert module.question(None, "Discard Changes", "second") is False
    assert dialogs.shown == [
        ("question", "Delete Device", "first"),
        ("question", "Discard Changes", "second"),
    ]


def test_question_without_answer_raises(dialogs):
    question = importlib.import_module("genviewer.views.device_table").question

    with pytest.raises(AssertionError, match="Delete Device"):
        question(None, "Delete Device", "x")

    assert dialogs.shown == [("question", "Delete Device", "x")]
    assert len(dialogs.unexpected) == 1
    assert "Delete Device" in dialogs.unexpected[0]
    dialogs.unexpected.clear()


def test_qmessagebox_question_uses_the_same_queue(dialogs):
    dialogs.answer_question(True, False)

    assert QMessageBox.question(None, "Q1", "a", QMessageBox.Yes | QMessageBox.No) == (
        QMessageBox.Yes
    )
    assert QMessageBox.question(None, "Q2", "b") == QMessageBox.No
    with pytest.raises(AssertionError, match="Q3"):
        QMessageBox.question(None, "Q3", "c")

    assert dialogs.shown == [
        ("question", "Q1", "a"),
        ("question", "Q2", "b"),
        ("question", "Q3", "c"),
    ]
    assert len(dialogs.unexpected) == 1
    dialogs.unexpected.clear()


def test_answer_question_rejects_non_bool(dialogs):
    with pytest.raises(TypeError):
        dialogs.answer_question("yes")
    with pytest.raises(TypeError):
        dialogs.answer_question(True, 1)  # 앞의 True 도 쌓이지 않는다
    assert dialogs.problems() == []


def test_swallowed_assertion_is_still_a_problem(dialogs):
    """`@report` 가 AssertionError 를 삼켜도 teardown 이 보는 problems() 에 남는다."""
    question = importlib.import_module("genviewer.controllers.device_tab").question

    class Controller:  # notifyRequested 가 없다 - device_tab 단독 fixture 처럼 알림이 갈 곳이 없다
        @report("Delete Failed")
        def delete(self):
            question(None, "Delete Process", "x")

    Controller().delete()  # 예외가 밖으로 나오지 않는다

    assert any("Delete Process" in line for line in dialogs.problems())
    dialogs.unexpected.clear()


# -- 저장 충돌 --------------------------------------------------------------


@pytest.mark.parametrize("module_name", CONFLICT_MODULES)
def test_ask_conflict_returns_queued_choice(dialogs, module_name):
    module = importlib.import_module(module_name)
    conflicts = _conflicts()
    dialogs.answer_conflict(OVERWRITE, CANCEL)

    assert module.ask_conflict(None, conflicts) == OVERWRITE
    assert module.ask_conflict(None, conflicts[:1]) == CANCEL

    joined = "\n".join(c.describe() for c in conflicts)
    assert dialogs.shown == [
        ("conflict", "Save Conflict", joined),
        ("conflict", "Save Conflict", conflicts[0].describe()),
    ]


def test_ask_conflict_without_answer_raises(dialogs):
    ask_conflict = importlib.import_module("genviewer.controllers.parameter_tab").ask_conflict

    with pytest.raises(AssertionError, match="Save Conflict"):
        ask_conflict(None, _conflicts())

    assert [kind for kind, _, _ in dialogs.shown] == ["conflict"]
    assert len(dialogs.unexpected) == 1
    dialogs.unexpected.clear()


def test_answer_conflict_rejects_unknown_choice(dialogs):
    with pytest.raises(ValueError):
        dialogs.answer_conflict("bogus")
    with pytest.raises(ValueError):
        dialogs.answer_conflict(RELOAD, "bogus")  # 앞의 RELOAD 도 쌓이지 않는다
    assert dialogs.problems() == []


# -- 답이 없는 모달 ----------------------------------------------------------


@pytest.mark.parametrize("method", ["exec", "exec_"])
def test_conflict_dialog_exec_raises(qtbot, dialogs, method):
    dialog = ConflictDialog(None, _conflicts())
    qtbot.addWidget(dialog)

    with pytest.raises(AssertionError, match="Save Conflict") as excinfo:
        getattr(dialog, method)()

    assert "ConflictDialog" in str(excinfo.value)
    assert len(dialogs.unexpected) == 1
    dialogs.unexpected.clear()


def test_message_box_instance_exec_raises(qtbot, dialogs):
    box = QMessageBox(QMessageBox.Warning, "Box Title", "x")
    qtbot.addWidget(box)

    with pytest.raises(AssertionError, match="Box Title"):
        box.exec()
    dialogs.unexpected.clear()


@pytest.mark.parametrize(
    ("open_dialog", "title"),
    [
        (lambda: file_dialogs.open_file(None, "Load CSV", "csv file (*.csv)"), "Load CSV"),
        (lambda: file_dialogs.save_file(None, "Export CSV", "csv file (*.csv)"), "Export CSV"),
        (lambda: QInputDialog.getText(None, "Add Process", "x"), "Add Process"),
        (lambda: QInputDialog.getItem(None, "Pick One", "x", ["a"]), "Pick One"),
    ],
)
def test_file_and_input_dialogs_raise(dialogs, open_dialog, title):
    with pytest.raises(AssertionError, match=title):
        open_dialog()

    assert len(dialogs.unexpected) == 1
    assert title in dialogs.unexpected[0]
    dialogs.unexpected.clear()


@pytest.mark.parametrize(("module_name", "builder"), MENU_BUILDERS)
def test_context_menu_builders_raise(dialogs, module_name, builder):
    build = getattr(importlib.import_module(module_name), builder)

    with pytest.raises(AssertionError, match=builder):
        build(None, [0])
    dialogs.unexpected.clear()


def test_menu_exec_underscore_raises(qtbot, dialogs):
    menu = QMenu("Header Menu")
    qtbot.addWidget(menu)

    with pytest.raises(AssertionError, match="Header Menu"):
        menu.exec_(QPoint(0, 0))
    dialogs.unexpected.clear()


# -- 알림 ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("severity", "kind"),
    [
        ("info", "info"),
        ("warn", "warning"),
        ("warning", "warning"),
        ("critical", "critical"),
        ("error", "error"),
        ("bogus", "error"),
    ],
)
def test_notify_kinds_match_main_window(qtbot, dialogs, severity, kind):
    from genviewer.views.main_window import MainWindow

    window = MainWindow("localhost")
    qtbot.addWidget(window)

    window.notify(severity, "T", "x")
    dialogs.record_notify(severity, "T", "y")

    assert dialogs.shown == [(kind, "T", "x"), (kind, "T", "y")]


@pytest.mark.parametrize(
    ("method", "kind"),
    [("information", "info"), ("warning", "warning"), ("critical", "critical")],
)
def test_qmessagebox_static_messages_are_recorded(dialogs, method, kind):
    result = getattr(QMessageBox, method)(None, "Database Not Loaded", "x")

    assert result == QMessageBox.Ok
    assert dialogs.shown == [(kind, "Database Not Loaded", "x")]


@pytest.mark.parametrize("func", MESSAGE_FUNCTIONS)
def test_message_functions_are_recorded(dialogs, func):
    for module_name in MESSAGE_MODULES:
        getattr(importlib.import_module(module_name), func)(None, "T", module_name)

    assert dialogs.shown == [(func, "T", name) for name in MESSAGE_MODULES]


# -- GUI 스레드 밖 -----------------------------------------------------------


@pytest.mark.parametrize(
    "call",
    [
        lambda d: d.question(None, "Worker Question", "x"),
        lambda d: d.info(None, "Worker Info", "x"),
        lambda d: d.ask_conflict(None, _conflicts()),
        lambda d: d.record_notify("error", "Worker Notify", "x"),
    ],
    ids=["question", "info", "ask_conflict", "record_notify"],
)
def test_calls_from_worker_thread_are_unexpected(dialogs, call):
    dialogs.answer_question(True)
    dialogs.answer_conflict(RELOAD)
    errors: list[BaseException] = []

    def worker():
        try:
            call(dialogs)
        except AssertionError as exc:
            errors.append(exc)

    thread = threading.Thread(target=worker, name="fake-worker")
    thread.start()
    thread.join(5)

    assert not thread.is_alive()
    assert len(errors) == 1
    assert len(dialogs.unexpected) == 1
    assert "fake-worker" in dialogs.unexpected[0]
    assert dialogs.shown == []
    # 워커 스레드 호출은 답을 쓰지 않는다
    assert dialogs.question(None, "Main Question", "x") is True
    assert dialogs.ask_conflict(None, []) == RELOAD
    dialogs.unexpected.clear()


# -- problems / install ------------------------------------------------------


def test_problems_reports_unused_answers():
    fake = FakeDialogs()  # 설치하지 않은 가짜
    fake.answer_question(True)
    fake.answer_conflict(RELOAD)

    assert len(fake.problems()) == 2

    assert fake.question(None, "T", "x") is True
    assert fake.ask_conflict(None, []) == RELOAD
    assert fake.problems() == []


def test_nested_install_is_undone(dialogs):
    """다시 설치했다 되돌리면 바깥 가짜로 돌아간다. 지난 가짜가 모듈에 남지 않는다."""
    device_table = importlib.import_module("genviewer.views.device_table")
    assert device_table.question == dialogs.question

    with pytest.MonkeyPatch.context() as mp:
        inner = install_dialogs(mp)
        assert device_table.question == inner.question

    assert device_table.question == dialogs.question


# -- 목록 완전성 -------------------------------------------------------------


def _module_name(path: Path) -> str:
    parts = list(path.relative_to(SRC.parent).with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _resolve(node: ast.ImportFrom, module: str, path: Path) -> str:
    if node.level == 0:
        return node.module or ""
    package = module.split(".") if path.name == "__init__.py" else module.split(".")[:-1]
    base = package[: len(package) - (node.level - 1)]
    return ".".join(base + ([node.module] if node.module else []))


def _bindings(target: str) -> set[tuple[str, str]]:
    """`from <target> import name` 을 하는 (모듈, name) 전부."""
    found: set[tuple[str, str]] = set()
    for path in sorted(SRC.rglob("*.py")):
        module = _module_name(path)
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and _resolve(node, module, path) == target:
                found.update((module, alias.name) for alias in node.names)
    return found


def test_every_dialogs_import_is_patched():
    """새 모듈이 question 등을 묶으면 진짜 QMessageBox 가 떠서 테스트가 멈춘다."""
    bindings = _bindings("genviewer.utils.dialogs")
    assert ("genviewer.views.main_window", "info") in bindings  # 스캐너가 동작한다

    missing = []
    for module, name in sorted(bindings):
        if name == "question":
            listed = module in QUESTION_MODULES
        elif name in MESSAGE_FUNCTIONS:
            listed = module in MESSAGE_MODULES
        else:
            listed = False  # 가짜가 모르는 이름
        if not listed:
            missing.append(f"{module}: {name}")
    assert missing == []


def test_every_ask_conflict_import_is_patched():
    bindings = _bindings("genviewer.dialogs.conflict")
    users = sorted(module for module, name in bindings if name == "ask_conflict")
    assert users  # 스캐너가 동작한다
    assert [module for module in users if module not in CONFLICT_MODULES] == []


def test_every_menu_builder_import_is_patched():
    bindings = _bindings("genviewer.utils.menus")
    builders = sorted(binding for binding in bindings if binding[1].startswith("build_"))
    assert builders  # 스캐너가 동작한다
    assert [binding for binding in builders if binding not in MENU_BUILDERS] == []
