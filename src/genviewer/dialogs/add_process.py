from PySide6.QtCore import Slot
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
)

from genviewer.service.repo.audit import process_label

# 빈 버전 "" 의 표시 글자(툴바 version 콤보). 값이 아니라서 버전 이름으로 받지 않는다.
NO_RELEASE_TEXT = "(none)"
NO_COPY_TEXT = "(no copy)"

_EXISTS = "This process already exists."
_NO_RELEASE = f"{NO_RELEASE_TEXT} cannot be used as a version name."


class AddProcessDialog(QDialog):
    """새 (이름, 버전) 쌍과 복사 원본을 고른다. repo 도 메시지 상자도 모른다.

    잘못된 입력은 OK 를 끄고 그 이유를 창 안의 한 줄로 보인다.
    """

    def __init__(
        self, pairs: list[tuple[str, str]], current: tuple[str, str], parent=None
    ):
        super().__init__(parent)
        self.setWindowTitle("Add Process")
        self.setMinimumWidth(320)
        self._pairs = [(n, r) for n, r in pairs]

        self.name_box = QComboBox()
        self.name_box.setEditable(True)
        # 기본 completer(대소문자 무시 inline 완성)가 친 이름을 기존 이름으로 바꾼다(K56).
        self.name_box.setCompleter(None)
        self.name_box.addItems(list(dict.fromkeys(n for n, _ in self._pairs)))
        self.name_box.setCurrentIndex(self.name_box.findText(current[0]))

        self.release_edit = QLineEdit()

        # 처음 값은 NO_COPY_TEXT 이다. 지금 쌍이면 새 process 를 만들려던 사람이 모르고
        # device 를 복사한다.
        self.source_box = QComboBox()
        self.source_box.addItems([NO_COPY_TEXT] + [process_label(*p) for p in self._pairs])

        form = QFormLayout()
        form.addRow("Process", self.name_box)
        form.addRow("Version", self.release_edit)
        form.addRow("Copy from", self.source_box)

        self.reason_label = QLabel("")
        self.reason_label.setObjectName("ErrorLabel")

        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)

        layout = QVBoxLayout()
        layout.addLayout(form)
        layout.addWidget(self.reason_label)
        layout.addWidget(self.buttons)
        self.setLayout(layout)

        self.name_box.editTextChanged.connect(self._update)
        self.release_edit.textChanged.connect(self._update)
        self._update()

    def values(self) -> tuple[str, str, tuple[str, str] | None]:
        """(다듬은 이름, 다듬은 버전, 복사 원본 쌍 또는 None)."""
        index = self.source_box.currentIndex()
        source = self._pairs[index - 1] if index > 0 else None
        return (
            self.name_box.currentText().strip(),
            self.release_edit.text().strip(),
            source,
        )

    @Slot()
    def _update(self):
        name, release, _source = self.values()
        if not name:
            reason, ok = "", False
        elif release == NO_RELEASE_TEXT:
            reason, ok = _NO_RELEASE, False
        elif (name, release) in self._pairs:
            reason, ok = _EXISTS, False
        else:
            reason, ok = "", True
        self.reason_label.setText(reason)
        self.buttons.button(QDialogButtonBox.Ok).setEnabled(ok)
