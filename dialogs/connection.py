"""PostgreSQL 접속 다이얼로그.

DB 가 파일이 아니게 되면서 "Load DB" 파일 대화상자를 대체한다.

주의: 메인 툴바에도 Server/Port/Connect 가 있는데 그건 Virtuoso 소켓이지
데이터베이스가 아니다. 그래서 이 창의 제목과 라벨에 "Database" 를 명시한다.

비밀번호는 기본적으로 저장하지 않는다. libpq 의 ~/.pgpass
(윈도우는 %APPDATA%\\postgresql\\pgpass.conf) 를 쓰는 편이 낫고, psycopg 가
번들한 libpq 가 그것을 자동으로 읽는다.
"""

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from service.config import DSN_ENV

_ORG = "molgen"
_APP = "molgenviewer"


def _quote(value: str) -> str:
    """keyword/value DSN 용 이스케이프."""
    escaped = value.replace("\\", "\\\\").replace("'", "\\'")
    return f"'{escaped}'"


class ConnectionDialog(QDialog):
    def __init__(self, parent=None, initial_dsn: str = ""):
        super().__init__(parent)
        self.setWindowTitle("Connect to Database")
        self.setMinimumWidth(380)

        settings = QSettings(_ORG, _APP)
        self.host_field = QLineEdit(settings.value("db/host", "127.0.0.1"))
        self.port_field = QLineEdit(settings.value("db/port", "55433"))
        self.db_field = QLineEdit(settings.value("db/name", "molgen"))
        self.user_field = QLineEdit(settings.value("db/user", ""))
        self.password_field = QLineEdit()
        self.password_field.setEchoMode(QLineEdit.Password)
        self.remember_box = QCheckBox("비밀번호 기억 (권장하지 않음)")

        form = QFormLayout()
        form.addRow("Host", self.host_field)
        form.addRow("Port", self.port_field)
        form.addRow("Database", self.db_field)
        form.addRow("User", self.user_field)
        form.addRow("Password", self.password_field)
        form.addRow("", self.remember_box)

        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)

        self.test_btn = QPushButton("연결 테스트")
        self.test_btn.clicked.connect(self._on_test)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        button_row = QHBoxLayout()
        button_row.addWidget(self.test_btn)
        button_row.addStretch()
        button_row.addWidget(buttons)

        layout = QVBoxLayout()
        layout.addWidget(
            QLabel(f"환경변수 {DSN_ENV} 가 있으면 그것이 기본값이 된다.")
        )
        layout.addLayout(form)
        layout.addWidget(self.status_label)
        layout.addLayout(button_row)
        self.setLayout(layout)

        if initial_dsn:
            self._prefill_from_dsn(initial_dsn)

    def _prefill_from_dsn(self, dsn: str) -> None:
        try:
            import psycopg

            info = psycopg.conninfo.conninfo_to_dict(dsn)
        except Exception:
            return
        if info.get("host"):
            self.host_field.setText(str(info["host"]))
        if info.get("port"):
            self.port_field.setText(str(info["port"]))
        if info.get("dbname"):
            self.db_field.setText(str(info["dbname"]))
        if info.get("user"):
            self.user_field.setText(str(info["user"]))

    def dsn(self) -> str:
        parts = [
            f"host={_quote(self.host_field.text().strip())}",
            f"port={_quote(self.port_field.text().strip())}",
            f"dbname={_quote(self.db_field.text().strip())}",
        ]
        user = self.user_field.text().strip()
        if user:
            parts.append(f"user={_quote(user)}")
        password = self.password_field.text()
        if password:
            parts.append(f"password={_quote(password)}")
        return " ".join(parts)

    def _on_test(self) -> None:
        from service.config import load_config
        from service.pool import Database

        self.status_label.setText("연결 중...")
        self.test_btn.setEnabled(False)
        try:
            db = Database(load_config(self.dsn()))
            ok = db.ping()
            db.close()
        except Exception as e:
            self.status_label.setText(f"실패: {e}")
            return
        finally:
            self.test_btn.setEnabled(True)
        self.status_label.setText("연결 성공" if ok else "실패: 접속할 수 없다")

    def accept(self) -> None:
        settings = QSettings(_ORG, _APP)
        settings.setValue("db/host", self.host_field.text().strip())
        settings.setValue("db/port", self.port_field.text().strip())
        settings.setValue("db/name", self.db_field.text().strip())
        settings.setValue("db/user", self.user_field.text().strip())
        if self.remember_box.isChecked():
            settings.setValue("db/password", self.password_field.text())
        else:
            settings.remove("db/password")
        super().accept()
