import select
from queue import Queue, Empty
from PySide6.QtCore import QThread, Signal
from net.client import Client


class ConnectWorker(QThread):
    connectWorkerSignal = Signal(tuple)

    def __init__(self, client: Client):
        super().__init__()
        self.client = client

    def run(self):
        status = self.client.connect()
        self.connectWorkerSignal.emit(status)


class DisconnectWorker(QThread):
    disConnectWorkerSignal = Signal(tuple)

    def __init__(self, client: Client):
        super().__init__()
        self.client = client

    def run(self):
        status = self.client.disConnect()
        self.disConnectWorkerSignal.emit(status)


class SendWorker(QThread):
    sendWorkerSignal = Signal(str)

    def __init__(self, client: Client):
        super().__init__()
        self.client = client
        self._queue = Queue()
        self._running = True

    def run(self):
        while self._running:
            try:
                msg = self._queue.get(timeout=0.1)
                self.client.send(msg)
            except Empty:
                continue

    def send(self, msg):
        self._queue.put(msg)

    def stop(self):
        self._running = False


class ReceiveWorker(QThread):
    receiveSignal = Signal(str)

    def __init__(self, client: Client):
        super().__init__()
        self.client = client
        self.header_size = 4
        self._running = True

    def stop(self):
        self._running = False

    def run(self):
        try:
            while self._running:
                if (
                    not self.client.clientSocket
                    or self.client.clientSocket.fileno() < 0
                ):
                    self.receiveSignal.emit("DISCONNECTED")
                    break

                try:
                    readable, _, _ = select.select(
                        [self.client.clientSocket], [], [], 0.1
                    )
                except Exception as e:
                    self.receiveSignal.emit(f"ERROR: select failed - {e}")
                    break

                for s in readable:
                    if s is self.client.clientSocket:
                        try:
                            length_data = self.client.recv_all(self.header_size)
                            total_length = int.from_bytes(length_data, byteorder="big")
                            data = self.client.recv_all(total_length)
                            if data:
                                self.receiveSignal.emit(data.decode())
                            else:
                                self.receiveSignal.emit("DISCONNECTED")
                                self._running = False
                                break
                        except Exception as e:
                            self.receiveSignal.emit(f"ERROR: recv failed - {e}")
                            self._running = False
                            break
        finally:
            try:
                if self.client.clientSocket:
                    self.client.clientSocket.close()
            except Exception:
                pass
