"""저장 충돌 다이얼로그.

QMessageBox 가 아니라 QDialog 인 이유는 device 여러 개가 한꺼번에 충돌할 수
있어서 목록을 보여줘야 하기 때문이다. utils.dialogs.question 은 Yes/No 전용이라
재사용할 수 없다.
"""

from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QVBoxLayout,
)

RELOAD = "reload"
OVERWRITE = "overwrite"
CANCEL = "cancel"


def can_overwrite(conflicts, my_deletions=()) -> bool:
    """충돌 대화상자가 덮어쓰기를 내놓을지. Qt 를 쓰지 않는다(테스트 가짜도 이것을 쓴다).

    내가 지운 행(my_deletions)의 충돌을 뺀 나머지가 있고 전부 "deleted" 면 False 다. 덮어쓸
    행이 없다. 내가 지운 행은 남도 지웠어도 덮어쓰기가 해가 없어서(지울 행이 이미 없다) 뺀다.
    """
    mine = set(my_deletions)
    rest = [c for c in conflicts if c.device_id not in mine]
    return not rest or any(c.reason != "deleted" for c in rest)


class ConflictDialog(QDialog):
    def __init__(self, parent, conflicts, *, allow_overwrite=True):
        super().__init__(parent)
        self.setWindowTitle("Save Conflict")
        self.setMinimumWidth(460)
        self._choice = CANCEL

        header = QLabel("Another user changed this data first.")
        header.setWordWrap(True)

        listing = QListWidget()
        for conflict in conflicts:
            listing.addItem(conflict.describe())
        listing.setMaximumHeight(160)

        reload_btn = QPushButton("Reload")
        reload_btn.setToolTip("Reload from the server. Your unsaved changes are discarded.")
        reload_btn.setDefault(True)
        reload_btn.clicked.connect(lambda: self._done(RELOAD))

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setToolTip("Save nothing. Your changes stay as they are.")
        cancel_btn.clicked.connect(lambda: self._done(CANCEL))

        row = QHBoxLayout()
        row.addWidget(reload_btn)
        # 덮어쓸 행이 없으면 만들지 않는다(can_overwrite). 고르면 편집이 조용히 사라지거나
        # (device 저장) 같은 충돌이 다시 난다(탭 저장).
        if allow_overwrite:
            overwrite_btn = QPushButton("Overwrite with Mine")
            overwrite_btn.setToolTip("Replace the other user's change with yours.")
            overwrite_btn.clicked.connect(lambda: self._done(OVERWRITE))
            row.addWidget(overwrite_btn)
        row.addStretch()
        row.addWidget(cancel_btn)

        layout = QVBoxLayout()
        layout.addWidget(header)
        layout.addWidget(listing)
        layout.addLayout(row)
        self.setLayout(layout)

    def _done(self, choice: str) -> None:
        self._choice = choice
        self.accept()

    @property
    def choice(self) -> str:
        return self._choice


def ask_conflict(parent, conflicts, my_deletions=()) -> str:
    """RELOAD / OVERWRITE / CANCEL 중 하나를 반환한다.

    my_deletions: 이번 저장에서 내가 지운 device id. 덮어쓰기를 숨겼으면 RELOAD / CANCEL 뿐이다.
    """
    dialog = ConflictDialog(
        parent, conflicts, allow_overwrite=can_overwrite(conflicts, my_deletions)
    )
    dialog.exec()
    return dialog.choice
