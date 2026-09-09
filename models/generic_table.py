from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex, Signal
from utils.validators import normalize_value, validate_field_value


class GenericTableModel(QAbstractTableModel):
    modified = Signal()

    def __init__(
        self,
        headers,
        columns,
        table_name=None,
        delegate_config=None,
        editable=True,
        required_columns=None,
        parent=None,
    ):
        super().__init__(parent)
        self._data: list[dict] = []
        self._original_data: list[dict] = []
        self._undo_stack: list[list[dict]] = []
        self._redo_stack: list[list[dict]] = []
        self.headers = headers
        self.columns = columns
        self.table_name = table_name or ""
        self.required_columns: set[str] = set(required_columns or [])
        self.delegate_config = delegate_config or {}
        self._editable = editable
        self.device_celltype: str | None = None

    def rowCount(self, parent=QModelIndex()):
        return len(self._data)

    def columnCount(self, parent=QModelIndex()):
        return len(self.columns)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        if role in (Qt.DisplayRole, Qt.EditRole):
            return self._data[index.row()].get(self.columns[index.column()], "")
        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role != Qt.DisplayRole:
            return None
        if orientation == Qt.Horizontal:
            return self.headers[section]
        return str(section + 1)

    def set_data(self, data: list[dict]):
        self.beginResetModel()
        self._data = [row.copy() for row in data]
        self._original_data = [row.copy() for row in self._data]
        self._undo_stack.clear()
        self._redo_stack.clear()
        self.endResetModel()

    def get_data(self) -> list[dict]:
        return self._data

    def flags(self, index):
        if not index.isValid():
            return Qt.NoItemFlags
        if not self._editable:
            return Qt.ItemIsSelectable | Qt.ItemIsEnabled
        return (
            super().flags(index)
            | Qt.ItemIsDragEnabled
            | Qt.ItemIsDropEnabled
            | Qt.ItemIsSelectable
            | Qt.ItemIsEnabled
            | Qt.ItemIsEditable
        )

    def setData(self, index, value, role=Qt.EditRole):
        if not (index.isValid() and role == Qt.EditRole):
            return False

        key = self.columns[index.column()]
        row = index.row()
        value = normalize_value(value)
        ok, _ = self._validate_value(key, value)
        if not ok:
            return False

        if self._data[row].get(key, "") == value:
            return False

        self._push_undo()
        self._data[row][key] = value
        self.dataChanged.emit(index, index)
        self._emit_modified()
        return True

    def insert_row(self, row, row_data=None, parent=QModelIndex()):
        if row_data is None:
            row_data = {key: "" for key in self.columns}
        row_data = {key: normalize_value(row_data.get(key, "")) for key in self.columns}
        if not self._validate_row(row_data):
            return False

        self._push_undo()
        self.beginInsertRows(QModelIndex(), row, row)
        self._data.insert(row, row_data)
        self.endInsertRows()
        self._emit_modified()
        return True

    def remove_rows(self, rows: list[int], parent=QModelIndex()):
        valid_rows = [
            r for r in sorted(set(rows), reverse=True) if 0 <= r < len(self._data)
        ]
        if not valid_rows:
            return False
        self._push_undo()
        for r in valid_rows:
            self.beginRemoveRows(QModelIndex(), r, r)
            self._data.pop(r)
            self.endRemoveRows()
        self._emit_modified()
        return True

    def update_row(self, row: int, values: dict) -> bool:
        if not (0 <= row < len(self._data)):
            return False
        changes = {}
        for c, col_name in enumerate(self.columns):
            value = normalize_value(values.get(col_name, ""))
            ok, _ = self._validate_value(col_name, value)
            if not ok:
                return False
            if self._data[row].get(col_name, "") != value:
                changes[c] = (col_name, value)

        if not changes:
            return False

        self._push_undo()
        for c, (col_name, value) in changes.items():
            self._data[row][col_name] = value
            idx = self.index(row, c)
            self.dataChanged.emit(idx, idx)
        self._emit_modified()
        return True

    def reset_modified(self):
        self._original_data = [row.copy() for row in self._data]
        self._undo_stack.clear()
        self._redo_stack.clear()

    def undo(self):
        if not self._undo_stack:
            return False
        self._redo_stack.append([row.copy() for row in self._data])
        data = self._undo_stack.pop()
        self.beginResetModel()
        self._data = data
        self.endResetModel()
        self._emit_modified()
        return True

    def redo(self):
        if not self._redo_stack:
            return False
        self._undo_stack.append([row.copy() for row in self._data])
        data = self._redo_stack.pop()
        self.beginResetModel()
        self._data = data
        self.endResetModel()
        self._emit_modified()
        return True

    def supportedDropActions(self):
        return Qt.MoveAction

    def relocateRow(self, source_row: int, target_row: int, count: int = 1) -> bool:
        return self.moveRows(
            QModelIndex(), source_row, count, QModelIndex(), target_row
        )

    def moveRows(self, sourceParent, sourceRow, count, destParent, destRow):
        if sourceRow == destRow or destRow == sourceRow + count:
            return False

        if not self.beginMoveRows(
            sourceParent, sourceRow, sourceRow + count - 1, destParent, destRow
        ):
            return False
        self._push_undo()
        real_dest = destRow - count if destRow > sourceRow else destRow
        moving_rows = self._data[sourceRow : sourceRow + count]
        del self._data[sourceRow : sourceRow + count]
        for i, row in enumerate(moving_rows):
            self._data.insert(real_dest + i, row)
        self.endMoveRows()
        self._emit_modified()
        return True

    def set_required_column(self, column_name: str):
        self.required_columns.add(column_name)

    def set_device_celltype(self, celltype: str | None):
        self.device_celltype = celltype

    def is_modified(self) -> bool:
        return self._data != self._original_data

    def _push_undo(self):
        self._undo_stack.append([r.copy() for r in self._data])
        self._redo_stack.clear()

    def _emit_modified(self):
        self.modified.emit()

    def _field_config(self, key: str) -> dict:
        cfg = self.delegate_config.get(self.table_name, {}).get(key, {}).copy()
        if key in self.required_columns:
            cfg["required"] = True
        return cfg

    def _validate_value(self, key: str, value: str) -> tuple[bool, str]:
        return validate_field_value(
            value,
            self._field_config(key),
            celltype=self.device_celltype,
            label=key,
        )

    def _validate_row(self, row_data: dict) -> bool:
        for key in self.columns:
            ok, _ = self._validate_value(key, row_data.get(key, ""))
            if not ok:
                return False
        return True
