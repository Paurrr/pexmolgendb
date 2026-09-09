from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex


class DeviceStateModel(QAbstractTableModel):
    def __init__(self, data: dict[str, dict], show_only_incomplete=False, parent=None):
        super().__init__(parent)
        self._headers = ["Name", "S", "L"]
        self._data = data
        self.show_only_incomplete = show_only_incomplete
        self._filtered_keys = self._filter_keys()

    def _filter_keys(self):
        if self.show_only_incomplete:
            return [
                name
                for name, val in self._data.items()
                if val["S"] != "O" or val["L"] != "O"
            ]
        return list(self._data.keys())

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._filtered_keys)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._headers)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        r, c = index.row(), index.column()

        name = self._filtered_keys[r]
        values = self._data.get(name, {})

        if role == Qt.DisplayRole:
            if c == 0:
                return name
            elif c == 1:
                return values["S"]
            elif c == 2:
                return values["L"]
        elif role == Qt.TextAlignmentRole and c != 0:
            return Qt.AlignCenter

        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role != Qt.DisplayRole:
            return None
        if orientation == Qt.Horizontal:
            return self._headers[section]
        return str(section + 1)

    def flags(self, index):
        if not index.isValid():
            return Qt.NoItemFlags
        return Qt.ItemIsEnabled | Qt.ItemIsSelectable

    def set_data(self, data: dict[str, dict]):
        self.beginResetModel()
        self._data = data
        self._filtered_keys = self._filter_keys()
        self.endResetModel()

    def get_data(self) -> dict[str, dict]:
        return self._data

    def update_data(self, new_data: dict[str, dict]):
        self.set_data(new_data)

    def clear(self):
        self.beginResetModel()
        self._data.clear()
        self._filtered_keys.clear()
        self.endResetModel()
