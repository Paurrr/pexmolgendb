from collections.abc import Callable

from PySide6.QtCore import QObject, Signal

from genviewer.net.client import Client
from genviewer.net.workers import ConnectWorker, DisconnectWorker, ReceiveWorker, SendWorker


class ConnectionController(QObject):
    received = Signal(str)
    statusChanged = Signal(bool, str)

    def __init__(
        self,
        client_factory: Callable[[str, int], Client] | None = None,
        parent: QObject | None = None,
    ):
        super().__init__(parent)
        self._client_factory = client_factory or (lambda h, p: Client(h, p))
        self._client: Client | None = None
        self._connectWorker: ConnectWorker | None = None
        self._disconnectWorker: DisconnectWorker | None = None
        self._receiveWorker: ReceiveWorker | None = None
        self._sendWorker: SendWorker | None = None

        self._connected: bool = False
        self._last_status_text: str = "Disconnected"

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def client(self) -> Client | None:
        return self._client

    def connect(self, host: str, port: int):
        # 접속하는 중이다. 워커를 새 것으로 바꾸면 실행 중인 QThread 의 마지막 참조가 사라져
        # 프로세스가 죽는다. 앞 시도의 결과를 기다린다.
        if self._connectWorker is not None and self._connectWorker.isRunning():
            return

        if self._connected:
            self._emit_status(True, f"Already connected: {host}:{port}")
            return

        self._cleanup_workers(only_send_recv=True)
        self._client = self._client_factory(host, port)

        self._connectWorker = ConnectWorker(self._client)
        self._connectWorker.connectWorkerSignal.connect(self._on_connect_worker_done)
        self._connectWorker.start()

    def disconnect(self) -> None:
        if not self._client:
            self._emit_status(False, "No active connection")
            return

        self._stop_io_workers()

        self._disconnectWorker = DisconnectWorker(self._client)
        self._disconnectWorker.disConnectWorkerSignal.connect(
            self._on_disconnect_worker_done
        )
        self._disconnectWorker.start()

    def shutdown(self) -> None:
        """창을 닫을 때 부른다. 받기·보내기 워커를 멈추고 기다린 뒤 클라이언트를 닫는다.

        돌던 워커가 컨트롤러와 함께 지워지면 프로세스가 죽는다. 여러 번 불러도 된다.
        창이 닫히는 중이라 상태를 알리지 않는다. 접속 중인 ConnectWorker 는 기다리지 않는다
        (접속 타임아웃만큼 창이 굳는다).
        """
        self._stop_io_workers()
        if self._client:
            self._client.close()
            self._client = None

    def send(self, msg: str) -> None:
        if self._sendWorker and self._sendWorker.isRunning():
            self._sendWorker.send(msg)
        else:
            self._emit_status(False, "Not connected (send ignored)")

    def _on_connect_worker_done(self, status: tuple) -> None:
        try:
            _, connection_status, is_connected = status
        except Exception:
            connection_status = "Connected" if status else "Disconnected"
            is_connected = bool(status)

        self._connected = bool(is_connected)
        self._last_status_text = str(connection_status)

        if self._connected:
            self._start_io_workers()
            self._emit_status(True, self._last_status_text)
        else:
            self._emit_status(False, self._last_status_text)

    def _on_disconnect_worker_done(self, status: tuple) -> None:
        try:
            _, connection_status, is_connected = status
        except Exception:
            connection_status = "Disconnected"
            is_connected = False

        self._connected = bool(is_connected)
        self._last_status_text = str(connection_status)
        self._teardown_client()
        self._emit_status(False, self._last_status_text)

    def _on_received(self, msg: str) -> None:
        self.received.emit(msg)

    def _start_io_workers(self) -> None:
        if not self._client:
            self._emit_status(False, "No client while starting IO workers")
            return

        self._receiveWorker = ReceiveWorker(self._client)
        self._receiveWorker.receiveSignal.connect(self._on_received)
        self._receiveWorker.start()

        self._sendWorker = SendWorker(self._client)
        # 보내기 실패도 받기 오류와 같은 길로 화면에 간다.
        self._sendWorker.sendWorkerSignal.connect(self._on_received)
        self._sendWorker.start()

    def _stop_io_workers(self) -> None:
        if self._receiveWorker:
            try:
                self._receiveWorker.stop()
                self._receiveWorker.wait()
            except Exception:
                pass
            finally:
                self._receiveWorker = None

        if self._sendWorker:
            try:
                self._sendWorker.stop()
                self._sendWorker.wait()
            except Exception:
                pass
            finally:
                self._sendWorker = None

    def _cleanup_workers(self, *, only_send_recv: bool = False) -> None:
        self._stop_io_workers()

        if not only_send_recv:
            if self._connectWorker:
                try:
                    self._connectWorker.quit()
                    self._connectWorker.wait()
                except Exception:
                    pass
                finally:
                    self._connectWorker = None

            if self._disconnectWorker:
                try:
                    self._disconnectWorker.quit()
                    self._disconnectWorker.wait()
                except Exception:
                    pass
                finally:
                    self._disconnectWorker = None

    def _teardown_client(self) -> None:
        self._cleanup_workers()
        if self._client:
            self._client.close()
            self._client = None

    def _emit_status(self, connected: bool, text: str) -> None:
        self._connected = bool(connected)
        self._last_status_text = str(text)
        self.statusChanged.emit(self._connected, self._last_status_text)
