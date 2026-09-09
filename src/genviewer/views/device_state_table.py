import re

from PySide6.QtCore import QRegularExpression, QSortFilterProxyModel, Slot
from PySide6.QtWidgets import QTableView

from models.device_state import DeviceStateModel


class DeviceStateTableView(QTableView):
    def __init__(self, parent=None, show_only_incomplete: bool = False):
        super().__init__(parent)
        self._model = DeviceStateModel({}, show_only_incomplete=show_only_incomplete)
        self._proxy_model = QSortFilterProxyModel(self)
        self._proxy_model.setSourceModel(self._model)
        self._proxy_model.setFilterKeyColumn(0)
        self.setModel(self._proxy_model)
        self.setAlternatingRowColors(True)
        self.verticalHeader().setDefaultSectionSize(20)
        self.verticalHeader().setMinimumSectionSize(18)
        self.horizontalHeader().setFixedHeight(22)

    def get_devices(self):
        return self._model.get_data()

    def update_devices(self, data):
        self._model.update_data(data)

    def clear_devices(self):
        self._model.clear()

    @Slot()
    def filter_devices(self, text):
        if not text:
            self._proxy_model.setFilterRegularExpression(QRegularExpression())
            return

        regex = QRegularExpression(text)
        if not regex.isValid():
            regex = QRegularExpression(re.escape(text))
        self._proxy_model.setFilterRegularExpression(regex)


class VirtuosoDeviceTableView(DeviceStateTableView):
    def __init__(self, parent=None):
        super().__init__(parent, show_only_incomplete=False)


class FilteredDeviceTableView(DeviceStateTableView):
    def __init__(self, parent=None):
        super().__init__(parent, show_only_incomplete=True)
