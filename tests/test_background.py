"""run_blocking 이 실제로 GUI 스레드를 비우는지 확인한다.

여기가 틀리면 증상이 "가끔 창이 좀 굳는다" 로만 나타나서 알아채기 어렵다.
Qt 애플리케이션이 하나 필요하지만 창은 띄우지 않는다(offscreen).
"""

import os
import threading
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication, QEvent, QObject, QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from genviewer.utils import background  # noqa: E402


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication(["pytest"])
    yield app


def test_runs_on_a_worker_thread(qapp):
    gui_thread = threading.get_ident()
    worker_thread = background.run_blocking(threading.get_ident)
    assert worker_thread != gui_thread


def test_event_loop_keeps_running_while_blocked(qapp):
    """이게 이 모듈의 존재 이유다. 대기 중에도 타이머가 돌아야 한다."""
    ticks = []
    timer = QTimer()
    timer.setInterval(10)
    timer.timeout.connect(lambda: ticks.append(1))
    timer.start()
    try:
        background.run_blocking(lambda: time.sleep(0.3))
    finally:
        timer.stop()

    assert ticks, "run_blocking 이 이벤트 루프를 세웠다 — GUI 가 굳는다"


def test_exception_reaches_the_caller(qapp):
    class Boom(RuntimeError):
        pass

    def explode():
        raise Boom("워커에서 터졌다")

    with pytest.raises(Boom, match="워커에서 터졌다"):
        background.run_blocking(explode)


def test_is_busy_is_true_only_while_running(qapp):
    seen = []
    assert not background.is_busy()
    background.run_blocking(lambda: seen.append(background.is_busy()))
    assert seen == [True]
    assert not background.is_busy()


def test_is_busy_clears_after_a_failure(qapp):
    with pytest.raises(ValueError):
        background.run_blocking(lambda: (_ for _ in ()).throw(ValueError("x")))
    assert not background.is_busy(), "예외가 나도 재진입 가드는 풀려야 한다"


def _tasks_left_under(parent: QObject) -> list:
    """지연 삭제를 처리한 뒤에도 parent 의 자식으로 남은 Task."""
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    return parent.findChildren(background.Task)


def test_a_successful_call_leaves_no_task_under_the_parent(qapp):
    """K22: 컨트롤러가 parent 면 저장·접속마다 끝난 QThread 가 하나씩 쌓였다."""
    parent = QObject()
    assert background.run_blocking(lambda: 1, parent) == 1
    assert _tasks_left_under(parent) == []


def test_a_failed_call_leaves_no_task_under_the_parent(qapp):
    parent = QObject()
    boom = ValueError("x")

    def explode():
        raise boom

    with pytest.raises(ValueError) as excinfo:
        background.run_blocking(explode, parent)
    assert excinfo.value is boom
    assert _tasks_left_under(parent) == []


def test_repeated_calls_do_not_pile_up_tasks_under_the_parent(qapp):
    parent = QObject()
    results = [background.run_blocking(lambda i=i: i, parent) for i in range(5)]
    assert results == [0, 1, 2, 3, 4]
    assert _tasks_left_under(parent) == []


def test_a_task_still_running_when_the_wait_is_interrupted_is_not_released(
    qapp, monkeypatch
):
    """기다림이 예외로 끊기면 워커는 아직 돈다. 돌고 있는 QThread 를 지우면 프로세스가 죽는다."""

    class Interrupted(Exception):
        pass

    def interrupt(*_args):
        raise Interrupted

    parent = QObject()
    release = threading.Event()
    monkeypatch.setattr(QCoreApplication, "processEvents", staticmethod(interrupt))
    try:
        with pytest.raises(Interrupted):
            background.run_blocking(lambda: release.wait(5), parent)
        monkeypatch.undo()

        left = _tasks_left_under(parent)
        assert len(left) == 1
        assert left[0].isRunning()
    finally:
        release.set()
        for task in parent.findChildren(background.Task):
            task.wait()
    assert not background.is_busy()


def test_falls_back_to_a_direct_call_without_qt(monkeypatch):
    """Qt 애플리케이션이 없으면(스크립트/테스트) 그냥 부른다."""
    monkeypatch.setattr(QCoreApplication, "instance", staticmethod(lambda: None))
    assert background.run_blocking(lambda: threading.get_ident()) == threading.get_ident()
