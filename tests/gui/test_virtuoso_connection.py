"""Virtuoso 접속(ConnectionController)의 지금 동작을 공개 API 로 고정한다 (phase 13 step 0).

step 2 가 `net/` 을 QTcpSocket 하나로 다시 쓴다. 이 테스트는 그때도 그대로 통과해야 하는 그물이라
공개 API 만 쓴다: `connect(host, port)`, `disconnect()`, `send(msg)`, `shutdown()`, `is_connected`,
시그널 `received(str)`·`statusChanged(bool, str)`. 상대는 127.0.0.1 에 테스트가 띄운
`LocalVirtuoso` 이고, 접속 거부는 닫힌 포트(127.0.0.1:1)로 만든다.

알려진 버그(K14·K24·K39·K40)는 strict xfail 로 재현한다. K39·K40 은 실행 중인 QThread 를 놓쳐
프로세스가 죽으므로 서브프로세스(`gui_support.virtuoso_child`)에서 돌린다.
"""

import json
import os
import subprocess
import sys
import time
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from gui_support.virtuoso_server import LocalVirtuoso, frame
from PySide6.QtCore import QCoreApplication, QThread

from genviewer.net.controller import ConnectionController

HOST = "127.0.0.1"
CLOSED_PORT = 1
CONNECTED = (True, "Connected")
DISCONNECTED = (False, "Disconnected")
PEER_CLOSED_MESSAGE = "ERROR: recv failed - Server connection closed"
TESTS_DIR = Path(__file__).resolve().parents[1]

# 정리 때 5초 안에 끝나지 않은 스레드. 참조를 놓으면 실행 중인 QThread 가 지워져 프로세스가 죽는다.
# 끝까지 쥐고 있고 그 테스트는 실패시킨다(test_socket_workers.py 의 _STUCK 과 같은 이유).
_STUCK: list[QThread] = []


@pytest.fixture
def server() -> Iterator[LocalVirtuoso]:
    srv = LocalVirtuoso()
    yield srv
    srv.close()  # 멱등. make_controller 정리가 먼저 불렀을 수 있다


@pytest.fixture
def make_controller(server) -> Iterator[Callable[[], ConnectionController]]:
    made: list[ConnectionController] = []

    def make() -> ConnectionController:
        ctrl = ConnectionController()
        made.append(ctrl)
        return ctrl

    yield make

    # 1. 서버를 먼저 닫는다. 연결이 닫혀야 막혀 있는 recv 가 풀린다.
    server.close()
    stuck: list[QThread] = []
    for ctrl in made:
        # 2. 창을 닫을 때처럼 멈춘다.
        ctrl.shutdown()
        # 3. step 0 한정: shutdown 이 기다리지 않는 접속·끊기 워커를 기다린다(private, 정리용).
        #    step 2 가 이 줄을 지운다.
        for name in ("_connectWorker", "_disconnectWorker"):
            worker = getattr(ctrl, name, None)
            if worker is not None and not worker.wait(5000):
                stuck.append(worker)
    # 끝난 워커의 결과가 아직 큐에 있으면 여기서 배달하고, 그것이 띄운 것까지 다시 멈춘다.
    QCoreApplication.sendPostedEvents()
    for ctrl in made:
        ctrl.shutdown()
    if stuck:
        # 4. 놓으면 프로세스가 죽는다. 쥐고 있고 이 테스트는 실패시킨다.
        _STUCK.extend(stuck)
        names = [type(t).__name__ for t in stuck]
        pytest.fail(f"정리 때 끝나지 않은 스레드: {names}", pytrace=False)


def record(signal) -> list[tuple]:
    got: list[tuple] = []
    signal.connect(lambda *args: got.append(args))
    return got


def record_received(ctrl: ConnectionController) -> list[str]:
    got: list[str] = []
    ctrl.received.connect(got.append)
    return got


def connect_and_wait(qtbot, ctrl: ConnectionController, server: LocalVirtuoso, n: int = 1) -> None:
    """붙고, 서버가 n 번째 연결을 받을 때까지 기다린다."""
    ctrl.connect(HOST, server.port)
    qtbot.waitUntil(lambda: ctrl.is_connected)
    qtbot.waitUntil(lambda: server.accepted == n)


# -- 접속 ------------------------------------------------------------------------


def test_connect_reports_connected(qtbot, server, make_controller):
    ctrl = make_controller()
    statuses = record(ctrl.statusChanged)

    connect_and_wait(qtbot, ctrl, server)

    assert statuses == [CONNECTED]
    assert ctrl.is_connected
    assert server.accepted == 1


def test_connect_to_a_closed_port_is_refused(qtbot, make_controller):
    ctrl = make_controller()
    statuses = record(ctrl.statusChanged)

    ctrl.connect(HOST, CLOSED_PORT)
    # Windows 는 거부된 SYN 을 몇 번 다시 보내서 약 2초 걸린다.
    qtbot.waitUntil(lambda: statuses != [], timeout=10000)

    assert statuses == [(False, "ConnectionRefused")]
    assert not ctrl.is_connected


