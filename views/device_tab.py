from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import (
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from dialogs.connection import ConnectionDialog
from utils.file_dialogs import open_file
from utils.table_utils import (
    build_searchable_labeled_view,
    setup_tableview,
)
from views.device_state_table import FilteredDeviceTableView, VirtuosoDeviceTableView
from views.device_tab_toolbar import DeviceTabToolBar
from views.device_table import DeviceTableView
from views.parameter_tab import ParameterTab


class DeviceTab(QWidget):
    dbConnectRequested = Signal(str)
    loadCsvRequested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.device_tab_toolbar_view = DeviceTabToolBar(self)
        self.virtuoso_device_table = VirtuosoDeviceTableView(self)
        self.filtered_device_table = FilteredDeviceTableView(self)
        self.device_table_view = DeviceTableView(self)
        self.parameter_tab_view = ParameterTab(self)

        setup_tableview(self.virtuoso_device_table, [0], "fixed")
        setup_tableview(self.filtered_device_table, [0], "fixed")
        setup_tableview(self.device_table_view, [2])

        splitter = QSplitter(Qt.Horizontal)
        self.search_labeled_virtuoso_device = build_searchable_labeled_view(
            "Device List", self.virtuoso_device_table
        )
        self.search_labeled_filter = build_searchable_labeled_view(
            "Filtered List", self.filtered_device_table
        )
        self.search_labeled_device = build_searchable_labeled_view(
            "Device Info",
            self.device_table_view,
            actions=[
                ("Insert", self.device_table_view.open_insert_dialog),
                ("Edit", self.device_table_view.edit_selected_row),
                ("Delete", self.device_table_view.delete_selected_rows),
                ("Copy", self.device_table_view.copy_selected_rows),
                ("Paste", self.device_table_view.paste_selected_rows),
                ("Clear Sel", self.device_table_view.clearSelection),
            ],
        )

        splitter.addWidget(self.search_labeled_virtuoso_device)
        splitter.addWidget(self.search_labeled_filter)
        splitter.addWidget(self.search_labeled_device)
        splitter.addWidget(self.parameter_tab_view)
        splitter.setSizes([300, 300, 300, 500])

        layout = QVBoxLayout()
        layout.addWidget(self.device_tab_toolbar_view)
        layout.addWidget(splitter)
        layout.setContentsMargins(1, 1, 1, 1)
        layout.setSpacing(1)
        self.setLayout(layout)
        self.hide_views()

    def show_views(self):
        self.search_labeled_virtuoso_device.show()
        self.search_labeled_filter.show()

    def hide_views(self):
        self.search_labeled_virtuoso_device.hide()
        self.search_labeled_filter.hide()

    @Slot()
    def _open_connect(self, initial_dsn: str = ""):
        dialog = ConnectionDialog(self, initial_dsn)
        if dialog.exec():
            self.dbConnectRequested.emit(dialog.dsn())

    @Slot()
    def _ask_load_csv(self):
        path = open_file(self, "Load CSV", "csv file (*.csv)", "")
        if path:
            self.loadCsvRequested.emit(path)
