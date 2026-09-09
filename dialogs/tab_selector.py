from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QListWidget,
    QDialogButtonBox,
)


class TabSelectorDialog(QDialog):
    def __init__(self, available_tabs, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Tab to Add")

        layout = QVBoxLayout()
        self.list_widget = QListWidget()
        self.list_widget.addItems(available_tabs)
        layout.addWidget(self.list_widget)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        self.setLayout(layout)

    def get_selected_tab(self) -> str | None:
        selected_items = self.list_widget.selectedItems()
        if selected_items:
            return selected_items[0].text()
        return None
