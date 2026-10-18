"""DB 접속 실패의 원인이 화면에 보인다 (phase 11 step 1, K3 의 GUI 쪽).

phase 7 step 2 이후 `Database.connection()` 은 풀에서 커넥션을 얻지 못하면 한 번 직접 붙어 실제
원인(libpq 원문의 첫 줄, 비밀번호 가림)을 담은 DbUnavailableError 를 낸다. GUI 의 두 확인은
`ping()` 의 bool 만 봐서 그 원인을 버렸다.

- `DeviceTabController._open_database`: 실패하면 고정 문구 "서버가 응답하지 않는다" 를 냈다.
  그래서 로그 패널의 `Database connect failed: …` 줄에 원인이 없었다.
- Connect 창의 연결 테스트: "실패: 접속할 수 없다" 만 띄웠고, 그 밖의 예외는 str(e) 였다.

"Connect Failed" 알림 문구와 로그 접두어는 그대로다(2026-10-17 승인 범위).
"""

from collections.abc import Callable
from contextlib import contextmanager

import pytest

from genviewer.controllers import device_tab as device_tab_module
from genviewer.controllers.device_tab import DeviceTabController
from genviewer.dialogs import connection as connection_module
from genviewer.dialogs.connection import ConnectionDialog
from genviewer.service import config as config_module
from genviewer.service import pool as pool_module
from genviewer.service.config import DbConfig
from genviewer.service.errors import DbUnavailableError, user_message

# install_fake_db 가 바꾸기 전의 원래 함수. 가짜 Database 위에서 본문을 그대로 돌린다.
OPEN_DATABASE = DeviceTabController.__dict__["_open_database"].__func__

PASSWORD = "s3cret"
# phase 7 step 2 의 Database._failure_cause 가 DbUnavailableError 에 담는 모양(libpq 원문의 첫 줄).
CAUSE = (
    'connection failed: connection to server at "127.0.0.1", port 55433 failed: '
    'FATAL:  password authentication failed for user "app"'
)
CAUSE_KEY = "password authentication failed"
PREFILL = {"host": "127.0.0.1", "port": "55433", "dbname": "molgen", "user": "app"}


class AcceptingDatabase:
    """`service.pool.Database` 자리. 확인 접속이 된다. 커넥션 자리도 겸한다(`execute` 를 기록)."""

    def __init__(self, cfg: DbConfig) -> None:
        self.cfg = cfg
        self.closed = True
        self.open_count = 0
        self.close_count = 0
        self.executed: list[str] = []

    def open(self) -> None:
        self.closed = False
        self.open_count += 1

    def close(self) -> None:
        self.closed = True
        self.close_count += 1

    def ping(self) -> bool:
        return True

    @contextmanager
    def connection(self):
        yield self

    def execute(self, sql: str) -> None:
        self.executed.append(sql)


class RefusingDatabase(AcceptingDatabase):
    """서버가 접속을 거절한다. 실제 `connection()` 처럼 커넥션을 얻을 때(with 진입) 원인이 담긴
    DbUnavailableError 를 내고, 실제 `ping()` 처럼 그것을 삼켜 False 를 준다."""

    def ping(self) -> bool:
        return False

    @contextmanager
    def connection(self):
        raise DbUnavailableError(CAUSE)
        yield  # contextmanager 는 생성기여야 한다


def fake_load_config(dsn: str) -> DbConfig:
    return DbConfig(dsn=dsn or "x", app_user="tester")


def install_database(
    monkeypatch,
    cls: type[AcceptingDatabase],
    *,
    database_in,
    load_config_in,
    load_config: Callable[[str], DbConfig] = fake_load_config,
) -> list[AcceptingDatabase]:
    """`database_in.Database` 와 `load_config_in.load_config` 를 바꾼다.

    만들어진 DB 를 모으는 리스트를 돌려준다.
    """
    made: list[AcceptingDatabase] = []

    def make(cfg: DbConfig) -> AcceptingDatabase:
        db = cls(cfg)
        made.append(db)
        return db

    monkeypatch.setattr(database_in, "Database", make)
    monkeypatch.setattr(load_config_in, "load_config", load_config)
    return made


