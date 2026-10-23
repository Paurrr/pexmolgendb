"""DB 접속 실패의 원인이 화면에 보인다 (phase 11 step 1, K3 의 GUI 쪽).

phase 7 step 2 이후 `Database.connection()` 은 풀에서 커넥션을 얻지 못하면 한 번 직접 붙어 실제
원인(libpq 원문의 첫 줄, 비밀번호 가림)을 담은 DbUnavailableError 를 낸다. GUI 의 두 확인은
`ping()` 의 bool 만 봐서 그 원인을 버렸다.

- `DeviceTabController._open_database`: 실패하면 고정 문구 "서버가 응답하지 않는다" 를 냈다.
  그래서 로그 패널의 `Database connect failed: …` 줄에 원인이 없었다.
- Connect 창의 연결 테스트: "실패: 접속할 수 없다" 만 띄웠고, 그 밖의 예외는 str(e) 였다.

"Connect Failed" 알림 문구와 로그 접두어는 그대로다(2026-10-17 승인 범위).

step 2(K22 일부): `_open_database` 는 `open()` 이나 확인이 실패하면 예외만 내고 연 Database 를
닫지 않았다. 실패할 때마다 풀 하나가 남아 그 워커가 죽은 서버에 계속 다시 붙으려 했고, 종료할 때
`ConnectionPool.__del__` 이 그 워커를 join 하려다 멈출 수 있었다(`close_db` docstring).
"""

import logging
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


class OpenFailingDatabase(AcceptingDatabase):
    """`open()` 이 예외를 낸다."""

    def open(self) -> None:
        self.open_count += 1
        raise DbUnavailableError("down")


class QueryFailingDatabase(AcceptingDatabase):
    """커넥션은 얻지만 확인 쿼리가 DbUnavailableError 가 아닌 예외를 낸다."""

    def execute(self, sql: str) -> None:
        raise RuntimeError("SELECT 1 failed")


class UnclosableDatabase(RefusingDatabase):
    """확인이 실패하고, 닫기도 실패한다."""

    def close(self) -> None:
        self.close_count += 1
        raise RuntimeError("close failed")


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


def install_controller_database(monkeypatch, cls, **kwargs) -> list[AcceptingDatabase]:
    """`_open_database` 가 쓰는 이름(controllers.device_tab 모듈 수준 import)을 바꾼다."""
    return install_database(
        monkeypatch,
        cls,
        database_in=device_tab_module,
        load_config_in=device_tab_module,
        **kwargs,
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
    assert db.close_count == 0


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
# 실패하면 연 Database 를 닫는다 (step 2, K22)
# ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("cls", "exc_type", "text"),
    [
        (RefusingDatabase, DbUnavailableError, CAUSE),
        (QueryFailingDatabase, RuntimeError, "SELECT 1 failed"),
    ],
    ids=["no-connection", "query-error"],
)
def test_a_failed_check_closes_the_database(monkeypatch, cls, exc_type, text):
    made = install_controller_database(monkeypatch, cls)

    with pytest.raises(exc_type) as info:
        OPEN_DATABASE("host=h")

    assert str(info.value) == text
    assert [db.open_count for db in made] == [1]
    assert [db.close_count for db in made] == [1]


def test_a_failed_open_closes_the_database(monkeypatch):
    made = install_controller_database(monkeypatch, OpenFailingDatabase)

    with pytest.raises(DbUnavailableError) as info:
        OPEN_DATABASE("host=h")

    assert str(info.value) == "down"
    assert [db.close_count for db in made] == [1]


def test_a_close_error_does_not_hide_the_connect_failure(monkeypatch, caplog):
    made = install_controller_database(monkeypatch, UnclosableDatabase)

    with (
        caplog.at_level(logging.WARNING, logger=device_tab_module.__name__),
        pytest.raises(DbUnavailableError) as info,
    ):
        OPEN_DATABASE("host=h")

    assert CAUSE_KEY in user_message(info.value)
    assert [db.close_count for db in made] == [1]
    # 닫기 실패는 파일 로그에만 남는다.
    assert [r.exc_info[0] for r in caplog.records if r.exc_info] == [RuntimeError]


def test_a_config_error_has_nothing_to_close(monkeypatch):
    def broken_load_config(dsn: str) -> DbConfig:
        raise RuntimeError("no config")

    made = install_controller_database(
        monkeypatch, AcceptingDatabase, load_config=broken_load_config
    )

    with pytest.raises(RuntimeError, match="no config"):
        OPEN_DATABASE("")

    assert made == []


def test_failed_reconnects_close_every_database_they_opened(main_window, dialogs, monkeypatch):
    monkeypatch.setattr(DeviceTabController, "_open_database", staticmethod(OPEN_DATABASE))
    made = install_controller_database(monkeypatch, RefusingDatabase)
    tab = main_window.device_tab
    db1 = tab.db

    for _ in range(2):
        main_window.ui.device_tab_view.dbConnectRequested.emit("host=other")

    assert len(made) == 2
    assert [db.close_count for db in made] == [1, 1]
    assert [db.closed for db in made] == [True, True]
    assert dialogs.shown == [("error", "Connect Failed", "데이터베이스에 연결하지 못했다.")] * 2
    # 지금 DB 는 닫지 않고 그대로 쓴다(phase 4 G13).
    assert tab.db is db1
    assert db1.close_count == 0
    assert db1.closed is False
    assert tab.connected is True


# ----------------------------------------------------------------------
# Connect 창의 연결 테스트
# ----------------------------------------------------------------------


def test_the_connection_test_shows_the_real_cause(dialog, monkeypatch):
    made = install_dialog_database(monkeypatch, RefusingDatabase)

    dialog._on_test()

    text = dialog.status_label.text()
    assert text.startswith("Failed: ")
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
    assert text.startswith("Failed: ")
    assert PASSWORD not in text
    assert dialog.test_btn.isEnabled()


def test_a_successful_connection_test_says_so(dialog, monkeypatch):
    made = install_dialog_database(monkeypatch, AcceptingDatabase)

    dialog._on_test()

    assert dialog.status_label.text() == "Connected."
    assert dialog.test_btn.isEnabled()
    assert [PASSWORD in db.cfg.dsn for db in made] == [True]
    assert [db.close_count for db in made] == [1]
