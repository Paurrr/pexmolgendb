"""Virtuoso 소켓 워커와 마지막 예외 그물 (phase 4 step 6).

- 접속하는 동안 Connect 를 또 누르면 실행 중인 ConnectWorker 를 덮어써 프로세스가 죽었다.
  두 번째 호출은 아무것도 바꾸지 않는다.
- 보내기 실패가 SendWorker.run 밖으로 새어 워커 스레드에서 sys.excepthook 이 불렸다. 워커가
  잡아 "ERROR: send failed - …" 를 received 로 넘긴다(받기 오류와 같은 길). 접속 상태는 그대로(K14).
- 창을 닫아도 Receive/Send 워커가 돌고 있었다. ConnectionController.shutdown() 이 멈추고 기다린 뒤
  클라이언트를 닫고, MainWindowController.shutdown() 이 그것을 부른다.
- main.py 의 hook 이 어느 스레드에서 불리든 상자를 열었다. 메인(GUI) 스레드에서만 연다.

실제 서버·포트에 붙지 않는다. 클라이언트는 FakeVirtuosoClient 이고, ReceiveWorker 가 살아 있어야
하는 테스트만 socketpair(로컬 소켓 한 쌍)를 준다. 실행 중인 QThread 를 놓치면 pytest 프로세스가
통째로 죽으므로 `virtuoso` fixture 가 만들어진 워커를 모두 쥐고 있다가 정리 때 멈추고 기다린다.
"""

import contextlib
import logging
import socket
import sys
import threading
from collections.abc import Iterator

import pytest
from gui_support.fakes import FakeVirtuosoClient
from PySide6.QtCore import QCoreApplication, QThread

import genviewer.main
from genviewer.controllers.main_window import MainWindowController
from genviewer.net import controller as net_controller
from genviewer.net.controller import ConnectionController

WORKERS = ("ConnectWorker", "DisconnectWorker", "ReceiveWorker", "SendWorker")
CONNECTED = (True, "Connected")

# 정리 때 5초 안에 끝나지 않은 워커. 참조를 놓으면 실행 중인 QThread 가 지워져 프로세스가 죽는다.
# 끝까지 쥐고 있고 그 테스트는 실패시킨다.
_STUCK: list[QThread] = []


class Virtuoso:
    """ConnectionController 에 넣을 가짜 클라이언트 factory 와, 만들어진 워커 기록."""

    def __init__(self) -> None:
        self.clients: list[FakeVirtuosoClient] = []
        self.threads: list[QThread] = []
        self.controllers: list[ConnectionController] = []
        self.blocked = False  # True 면 새 클라이언트의 connect() 가 release 를 기다린다
        self.with_socket = False  # True 면 ReceiveWorker 가 살아 있도록 socketpair 한쪽을 준다
        self.result: tuple | None = None  # 있으면 새 클라이언트의 connect() 결과
        self._peers: list[socket.socket] = []

    def factory(self, host: str, port: int) -> FakeVirtuosoClient:
        sock = None
        if self.with_socket:
            sock, peer = socket.socketpair()
            self._peers.append(peer)
        client = FakeVirtuosoClient(host, port, sock)
        if self.blocked:
            client.release.clear()
        if self.result is not None:
            client.result = self.result
        self.clients.append(client)
        return client

    def controller(self) -> ConnectionController:
        ctrl = ConnectionController(client_factory=self.factory)
        self.controllers.append(ctrl)
        return ctrl

    def cleanup(self) -> list[QThread]:
        """release.set() → 워커 멈추고 기다림 → _stop_io_workers(). 끝나지 않은 워커를 돌려준다."""
        for client in self.clients:
            client.release.set()
        stuck = self._stop_threads()
        # 끝난 ConnectWorker 의 결과는 아직 GUI 스레드 큐에 있다. 여기서 배달해서 그것이 띄우는
        # IO 워커까지 이 테스트 안에서 끝낸다(다음 테스트 도중에 뜨면 아무도 쥐고 있지 않다).
        QCoreApplication.sendPostedEvents()
        stuck += self._stop_threads()
        for ctrl in self.controllers:
            ctrl._stop_io_workers()
        for peer in self._peers:
            peer.close()
        return stuck

    def _stop_threads(self) -> list[QThread]:
        for thread in self.threads:
            if hasattr(thread, "stop"):
                thread.stop()
        return [thread for thread in self.threads if not thread.wait(5000)]


