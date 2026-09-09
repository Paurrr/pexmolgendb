import socket


class Client:
    def __init__(self, server_ip, server_port):
        self.server_ip = server_ip
        self.server_port = server_port
        self.size = 1024
        self.server_addr = (server_ip, server_port)
        self.header_size = 4
        self.clientSocket: socket.socket | None = None

    def connect(self):
        try:
            self.clientSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.clientSocket.connect(self.server_addr)
            return ("Disconnect", "Connected", True)
        except socket.gaierror:
            return ("Connect", "InvalidAddress", False)
        except ConnectionRefusedError:
            return ("Connect", "ConnectionRefused", False)
        except TimeoutError:
            return ("Connect", "ConnectionTimedOut", False)
        except Exception as e:
            return ("Connect", f"Error: {str(e)}", False)

    def disConnect(self):
        if self.clientSocket:
            self.clientSocket.close()
        return ("Connect", "Disconnected", False)

    def close(self):
        if self.clientSocket:
            try:
                self.clientSocket.close()
            except Exception:
                pass
            self.clientSocket = None

    def send(self, command: str) -> None:
        data = command.encode()
        length = len(data).to_bytes(self.header_size, byteorder="big")
        self.clientSocket.sendall(length + data)

    def recv_all(self, total_size):
        """Receive exactly total_size bytes."""
        buffer = b""
        while len(buffer) < total_size:
            chunk = self.clientSocket.recv(min(self.size, total_size - len(buffer)))
            if not chunk:
                raise ConnectionResetError("Server connection closed")
            buffer += chunk
        return buffer
