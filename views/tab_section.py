from PySide6.QtCore import QPoint, Qt, Signal, Slot
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QStyledItemDelegate,
    QVBoxLayout,
    QWidget,
)

from dialogs.insert import InsertDialog
from models.generic_table import GenericTableModel
from utils.dialogs import question
from views.parameter_table import ParameterTableView


class TabSection(QWidget):
    dirtyChanged = Signal(bool)
    insertRequested = Signal(dict)
    editRequested = Signal(int, dict)
    deleteRequested = Signal(list)
    copyRequested = Signal(list)
    pasteRequested = Signal(list)
    contextMenuRequested = Signal(list, QPoint)

    def __init__(
        self,
        columns: list[str],
        headers: list[str],
        table_name: str,
        title: str | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.columns = columns
        self.headers = headers
        self.table_name = table_name
        self.title = title or table_name
        self.table_view = ParameterTableView(self)

        v_layout = QVBoxLayout()
        v_layout.setContentsMargins(3, 3, 3, 3)
        v_layout.setSpacing(2)
        v_layout.addWidget(self._build_header())
        v_layout.addWidget(self.table_view)
        self.setLayout(v_layout)

    def _build_header(self) -> QWidget:
        widget = QWidget(self)
        widget.setObjectName("TabSectionHeader")
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(2)

        title_label = QLabel(f"<b>{self.title}</b>")
        title_label.setObjectName("TabSectionTitle")
        title_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout.addWidget(title_label)

        self.insert_btn = QPushButton("Insert")
        self.edit_btn = QPushButton("Edit")
        self.delete_btn = QPushButton("Delete")
        self.copy_btn = QPushButton("Copy")
        self.paste_btn = QPushButton("Paste")
        self.clear_selection_btn = QPushButton("Clear Sel")

        self.insert_btn.clicked.connect(self.open_insert_dialog)
        self.edit_btn.clicked.connect(self.edit_selected_row)
        self.delete_btn.clicked.connect(
            lambda: self.delete_rows(self.table_view._selected_rows())
        )
        self.copy_btn.clicked.connect(
            lambda: self.copy_selected_from_rows(self.table_view._selected_rows())
        )
        self.paste_btn.clicked.connect(
            lambda: self.paste_to_rows(self.table_view._selected_rows())
        )
        self.clear_selection_btn.clicked.connect(self.table_view.clearSelection)

        for button in (
            self.insert_btn,
            self.edit_btn,
            self.delete_btn,
            self.copy_btn,
            self.paste_btn,
            self.clear_selection_btn,
        ):
            button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            layout.addWidget(button)

        return widget

    @Slot(object, object)
    def on_device_changed(self, device_id, device_celltype):
        self.device_id = device_id
        self.device_celltype = device_celltype

    def open_insert_dialog(self):
        dlg = InsertDialog(
            self.device_celltype, self.table_name, self.columns, self.headers, self
        )
        if dlg.exec_() == QDialog.Accepted:
            values = dlg.get_data()
            if values:
                self.insertRequested.emit(values)

    def open_edit_dialog(self, r: int, old_values: dict):
        dlg = InsertDialog(
            self.device_celltype,
            self.table_name,
            self.columns,
            self.headers,
            self,
            prefill=old_values,
            window_title="Edit",
        )
        if dlg.exec_() != QDialog.Accepted:
            return

        new_values = dlg.get_data()
        if new_values is None:
            return

        self.editRequested.emit(r, new_values)

    def edit_selected_row(self):
        rows = self.table_view._selected_rows()
        if not rows:
            return
        model = self.table_view.model()
        old_values = {}
        if model:
            old_values = {
                col: model.data(model.index(rows[0], c))
                for c, col in enumerate(self.columns)
            }
        self.open_edit_dialog(rows[0], old_values)

    def delete_rows(self, rows: list[int]):
        if not rows:
            return
        if not question(
            self, "Delete Confirmation",
            f"Are you sure you want to delete {len(rows)} data?"
        ):
            return
        self.deleteRequested.emit(rows)

    def copy_selected_from_rows(self, rows: list[int]):
        if not rows:
            return
        self.copyRequested.emit(rows)

    def paste_to_rows(self, rows: list[int]):
        self.pasteRequested.emit(rows)

    def contextMenuEvent(self, event):
        rows = self.table_view._selected_rows()
        index = self.table_view.indexAt(
            self.table_view.viewport().mapFrom(self, event.pos())
        )
        if index.isValid() and not rows:
            rows = [index.row()]

        global_pos = self.mapToGlobal(event.pos())
        self.contextMenuRequested.emit(rows, global_pos)

    def keyPressEvent(self, event):
        if event.modifiers() == Qt.ControlModifier:
            if event.key() == Qt.Key_C:
                self.copy_selected_from_rows(self.table_view._selected_rows())
            elif event.key() == Qt.Key_V:
                self.paste_to_rows(self.table_view._selected_rows())
            elif event.key() == Qt.Key_I:
                self.open_insert_dialog()
            elif event.key() == Qt.Key_D:
                self.delete_rows(self.table_view._selected_rows())
            elif event.key() == Qt.Key_E:
                rows = self.table_view._selected_rows()
                if rows:
                    self.open_edit_dialog(rows[0], {})
        elif event.modifiers() == Qt.NoModifier:
            if event.key() == Qt.Key_Delete:
                self.delete_rows(self.table_view._selected_rows())
        super().keyPressEvent(event)

    def mark_dirty_ui(self, on: bool):
        self.dirtyChanged.emit(on)

    def _wire_model_dirty(self, model: GenericTableModel):
        model.modified.connect(lambda: self.dirtyChanged.emit(model.is_modified()))

    def install_delegate(
        self, model: GenericTableModel, col_name: str, delegate: QStyledItemDelegate
    ):
        if not model or col_name not in model.columns:
            return
        col_index = self.columns.index(col_name)
        self.table_view.setItemDelegateForColumn(col_index, delegate)