def _recording(worker_cls: type[QThread], threads: list[QThread]) -> type[QThread]:
    """만들어질 때 threads 에 자기를 남기는 워커. 동작은 원래 클래스 그대로다."""

    class Recording(worker_cls):
        def __init__(self, client) -> None:
            super().__init__(client)
            threads.append(self)

    return Recording


@pytest.fixture
def virtuoso(monkeypatch) -> Iterator[Virtuoso]:
    fakes = Virtuoso()
    for name in WORKERS:
        monkeypatch.setattr(
            net_controller, name, _recording(getattr(net_controller, name), fakes.threads)
        )
    yield fakes
    stuck = fakes.cleanup()
    if stuck:
        _STUCK.extend(stuck)
        names = [type(t).__mro__[1].__name__ for t in stuck]
        pytest.fail(f"정리 때 끝나지 않은 워커: {names}", pytrace=False)


def record(signal) -> list[tuple]:
    got: list[tuple] = []
    signal.connect(lambda *args: got.append(args))
    return got


def connect_and_wait(qtbot, ctrl: ConnectionController) -> FakeVirtuosoClient:
    ctrl.connect("h", 1)
    qtbot.waitUntil(lambda: ctrl.is_connected)
    return ctrl.client


# -- (a) 접속 중 다시 connect ---------------------------------------------------


def test_connect_while_connecting_is_ignored(qtbot, virtuoso):
    virtuoso.blocked = True
    ctrl = virtuoso.controller()
    statuses = record(ctrl.statusChanged)

    ctrl.connect("h", 1)
    first = ctrl._connectWorker
    assert first.isRunning()

    ctrl.connect("h", 1)

    assert len(virtuoso.clients) == 1
    assert ctrl._connectWorker is first
    assert ctrl.client is virtuoso.clients[0]
    assert statuses == []

    virtuoso.clients[0].release.set()
    qtbot.waitUntil(lambda: ctrl.is_connected)
    assert statuses == [CONNECTED]
    assert ctrl.client is virtuoso.clients[0]


def test_connect_after_a_failed_attempt_tries_again(qtbot, virtuoso):
    ctrl = virtuoso.controller()
    statuses = record(ctrl.statusChanged)
    virtuoso.result = ("Connect", "ConnectionRefused", False)

    ctrl.connect("h", 1)
    qtbot.waitUntil(lambda: statuses == [(False, "ConnectionRefused")])
    first = ctrl._connectWorker
    assert first.wait(5000)  # 결과는 run() 이 끝나기 전에 온다

    virtuoso.result = None
    ctrl.connect("h", 1)

    assert len(virtuoso.clients) == 2
    assert ctrl._connectWorker is not first
    qtbot.waitUntil(lambda: ctrl.is_connected)
    assert ctrl.client is virtuoso.clients[1]
    assert statuses == [(False, "ConnectionRefused"), CONNECTED]


# -- (b) 보내기 실패 -------------------------------------------------------------


