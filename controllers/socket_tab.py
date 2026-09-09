from PySide6.QtCore import QObject, Signal

from views.socket_tab import SocketTab


class SocketTabController(QObject):
    sendDataRequested = Signal(str)

    def __init__(self, ui: SocketTab):
        super().__init__(ui)
        self.ui = ui
        self.ui.send_btn.clicked.connect(self.send_data)

    def send_data(self):
        self.sendDataRequested.emit(self.ui.msg_input.text())
