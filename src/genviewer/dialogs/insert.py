from PySide6.QtCore import QRegularExpression, Qt
from PySide6.QtGui import (
    QDoubleValidator,
    QFontMetrics,
    QIntValidator,
    QRegularExpressionValidator,
)
from PySide6.QtWidgets import (
    QComboBox,
    QCompleter,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from genviewer.config.config import delegate_config
from genviewer.utils.validators import allowed_items, validate_field_value


class InsertDialog(QDialog):
    def __init__(
        self,
        device_celltype: str | None,
        table_name: str,
        field_names: list[str],
        headers: list[str],
        parent=None,
        prefill=None,
        window_title="Insert",
    ):
        super().__init__(parent)
        self.setWindowTitle(window_title)
        self.column_to_label = dict(zip(field_names, headers, strict=True))
        self.device_celltype = device_celltype
        self.field_names = field_names
        self.fields: dict[str, QLineEdit | QComboBox] = {}
        self.field_configs: dict[str, dict] = {}

        layout = QVBoxLayout()

        font_metrics = QFontMetrics(self.font())
        max_width = (
            max(font_metrics.horizontalAdvance(name) for name in field_names) + 10
        )

        table_config = delegate_config.get(table_name, {})
        row_length = len(field_names) + 1

        self.setFixedHeight(row_length * 35)
        self.resize(400, row_length * 35)

        for name in field_names:
            label_text = self.column_to_label.get(name, name)
            field_config = table_config.get(name, {})
            self.field_configs[name] = field_config
            is_required = field_config.get("required", False)

            hlayout = QHBoxLayout()
            label = QLabel(label_text)
            label.setFixedWidth(max_width)

            if "items" in field_config:
                items = allowed_items(field_config, self.device_celltype)
                widget = self._make_locked_searchable_combo(items)
                if prefill and name in prefill:
                    widget.setCurrentText(str(prefill.get(name, "")))
            else:
                widget = QLineEdit()
                if field_config.get("type") == "int":
                    widget.setValidator(QIntValidator())
                elif field_config.get("type") == "float":
                    widget.setValidator(QDoubleValidator())

                if prefill and name in prefill:
                    widget.setText(str(prefill.get(name, "")))

            if is_required:
                widget.setProperty("requiredField", "true")

            hlayout.addWidget(label)
            hlayout.addWidget(widget)
            layout.addLayout(hlayout)
            self.fields[name] = widget

        button_layout = QHBoxLayout()
        ok_button = QPushButton("OK")
        cancel_button = QPushButton("Cancel")
        ok_button.clicked.connect(self._on_ok_clicked)
        cancel_button.clicked.connect(self.reject)
        button_layout.addStretch(1)
        button_layout.addWidget(ok_button)
        button_layout.addWidget(cancel_button)

        self.error_label = QLabel("")
        self.error_label.setObjectName("ErrorLabel")
        self.error_label.setVisible(False)

        layout.addLayout(button_layout)
        layout.addWidget(self.error_label)
        self.setLayout(layout)

    def get_data(self) -> dict | None:
        data = {}
        invalid_widgets = []

        for name, widget in self.fields.items():
            value = (
                widget.currentText() if isinstance(widget, QComboBox) else widget.text()
            ).strip()
            label = self.column_to_label.get(name, name)
            ok, message = validate_field_value(
                value,
                self.field_configs.get(name, {}),
                celltype=self.device_celltype,
                label=label,
            )
            if not ok:
                invalid_widgets.append((widget, message))
            data[name] = value

        if invalid_widgets:
            widget, message = invalid_widgets[0]
            self.error_label.setText(message)
            self.error_label.setVisible(True)
            widget.setFocus()
            current_width = self.width()
            expanded_height = self.height() + 30
            self.setFixedHeight(0)
            self.resize(current_width, expanded_height)
            self.setFixedHeight(expanded_height)
            return None

        self.error_label.setVisible(False)
        return data

    def _on_ok_clicked(self):
        data = self.get_data()
        if data is not None:
            self._result_data = data
            self.accept()

    def get_result(self) -> dict:
        return getattr(self, "_result_data", {})

    def _make_locked_searchable_combo(self, items: list[str]) -> QComboBox:
        combo = QComboBox()
        combo.setEditable(True)
        combo.addItems(items)
        combo.setInsertPolicy(QComboBox.NoInsert)

        comp = combo.completer()
        comp.setCompletionMode(QCompleter.PopupCompletion)
        comp.setFilterMode(Qt.MatchContains)

        if items:
            escaped = [QRegularExpression.escape(s) for s in items]
            pattern = f"^(?:{'|'.join(escaped)})$"
            validator = QRegularExpressionValidator(QRegularExpression(pattern))
            combo.lineEdit().setValidator(validator)

        def normalize_to_valid():
            txt = combo.currentText()
            idx = combo.findText(txt, Qt.MatchFixedString)
            if idx >= 0:
                combo.setCurrentIndex(idx)
            elif combo.currentIndex() < 0 and combo.count() > 0:
                combo.setCurrentIndex(0)

        combo.lineEdit().editingFinished.connect(normalize_to_valid)
        return combo
