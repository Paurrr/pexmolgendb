"""변경 이력 화면.

평소에는 존재하지 않는다. genviewer --history 로 띄울 때만 MainWindow 가 이것을
만들어 왼쪽 목록에 끼워 넣는다.

읽기 전용이다. 여기서 되돌리거나 고칠 수 있는 것은 없다 - 이력은 무슨 일이
있었는지 보는 곳이고, 고치는 것은 Device 화면에서 한다.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QSplitter,
    QTableView,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

# (보여줄 이름, 얼마나 거슬러 볼까). 빈 문자열은 전체.
RANGES = (
    ("최근 1일", "1d"),
    ("최근 7일", "7d"),
    ("최근 30일", "30d"),
    ("전체", ""),
)

HEADERS = ["시각", "사람", "출처", "process / device", "내용"]
COLUMNS = ["at", "actor", "source", "where", "summary"]


class HistoryTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        layout.addWidget(self._build_filters())

        self.table = QTableView()
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)

        self.detail_te = QTextEdit()
        self.detail_te.setReadOnly(True)
        self.detail_te.setPlaceholderText("줄을 고르면 바뀐 값이 여기 나온다.")

        splitter = QSplitter(Qt.Vertical)
        splitter.addWidget(self.table)
        splitter.addWidget(self.detail_te)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter)

        self.count_label = QLabel("")
        layout.addWidget(self.count_label)

    def _build_filters(self) -> QWidget:
        bar = QWidget()
        row = QHBoxLayout(bar)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)

        self.range_cb = QComboBox()
        for label, value in RANGES:
            self.range_cb.addItem(label, value)
        self.range_cb.setCurrentIndex(1)  # 최근 7일

        self.who_field = QLineEdit()
        self.who_field.setPlaceholderText("사람")
        self.who_field.setFixedWidth(110)

        self.process_cb = QComboBox()
        self.process_cb.setEditable(False)
        self.process_cb.setMinimumWidth(120)

        self.find_field = QLineEdit()
        self.find_field.setPlaceholderText("찾을 글자 (바뀐 값까지 뒤진다)")

        self.refresh_btn = QPushButton("새로고침")
        self.refresh_btn.setFixedWidth(84)

        self.auto_cb = QCheckBox("자동")
        self.auto_cb.setChecked(True)
        self.auto_cb.setToolTip("10초마다 다시 읽는다.")

        row.addWidget(QLabel("기간"))
        row.addWidget(self.range_cb)
        row.addWidget(self.who_field)
        row.addWidget(QLabel("process"))
        row.addWidget(self.process_cb)
        row.addWidget(self.find_field, 1)
        row.addWidget(self.refresh_btn)
        row.addWidget(self.auto_cb)
        return bar

    def set_model(self, model) -> None:
        self.table.setModel(model)
        header = self.table.horizontalHeader()
        for i in range(len(COLUMNS) - 1):
            header.setSectionResizeMode(i, QHeaderView.ResizeToContents)
        # 마지막(내용)이 남는 폭을 다 먹는다. 가장 길고 가장 중요한 칸이다.
        header.setSectionResizeMode(len(COLUMNS) - 1, QHeaderView.Stretch)

    def set_processes(self, names: list[str]) -> None:
        """고른 값은 유지한다. 10초마다 목록이 튀면 못 쓴다."""
        current = self.process_cb.currentText()
        self.process_cb.blockSignals(True)
        self.process_cb.clear()
        self.process_cb.addItem("(전체)")
        self.process_cb.addItems(names)
        index = self.process_cb.findText(current)
        self.process_cb.setCurrentIndex(index if index >= 0 else 0)
        self.process_cb.blockSignals(False)

    def selected_process(self) -> str:
        name = self.process_cb.currentText()
        return "" if name == "(전체)" else name

    def show_detail(self, text: str) -> None:
        self.detail_te.setPlainText(text)

    def show_count(self, text: str) -> None:
        self.count_label.setText(text)
