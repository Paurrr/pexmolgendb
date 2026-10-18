"""Virtuoso SKILL 세션과의 TCP 연결. GUI 스레드의 QTcpSocket 하나로 돈다(스레드 없음).

프레임은 4바이트 big-endian 길이 다음에 UTF-8 본문이다. Virtuoso SKILL 쪽 코드가 이 형식을 쓴다.
0바이트 프레임은 메시지가 아니라서 버린다(끊김이 아니다).

상대가 끊거나 받기가 실패하면 `received("ERROR: recv failed - …")` 뒤에 `(False, "Disconnected")`
를 낸다. 내가 끊으면(`disconnect`) 상태만 알리고, `shutdown` 은 아무것도 알리지 않는다. 놓은 소켓은
시그널을 막고 abort 한다. 그래서 Qt 가 한 끊김에 `errorOccurred` 와 `disconnected` 를 둘 다 내도,
내가 부른 abort 가 `disconnected` 를 내도 알림은 한 번이다. 소켓의 대기 메서드는 쓰지 않는다(GUI
스레드를 막는다).
"""

import logging

from PySide6.QtCore import QObject, Signal
from PySide6.QtNetwork import QAbstractSocket, QTcpSocket

log = logging.getLogger(__name__)

HEADER_SIZE = 4
PEER_CLOSED = "Server connection closed"

_CONNECT_FAILURES = {
    QAbstractSocket.SocketError.HostNotFoundError: "InvalidAddress",
    QAbstractSocket.SocketError.ConnectionRefusedError: "ConnectionRefused",
    QAbstractSocket.SocketError.SocketTimeoutError: "ConnectionTimedOut",
}


class ConnectionController(QObject):
    received = Signal(str)
    statusChanged = Signal(bool, str)

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._socket: QTcpSocket | None = None  # 접속하는 중이거나 붙어 있을 때만 있다
        self._connected: bool = False
        self._buffer = bytearray()  # 아직 프레임이 다 오지 않은 바이트
        # 끊은 소켓. 그 소켓의 시그널을 처리하는 도중(모달 안)에 끊었을 수 있어서 바로 지우지 않고
        # 다음 connect 때 지운다.
        self._closed: QTcpSocket | None = None

    @property
    def is_connected(self) -> bool:
        return self._connected

    def connect(self, host: str, port: int) -> None:
        if self._socket is not None:
            if self._connected:
                self._emit_status(True, f"Already connected: {host}:{port}")
            # 아니면 접속하는 중이다. 앞 시도의 결과를 기다린다(소켓은 하나).
            return
        if not 0 <= port <= 0xFFFF:
            # QTcpSocket 은 여기서 OverflowError 를 낸다. 지금까지(파이썬 socket)의 문구로 알린다.
            self._emit_status(False, "Error: connect(): port must be 0-65535.")
            return

        if self._closed is not None:
            self._closed.deleteLater()
            self._closed = None
        sock = QTcpSocket(self)
        sock.connected.connect(self._on_connected)
        sock.readyRead.connect(self._on_ready_read)
        sock.errorOccurred.connect(self._on_error)
        sock.disconnected.connect(self._on_disconnected)
        # 오류가 connectToHost 안에서 바로 올 수 있다(예: 포트 0). 먼저 지금 소켓으로 둔다.
        self._socket = sock
        sock.connectToHost(host, port)

    def disconnect(self) -> None:
        if self._socket is None:
            self._emit_status(False, "No active connection")
            return
        self._drop(flush=True)
        self._emit_status(False, "Disconnected")

    def shutdown(self) -> None:
        """창을 닫을 때 부른다. 소켓을 닫고 상태는 알리지 않는다. 여러 번 불러도 된다."""
        self._drop(flush=True)

    def send(self, msg: str) -> None:
        sock = self._socket
        if sock is None or not self._connected:
            self._emit_status(False, "Not connected (send ignored)")
            return
        data = msg.encode()
        if sock.write(len(data).to_bytes(HEADER_SIZE, byteorder="big") + data) == -1:
            reason = sock.errorString()
            log.warning("Virtuoso 보내기 실패: %s", reason)
            self._lose(f"ERROR: send failed - {reason}")

    def _on_connected(self) -> None:
        self._connected = True
        self._emit_status(True, "Connected")

    def _on_ready_read(self) -> None:
        sock = self._socket
        # received 를 받은 쪽이 모달을 띄우면 그동안 readyRead 가 다시 오지 않는다(Qt 는 재귀로
        # 내지 않는다). 그래서 프레임 하나를 낼 때마다 남은 바이트를 다시 읽는다. 받은 쪽이
        # 끊었으면 멈춘다.
        while sock is not None and sock is self._socket:
            self._buffer += sock.readAll().data()
            body = self._take_frame()
            if body is None:
                return
            if not body:
                continue
            try:
                text = body.decode()
            except UnicodeDecodeError as e:
                log.warning("Virtuoso 받기 실패", exc_info=e)
                self._lose(f"ERROR: recv failed - {e}")
                return
            self.received.emit(text)

    def _take_frame(self) -> bytes | None:
        """버퍼 앞의 완성된 프레임 본문을 떼어 낸다. 아직 다 오지 않았으면 None."""
        if len(self._buffer) < HEADER_SIZE:
            return None
        end = HEADER_SIZE + int.from_bytes(self._buffer[:HEADER_SIZE], byteorder="big")
        if len(self._buffer) < end:
            return None
        body = bytes(self._buffer[HEADER_SIZE:end])
        del self._buffer[:end]
        return body

    def _on_error(self, error: QAbstractSocket.SocketError) -> None:
        sock = self._socket
        if sock is None:
            return
        reason = sock.errorString()
        if not self._connected:
            log.warning("Virtuoso 접속 실패: %s", reason)
            self._drop()
            self._emit_status(False, _CONNECT_FAILURES.get(error, f"Error: {reason}"))
            return
        # 이미 온 프레임을 먼저 낸다(모달 안이면 readyRead 가 아직 오지 않았다).
        self._on_ready_read()
        if sock is not self._socket:
            return
        log.warning("Virtuoso 연결 오류: %s", reason)
        if error == QAbstractSocket.SocketError.RemoteHostClosedError:
            reason = PEER_CLOSED
        self._lose(f"ERROR: recv failed - {reason}")

    def _on_disconnected(self) -> None:
        # 상대가 닫으면 보통 errorOccurred(RemoteHostClosedError) 가 먼저 와서 이미 정리했다.
        sock = self._socket
        if sock is None or not self._connected:
            return
        self._on_ready_read()
        if sock is not self._socket:
            return
        log.warning("Virtuoso 연결이 끊겼다")
        self._lose(f"ERROR: recv failed - {PEER_CLOSED}")

    def _lose(self, message: str) -> None:
        """상대가 끊었거나 주고받기가 실패했다. Socket 탭에 알리고 끊김으로 바꾼다."""
        self._drop()
        self.received.emit(message)
        self._emit_status(False, "Disconnected")

    def _drop(self, *, flush: bool = False) -> None:
        """지금 소켓을 놓는다. 그 소켓의 시그널은 더 받지 않는다. 없으면 아무것도 하지 않는다."""
        sock, self._socket = self._socket, None
        self._connected = False
        self._buffer.clear()
        if sock is None:
            return
        sock.blockSignals(True)
        if flush:
            sock.flush()  # 막지 않고, 써 둔 것을 OS 로 넘긴다
        sock.abort()
        self._closed = sock  # 지우는 것은 다음 connect 다(__init__ 의 _closed)

    def _emit_status(self, connected: bool, text: str) -> None:
        self.statusChanged.emit(connected, text)
