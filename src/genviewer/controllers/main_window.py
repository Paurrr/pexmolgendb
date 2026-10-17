import logging

from PySide6.QtCore import QObject, Signal, Slot
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QApplication

from genviewer.controllers.device_tab import DeviceTabController
from genviewer.controllers.socket_tab import SocketTabController
from genviewer.net.controller import ConnectionController
from genviewer.service import virtuoso_protocol
from genviewer.service.errors import user_message
from genviewer.utils.palette import THEMES, apply_theme
from genviewer.views.main_window import MainWindow

log = logging.getLogger(__name__)


class MainWindowController(QObject):
    statusMessageRequested = Signal(str, int)

    def __init__(self, ui: MainWindow, dsn: str):
        super().__init__()
        self.ui = ui
        self.connection_controller = ConnectionController()
        self.is_connected = False
        self.theme_name = "graphite"

        self.device_tab = DeviceTabController(self.ui.device_tab_view, dsn)
        self.socket_tab = SocketTabController(self.ui.socket_tab_view)

        self.device_tab.sendDataRequested.connect(self.connection_controller.send)
        self.socket_tab.sendDataRequested.connect(self.connection_controller.send)
        self.ui.connect_btn.clicked.connect(self._on_click_connect_toggle)
        self.ui.theme_btn.clicked.connect(self._toggle_theme)
        self.ui.set_theme_name(THEMES[self.theme_name]["name"])
        self.device_tab.device_tab_toolbar.connect_load_virtuoso(
            self._action_load_virtuoso
        )
        self.device_tab.device_tab_toolbar.connect_load_libraries(
            self._action_load_libraries
        )

        self.connection_controller.received.connect(self._on_received_from_controller)
        self.connection_controller.statusChanged.connect(self._on_status_changed)

        self.statusMessageRequested.connect(self._on_status_message)
        self.device_tab.statusMessageRequested.connect(self._on_status_message)
        self.device_tab.notifyRequested.connect(self._on_notify_requested)
        self.device_tab.logRequested.connect(self.ui.append_log)

        # 이력 화면은 --history 로 띄웠을 때만 존재한다. Device 화면이 쓰는
        # Database 를 그대로 받아 쓴다 - 풀을 하나 더 열 이유가 없다.
        self.history_tab = None
        if self.ui.history_tab_view is not None:
            from genviewer.controllers.history_tab import HistoryTabController

            self.history_tab = HistoryTabController(self.ui.history_tab_view, self.ui)
            self.history_tab.logRequested.connect(self.ui.append_log)
            self.device_tab.dbChanged.connect(self.history_tab.set_db)
            self.history_tab.set_db(self.device_tab.db)

        self._setup_actions()

    def shutdown(self) -> None:
        """앱 종료 시 커넥션 풀을 닫는다. main() 이 app.exec() 후에 부른다."""
        # 이력 쪽 작업이 먼저 끝나야 한다. 풀을 닫은 뒤에 남아 있으면 터진다.
        if self.history_tab is not None:
            self.history_tab.shutdown()
        self.device_tab.close_db()

    def _setup_actions(self):
        act_save = QAction("Save", self.ui)
        act_save.setShortcut(QKeySequence.Save)
        act_save.triggered.connect(self._on_save_triggered)
        self.ui.addAction(act_save)

        act_undo = QAction("Undo", self.ui)
        act_undo.setShortcut(QKeySequence.Undo)
        act_undo.triggered.connect(self._on_undo_triggered)
        self.ui.addAction(act_undo)

        act_redo = QAction("Redo", self.ui)
        act_redo.setShortcut(QKeySequence.Redo)
        act_redo.triggered.connect(self._on_redo_triggered)
        self.ui.addAction(act_redo)

        file_menu = self.ui.menubar.addMenu("Database")

        connect_action = QAction("Connect...", self.ui)
        connect_action.triggered.connect(self.ui.device_tab_view._open_connect)
        file_menu.addAction(connect_action)

        file_menu.addSeparator()

        # 이름은 "Save DB" 였지만 실제로는 화면의 변경사항을 쓰는 동작이다.
        # DB 가 더 이상 파일이 아니므로 이름만 바로잡는다.
        save_action = QAction("Save", self.ui)
        save_action.triggered.connect(self.device_tab.save_db)
        file_menu.addAction(save_action)

        file_menu.addSeparator()

        load_csv_action = QAction("Load CSV", self.ui)
        load_csv_action.triggered.connect(self.ui.device_tab_view._ask_load_csv)
        file_menu.addAction(load_csv_action)

    @Slot()
    def _action_load_virtuoso(self):
        """현재 process를 기준으로 Virtuoso 필터 명령을 만들어 전송."""
        self.device_tab.clear()
        process_name = self.device_tab.device_tab_toolbar.get_current_process()
        if not process_name:
            self.notify_status("No process selected", 2000)
            return
        cmd = virtuoso_protocol.make_filter_cell_has_symbol_layout(process_name)
        self.connection_controller.send(cmd)
        self._request_virtuoso_libraries()
        self.notify_status("Requested Virtuoso device and library list", 2000)

    @Slot()
    def _action_load_libraries(self):
        self._request_virtuoso_libraries()
        self.notify_status("Requested Virtuoso library list", 2000)

    @Slot(str)
    def _on_received_from_controller(self, raw: str):
        msg_type, msg = virtuoso_protocol.parse(raw)

        if msg_type == "DeviceList":
            device_state_data = virtuoso_protocol.to_device_state(msg)
            self.device_tab.ui.virtuoso_device_table.update_devices(device_state_data)
            self.device_tab.ui.filtered_device_table.update_devices(device_state_data)
            self.device_tab.device_table.device_state_data = device_state_data
            self.device_tab.device_table.refresh_devices()
            self.ui.append_log(f"Received Virtuoso device list: {len(device_state_data)} item(s).")
        elif msg_type == "LibraryList":
            libraries = virtuoso_protocol.to_library_list(msg)
            self.device_tab.device_tab_toolbar.set_libraries(libraries)
            self.ui.append_log(f"Received Virtuoso library list: {len(libraries)} item(s).")
        else:
            self.socket_tab.ui.recv_msg_te.setText(msg)
            self.ui.append_log("Received socket message.")

    @Slot(bool, str)
    def _on_status_changed(self, connected: bool, text: str):
        self.ui.apply_connection_ui(connected, text)
        self.device_tab.set_client(
            self.connection_controller.client if connected else None
        )
        self.notify_status(text)

    @Slot()
    def _on_click_connect_toggle(self):
        host = self.ui.server_field.text().strip()
        port = self.ui.port_field.text().strip()

        try:
            if not self.connection_controller.is_connected:
                if not host or not port:
                    self.notify_status("Please enter both server and port", 3000)
                    return
                port_num = int(port)
                self.notify_status(f"Connecting to {host}:{port_num}", 1500)
                self.connection_controller.connect(host, port_num)
            else:
                self.notify_status("Disconnecting", 1500)
                self.connection_controller.disconnect()
        except ValueError:
            self.notify_status("Port must be an integer", 3000)
        except Exception as e:
            self.notify_status(f"Connection error: {e}", 5000)

    @Slot()
    def _on_save_triggered(self) -> None:
        fw = self.ui.focusWidget()

        # 세 갈래 중 둘은 아무것도 잡지 않고 있었다. 포커스가 어디 있느냐에 따라
        # 같은 Ctrl+S 가 메시지 박스로 끝나기도 하고 트레이스백이 되기도 했다.
        # 상태 표시줄 문구는 저장했을 때만 낸다. 취소·실패 뒤에 "saved" 가 뜨면 안 된다.
        try:
            if self.device_tab.ui.device_table_view.isAncestorOf(fw):
                if self.device_tab.device_table.save_all():
                    self.notify_status("Device table saved")
            elif self.device_tab.ui.parameter_tab_view.isAncestorOf(fw):
                if self.device_tab.parameter_tab.save_all():
                    self.notify_status("Tab section data saved")
            else:
                if self.device_tab.save_db():
                    self.notify_status("All device and tab data saved")
        except Exception as e:
            log.error("저장 실패", exc_info=e)
            self.ui.notify("error", "Save Failed", user_message(e))

    @Slot()
    def _on_undo_triggered(self):
        fw = self.ui.focusWidget()
        handled = False
        if self.device_tab.ui.device_table_view.isAncestorOf(fw):
            handled = self.device_tab.device_table.undo()
        elif self.device_tab.ui.parameter_tab_view.isAncestorOf(fw):
            handled = self.device_tab.parameter_tab.undo_current()

        if not handled:
            self.notify_status("Nothing to undo", 1500)

    @Slot()
    def _on_redo_triggered(self):
        fw = self.ui.focusWidget()
        handled = False
        if self.device_tab.ui.device_table_view.isAncestorOf(fw):
            handled = self.device_tab.device_table.redo()
        elif self.device_tab.ui.parameter_tab_view.isAncestorOf(fw):
            handled = self.device_tab.parameter_tab.redo_current()

        if not handled:
            self.notify_status("Nothing to redo", 1500)

    @Slot(str, int)
    def _on_status_message(self, text: str, ms: int = 2000):
        self.ui.show_status(text, ms)
        self.ui.append_log(text)

    @Slot(str, str, str)
    def _on_notify_requested(self, severity: str, title: str, text: str):
        self.ui.notify(severity, title, text)
        one_line = " ".join(str(text).split())
        self.ui.append_log(f"{title}: {one_line}")
        # 사용자가 본 것은 파일에도 남긴다. 로그 패널은 창을 닫으면 사라지고
        # Clear 버튼으로도 없어진다.
        level = logging.ERROR if severity in ("error", "critical") else logging.INFO
        log.log(level, "%s: %s", title, one_line)

    def notify_status(self, text: str, ms=2000):
        self.statusMessageRequested.emit(text, ms)

    def _request_virtuoso_libraries(self):
        cmd = virtuoso_protocol.make_library_list_request()
        self.connection_controller.send(cmd)
        if cmd:
            self.ui.append_log("Sent Virtuoso library request.")
        else:
            self.ui.append_log("Sent empty Virtuoso library request placeholder.")

    @Slot()
    def _toggle_theme(self):
        self.theme_name = "mist" if self.theme_name == "graphite" else "graphite"
        apply_theme(QApplication.instance(), self.theme_name)
        self.ui.set_theme_name(THEMES[self.theme_name]["name"])
        self.ui.append_log(f"Theme changed to {THEMES[self.theme_name]['name']}.")
