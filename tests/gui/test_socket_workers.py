"""마지막 예외 그물 (phase 4 step 6).

main.py 의 hook 이 어느 스레드에서 불리든 상자를 열었다. 메인(GUI) 스레드에서만 연다.

여기 있던 Virtuoso 소켓 워커 테스트((a) 접속 중 다시 connect, (b) 보내기 실패, (c) 창을 닫을 때)는
phase 13 이 `net/` 을 GUI 스레드의 QTcpSocket 하나로 바꾸며 지웠다(워커가 없다). 그 성질은
`test_virtuoso_connection.py` 가 공개 API 로 덮는다.
"""

import contextlib
import logging
import sys
import threading
from collections.abc import Iterator

from PySide6.QtCore import QThread

import genviewer.main

# -- (d) 마지막 예외 그물 ---------------------------------------------------------


@contextlib.contextmanager
def app_excepthooks() -> Iterator[None]:
    """genviewer.main 의 hook 을 걸고, 블록을 나갈 때 둘 다 되돌린다.

    monkeypatch 로 되돌리면 안 된다. pytest-qt 는 테스트 호출 구간에만 자기 hook 을 걸었다 푸는데,
    monkeypatch 정리는 그 뒤(teardown)에 돌아 pytest-qt 의 hook 을 되살려 놓는다.
    """
    old, old_thread = sys.excepthook, threading.excepthook
    try:
        genviewer.main.install_excepthooks()
        yield
    finally:
        sys.excepthook, threading.excepthook = old, old_thread


def record_unexpected(monkeypatch) -> list[tuple[str, str]]:
    """상자 대신 (예외, 부른 스레드 이름) 을 남긴다."""
    shown: list[tuple[str, str]] = []
    monkeypatch.setattr(
        genviewer.main,
        "_show_unexpected",
        lambda exc: shown.append((repr(exc), threading.current_thread().name)),
    )
    return shown


def unhandled_logged(caplog, exc: BaseException) -> bool:
    return any(
        r.name == "genviewer.main"
        and r.levelno == logging.CRITICAL
        and r.getMessage() == "처리되지 않은 예외"
        and r.exc_info[1] is exc
        for r in caplog.records
    )


class RaisingThread(QThread):
    def __init__(self, exc: BaseException) -> None:
        super().__init__()
        self.exc = exc

    def run(self) -> None:
        raise self.exc


def test_the_hook_called_from_a_python_thread_only_logs(monkeypatch, caplog):
    shown = record_unexpected(monkeypatch)
    error = RuntimeError("boom")

    with app_excepthooks():
        thread = threading.Thread(
            target=lambda: sys.excepthook(type(error), error, None), name="worker"
        )
        thread.start()
        thread.join(5)

    assert shown == []
    assert unhandled_logged(caplog, error)


def test_an_exception_escaping_qthread_run_only_logs(qtbot, monkeypatch, caplog):
    shown = record_unexpected(monkeypatch)
    error = RuntimeError("boom in QThread.run")
    thread = RaisingThread(error)

    with app_excepthooks():
        thread.start()
        assert thread.wait(5000)

    assert shown == []
    assert unhandled_logged(caplog, error)


def test_an_unhandled_exception_on_the_main_thread_still_shows_the_box(monkeypatch, caplog):
    shown = record_unexpected(monkeypatch)
    error = RuntimeError("boom")

    with app_excepthooks():
        sys.excepthook(type(error), error, None)

    assert shown == [(repr(error), threading.main_thread().name)]
    assert unhandled_logged(caplog, error)
