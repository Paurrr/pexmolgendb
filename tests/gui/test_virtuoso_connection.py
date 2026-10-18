"""Virtuoso 접속(ConnectionController)을 공개 API 로 고정한다 (phase 13).

`net/` 은 step 2 부터 GUI 스레드의 QTcpSocket 하나다. 이 테스트는 다음 구조 변경 때도 그물이 되도록
공개 API 만 쓴다: `connect(host, port)`, `disconnect()`, `send(msg)`, `shutdown()`, `is_connected`,
시그널 `received(str)`·`statusChanged(bool, str)`. 상대는 127.0.0.1 에 테스트가 띄운
`LocalVirtuoso` 이고, 접속 거부는 닫힌 포트(127.0.0.1:1)로 만든다.

step 0 이 strict xfail 로 재현한 버그(K14·K24·K39·K40)는 step 2 가 고쳤다. K39·K40 은 되살아나면
프로세스가 죽으므로 계속 서브프로세스(`gui_support.virtuoso_child`)에서 돌린다.

늦게 올 수 있는 신호(앞 시도의 접속 결과, 두 번째 상태 신호)가 없다는 것은 고정 대기 대신, 붙은
채로 한 번 주고받은 뒤(`exchange`) 기록을 보고 단언한다. 그동안 이벤트를 여러 번 돌렸다.
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
from PySide6.QtCore import QEventLoop, QTimer

from genviewer.controllers.main_window import MainWindowController
from genviewer.net.controller import ConnectionController

HOST = "127.0.0.1"
CLOSED_PORT = 1
CONNECTED = (True, "Connected")
DISCONNECTED = (False, "Disconnected")
PEER_CLOSED_MESSAGE = "ERROR: recv failed - Server connection closed"
TESTS_DIR = Path(__file__).resolve().parents[1]


@pytest.fixture
def server() -> Iterator[LocalVirtuoso]:
    srv = LocalVirtuoso()
    yield srv
    srv.close()  # 멱등. make_controller 정리가 먼저 불렀을 수 있다


def stop_controllers(server: LocalVirtuoso, made: list[ConnectionController]) -> None:
    """테스트가 쓴 컨트롤러를 창을 닫을 때처럼 멈추고 서버를 닫는다."""
    for ctrl in made:
        ctrl.shutdown()
    server.close()


@pytest.fixture
def make_controller(server) -> Iterator[Callable[[], ConnectionController]]:
    made: list[ConnectionController] = []

    def make() -> ConnectionController:
        ctrl = ConnectionController()
        made.append(ctrl)
        return ctrl

    yield make
    stop_controllers(server, made)


@pytest.fixture
def window(main_window, server) -> Iterator[MainWindowController]:
    """`main_window` 이고, 그 `connection_controller` 를 make_controller 와 같은 순서로 정리한다.

    pytest-qt 는 fixture 정리보다 먼저 창을 닫는다. 그때 `main_window` 의 before_close_func 가
    `shutdown()` 을 한 번 부르고, 여기서 한 번 더 부른다(여러 번 불러도 된다).
    """
    yield main_window
    stop_controllers(server, [main_window.connection_controller])


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


def exchange(qtbot, ctrl: ConnectionController, server: LocalVirtuoso, received: list[str]) -> None:
    """붙은 채로 "ping" 을 보내고 "pong" 을 받는다. 늦게 올 신호가 있었다면 그동안 왔다.

    "ping" 이 닿은 연결이 마지막 연결이므로 "pong" 은 지금 연결로 간다(앞 시도의 연결이 서버에
    늦게 기록됐더라도).
    """
    ctrl.send("ping")
    qtbot.waitUntil(lambda: server.frames()[-1:] == [b"ping"])
    server.send_frame("pong")
    qtbot.waitUntil(lambda: received[-1:] == ["pong"])


def decode_error_message(data: bytes) -> str:
    try:
        data.decode()
    except UnicodeDecodeError as e:
        return f"ERROR: recv failed - {e}"
    raise AssertionError("UTF-8 로 읽히는 바이트다")


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


def test_connect_again_after_a_refused_attempt(qtbot, server, make_controller):
    ctrl = make_controller()
    statuses = record(ctrl.statusChanged)
    ctrl.connect(HOST, CLOSED_PORT)
    qtbot.waitUntil(lambda: statuses != [], timeout=10000)

    connect_and_wait(qtbot, ctrl, server)

    assert statuses == [(False, "ConnectionRefused"), CONNECTED]


@pytest.mark.parametrize("port", [70000, -1])
def test_connect_to_an_out_of_range_port_reports_an_error(qtbot, server, make_controller, port):
    ctrl = make_controller()
    statuses = record(ctrl.statusChanged)

    ctrl.connect(HOST, port)
    qtbot.waitUntil(lambda: statuses != [])

    # 파이썬 socket 이 내던 문구 그대로다. 접속 중으로 남지 않는다.
    assert statuses == [(False, "Error: connect(): port must be 0-65535.")]
    assert not ctrl.is_connected
    connect_and_wait(qtbot, ctrl, server)


def test_connect_while_connecting_is_ignored(qtbot, server, make_controller):
    ctrl = make_controller()
    statuses = record(ctrl.statusChanged)
    received = record_received(ctrl)

    ctrl.connect(HOST, server.port)
    ctrl.connect(HOST, server.port)  # 결과 전(이벤트를 돌리지 않았다)

    assert statuses == []
    qtbot.waitUntil(lambda: ctrl.is_connected)
    exchange(qtbot, ctrl, server, received)
    assert statuses == [CONNECTED]
    assert server.accepted == 1


def test_disconnect_while_connecting_stops_the_attempt(qtbot, server, make_controller):
    ctrl = make_controller()
    statuses = record(ctrl.statusChanged)
    received = record_received(ctrl)

    ctrl.connect(HOST, server.port)
    ctrl.disconnect()  # 결과 전

    assert statuses == [DISCONNECTED]
    assert not ctrl.is_connected
    # 다시 붙는다. 앞 시도의 결과("Connected")는 주고받는 동안에도 오지 않는다.
    ctrl.connect(HOST, server.port)
    qtbot.waitUntil(lambda: ctrl.is_connected)
    exchange(qtbot, ctrl, server, received)
    assert statuses == [DISCONNECTED, CONNECTED]
    assert received == ["pong"]


def test_shutdown_while_connecting_is_quiet(qtbot, server, make_controller):
    ctrl = make_controller()
    statuses = record(ctrl.statusChanged)
    received = record_received(ctrl)

    ctrl.connect(HOST, server.port)
    ctrl.shutdown()  # 결과 전. 창이 닫히는 중이라 알리지 않는다

    assert statuses == []
    assert not ctrl.is_connected
    # 앞 시도의 결과가 늦게 오지 않는지 보려고 같은 컨트롤러로 다시 붙어 주고받는다.
    ctrl.connect(HOST, server.port)
    qtbot.waitUntil(lambda: ctrl.is_connected)
    exchange(qtbot, ctrl, server, received)
    assert statuses == [CONNECTED]


def test_send_while_connecting_is_ignored(qtbot, server, make_controller):
    ctrl = make_controller()
    statuses = record(ctrl.statusChanged)
    received = record_received(ctrl)

    ctrl.connect(HOST, server.port)
    ctrl.send("early")

    assert statuses == [(False, "Not connected (send ignored)")]
    qtbot.waitUntil(lambda: ctrl.is_connected)
    exchange(qtbot, ctrl, server, received)
    assert server.frames() == [b"ping"]  # "early" 는 쓰지 않았다


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


@pytest.mark.parametrize("then_close", [False, True], ids=["stays", "closes"])
def test_frames_that_arrive_while_a_receiver_waits_still_come_out(
    qtbot, server, make_controller, then_close
):
    # received 를 받은 쪽이 모달을 띄운 동안 온 프레임이다. 예: DeviceList 의 Refresh 질문 중에
    # 오는 LibraryList(Load Virtuoso 는 두 요청을 잇달아 보낸다).
    ctrl = make_controller()
    received = record_received(ctrl)
    connect_and_wait(qtbot, ctrl, server)

    def wait_like_a_modal(text: str) -> None:
        if text != "first":
            return
        server.send_frame("second")
        if then_close:
            server.close_peer()
        loop = QEventLoop()
        QTimer.singleShot(300, loop.quit)
        loop.exec()

    ctrl.received.connect(wait_like_a_modal)
    server.send_frame("first")

    expected = ["first", "second"] + ([PEER_CLOSED_MESSAGE] if then_close else [])
    qtbot.waitUntil(lambda: received == expected)


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


def test_reconnecting_after_disconnecting_mid_frame_starts_clean(qtbot, server, make_controller):
    ctrl = make_controller()
    statuses = record(ctrl.statusChanged)
    received = record_received(ctrl)
    connect_and_wait(qtbot, ctrl, server)
    # 완전한 프레임 하나와, 100바이트라고 적은 머리 + 10바이트.
    server.send_raw(frame("first") + (100).to_bytes(4, byteorder="big") + b"x" * 10)
    qtbot.waitUntil(lambda: received == ["first"])

    ctrl.disconnect()
    connect_and_wait(qtbot, ctrl, server, n=2)
    exchange(qtbot, ctrl, server, received)

    assert received == ["first", "pong"]  # 반쯤 받은 프레임은 새 연결로 넘어가지 않는다
    assert statuses == [CONNECTED, DISCONNECTED, CONNECTED]


def test_send_after_the_peer_closed_is_ignored(qtbot, server, make_controller):
    ctrl = make_controller()
    statuses = record(ctrl.statusChanged)
    connect_and_wait(qtbot, ctrl, server)
    server.close_peer()
    qtbot.waitUntil(lambda: statuses[-1] == DISCONNECTED)

    ctrl.send("abc")

    assert statuses[-1] == (False, "Not connected (send ignored)")
    assert server.data() == b""


def close_peer(server: LocalVirtuoso) -> str:
    server.close_peer()
    return PEER_CLOSED_MESSAGE


def close_peer_mid_frame(server: LocalVirtuoso) -> str:
    server.send_raw((100).to_bytes(4, byteorder="big") + b"x" * 10)
    server.close_peer()
    return PEER_CLOSED_MESSAGE  # 반쯤 받은 프레임은 버린다


def send_non_utf8(server: LocalVirtuoso) -> str:
    server.send_frame(b"\xff\xfe")
    return decode_error_message(b"\xff\xfe")


@pytest.mark.parametrize("lose", [close_peer, close_peer_mid_frame, send_non_utf8])
def test_a_lost_connection_reports_once(qtbot, server, make_controller, lose):
    ctrl = make_controller()
    statuses = record(ctrl.statusChanged)
    received = record_received(ctrl)
    connect_and_wait(qtbot, ctrl, server)

    message = lose(server)
    qtbot.waitUntil(lambda: statuses[-1] == DISCONNECTED)
    # 다시 붙어 주고받는다. 두 번째 알림이나 남은 바이트가 있었다면 그동안 드러난다.
    connect_and_wait(qtbot, ctrl, server, n=2)
    exchange(qtbot, ctrl, server, received)

    assert statuses == [CONNECTED, DISCONNECTED, CONNECTED]
    assert received == [message, "pong"]


# -- 창: Load Virtuoso 의 목록 표시 -------------------------------------------------
# "Device List"·"Filtered List" 는 DB 와 Virtuoso 에 둘 다 붙어 있을 때만 보인다(UI_GUIDE 레이아웃).


def virtuoso_lists_hidden(window: MainWindowController) -> tuple[bool, bool]:
    ui = window.device_tab.ui
    return (ui.search_labeled_virtuoso_device.isHidden(), ui.search_labeled_filter.isHidden())


def test_load_virtuoso_keeps_the_lists_hidden_before_connecting(window):
    assert window.device_tab.connected  # DB 에는 붙어 있다. Virtuoso 만 아니다

    window.device_tab.device_tab_toolbar.show_views()

    assert virtuoso_lists_hidden(window) == (True, True)


def test_load_virtuoso_shows_the_lists_while_connected(qtbot, server, window):
    connect_and_wait(qtbot, window.connection_controller, server)

    window.device_tab.device_tab_toolbar.show_views()

    assert virtuoso_lists_hidden(window) == (False, False)


def test_load_virtuoso_hides_the_lists_again_after_disconnecting(qtbot, server, window):
    ctrl = window.connection_controller
    statuses = record(ctrl.statusChanged)
    connect_and_wait(qtbot, ctrl, server)
    window.device_tab.device_tab_toolbar.show_views()
    assert virtuoso_lists_hidden(window) == (False, False)

    ctrl.disconnect()
    qtbot.waitUntil(lambda: statuses[-1] == DISCONNECTED)

    assert virtuoso_lists_hidden(window) == (False, False)  # 끊는다고 숨기지는 않는다(지금 동작)
    window.device_tab.ui.hide_views()  # process 를 바꾸면 숨긴다
    window.device_tab.device_tab_toolbar.show_views()

    assert virtuoso_lists_hidden(window) == (True, True)


# -- 창: Socket 탭과 툴바 상태 -----------------------------------------------------


def test_peer_closing_shows_in_the_socket_tab_and_the_toolbar(qtbot, server, window):
    connect_and_wait(qtbot, window.connection_controller, server)
    assert window.ui.status_label.text() == "Connected"
    assert window.ui.connect_btn.text() == "Disconnect"

    server.close_peer()

    qtbot.waitUntil(lambda: window.ui.status_label.text() == "Disconnected")
    assert window.socket_tab.ui.recv_msg_te.toPlainText() == PEER_CLOSED_MESSAGE
    assert window.ui.connect_btn.text() == "Connect"


def test_closing_the_window_closes_the_socket(qtbot, server, window):
    statuses = record(window.connection_controller.statusChanged)
    connect_and_wait(qtbot, window.connection_controller, server)

    window.shutdown()  # 창을 닫으면 main() 이 부른다. fixture 정리가 한 번 더 부른다

    qtbot.waitUntil(server.peer_closed)
    assert statuses == [CONNECTED]


# -- 버그 재현 (step 0 의 strict xfail 이었다. step 2 가 고쳤다) ---------------------------


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


def test_closing_the_window_while_connecting_does_not_crash():
    proc = run_child("k39")

    assert proc.returncode == 0, describe(proc)
    assert proc.stdout.splitlines()[-1:] == ["OK"], describe(proc)


def test_a_second_connect_before_the_result_makes_one_connection():
    proc = run_child("k40")

    assert proc.returncode == 0, describe(proc)
    lines = proc.stdout.splitlines()
    assert lines[-1:] == ["OK"], describe(proc)
    result = json.loads(lines[-2])
    assert result["accepted"] == 1, describe(proc)
    assert result["connected"], describe(proc)
