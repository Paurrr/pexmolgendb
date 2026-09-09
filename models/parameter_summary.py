from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt


class ParameterSummaryModel(QAbstractTableModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.headers = ["Section", "Row", "Column", "Value"]
        self._rows: list[dict] = []

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.headers)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None

        row = self._rows[index.row()]
        if role in (Qt.DisplayRole, Qt.EditRole):
            key = ("section", "row", "column", "value")[index.column()]
            return row.get(key, "")

        if role == Qt.TextAlignmentRole and index.column() == 1:
            return Qt.AlignCenter

        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role != Qt.DisplayRole:
            return None
        if orientation == Qt.Horizontal:
            return self.headers[section]
        return str(section + 1)

    def flags(self, index):
        if not index.isValid():
            return Qt.NoItemFlags
        return Qt.ItemIsSelectable | Qt.ItemIsEnabled

    def set_rows(self, rows: list[dict]):
        self.beginResetModel()
        self._rows = rows
        self.endResetModel()

    def source_at(self, row: int) -> tuple[str, int, int] | None:
        if not (0 <= row < len(self._rows)):
            return None

        item = self._rows[row]
        tab_name = item.get("tab_name")
        source_row = item.get("source_row")
        source_col = item.get("source_col")
        if tab_name is None or source_row is None or source_col is None:
            return None
        return tab_name, source_row, source_col