def test_connect_while_connected_says_already_connected(qtbot, server, make_controller):
    ctrl = make_controller()
    statuses = record(ctrl.statusChanged)
    connect_and_wait(qtbot, ctrl, server)

    ctrl.connect(HOST, server.port)

    assert statuses[-1] == (True, f"Already connected: {HOST}:{server.port}")
    assert ctrl.is_connected
    assert server.accepted == 1


# -- 보내기·받기 -------------------------------------------------------------------


def test_send_writes_length_prefixed_utf8_frames(qtbot, server, make_controller):
    ctrl = make_controller()
    connect_and_wait(qtbot, ctrl, server)

    ctrl.send("abc")
    ctrl.send("가나")

    qtbot.waitUntil(lambda: len(server.frames()) == 2)
    assert server.frames() == [b"abc", "가나".encode()]
    assert server.data().startswith(b"\x00\x00\x00\x03abc")


def test_received_frames_come_out_in_order(qtbot, server, make_controller):
    ctrl = make_controller()
    received = record_received(ctrl)
    connect_and_wait(qtbot, ctrl, server)

    server.send_frame("hello")
    server.send_frame("안녕하세요")
    server.send_raw(frame("one") + frame("two"))  # 한 번의 쓰기에 프레임 둘
    qtbot.waitUntil(lambda: len(received) == 4)

    split = frame("나눠 보낸 프레임")
    server.send_raw(split[:6])  # 머리와 본문 일부
    qtbot.wait(100)  # 앞 조각이 클라이언트에 닿을 시간. 단언용 대기가 아니다
    server.send_raw(split[6:])
    qtbot.waitUntil(lambda: len(received) == 5)

    assert received == ["hello", "안녕하세요", "one", "two", "나눠 보낸 프레임"]


# -- 끊기 ------------------------------------------------------------------------


def test_disconnect_reports_disconnected_and_closes_the_socket(qtbot, server, make_controller):
    ctrl = make_controller()
    statuses = record(ctrl.statusChanged)
    received = record_received(ctrl)
    connect_and_wait(qtbot, ctrl, server)

    ctrl.disconnect()

    qtbot.waitUntil(lambda: statuses[-1] == DISCONNECTED)
    assert statuses == [CONNECTED, DISCONNECTED]
    assert not ctrl.is_connected
    assert received == []  # 내가 끊으면 Socket 탭으로 아무것도 보내지 않는다
    qtbot.waitUntil(server.peer_closed)


def test_disconnect_before_connecting(qtbot, make_controller):
    ctrl = make_controller()
    statuses = record(ctrl.statusChanged)

    ctrl.disconnect()

    assert statuses == [(False, "No active connection")]
    assert not ctrl.is_connected


def test_send_without_a_connection_is_ignored(qtbot, server, make_controller):
    ctrl = make_controller()
    statuses = record(ctrl.statusChanged)

    ctrl.send("abc")

    assert statuses[-1] == (False, "Not connected (send ignored)")
    assert server.accepted == 0
    assert server.data() == b""


def test_shutdown_after_connecting_closes_quietly(qtbot, server, make_controller):
    ctrl = make_controller()
    statuses = record(ctrl.statusChanged)
    connect_and_wait(qtbot, ctrl, server)

    ctrl.shutdown()

    qtbot.waitUntil(server.peer_closed)
    assert statuses == [CONNECTED]  # 창이 닫히는 중이다. 상태를 알리지 않는다

    ctrl.shutdown()  # 두 번 불러도 된다

    assert statuses == [CONNECTED]


def test_shutdown_before_connecting_does_nothing(qtbot, make_controller):
    ctrl = make_controller()
    statuses = record(ctrl.statusChanged)

    ctrl.shutdown()
    ctrl.shutdown()

    assert statuses == []
    assert not ctrl.is_connected


def test_connect_again_after_disconnecting(qtbot, server, make_controller):
    ctrl = make_controller()
    statuses = record(ctrl.statusChanged)
    received = record_received(ctrl)
    connect_and_wait(qtbot, ctrl, server)
    ctrl.disconnect()
    qtbot.waitUntil(lambda: statuses[-1] == DISCONNECTED)

    connect_and_wait(qtbot, ctrl, server, n=2)

    assert statuses == [CONNECTED, DISCONNECTED, CONNECTED]
    assert server.accepted == 2
    ctrl.send("again")
    qtbot.waitUntil(lambda: server.frames() == [b"again"])
    server.send_frame("back")
    qtbot.waitUntil(lambda: received == ["back"])


# -- 버그 재현 (strict xfail) ------------------------------------------------------