def test_a_failed_send_comes_back_as_a_received_error(qtbot, virtuoso, caplog):
    ctrl = virtuoso.controller()
    statuses = record(ctrl.statusChanged)
    received = record(ctrl.received)
    fake = connect_and_wait(qtbot, ctrl)
    fake.send_error = ConnectionResetError(10054, "reset")
    sw = ctrl._sendWorker

    hooked: list[tuple[str, str]] = []
    old = sys.excepthook
    sys.excepthook = lambda t, e, tb: hooked.append((t.__name__, threading.current_thread().name))
    try:
        ctrl.send("x")
        qtbot.waitUntil(lambda: fake.sent != [])
        qtbot.waitUntil(lambda: not sw.isRunning())
    finally:
        sys.excepthook = old

    assert hooked == []
    expected = f"ERROR: send failed - {fake.send_error}"
    qtbot.waitUntil(lambda: (expected,) in received)
    assert fake.sent == ["x"]
    # 끊김을 접속 상태에 반영하지 않는다(K14).
    assert statuses == [CONNECTED]
    assert ctrl.is_connected
    assert [
        r for r in caplog.records
        if r.name == "genviewer.net.workers" and r.levelno == logging.WARNING and r.exc_info
    ]

    # 그 뒤의 보내기는 지금처럼 무시된다.
    ctrl.send("y")
    assert statuses[-1] == (False, "Not connected (send ignored)")
    assert fake.sent == ["x"]


def test_a_failed_send_shows_in_the_socket_tab(qtbot, main_window, virtuoso):
    virtuoso.with_socket = True  # 소켓이 없으면 ReceiveWorker 의 "DISCONNECTED" 가 수신 칸을 덮는다
    conn = main_window.connection_controller
    conn._client_factory = virtuoso.factory
    virtuoso.controllers.append(conn)
    fake = connect_and_wait(qtbot, conn)
    fake.send_error = BrokenPipeError(32, "Broken pipe")

    hooked: list[str] = []
    old = sys.excepthook
    sys.excepthook = lambda t, e, tb: hooked.append(t.__name__)
    try:
        conn.send("x")
        recv = main_window.socket_tab.ui.recv_msg_te
        qtbot.waitUntil(lambda: recv.toPlainText().startswith("ERROR: send failed"))
    finally:
        sys.excepthook = old

    assert hooked == []
    assert recv.toPlainText() == f"ERROR: send failed - {fake.send_error}"


# -- (c) 창을 닫을 때 ------------------------------------------------------------


def test_shutdown_stops_the_io_workers_and_closes_the_client(qtbot, virtuoso):
    virtuoso.with_socket = True
    ctrl = virtuoso.controller()
    statuses = record(ctrl.statusChanged)
    fake = connect_and_wait(qtbot, ctrl)
    rw, sw = ctrl._receiveWorker, ctrl._sendWorker
    assert rw.isRunning() and sw.isRunning()

    ctrl.shutdown()

    assert rw.isFinished()
    assert sw.isFinished()
    assert ctrl._receiveWorker is None
    assert ctrl._sendWorker is None
    assert fake.calls == ["connect", "close"]
    assert ctrl.client is None
    assert statuses == [CONNECTED]  # 창이 닫히는 중이다. 상태를 알리지 않는다

    ctrl.shutdown()  # 두 번 불러도 된다

    assert fake.calls == ["connect", "close"]
    assert statuses == [CONNECTED]


def test_shutdown_before_connecting_does_nothing(qtbot, virtuoso):
    ctrl = virtuoso.controller()
    statuses = record(ctrl.statusChanged)

    ctrl.shutdown()
    ctrl.shutdown()

    assert statuses == []
    assert virtuoso.clients == []
    assert virtuoso.threads == []


def test_closing_the_window_stops_the_socket_workers(
    qtbot, main_window: MainWindowController, virtuoso
):
    virtuoso.with_socket = True
    conn = main_window.connection_controller
    conn._client_factory = virtuoso.factory
    virtuoso.controllers.append(conn)
    fake = connect_and_wait(qtbot, conn)
    rw, sw = conn._receiveWorker, conn._sendWorker
    assert rw.isRunning() and sw.isRunning()

    main_window.shutdown()  # fixture 정리가 한 번 더 부른다

    assert rw.isFinished()
    assert sw.isFinished()
    assert fake.calls == ["connect", "close"]


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