def install_controller_database(monkeypatch, cls) -> list[AcceptingDatabase]:
    """`_open_database` 가 쓰는 이름(controllers.device_tab 모듈 수준 import)을 바꾼다."""
    return install_database(
        monkeypatch, cls, database_in=device_tab_module, load_config_in=device_tab_module
    )


def install_dialog_database(monkeypatch, cls, **kwargs) -> list[AcceptingDatabase]:
    """`probe()` 는 함수 안에서 import 하므로 원래 모듈의 이름을 바꾼다."""
    return install_database(
        monkeypatch, cls, database_in=pool_module, load_config_in=config_module, **kwargs
    )


@pytest.fixture
def dialog(qtbot, monkeypatch) -> ConnectionDialog:
    # prefill() 은 env_file.load 로 개발 PC 의 실제 genviewer.env 를 os.environ 에 넣는다.
    monkeypatch.setattr(connection_module, "prefill", lambda: dict(PREFILL))
    dlg = ConnectionDialog()
    qtbot.addWidget(dlg)
    dlg.password_field.setText(PASSWORD)
    return dlg


def log_text(controller) -> str:
    return controller.ui.log_te.toPlainText()


# ----------------------------------------------------------------------
# DeviceTabController._open_database
# ----------------------------------------------------------------------


def test_open_database_raises_the_real_cause(monkeypatch):
    install_controller_database(monkeypatch, RefusingDatabase)

    with pytest.raises(DbUnavailableError) as info:
        OPEN_DATABASE("host=h")

    assert CAUSE_KEY in user_message(info.value)


def test_open_database_returns_the_opened_database(monkeypatch):
    made = install_controller_database(monkeypatch, AcceptingDatabase)

    db = OPEN_DATABASE("host=h")

    assert made == [db]
    assert db.cfg.dsn == "host=h"
    assert db.open_count == 1
    assert db.closed is False


def test_a_failed_reconnect_logs_the_real_cause(main_window, dialogs, monkeypatch):
    monkeypatch.setattr(DeviceTabController, "_open_database", staticmethod(OPEN_DATABASE))
    made = install_controller_database(monkeypatch, RefusingDatabase)
    tab = main_window.device_tab
    db1 = tab.db
    dsn = f"host=other password={PASSWORD}"

    main_window.ui.device_tab_view.dbConnectRequested.emit(dsn)

    assert [db.cfg.dsn for db in made] == [dsn]  # 원래 _open_database 본문이 돌았다
    log = log_text(main_window)
    assert "Database connect failed:" in log
    assert CAUSE_KEY in log
    assert PASSWORD not in log
    assert dialogs.shown == [("error", "Connect Failed", "데이터베이스에 연결하지 못했다.")]
    # 지금 DB 를 그대로 쓴다(phase 4).
    assert tab.db is db1
    assert db1.closed is False
    assert tab.connected is True


# ----------------------------------------------------------------------
# Connect 창의 연결 테스트
# ----------------------------------------------------------------------


def test_the_connection_test_shows_the_real_cause(dialog, monkeypatch):
    made = install_dialog_database(monkeypatch, RefusingDatabase)

    dialog._on_test()

    text = dialog.status_label.text()
    assert text.startswith("실패: ")
    assert CAUSE_KEY in text
    assert PASSWORD not in text
    assert dialog.test_btn.isEnabled()
    assert [db.close_count for db in made] == [1]


def test_an_unexpected_connection_test_error_hides_the_password(dialog, monkeypatch):
    def broken_load_config(dsn: str) -> DbConfig:
        raise RuntimeError(f"bad password={PASSWORD}")

    install_dialog_database(monkeypatch, AcceptingDatabase, load_config=broken_load_config)

    dialog._on_test()

    text = dialog.status_label.text()
    assert text.startswith("실패: ")
    assert PASSWORD not in text
    assert dialog.test_btn.isEnabled()


def test_a_successful_connection_test_says_so(dialog, monkeypatch):
    made = install_dialog_database(monkeypatch, AcceptingDatabase)

    dialog._on_test()

    assert dialog.status_label.text() == "연결 성공"
    assert dialog.test_btn.isEnabled()
    assert [PASSWORD in db.cfg.dsn for db in made] == [True]
    assert [db.close_count for db in made] == [1]
