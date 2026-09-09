from PySide6.QtWidgets import (
    QWidget,
    QLineEdit,
    QPushButton,
    QHBoxLayout,
    QTextEdit,
    QVBoxLayout,
)
from utils.table_utils import build_labeled_view


class SocketTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.recv_msg_te = QTextEdit()
        labeled_recv_msg_te = build_labeled_view("Received Message", self.recv_msg_te)

        send_msg_layout = QHBoxLayout()
        self.msg_input = QLineEdit()
        self.msg_input.setPlaceholderText("Send device data to server")
        self.send_btn = QPushButton("Send")
        send_msg_layout.addWidget(self.msg_input)
        send_msg_layout.addWidget(self.send_btn)
        send_msg_layout.setContentsMargins(0, 0, 0, 0)

        send_msg_widget = QWidget()
        send_msg_widget.setLayout(send_msg_layout)

        layout = QVBoxLayout()
        layout.addWidget(labeled_recv_msg_te)
        layout.addWidget(send_msg_widget)
        layout.setContentsMargins(2, 2, 2, 2)
        self.setLayout(layout)