@pytest.mark.xfail(strict=True, reason="K14: 상대가 닫아도 상태가 Connected 로 남는다")
def test_peer_closing_reports_disconnected(qtbot, server, make_controller):
    ctrl = make_controller()
    statuses = record(ctrl.statusChanged)
    received = record_received(ctrl)
    connect_and_wait(qtbot, ctrl, server)

    server.close_peer()

    qtbot.waitUntil(lambda: received != [])
    qtbot.waitUntil(lambda: statuses[-1] == DISCONNECTED, timeout=2000)
    assert received == [PEER_CLOSED_MESSAGE]  # 문구는 지금 그대로(사용자 확인 2026-10-17)
    assert not ctrl.is_connected


@pytest.mark.xfail(strict=True, reason="K14: UTF-8 이 아닌 프레임 뒤에도 상태가 Connected 다")
def test_a_non_utf8_frame_reports_an_error_and_disconnects(qtbot, server, make_controller):
    ctrl = make_controller()
    statuses = record(ctrl.statusChanged)
    received = record_received(ctrl)
    connect_and_wait(qtbot, ctrl, server)

    server.send_frame(b"\xff\xfe")

    qtbot.waitUntil(lambda: received != [])
    assert len(received) == 1
    assert received[0].startswith("ERROR: recv failed - ")
    qtbot.waitUntil(lambda: statuses[-1] == DISCONNECTED, timeout=2000)
    assert not ctrl.is_connected
    qtbot.waitUntil(server.peer_closed)


@pytest.mark.xfail(strict=True, reason="K14: 0바이트 프레임을 끊김으로 보고 수신을 멈춘다")
def test_an_empty_frame_is_not_a_disconnect(qtbot, server, make_controller):
    ctrl = make_controller()
    statuses = record(ctrl.statusChanged)
    received = record_received(ctrl)
    connect_and_wait(qtbot, ctrl, server)

    server.send_raw(b"\x00\x00\x00\x00")
    server.send_frame("hello")

    qtbot.waitUntil(lambda: received == ["hello"], timeout=2000)
    assert ctrl.is_connected
    assert statuses == [CONNECTED]


@pytest.mark.xfail(strict=True, reason="K24: 프레임 중간에서 상대가 멈추면 끊기가 굳는다")
def test_disconnect_does_not_wait_for_a_half_received_frame(qtbot, server, make_controller):
    ctrl = make_controller()
    statuses = record(ctrl.statusChanged)
    received = record_received(ctrl)
    connect_and_wait(qtbot, ctrl, server)

    # 완전한 프레임 하나와, 100바이트라고 적은 머리 + 10바이트.
    server.send_raw(frame("first") + (100).to_bytes(4, byteorder="big") + b"x" * 10)
    server.close_peer_after(3.0)  # 지금 코드가 영원히 멈추지 않게 3초 뒤 연결을 닫는다
    qtbot.waitUntil(lambda: received == ["first"])
    time.sleep(0.2)  # 이벤트를 돌리지 않고 수신 쪽이 프레임 중간에서 막히게 둔다. 단언용이 아니다

    started = time.monotonic()
    ctrl.disconnect()
    elapsed = time.monotonic() - started

    assert elapsed < 1.0
    qtbot.waitUntil(lambda: statuses[-1] == DISCONNECTED)


def run_child(case: str) -> subprocess.CompletedProcess:
    env = {
        **os.environ,
        "QT_QPA_PLATFORM": "offscreen",
        # Windows 에서 stderr 가 파이프면 Qt 는 qFatal 문구를 디버거 출력으로 보낸다.
        "QT_FORCE_STDERR_LOGGING": "1",
        "PYTHONIOENCODING": "utf-8",
        "PYTHONPATH": os.pathsep.join(
            p for p in (str(TESTS_DIR), os.environ.get("PYTHONPATH", "")) if p
        ),
    }
    return subprocess.run(
        [sys.executable, "-m", "gui_support.virtuoso_child", case],
        timeout=30,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )


def describe(proc: subprocess.CompletedProcess) -> str:
    tail = "\n".join(proc.stderr.splitlines()[-8:])
    return f"rc={proc.returncode:#x}\nstdout:\n{proc.stdout}\nstderr(끝):\n{tail}"


@pytest.mark.xfail(strict=True, reason="K39: 접속하는 동안 창을 닫으면 프로세스가 죽는다")
def test_closing_the_window_while_connecting_does_not_crash():
    proc = run_child("k39")

    assert proc.returncode == 0, describe(proc)
    assert proc.stdout.splitlines()[-1:] == ["OK"], describe(proc)


@pytest.mark.xfail(strict=True, reason="K40: 결과 전의 두 번째 Connect 가 워커를 덮어써 죽는다")
def test_a_second_connect_before_the_result_makes_one_connection():
    proc = run_child("k40")

    assert proc.returncode == 0, describe(proc)
    lines = proc.stdout.splitlines()
    assert lines[-1:] == ["OK"], describe(proc)
    result = json.loads(lines[-2])
    assert result["accepted"] == 1, describe(proc)
    assert result["connected"], describe(proc)
