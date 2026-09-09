from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, Signal
from PySide6.QtGui import QColor

from utils.validators import normalize_value


class DeviceTableModel(QAbstractTableModel):
    modified = Signal()

    def __init__(
        self,
        devices=None,
        known_device_names=None,
        required_columns=None,
        parent=None,
    ):
        super().__init__(parent)
        self._headers = ["Name", "CellType", "Description"]
        self._columns = ["name", "celltype", "description"]
        self._devices = devices or []
        self._original_devices = [row.copy() for row in self._devices]
        self._original_by_id = self._build_original_by_id()
        self._undo_stack: list[list[dict]] = []
        self._redo_stack: list[list[dict]] = []
        self._dirty_cells: set[tuple[int, int]] = set()
        self.known_names = known_device_names or set()
        self.required_columns: set[str] = set(required_columns or [])

    def rowCount(self, parent=None):
        return len(self._devices)

    def columnCount(self, parent=None):
        return len(self._headers)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        device = self._devices[index.row()]
        if role in (Qt.DisplayRole, Qt.EditRole):
            return device.get(self._columns[index.column()])
        if (
            role == Qt.BackgroundRole
            and (index.row(), index.column()) in self._dirty_cells
        ):
            return QColor(255, 249, 196)
        if role == Qt.ForegroundRole and index.column() == 0:
            name = device["name"]
            return QColor(Qt.black) if name in self.known_names else QColor(Qt.red)
        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role != Qt.DisplayRole:
            return None
        if orientation == Qt.Horizontal:
            return self._headers[section]
        return str(section + 1)

    def get_device(self, row_index: int) -> dict | None:
        if 0 <= row_index < len(self._devices):
            return self._devices[row_index]
        return None

    def get_device_id(self, row_index: int):
        dev = self.get_device(row_index)
        return dev.get("id") if dev else None

    def get_devices(self):
        return self._devices

    def set_devices(self, devices):
        self.beginResetModel()
        self._devices = [row.copy() for row in devices]
        self.reset_modified()
        self.endResetModel()

    def update_devices(self, devices, known_names=None):
        self.beginResetModel()
        self._devices = [row.copy() for row in devices]
        self.known_names = known_names or set()
        self.reset_modified()
        self.endResetModel()

    def insert_row(self, row: int, values: dict, parent=None):
        row_data = {
            col: normalize_value(values.get(col, "")) for col in self._columns
        }
        if not self._validate_row(row_data):
            return False
        self._push_undo()
        self.beginInsertRows(parent or QModelIndex(), row, row)
        self._devices.insert(row, row_data)
        self.endInsertRows()
        self._recompute_dirty_cells()
        self._emit_background_changed()
        self._emit_modified()
        return True

    def remove_rows(self, rows: list[int]) -> int:
        valid_rows = [
            r for r in sorted(set(rows), reverse=True) if 0 <= r < len(self._devices)
        ]
        if not valid_rows:
            return 0
        self._push_undo()
        cnt = 0
        for r in valid_rows:
            self.beginRemoveRows(QModelIndex(), r, r)
            del self._devices[r]
            self.endRemoveRows()
            cnt += 1
        self._recompute_dirty_cells()
        self._emit_background_changed()
        self._emit_modified()
        return cnt

    def update_row(self, row: int, values: dict) -> bool:
        if not (0 <= row < len(self._devices)):
            return False
        changes = {}
        for c, col_name in enumerate(self._columns):
            value = normalize_value(values.get(col_name, ""))
            if col_name in self.required_columns and not value:
                return False
            if self._devices[row].get(col_name, "") != value:
                changes[c] = (col_name, value)

        if not changes:
            return False

        self._push_undo()
        for c, (col_name, value) in changes.items():
            self._devices[row][col_name] = value
            self._refresh_dirty_cell(row, c)
            idx = self.index(row, c)
            self.dataChanged.emit(
                idx, idx, [Qt.DisplayRole, Qt.EditRole, Qt.BackgroundRole]
            )
        self._emit_modified()
        return True

    def clear_dirty(self):
        self._dirty_cells.clear()
        self._emit_background_changed()

    def _refresh_dirty_cell(self, row: int, col: int):
        if self._cell_matches_original(row, col):
            self._dirty_cells.discard((row, col))
        else:
            self._dirty_cells.add((row, col))
        idx = self.index(row, col)
        self.dataChanged.emit(idx, idx, [Qt.BackgroundRole])

    def setData(self, index, value, role=Qt.EditRole):
        if not (index.isValid() and role == Qt.EditRole):
            return False
        row, col = index.row(), index.column()
        try:
            key = self._columns[col]
        except IndexError:
            return False

        s = normalize_value(value)
        if key in self.required_columns and not s.strip():
            return False

        if self._devices[row].get(key, "") == s:
            return False

        self._push_undo()
        self._devices[row][key] = s
        self._refresh_dirty_cell(row, col)
        self.dataChanged.emit(index, index, [Qt.DisplayRole, Qt.EditRole])
        self._emit_modified()
        return True

    def flags(self, index):
        if not index.isValid():
            return Qt.NoItemFlags
        return (
            super().flags(index)
            | Qt.ItemIsDragEnabled
            | Qt.ItemIsDropEnabled
            | Qt.ItemIsSelectable
            | Qt.ItemIsEnabled
            | Qt.ItemIsEditable
        )

    def supportedDropActions(self):
        return Qt.MoveAction

    def relocateRow(self, source_row: int, target_row: int, count: int = 1) -> bool:
        return self.moveRows(
            QModelIndex(), source_row, count, QModelIndex(), target_row
        )

    def moveRows(self, sourceParent, sourceRow, count, destParent, destRow):
        row_count = len(self._devices)
        if count <= 0 or sourceRow < 0 or destRow < 0:
            return False
        if sourceRow + count > row_count or destRow > row_count:
            return False
        if sourceRow == destRow or destRow == sourceRow + count:
            return False

        if not self.beginMoveRows(
            sourceParent, sourceRow, sourceRow + count - 1, destParent, destRow
        ):
            return False

        try:
            self._push_undo()
            real_dest = destRow - count if destRow > sourceRow else destRow
            moving_rows = self._devices[sourceRow : sourceRow + count]
            del self._devices[sourceRow : sourceRow + count]
            for i, row in enumerate(moving_rows):
                self._devices.insert(real_dest + i, row)
        finally:
            self.endMoveRows()
        self._recompute_dirty_cells()
        self._emit_background_changed()
        self._emit_modified()
        return True

    def set_required_column(self, column_name: str):
        self.required_columns.add(column_name)

    def reset_modified(self):
        self._original_devices = [row.copy() for row in self._devices]
        self._original_by_id = self._build_original_by_id()
        self._undo_stack.clear()
        self._redo_stack.clear()
        self._dirty_cells.clear()

    def is_modified(self) -> bool:
        return self._devices != self._original_devices

    def undo(self) -> bool:
        if not self._undo_stack:
            return False
        self._redo_stack.append([row.copy() for row in self._devices])
        devices = self._undo_stack.pop()
        self.beginResetModel()
        self._devices = devices
        self._recompute_dirty_cells()
        self.endResetModel()
        self._emit_modified()
        return True

    def redo(self) -> bool:
        if not self._redo_stack:
            return False
        self._undo_stack.append([row.copy() for row in self._devices])
        devices = self._redo_stack.pop()
        self.beginResetModel()
        self._devices = devices
        self._recompute_dirty_cells()
        self.endResetModel()
        self._emit_modified()
        return True

    def _push_undo(self):
        self._undo_stack.append([row.copy() for row in self._devices])
        self._redo_stack.clear()

    def _emit_modified(self):
        self.modified.emit()

    def _validate_row(self, row_data: dict) -> bool:
        for col in self.required_columns:
            if not row_data.get(col, "").strip():
                return False
        return True

    def _cell_matches_original(self, row: int, col: int) -> bool:
        original = self._original_for_device(row)
        if original is None:
            return False
        key = self._columns[col]
        return self._devices[row].get(key, "") == original.get(key, "")

    def _recompute_dirty_cells(self):
        self._dirty_cells.clear()
        for row, device in enumerate(self._devices):
            original = self._original_for_device(row)
            for col, key in enumerate(self._columns):
                if original is None:
                    self._dirty_cells.add((row, col))
                elif device.get(key, "") != original.get(key, ""):
                    self._dirty_cells.add((row, col))

    def _build_original_by_id(self) -> dict[int, dict]:
        return {
            device_id: row.copy()
            for row in self._original_devices
            if (device_id := row.get("id")) is not None
        }

    def _original_for_device(self, row: int) -> dict | None:
        if not (0 <= row < len(self._devices)):
            return None

        device = self._devices[row]
        device_id = device.get("id")
        if device_id is not None:
            return self._original_by_id.get(device_id)

        if row < len(self._original_devices):
            original = self._original_devices[row]
            if original.get("id") is None:
                return original
        return None

    def _emit_background_changed(self):
        if self.rowCount() <= 0 or self.columnCount() <= 0:
            return
        top_left = self.index(0, 0)
        bottom_right = self.index(self.rowCount() - 1, self.columnCount() - 1)
        self.dataChanged.emit(top_left, bottom_right, [Qt.BackgroundRole])
