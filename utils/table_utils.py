from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)


def setup_tableview(
    tableview: QTableView, stretch_cols=None, non_stretch_mode: str = "interactive"
):
    """
    stretch_cols: 컬럼 인덱스 리스트 (해당 컬럼에 Stretch 적용)
    non_stretch_mode: "interactive" (사용자 드래그 가능) 또는 "fixed"
    """
    if stretch_cols is None:
        stretch_cols = [0]

    tableview.setAlternatingRowColors(True)
    tableview.verticalHeader().setDefaultSectionSize(20)
    tableview.verticalHeader().setMinimumSectionSize(18)

    header = tableview.horizontalHeader()
    header.setDefaultAlignment(Qt.AlignCenter)
    header.setFixedHeight(22)

    model = tableview.model()
    col_count = model.columnCount()
    header.setMinimumSectionSize(10)

    for col in range(col_count):
        if col in stretch_cols:
            header.setSectionResizeMode(col, QHeaderView.Stretch)
        elif non_stretch_mode.lower() == "interactive":
            header.setSectionResizeMode(col, QHeaderView.Interactive)
            header.resizeSection(col, 96)
        else:
            header.setSectionResizeMode(col, QHeaderView.Fixed)
            header.resizeSection(col, 26)


def build_searchable_labeled_view(
    title: str,
    view: QTableView,
    placeholder="Search...",
    filter_column=0,
    actions=None,
) -> QWidget:
    search_input = QLineEdit()
    search_input.setPlaceholderText(placeholder)

    if hasattr(view, "proxy_model"):
        view.proxy_model.setFilterKeyColumn(filter_column)

    if hasattr(view, "filter_devices"):
        search_input.textChanged.connect(view.filter_devices)
    else:
        raise AttributeError(f"{type(view).__name__} has no method 'filter_devices'")

    widget = QWidget()
    widget.setObjectName("LabeledTablePanel")
    layout = QVBoxLayout()
    layout.setContentsMargins(3, 3, 3, 3)
    layout.setSpacing(3)
    title_label = QLabel(f"<b>{title}</b>")
    title_label.setObjectName("PanelTitle")
    layout.addWidget(title_label)
    layout.addWidget(search_input)
    if actions:
        layout.addWidget(build_action_bar(actions))
    layout.addWidget(view)
    widget.setLayout(layout)
    return widget


def build_labeled_view(title: str, view: QTableView) -> QWidget:
    widget = QWidget()
    layout = QVBoxLayout()
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(2)
    layout.addWidget(QLabel(f"<b>{title}</b>"))
    layout.addWidget(view)
    widget.setLayout(layout)
    return widget


def build_action_bar(actions) -> QWidget:
    widget = QWidget()
    layout = QHBoxLayout(widget)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(2)
    for label, callback in actions:
        button = QPushButton(label)
        button.clicked.connect(callback)
        layout.addWidget(button)
    layout.addStretch(1)
    return widget
