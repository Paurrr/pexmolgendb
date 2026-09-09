import re
from PySide6.QtWidgets import (
    QTableView,
    QDialog,
    QAbstractItemView,
    QStyledItemDelegate,
)
from PySide6.QtCore import (
    Qt,
    QPoint,
    QRegularExpression,
    Signal,
    Slot,
)
from dialogs.insert import InsertDialog
from models.device_table import DeviceTableModel
from models.sorting_proxy import SortingProxyModel
from utils.dialogs import question
from utils.file_dialogs import save_file


class DeviceTableView(QTableView):
    dirtyChanged = Signal(bool)
    contextMenuRequested = Signal(list, QPoint)
    device_selected = Signal(int, str)
    insertRequested = Signal(dict)
    editRequested = Signal(int, dict)
    deleteRequested = Signal(list)
    copyRequested = Signal(list)
    pasteRequested = Signal(list)
    headerMenuRequested = Signal(int, QPoint)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.table_name = "device"
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QTableView.InternalMove)
        self.setSelectionBehavior(QTableView.SelectRows)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.setEditTriggers(QTableView.DoubleClicked | QTableView.SelectedClicked)
        self.setAlternatingRowColors(True)
        self.verticalHeader().setDefaultSectionSize(20)
        self.verticalHeader().setMinimumSectionSize(18)
        self.horizontalHeader().setFixedHeight(22)

        self._model = DeviceTableModel()
        self.proxy_model = SortingProxyModel(self)
        self.proxy_model.setSourceModel(self._model)
        self.proxy_model.setFilterKeyColumn(0)
        self.setModel(self.proxy_model)

        self.customContextMenuRequested.connect(self._emit_context_menu)

        header = self.horizontalHeader()
        header.setContextMenuPolicy(Qt.CustomContextMenu)
        header.customContextMenuRequested.connect(self._emit_header_menu)

    def model_safe(self):
        model = self._model
        if model and hasattr(model, "insert_row") and hasattr(model, "remove_rows"):
            return model
        return None

    def _emit_header_menu(self, pos: QPoint):
        header = self.horizontalHeader()
        logical_index = header.logicalIndexAt(pos)
        if logical_index < 0:
            return
        self.headerMenuRequested.emit(logical_index, header.mapToGlobal(pos))

    def _emit_context_menu(self, pos: QPoint):
        rows = self._selected_source_rows()
        global_pos = self.viewport().mapToGlobal(pos)
        self.contextMenuRequested.emit(rows, global_pos)

    def _ask_export_path(self, suggested_name: str) -> str:
        path = save_file(
            self, "Export", "CSV Files (*.csv);;Excel Files (*.xlsx)", suggested_name
        )
        return path or ""

    def keyPressEvent(self, event):
        if event.modifiers() == Qt.ControlModifier:
            if event.key() == Qt.Key_C:
                self.copy_selected_from_rows(self._selected_source_rows())
            elif event.key() == Qt.Key_V:
                self.open_paste_to_rows(self._selected_source_rows())
            elif event.key() == Qt.Key_I:
                self.open_insert_dialog()
            elif event.key() == Qt.Key_D:
                self.delete_rows(self._selected_source_rows())
            elif event.key() == Qt.Key_E:
                selected_rows = self._selected_source_rows()
                if selected_rows:
                    self.open_edit_dialog(selected_rows[0])
        elif event.modifiers() == Qt.NoModifier:
            if event.key() == Qt.Key_Delete:
                self.delete_rows(self._selected_source_rows())
        super().keyPressEvent(event)

    def _map_to_source_row(self, proxy_row: int) -> int:
        proxy_index = self.proxy_model.index(proxy_row, 0)
        source_index = self.proxy_model.mapToSource(proxy_index)
        return source_index.row() if source_index.isValid() else proxy_row

    def _selected_source_rows(self) -> list[int]:
        sel = self.selectionModel()
        if not sel:
            return []
        return sorted({self._map_to_source_row(i.row()) for i in sel.selectedRows()})

    def _selected_proxy_rows(self) -> list[int]:
        sel = self.selectionModel()
        if not sel:
            return []
        return sorted({idx.row() for idx in sel.selectedRows()})

    def _row_to_dict(self, src_row: int) -> dict:
        m = self.model_safe()
        return {col: m.data(m.index(src_row, c)) for c, col in enumerate(m._columns)}

    @Slot()
    def open_insert_dialog(self):
        model = self.model_safe()
        dlg = InsertDialog(None, self.table_name, model._columns, model._headers, self)
        if dlg.exec_() == QDialog.Accepted:
            values = dlg.get_data()
            if values:
                self.insertRequested.emit(values)

    @Slot()
    def open_edit_dialog(self, row: int):
        src_row = row
        old_values = self._row_to_dict(src_row)
        model = self.model_safe()

        dlg = InsertDialog(
            None, self.table_name, model._columns, model._headers, self, old_values
        )
        if dlg.exec_() != QDialog.Accepted:
            return
        new_values = dlg.get_data()
        if not new_values:
            return

        self.editRequested.emit(src_row, new_values)

    def edit_selected_row(self):
        rows = self._selected_source_rows()
        if rows:
            self.open_edit_dialog(rows[0])

    def delete_selected_rows(self):
        self.delete_rows(self._selected_source_rows())

    def copy_selected_rows(self):
        self.copy_selected_from_rows(self._selected_source_rows())

    def paste_selected_rows(self):
        self.open_paste_to_rows(self._selected_source_rows())

    @Slot()
    def delete_rows(self, rows: list[int]):
        if not rows:
            return
        if not question(
            self,
            "Delete Confirmation",
            f"Are you sure you want to delete {len(rows)} device(s)?",
        ):
            return
        self.deleteRequested.emit(rows)

    @Slot()
    def filter_devices(self, text):
        self.apply_filter(text)

    def apply_filter(self, text: str):
        regex = QRegularExpression(text)
        if not regex.isValid():
            regex = QRegularExpression(re.escape(text))
        self.proxy_model.setFilterRegularExpression(regex)

    @Slot()
    def copy_selected_from_rows(self, rows: list[int]):
        if not rows:
            return
        self.copyRequested.emit(rows)

    @Slot()
    def open_paste_to_rows(self, rows: list[int]):
        self.pasteRequested.emit(rows)

    def _wire_model_dirty(self, model: DeviceTableModel):
        model.modified.connect(lambda: self.dirtyChanged.emit(model.is_modified()))

    def install_delegate(self, col_name: str, delegate: QStyledItemDelegate):
        model = self.model_safe()
        if not model or col_name not in model._columns:
            return
        col_index = model._columns.index(col_name)
        self.setItemDelegateForColumn(col_index, delegate)

    def dropEvent(self, event):
        if event.source() is not self or (
            event.dropAction() != Qt.MoveAction
            and self.dragDropMode() != QAbstractItemView.InternalMove
        ):
            super().dropEvent(event)
            return

        sel_rows_proxy = self._selected_proxy_rows()
        if not sel_rows_proxy:
            super().dropEvent(event)
            return

        proxy_from_first = sel_rows_proxy[0]
        proxy_count = len(sel_rows_proxy)

        is_contiguous = sel_rows_proxy == list(
            range(proxy_from_first, proxy_from_first + proxy_count)
        )
        if not is_contiguous:
            event.ignore()
            return

        model = self.model_safe()
        if not model:
            event.ignore()
            return

        src_from = self._map_to_source_row(proxy_from_first)

        proxy_pos_index = self.indexAt(event.pos())
        drop_pos = self.dropIndicatorPosition()

        if drop_pos == QAbstractItemView.OnViewport:
            src_to = model.rowCount()
        else:
            if not proxy_pos_index.isValid():
                event.ignore()
                return
            src_hover = self._map_to_source_row(proxy_pos_index.row())
            if drop_pos == QAbstractItemView.AboveItem:
                src_to = src_hover
            elif drop_pos == QAbstractItemView.BelowItem:
                src_to = src_hover + 1
            else:
                src_to = src_hover if src_from > src_hover else src_hover + 1

        src_to = max(0, min(src_to, model.rowCount()))
        if src_from == src_to or proxy_count <= 0:
            event.ignore()
            return

        try:
            model.relocateRow(src_from, src_to, proxy_count)
            event.setDropAction(Qt.MoveAction)
            event.acceptProposedAction()
        except Exception:
            event.ignore()
