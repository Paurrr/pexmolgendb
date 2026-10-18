"""서브프로세스에서 도는 Virtuoso 접속 재현 (phase 13, K39·K40).

실행 중인 QThread 를 놓치면 프로세스가 qFatal 로 죽는다(예외가 아니다). 그래서 pytest 프로세스
밖에서 돌린다: `python -m gui_support.virtuoso_child <k39|k40>` (PYTHONPATH 에 tests).
정상으로 끝나면 마지막 줄에 `OK` 를 찍고 0 으로 끝난다. 공개 API 만 쓴다.
"""

import gc
import json
import socket
import sys
import threading
import time


def _no_crash_dialogs() -> None:
    """Windows 크래시 대화상자가 떠서 부모의 timeout 을 다 쓰지 않게 한다. PySide6 보다 먼저."""
    if sys.platform == "win32":
        import ctypes

        # SEM_FAILCRITICALERRORS | SEM_NOGPFAULTERRORBOX | SEM_NOOPENFILEERRORBOX
        ctypes.windll.kernel32.SetErrorMode(0x8003)


def _spin(seconds: float, until=None) -> None:
    """이벤트를 최대 seconds 동안 돌린다. until() 이 참이 되면 일찍 끝낸다."""
    from PySide6.QtCore import QCoreApplication, QEventLoop

    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        QCoreApplication.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 50)
        if until is not None and until():
            return
        time.sleep(0.01)


def k39() -> None:
    """접속하는 동안 창을 닫는다(shutdown 뒤 컨트롤러를 놓는다)."""
    real_connect = socket.socket.connect

    def slow_connect(self, address):
        time.sleep(2.0)
        return real_connect(self, address)

    socket.socket.connect = slow_connect

    from PySide6.QtCore import QCoreApplication

    from genviewer.net.controller import ConnectionController

    app = QCoreApplication([])  # noqa: F841 - 이벤트를 돌리는 동안 살아 있어야 한다
    ctrl = ConnectionController()
    ctrl.connect("127.0.0.1", 1)
    ctrl.shutdown()
    del ctrl
    gc.collect()
    _spin(0.5)
    print("OK", flush=True)
    sys.exit(0)


def k40() -> None:
    """결과가 오기 전에 Connect 를 한 번 더 누른다."""
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(("127.0.0.1", 0))
    listener.listen(8)
    listener.settimeout(0.05)
    port = listener.getsockname()[1]
    accepted: list[socket.socket] = []
    stop = threading.Event()

    def accept_loop() -> None:
        while not stop.is_set():
            try:
                conn, _ = listener.accept()
            except TimeoutError:
                continue
            except OSError:
                return
            accepted.append(conn)

    threading.Thread(target=accept_loop, daemon=True).start()

    from PySide6.QtCore import QCoreApplication

    from genviewer.net.controller import ConnectionController

    app = QCoreApplication([])  # noqa: F841 - 이벤트를 돌리는 동안 살아 있어야 한다
    ctrl = ConnectionController()
    statuses: list[list] = []
    ctrl.statusChanged.connect(lambda ok, text: statuses.append([ok, text]))

    ctrl.connect("127.0.0.1", port)
    time.sleep(0.5)  # 이벤트를 돌리지 않는다. 첫 시도의 결과가 큐에 머문다
    ctrl.connect("127.0.0.1", port)
    _spin(3.0, until=lambda: ctrl.is_connected)
    _spin(0.5)  # 늦게 오는 두 번째 결과·접속까지 본다
    print(
        json.dumps(
            {"accepted": len(accepted), "connected": ctrl.is_connected, "statuses": statuses}
        ),
        flush=True,
    )

    ctrl.shutdown()
    stop.set()
    for conn in accepted:
        conn.close()
    listener.close()
    print("OK", flush=True)
    sys.exit(0)


if __name__ == "__main__":
    _no_crash_dialogs()
    {"k39": k39, "k40": k40}[sys.argv[1]]()
