from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QPushButton,
    QSizePolicy,
    QWidget,
)

from genviewer.utils.dialogs import question


class DeviceTabToolBar(QWidget):
    addProcessRequested = Signal(str)
    removeProcessRequested = Signal(str)
    addLibraryRequested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("DeviceTabControlToolBar")
        layout = QHBoxLayout()
        layout.setSpacing(3)
        self.setMinimumSize(0, 0)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        self.setFixedHeight(34)

        self.process_selector_label = QLabel("Process")
        self.process_selector_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        layout.addWidget(self.process_selector_label)

        self.process_selector = QComboBox()
        self.process_selector.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.process_selector.setMinimumWidth(160)
        self.process_selector.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToContents
        )

        self.add_process_btn = QPushButton("+")
        self.add_process_btn.setToolTip("Add process")
        self.add_process_btn.clicked.connect(self.open_add_process_dialog)
        self.add_process_btn.setFixedWidth(30)
        self.add_process_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        self.remove_process_btn = QPushButton("-")
        self.remove_process_btn.setToolTip("Remove process")
        self.remove_process_btn.clicked.connect(self.open_remove_process_dialog)
        self.remove_process_btn.setFixedWidth(30)
        self.remove_process_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        self.load_virtuoso_btn = QPushButton("Load Virtuoso")
        self.load_virtuoso_btn.setToolTip("Load Virtuoso device list")
        self.load_virtuoso_btn.setFixedWidth(110)
        self.load_virtuoso_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        layout.addWidget(self.process_selector)
        layout.addWidget(self.add_process_btn)
        layout.addWidget(self.remove_process_btn)
        layout.addWidget(self.load_virtuoso_btn)
        layout.addSpacing(2)

        self.library_selector_label = QLabel("Library")
        self.library_selector_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        layout.addWidget(self.library_selector_label)

        self.library_selector = QComboBox()
        self.library_selector.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.library_selector.setMinimumWidth(150)
        self.library_selector.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToContents
        )
        layout.addWidget(self.library_selector)

        self.add_library_btn = QPushButton("+")
        self.add_library_btn.setToolTip("Add library")
        self.add_library_btn.clicked.connect(self.open_add_library_dialog)
        self.add_library_btn.setFixedWidth(30)
        self.add_library_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        layout.addWidget(self.add_library_btn)

        self.load_libraries_btn = QPushButton("Load Libs")
        self.load_libraries_btn.setToolTip("Load Virtuoso library list")
        self.load_libraries_btn.setFixedWidth(82)
        self.load_libraries_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        layout.addWidget(self.load_libraries_btn)
        layout.addSpacing(2)

        self.gen_layout_label = QLabel("Gen Layout")
        self.gen_layout_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        layout.addWidget(self.gen_layout_label)

        self.gen_layout_toggle = QPushButton("Off")
        self.gen_layout_toggle.setCheckable(True)
        self.gen_layout_toggle.setFixedWidth(64)
        self.gen_layout_toggle.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.gen_layout_toggle.toggled.connect(self._set_gen_layout_text)
        layout.addWidget(self.gen_layout_toggle)
        layout.addSpacing(2)

        self.run_type_label = QLabel("Run")
        self.run_type_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.selected_run_btn = QPushButton("Selected")
        self.selected_run_btn.setFixedWidth(80)
        self.selected_run_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        self.all_run_btn = QPushButton("All")
        self.all_run_btn.setFixedWidth(50)
        self.all_run_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        layout.addWidget(self.run_type_label)
        layout.addWidget(self.selected_run_btn)
        layout.addWidget(self.all_run_btn)
        layout.addStretch(1)
        layout.setContentsMargins(4, 3, 4, 3)
        self.setLayout(layout)
        self.setAttribute(Qt.WA_StyledBackground, True)

    @Slot(bool)
    def _set_gen_layout_text(self, checked: bool):
        self.gen_layout_toggle.setText("On" if checked else "Off")

    @Slot()
    def open_add_process_dialog(self):
        text, ok = QInputDialog.getText(self, "Add Process", "Enter new process name:")
        if not ok:
            return
        name = (text or "").strip()
        if not name:
            return
        self.addProcessRequested.emit(name)

    @Slot()
    def open_remove_process_dialog(self):
        name = self.process_selector.currentText()
        if not name:
            return
        if self.process_selector.findText(name) == -1:
            return
        if question(
            self,
            "Confirm Delete",
            f"Are you sure you want to delete the process:\n'{name}'?",
        ):
            self.removeProcessRequested.emit(name)

    @Slot()
    def open_add_library_dialog(self):
        text, ok = QInputDialog.getText(self, "Add Library", "Enter library name:")
        if not ok:
            return
        name = (text or "").strip()
        if not name:
            return
        self.addLibraryRequested.emit(name)

    @Slot()
    def set_processes(self, items: list[str]):
        # clear() 와 addItems() 는 "" 와 첫 항목으로 currentTextChanged 를 두 번 낸다. 그 사이
        # 지금 process 의 편집이 묻지도 않고 버려진다. 막고 다시 채운 뒤, 지금 process 가
        # 목록에서 사라져 바뀐 경우에만 최종 이름으로 한 번 낸다.
        current = self.process_selector.currentText()
        self.process_selector.blockSignals(True)
        self.process_selector.clear()
        self.process_selector.addItems(items)
        if current in items:
            self.process_selector.setCurrentText(current)
        self.process_selector.blockSignals(False)
        selected = self.process_selector.currentText()
        if selected != current:
            self.process_selector.currentTextChanged.emit(selected)

    @Slot()
    def select_process(self, name: str):
        self.process_selector.setCurrentText(name)

    def select_process_silently(self, name: str) -> bool:
        index = self.process_selector.findText(name)
        if index == -1:
            return False
        self.process_selector.blockSignals(True)
        self.process_selector.setCurrentIndex(index)
        self.process_selector.blockSignals(False)
        return True

    @Slot()
    def set_libraries(self, items: list[str]):
        current = self.library_selector.currentText()
        self.library_selector.blockSignals(True)
        self.library_selector.clear()
        self.library_selector.addItems(items)
        if current and current in items:
            self.library_selector.setCurrentText(current)
        self.library_selector.blockSignals(False)

    def add_library(self, name: str):
        if self.library_selector.findText(name) == -1:
            self.library_selector.addItem(name)
        self.library_selector.setCurrentText(name)
