from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QCompleter, QStyledItemDelegate

from utils.validators import allowed_items


class ComboBoxDelegate(QStyledItemDelegate):
    def __init__(
        self,
        items: list[str],
        required=False,
        strict=False,
        items_by_celltype=None,
        parent=None,
    ):
        super().__init__(parent)
        self.items = items
        self.items_by_celltype = items_by_celltype or {}
        self.required = required
        self.strict = strict

    def _items_for_index(self, index) -> list[str]:
        model = index.model()
        celltype = getattr(model, "device_celltype", None)
        return allowed_items(
            {"items": self.items, "items_by_celltype": self.items_by_celltype},
            celltype,
        )

    def createEditor(self, parent, option, index):
        combo = QComboBox(parent)
        combo.setEditable(True)
        combo.addItems(self._items_for_index(index))

        if self.strict:
            combo.setInsertPolicy(QComboBox.NoInsert)
        else:
            combo.setInsertPolicy(QComboBox.InsertAtTop)

        completer = combo.completer()
        completer.setCompletionMode(QCompleter.PopupCompletion)
        completer.setFilterMode(Qt.MatchContains)

        return combo

    def setEditorData(self, editor, index):
        value = index.data(Qt.EditRole)
        if value:
            idx = editor.findText(value)
            if idx >= 0:
                editor.setCurrentIndex(idx)
            else:
                editor.setEditText(value)

    def setModelData(self, editor, model, index):
        value = editor.currentText()
        if self.required and not value.strip():
            return
        if self.strict and value not in self._items_for_index(index):
            return
        model.setData(index, value, Qt.EditRole)
