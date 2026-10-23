from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QPushButton,
    QSizePolicy,
    QWidget,
)

# 빈 버전 "" 의 표시 글자. 값이 아니다. 버전은 글자가 아니라 index 로 _releases 에서 읽는다.
# 추가 창도 이 글자를 버전 이름으로 받지 않아야 해서 그쪽에 둔다.
from genviewer.dialogs.add_process import NO_RELEASE_TEXT, AddProcessDialog


class DeviceTabToolBar(QWidget):
    # (이름, 버전). 사용자 동작 한 번 또는 실제로 바뀐 선택 한 번에 정확히 한 번 낸다.
    selectionChanged = Signal(str, str)
    # (이름, 버전, 복사 원본 쌍 또는 None).
    addProcessRequested = Signal(str, str, object)
    # (이름, 버전). 지울 쌍이다.
    removeProcessRequested = Signal(str, str)
    addLibraryRequested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("DeviceTabControlToolBar")
        layout = QHBoxLayout()
        layout.setSpacing(3)
        self.setMinimumSize(0, 0)
        # Ignored 면 창이 툴바보다 좁아져 고정 너비 단추·콤보가 겹친다(K57).
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.setFixedHeight(34)

        self.process_selector_label = QLabel("Process")
        self.process_selector_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        layout.addWidget(self.process_selector_label)

        # process 이름은 대개 10글자 안이고 버전(S00-V1.0.0.0 …)이 더 길어서 Version 이 더 넓다.
        # 두 최소 너비의 합은 그대로라 창 최소 너비가 같다.
        self.process_selector = QComboBox()
        self.process_selector.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.process_selector.setMinimumWidth(120)
        self.process_selector.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToContents
        )

        self.release_selector_label = QLabel("Version")
        self.release_selector_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        self.release_selector = QComboBox()
        self.release_selector.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.release_selector.setMinimumWidth(160)
        self.release_selector.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToContents
        )

        # set_pairs 가 준 (이름, 버전) 목록, version 콤보 항목과 같은 순서의 버전, 마지막으로
        # 알린(또는 조용히 고른) 쌍.
        self._pairs: list[tuple[str, str]] = []
        self._releases: list[str] = []
        self._pair: tuple[str, str] = ("", "")
        self.process_selector.currentIndexChanged.connect(self._on_process_index_changed)
        self.release_selector.currentIndexChanged.connect(self._on_release_index_changed)

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
        layout.addWidget(self.release_selector_label)
        layout.addWidget(self.release_selector)
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
        answer = self._ask_add_pair()
        if answer is not None:
            self.addProcessRequested.emit(*answer)

    def _ask_add_pair(self) -> tuple[str, str, tuple[str, str] | None] | None:
        """추가 창을 띄운다. OK 면 (이름, 버전, 복사 원본 또는 None), 아니면 None."""
        dialog = AddProcessDialog(self.pairs(), self.current_pair(), self)
        try:
            if dialog.exec() != QDialog.Accepted:
                return None
            return dialog.values()
        finally:
            dialog.deleteLater()

    @Slot()
    def open_remove_process_dialog(self):
        # 묻지 않는다. 확인은 controller 의 Remove Process 질문 하나다(device 수를 알려 준다).
        name, release = self.current_pair()
        if not name:
            return
        self.removeProcessRequested.emit(name, release)

    @Slot()
    def open_add_library_dialog(self):
        text, ok = QInputDialog.getText(self, "Add Library", "Enter library name:")
        if not ok:
            return
        name = (text or "").strip()
        if not name:
            return
        self.addLibraryRequested.emit(name)

    def pairs(self) -> list[tuple[str, str]]:
        return list(self._pairs)

    def releases_of(self, name: str) -> list[str]:
        return [release for n, release in self._pairs if n == name]

    def current_pair(self) -> tuple[str, str]:
        """지금 (이름, 버전). 어느 콤보든 비었으면 ("", "")."""
        index = self.release_selector.currentIndex()
        if self.process_selector.currentIndex() == -1 or not 0 <= index < len(self._releases):
            return ("", "")
        return (self.process_selector.currentText(), self._releases[index])

    @Slot(list)
    def set_pairs(self, pairs: list[tuple[str, str]]):
        """두 콤보를 시그널 없이 다시 채운다. 쌍이 바뀌었을 때만 selectionChanged 를 한 번 낸다.

        지금 쌍이 있으면 그대로, 이름만 있으면 그 이름의 첫 버전, 이름도 없으면 첫 쌍.
        """
        name, release = self.current_pair()
        self._pairs = [(n, r) for n, r in pairs]
        if (name, release) in self._pairs:
            target = (name, release)
        elif releases := self.releases_of(name):
            target = (name, releases[0])
        elif self._pairs:
            target = self._pairs[0]
        else:
            target = ("", "")
        self._block(True)
        self.process_selector.clear()
        self.process_selector.addItems(list(dict.fromkeys(n for n, _ in self._pairs)))
        self._show(*target)
        self._block(False)
        self._announce()

    def select_pair(self, name: str, release: str):
        """그 쌍을 고른다. 바뀌었으면 selectionChanged 한 번. 없는 쌍이면 아무것도 하지 않는다."""
        if self._select(name, release):
            self._announce()

    def select_silently(self, name: str, release: str) -> bool:
        """selectionChanged 없이 그 쌍을 고른다. 목록에 없으면 아무것도 바꾸지 않고 False."""
        if not self._select(name, release):
            return False
        # 조용히 고른 쌍이 다음 비교의 기준이다.
        self._pair = self.current_pair()
        return True

    def _select(self, name: str, release: str) -> bool:
        if (name, release) not in self._pairs:
            return False
        self._block(True)
        self._show(name, release)
        self._block(False)
        return True

    def _block(self, blocked: bool):
        self.process_selector.blockSignals(blocked)
        self.release_selector.blockSignals(blocked)

    def _show(self, name: str, release: str):
        """시그널을 막은 채로 부른다. 목록에 없는 이름이면 version 콤보가 빈다."""
        self.process_selector.setCurrentIndex(self.process_selector.findText(name))
        self._fill_releases(name, release)

    def _fill_releases(self, name: str, release: str | None):
        """version 콤보를 name 의 버전으로 채운다. release 가 있으면 그것, 없으면 첫 버전."""
        self._releases = self.releases_of(name)
        self.release_selector.clear()
        self.release_selector.addItems([r or NO_RELEASE_TEXT for r in self._releases])
        if release in self._releases:
            self.release_selector.setCurrentIndex(self._releases.index(release))

    def _announce(self):
        pair = self.current_pair()
        if pair != self._pair:
            self._pair = pair
            self.selectionChanged.emit(*pair)

    @Slot(int)
    def _on_process_index_changed(self, index: int):
        # 시그널을 막지 않은 채 이름이 바뀌었다(사용자). 지금 버전이 그
        # 이름에도 있으면 그것, 없으면 첫 버전. version 콤보를 채우는 동안 중간 쌍을 알리지 않는다.
        selected = self.release_selector.currentIndex()
        release = self._releases[selected] if 0 <= selected < len(self._releases) else None
        self.release_selector.blockSignals(True)
        self._fill_releases(self.process_selector.itemText(index), release)
        self.release_selector.blockSignals(False)
        self._announce()

    @Slot(int)
    def _on_release_index_changed(self, index: int):
        self._announce()

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
