"""127.0.0.1 에서 테스트가 띄우는 Virtuoso 흉내 서버 (phase 13).

`ConnectionController` 를 실제 소켓으로 시험한다. 바깥 호스트나 실제 Virtuoso 에는 붙지 않는다.
프레임 형식은 Virtuoso SKILL 쪽과 같다: 4바이트 big-endian 길이 다음에 UTF-8 본문.

accept 와 연결별 읽기는 daemon 스레드에서 돈다. 스레드 사이에서 넘기는 기록은 리스트에 덧붙이기만
한다. 모든 소켓 연산에 짧은 타임아웃이 있어 어떤 실패도 테스트를 멈추게 하지 않는다.
"""

from __future__ import annotations

import socket
import threading
import time

HEADER_SIZE = 4
POLL = 0.05  # accept·recv·send 타임아웃. 닫기(close)가 이만큼 안에 스레드에 닿는다
WAIT_ACCEPT = 5.0


def frame(body: bytes | str) -> bytes:
    """본문 하나를 프레임으로 만든다. str 은 UTF-8 로 바꾼다."""
    data = body.encode("utf-8") if isinstance(body, str) else body
    return len(data).to_bytes(HEADER_SIZE, byteorder="big") + data


class _Peer:
    """받은 연결 하나. 기록(`chunks`, `ended`, `closing`)은 덧붙이기만 한다."""

    def __init__(self, sock: socket.socket) -> None:
        self.sock = sock
        self.chunks: list[bytes] = []  # 클라이언트가 보낸 바이트
        self.ended: list[str] = []  # 클라이언트가 닫았으면 "eof" 또는 "reset"
        self.closing: list[bool] = []  # 서버(테스트)가 닫았으면 [True]
        self.thread: threading.Thread | None = None

    def data(self) -> bytes:
        return b"".join(list(self.chunks))

    def close(self) -> None:
        self.closing.append(True)
        try:
            self.sock.shutdown(socket.SHUT_RDWR)  # FIN 을 먼저 보낸다. 상대 recv 가 b"" 를 본다
        except OSError:
            pass
        try:
            self.sock.close()
        except OSError:
            pass


class LocalVirtuoso:
    """127.0.0.1:0 에 listen 하는 테스트용 Virtuoso 흉내. 모든 소켓 연산에 타임아웃이 있다.

    `send_*`/`close_peer` 는 마지막으로 받은 연결에 대고 한다. 클라이언트가 붙은 직후에는 accept
    스레드가 아직 연결을 기록하지 않았을 수 있으므로, 연결이 없으면 최대 5초 기다린다. 다시 접속한
    뒤라면 테스트가 먼저 `accepted` 를 기다린다(옛 연결에 보내지 않게).
    """

    def __init__(self) -> None:
        self._listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._listener.bind(("127.0.0.1", 0))
        self._listener.listen(8)
        self._listener.settimeout(POLL)
        self.port: int = self._listener.getsockname()[1]
        self._peers: list[_Peer] = []
        self._timers: list[threading.Timer] = []
        self._stop = threading.Event()
        self._accept_thread = threading.Thread(
            target=self._accept_loop, name="LocalVirtuoso-accept", daemon=True
        )
        self._accept_thread.start()

    @property
    def accepted(self) -> int:
        """지금까지 받은 연결 수."""
        return len(self._peers)

    def frames(self) -> list[bytes]:
        """클라이언트가 보낸 바이트를 연결마다 4바이트 길이 프레임으로 나눈 본문들(받은 순서).

        끝이 덜 온 프레임은 넣지 않는다.
        """
        bodies: list[bytes] = []
        for peer in list(self._peers):
            data = peer.data()
            pos = 0
            while pos + HEADER_SIZE <= len(data):
                size = int.from_bytes(data[pos : pos + HEADER_SIZE], byteorder="big")
                end = pos + HEADER_SIZE + size
                if end > len(data):
                    break
                bodies.append(data[pos + HEADER_SIZE : end])
                pos = end
        return bodies

    def data(self) -> bytes:
        """클라이언트가 보낸 원시 바이트(연결 순서대로 이어 붙임)."""
        return b"".join(peer.data() for peer in list(self._peers))

    def peer_closed(self) -> bool:
        """마지막 연결에서 클라이언트가 닫았다(recv 가 b"" 이거나 연결이 재설정됨)."""
        peers = list(self._peers)
        return bool(peers) and bool(peers[-1].ended)

    def send_frame(self, body: bytes | str) -> None:
        self.send_raw(frame(body))

    def send_raw(self, data: bytes) -> None:
        self._last_peer().sock.sendall(data)

    def close_peer(self) -> None:
        """마지막 연결을 서버 쪽에서 닫는다."""
        self._last_peer().close()

    def close_peer_after(self, seconds: float) -> None:
        """지금의 마지막 연결을 seconds 뒤에 닫는다(threading.Timer). `close()` 가 취소한다."""
        peer = self._last_peer()
        timer = threading.Timer(seconds, peer.close)
        timer.daemon = True
        self._timers.append(timer)
        timer.start()

    def close(self) -> None:
        """listen 소켓과 모든 연결을 닫고 스레드를 잠깐 기다린다. 여러 번 불러도 된다."""
        self._stop.set()
        for timer in list(self._timers):
            timer.cancel()
        try:
            self._listener.close()
        except OSError:
            pass
        for peer in list(self._peers):
            if not peer.closing:
                peer.close()
        self._accept_thread.join(1.0)
        for peer in list(self._peers):
            if peer.thread is not None:
                peer.thread.join(1.0)

    # -- 스레드 ---------------------------------------------------------------

    def _last_peer(self) -> _Peer:
        deadline = time.monotonic() + WAIT_ACCEPT
        while not self._peers:
            if time.monotonic() > deadline:
                raise AssertionError("LocalVirtuoso: 받은 연결이 없다")
            time.sleep(0.01)
        return self._peers[-1]

    def _accept_loop(self) -> None:
        while not self._stop.is_set():
            try:
                sock, _ = self._listener.accept()
            except TimeoutError:
                continue
            except OSError:
                break  # close() 가 listen 소켓을 닫았다
            sock.settimeout(POLL)
            peer = _Peer(sock)
            peer.thread = threading.Thread(
                target=self._read_loop,
                args=(peer,),
                name=f"LocalVirtuoso-read-{len(self._peers)}",
                daemon=True,
            )
            self._peers.append(peer)
            peer.thread.start()

    def _read_loop(self, peer: _Peer) -> None:
        while not self._stop.is_set() and not peer.closing:
            try:
                chunk = peer.sock.recv(65536)
            except TimeoutError:
                continue
            except OSError:
                # 서버가 닫았으면(closing) 클라이언트의 일이 아니다. 아니면 클라이언트가 RST 로
                # 끊었다(받지 않은 데이터를 남기고 닫으면 Windows 는 RST 를 보낸다).
                if not peer.closing:
                    peer.ended.append("reset")
                return
            if not chunk:
                if not peer.closing:
                    peer.ended.append("eof")
                return
            peer.chunks.append(chunk)
