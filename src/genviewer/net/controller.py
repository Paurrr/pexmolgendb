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
