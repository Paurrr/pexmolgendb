from PySide6.QtWidgets import QTableView, QHeaderView
from PySide6.QtCore import Signal
from models.parameter_summary import ParameterSummaryModel


class ParameterSummaryView(QTableView):
    sourceActivated = Signal(str, int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._model = ParameterSummaryModel(self)
        self.setModel(self._model)
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QTableView.SelectRows)
        self.setEditTriggers(QTableView.NoEditTriggers)
        self.verticalHeader().setDefaultSectionSize(20)
        self.verticalHeader().setMinimumSectionSize(18)
        self.horizontalHeader().setFixedHeight(22)
        self.doubleClicked.connect(self._activate_source)
        self._resize_columns()

    def set_rows(self, rows: list[dict]):
        self._model.set_rows(rows)
        self._resize_columns()

    def _activate_source(self, index):
        source = self._model.source_at(index.row())
        if source:
            self.sourceActivated.emit(*source)

    def _resize_columns(self):
        header = self.horizontalHeader()
        widths = [96, 42, 180, 220]
        for col, width in enumerate(widths):
            header.setSectionResizeMode(col, QHeaderView.Interactive)
            header.resizeSection(col, width)
        header.setSectionResizeMode(3, QHeaderView.Stretch)
