from PySide6.QtCore import QDateTime, QSize, Qt
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QStatusBar,
    QTextEdit,
    QToolBar,
    QVBoxLayout,
    QWidget,
    QWidgetAction,
)

from genviewer.utils.dialogs import critical, error, info, warning
from genviewer.views.device_tab import DeviceTab
from genviewer.views.socket_tab import SocketTab


class MainWindow(QMainWindow):
    def __init__(self, hostname: str):
        super().__init__()
        self.setWindowTitle("Device Viewer")
        self.resize(1200, 700)
        self.setMinimumSize(0, 0)

        central_widget = QWidget(self)
        layout = QHBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        self.setCentralWidget(central_widget)

        self.tab_list = QListWidget()
        self.tab_list.setFixedWidth(96)
        self.tab_list.setUniformItemSizes(True)
        self.tab_list.setSpacing(0)
        self.tab_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        for text in ("Device", "Socket"):
            item = QListWidgetItem(text)
            item.setSizeHint(QSize(96, 28))
            self.tab_list.addItem(item)

        self.stack = QStackedWidget()

        self.device_tab_view = DeviceTab(self)
        self.socket_tab_view = SocketTab(self)
        self.stack.addWidget(self.device_tab_view)
        self.stack.addWidget(self.socket_tab_view)

        self.tab_list.setCurrentRow(0)
        self.tab_list.currentRowChanged.connect(self.stack.setCurrentIndex)

        toolbar = QToolBar("Main Toolbar")
        self.addToolBar(toolbar)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        spacer_action = QWidgetAction(self)
        spacer_action.setDefaultWidget(spacer)
        toolbar.addAction(spacer_action)

        self.theme_btn = QPushButton("Theme: Graphite")
        self.theme_btn.setObjectName("ThemeButton")
        self.theme_btn.setFixedWidth(126)
        theme_action = QWidgetAction(self)
        theme_action.setDefaultWidget(self.theme_btn)
        toolbar.addAction(theme_action)

        self.server_input = QLabel("Server:")
        self.server_field = QLineEdit()
        self.server_field.setPlaceholderText("Hostname")
        self.server_field.setFixedWidth(120)
        self.server_field.setText(hostname)
        self.port_input = QLabel("Port:")
        self.port_field = QLineEdit()
        self.port_field.setPlaceholderText("Port")
        self.port_field.setFixedWidth(80)
        self.connect_btn = QPushButton("Connect")
        self.connect_btn.setObjectName("ConnectButton")
        self.connect_btn.setFixedWidth(80)
        self.status_label = QLabel("Disconnected")
        self.status_label.setObjectName("ConnectionStatus")
        self.status_label.setProperty("connected", "false")
        self.status_label.setFixedWidth(120)

        for widget in (
            self.server_input,
            self.server_field,
            self.port_input,
            self.port_field,
            self.connect_btn,
            self.status_label,
        ):
            action = QWidgetAction(self)
            action.setDefaultWidget(widget)
            toolbar.addAction(action)

        self.log_te = QTextEdit()
        self.log_te.setReadOnly(True)
        self.clear_log_btn = QPushButton("Clear")
        self.clear_log_btn.clicked.connect(self.log_te.clear)
        labeled_log_te = self._build_log_panel()
        labeled_log_te.setMaximumHeight(150)

        v_splitter = QSplitter(Qt.Vertical)
        v_splitter.addWidget(self.stack)
        v_splitter.addWidget(labeled_log_te)

        layout.addWidget(self.tab_list)
        layout.addWidget(v_splitter)
        layout.setSpacing(0)

        self.menubar = self.menuBar()

        self.setStatusBar(QStatusBar())
        self.show_status("No database loaded")

        self.center()

    def _build_log_panel(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(2, 1, 2, 1)
        header_layout.setSpacing(2)
        header_layout.addWidget(QLabel("<b>Log</b>"))
        header_layout.addStretch(1)
        header_layout.addWidget(self.clear_log_btn)

        layout.addWidget(header)
        layout.addWidget(self.log_te)
        return widget

    def center(self):
        screen = QApplication.primaryScreen()
        screen_geometry = screen.availableGeometry()
        x = (screen_geometry.width() - self.width()) // 2
        y = (screen_geometry.height() - self.height()) // 2
        self.move(x, y)

    def apply_connection_ui(self, connected: bool, text: str):
        self.connect_btn.setText("Disconnect" if connected else "Connect")
        self.status_label.setText(text)
        self.status_label.setProperty("connected", "true" if connected else "false")
        self._refresh_style(self.status_label)

    def set_theme_name(self, theme_name: str):
        self.theme_btn.setText(f"Theme: {theme_name}")
        self._refresh_style(self)

    def notify(self, severity: str, title: str, text: str):
        if severity == "info":
            info(self, title, text)
        elif severity in ("warn", "warning"):
            warning(self, title, text)
        elif severity == "critical":
            critical(self, title, text)
        else:
            # 모르는 severity 도 보여준다. 예전에는 조용히 버려서, 오타 하나로
            # 에러 메시지가 통째로 사라졌다.
            error(self, title, text)

    def show_status(self, text: str, ms=2000):
        self.statusBar().showMessage(text, ms)

    def append_log(self, text: str):
        timestamp = QDateTime.currentDateTime().toString("HH:mm:ss")
        self.log_te.append(f"[{timestamp}] {text}")

    def _refresh_style(self, widget: QWidget):
        widget.style().unpolish(widget)
        widget.style().polish(widget)
        widget.update()
