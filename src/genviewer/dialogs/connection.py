"""PostgreSQL 접속 다이얼로그.

DB 가 파일이 아니게 되면서 "Load DB" 파일 대화상자를 대체한다.

주의: 메인 툴바에도 Server/Port/Connect 가 있는데 그건 Virtuoso 소켓이지
데이터베이스가 아니다. 그래서 이 창의 제목과 라벨에 "Database" 를 명시한다.

**아무것도 저장하지 않는다.** 기본값은 지금 적용된 설정(genviewer.env 가 넣어 둔
PG* 환경변수)에서 가져온다. 이 창은 "지금 한 번 다른 데로 붙어 본다" 는 용도고,
계속 쓸 값은 genviewer.env 에 적는 것이 맞다.

예전에는 QSettings 에 host/port/dbname/user 를 저장했는데, 정작 앱이 시작할 때
그 값을 읽는 코드가 없어서 다음 실행에 반영되지 않았다. 이 창을 다시 열어야만
보이는 값이라 설정이 두 군데로 갈라지기만 했다.
"""

import os

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from genviewer.service import env_file
from genviewer.service.config import CONFIG_ENV

# 아무 설정도 없을 때 칸을 채울 값. 개발 클러스터 기준이다.
_FALLBACK = {"host": "127.0.0.1", "port": "55433", "dbname": "molgen", "user": ""}


def prefill() -> dict[str, str]:
    """지금 적용된 접속 정보를 읽어 칸에 넣을 값을 만든다.

    env_file.load 를 한 번 더 부르는 이유는 이 창이 혼자서도 맞아야 하기
    때문이다. 이미 불렸으면 setdefault 라 아무 일도 안 일어난다. 설정 파일이
    깨졌으면 여기서 따질 일이 아니라서(접속할 때 제대로 된 에러가 난다) 넘긴다.
    """
    try:
        env_file.load(os.environ.get(CONFIG_ENV, "").strip())
    except RuntimeError:
        pass
    return {
        "host": os.environ.get("PGHOST", "") or _FALLBACK["host"],
        "port": os.environ.get("PGPORT", "") or _FALLBACK["port"],
        "dbname": os.environ.get("PGDATABASE", "") or _FALLBACK["dbname"],
        "user": os.environ.get("PGUSER", "") or _FALLBACK["user"],
    }


def _quote(value: str) -> str:
    """keyword/value DSN 용 이스케이프."""
    escaped = value.replace("\\", "\\\\").replace("'", "\\'")
    return f"'{escaped}'"


class ConnectionDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Connect to Database")
        self.setMinimumWidth(380)

        current = prefill()
        self.host_field = QLineEdit(current["host"])
        self.port_field = QLineEdit(current["port"])
        self.db_field = QLineEdit(current["dbname"])
        self.user_field = QLineEdit(current["user"])
        self.password_field = QLineEdit()
        self.password_field.setEchoMode(QLineEdit.Password)

        form = QFormLayout()
        form.addRow("Host", self.host_field)
        form.addRow("Port", self.port_field)
        form.addRow("Database", self.db_field)
        form.addRow("User", self.user_field)
        form.addRow("Password", self.password_field)

        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)

        self.test_btn = QPushButton("Test Connection")
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
            QLabel(
                f"Defaults are the current settings ({env_file.SITE_NAME}). "
                "Changes here are used for this connection only and are not saved."
            )
        )
        layout.addLayout(form)
        layout.addWidget(self.status_label)
        layout.addLayout(button_row)
        self.setLayout(layout)

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
        from genviewer.service.config import load_config
        from genviewer.service.errors import user_message
        from genviewer.service.pool import Database
        from genviewer.utils.background import run_blocking

        def probe() -> None:
            db = Database(load_config(self.dsn()))
            try:
                # ping 은 예외를 삼키고 bool 만 준다. 실패 원인이 담긴 예외가 올라오게 직접 본다.
                with db.connection() as conn:
                    conn.execute("SELECT 1")
            finally:
                db.close()

        self.status_label.setText("Connecting...")
        self.test_btn.setEnabled(False)
        try:
            # 죽은 호스트를 찍었을 때 이 창까지 같이 얼지 않게 워커에서 돈다.
            run_blocking(probe, self)
        except Exception as e:
            # str(e) 를 쓰면 안 된다. psycopg 의 접속 실패 문자열에는 conninfo(비밀번호)가 있다.
            self.status_label.setText(f"Failed: {user_message(e)}")
            return
        finally:
            self.test_btn.setEnabled(True)
        self.status_label.setText("Connected.")
