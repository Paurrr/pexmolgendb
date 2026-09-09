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


class ConflictDialog(QDialog):
    def __init__(self, parent, conflicts):
        super().__init__(parent)
        self.setWindowTitle("Save Conflict")
        self.setMinimumWidth(460)
        self._choice = CANCEL

        header = QLabel("다른 사용자가 편집 중인 데이터를 먼저 변경했다.")
        header.setWordWrap(True)

        listing = QListWidget()
        for conflict in conflicts:
            listing.addItem(conflict.describe())
        listing.setMaximumHeight(160)

        reload_btn = QPushButton("다시 읽기")
        reload_btn.setToolTip("서버 내용으로 되돌린다. 내가 편집한 내용은 버려진다.")
        reload_btn.setDefault(True)
        reload_btn.clicked.connect(lambda: self._done(RELOAD))

        overwrite_btn = QPushButton("내 변경으로 덮어쓰기")
        overwrite_btn.setToolTip("상대의 변경을 내 내용으로 덮어쓴다.")
        overwrite_btn.clicked.connect(lambda: self._done(OVERWRITE))

        cancel_btn = QPushButton("취소")
        cancel_btn.setToolTip("아무것도 저장하지 않는다. 편집 내용은 그대로 남는다.")
        cancel_btn.clicked.connect(lambda: self._done(CANCEL))

        row = QHBoxLayout()
        row.addWidget(reload_btn)
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


def ask_conflict(parent, conflicts) -> str:
    """RELOAD / OVERWRITE / CANCEL 중 하나를 반환한다."""
    dialog = ConflictDialog(parent, conflicts)
    dialog.exec()
    return dialog.choice
