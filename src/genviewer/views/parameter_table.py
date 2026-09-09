from PySide6.QtCore import Qt
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import QAbstractItemView, QHeaderView, QTableView

from genviewer.models.generic_table import GenericTableModel


class ParameterTableView(QTableView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QTableView.InternalMove)
        self.setSelectionBehavior(QTableView.SelectRows)
        self.setDefaultDropAction(Qt.MoveAction)
        self.verticalHeader().setVisible(True)
        self.setAlternatingRowColors(True)
        self.verticalHeader().setDefaultSectionSize(20)
        self.verticalHeader().setMinimumSectionSize(18)
        self.horizontalHeader().setFixedHeight(22)

    def setModel(self, model):
        super().setModel(model)
        if isinstance(model, GenericTableModel):
            self._auto_resize_columns(model)

    def _selected_rows(self) -> list[int]:
        sel = self.selectionModel()
        if not sel:
            return []
        return sorted({idx.row() for idx in sel.selectedRows()})

    def _auto_resize_columns(self, model):
        fm = QFontMetrics(self.font())
        header = self.horizontalHeader()
        col_count = model.columnCount()

        for i in range(col_count):
            header.setSectionResizeMode(i, QHeaderView.Interactive)
            width = fm.horizontalAdvance(model.headers[i]) + 18
            header.resizeSection(i, width)

        if col_count > 0:
            header.setSectionResizeMode(col_count - 1, QHeaderView.Stretch)

    def dropEvent(self, event):
        if event.source() is not self or (
            event.dropAction() != Qt.MoveAction
            and self.dragDropMode() != QAbstractItemView.InternalMove
        ):
            super().dropEvent(event)
            return

        model = self.model()
        if model is None:
            super().dropEvent(event)
            return
        row_count_src = model.rowCount()

        sel = self.selectionModel().selectedRows()
        if not sel:
            super().dropEvent(event)
            return

        rows = sorted(idx.row() for idx in sel)
        first_row = rows[0]
        count = len(rows)

        if rows != list(range(first_row, first_row + count)):
            event.ignore()
            return

        src_from = first_row
        hover_idx = self.indexAt(event.pos())
        drop_pos = self.dropIndicatorPosition()

        if drop_pos == QAbstractItemView.OnViewport:
            src_to = row_count_src
        else:
            if not hover_idx.isValid():
                event.ignore()
                return
            src_hover = hover_idx.row()

            if drop_pos == QAbstractItemView.AboveItem:
                src_to = src_hover
            elif drop_pos == QAbstractItemView.BelowItem:
                src_to = src_hover + 1
            else:
                src_to = src_hover if src_from > src_hover else src_hover + 1

        src_to = max(0, min(src_to, row_count_src))
        if src_from == src_to or count <= 0:
            event.ignore()
            return

        try:
            model.relocateRow(src_from, src_to, count)
            event.setDropAction(Qt.MoveAction)
            event.acceptProposedAction()
        except Exception:
            event.ignore()
