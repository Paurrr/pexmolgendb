"""DeviceTabController 의 DB 접속 경로 (phase 4 step 4).

- S8: 로그 패널의 "Database connected: …" 줄에 DSN 의 비밀번호가 찍히지 않는다.
- G13: 다시 접속할 때 새 DB 를 먼저 연다. 실패하면 지금 DB 와 repo 를 그대로 쓰고, 성공하면
  도는 폴링 작업이 끝난 뒤에 옛 DB 를 닫는다.
- G16: 시작할 때의 접속이 창의 로그 패널·알림이 이어진 뒤에 돌아, 실패가 화면에 보인다.
"""

import threading
from collections.abc import Callable, Iterator

import pytest
from gui_support.fakes import FakeStore
from gui_support.helpers import install_fake_db, select_process

from genviewer.controllers.main_window import MainWindowController
from genviewer.service.errors import DbUnavailableError
from genviewer.utils.background import Task
from genviewer.views.main_window import MainWindow

KEY_VALUE_DSN = "host=127.0.0.1 dbname=molgen user=app password=s3cret"
URL_DSN = "postgresql://app:s3cret@127.0.0.1/molgen"


def log_text(controller: MainWindowController) -> str:
    return controller.ui.log_te.toPlainText()


def titles(dialogs) -> list[str]:
    return [title for _kind, title, _text in dialogs.shown]


def device_count(controller: MainWindowController) -> int:
    return controller.device_tab.ui.device_table_view.model().rowCount()


@pytest.fixture
def start_window(qtbot, monkeypatch) -> Iterator[Callable[[FakeStore], MainWindowController]]:
    """`main_window` fixture 와 같은 방식으로 창을 만들되, 만들기 전에 store 를 손볼 수 있다.

    store 를 받아 MainWindow + MainWindowController 를 만들고 돌려준다. 첫 접속은 기다리지 않는다
    (테스트가 dbChanged 를 먼저 이을 수 있게). 정리 때 shutdown 후 close 한다.
    """
    made: list[MainWindowController] = []

    def start(store: FakeStore) -> MainWindowController:
        install_fake_db(monkeypatch, store)
        ui = MainWindow("localhost")
        qtbot.addWidget(ui)
        controller = MainWindowController(ui, "")
        made.append(controller)
        return controller

    yield start
    for controller in made:
        # 예약된 첫 접속이 다음 테스트 도중에 돌지 않게 먼저 끝낸다.
        qtbot.waitUntil(lambda c=controller: c.device_tab.connected is not None)
        controller.shutdown()
        controller.ui.close()


# ----------------------------------------------------------------------
# S8: 접속 줄의 비밀번호
# ----------------------------------------------------------------------


@pytest.mark.parametrize("dsn", [KEY_VALUE_DSN, URL_DSN], ids=["key_value", "url"])
def test_the_connected_log_line_hides_the_password(main_window, dialogs, dsn):
    main_window.ui.device_tab_view.dbConnectRequested.emit(dsn)

    assert main_window.device_tab.db.cfg.dsn == dsn
    assert "Database connected:" in log_text(main_window)
    assert "s3cret" not in log_text(main_window)
    assert titles(dialogs) == ["Connected"]


# ----------------------------------------------------------------------
# G13: 다시 접속
# ----------------------------------------------------------------------


def test_a_failed_reconnect_keeps_the_current_database(main_window, store, dialogs, qtbot):
    tab = main_window.device_tab
    db1 = tab.db
    store.fail_next("open_database", DbUnavailableError("down"))

    main_window.ui.device_tab_view.dbConnectRequested.emit("host=other")

    assert tab.db is db1
    assert db1.closed is False
    assert db1.close_count == 0
    assert tab.connected is True
    assert titles(dialogs) == ["Connect Failed"]
    assert "Database connect failed:" in log_text(main_window)

    # 옛 DB 로 계속 읽힌다. sf2p 는 이미 골라져 있어 sf4u 로 옮겨 본다.
    select_process(tab, "sf4u")
    qtbot.waitUntil(
        lambda: tab.device_table.current_process == "sf4u" and device_count(main_window) == 1
    )
    assert tab.device_table.repo.db is db1
    assert tab.device_tab_toolbar.repo.db is db1


def test_a_successful_reconnect_switches_to_the_new_database_once(main_window, store, dialogs):
    tab = main_window.device_tab
    db1 = tab.db
    changes: list = []
    tab.dbChanged.connect(changes.append)

    main_window.ui.device_tab_view.dbConnectRequested.emit("host=other")

    db2 = tab.db
    assert db2 is not db1
    assert changes == [db2]
    assert db1.close_count == 1
    assert db2.closed is False
    assert db2.close_count == 0
    assert tab.connected is True
    assert tab.device_table.repo.db is db2
    assert tab.device_tab_toolbar.repo.db is db2
    assert tab.parameter_tab.repo.db is db2
    assert tab._poll_timer.isActive()
    assert titles(dialogs) == ["Connected"]
    assert "Database connected: host=other." in log_text(main_window)


def test_a_reconnect_waits_for_the_running_poll_before_closing(
    main_window, monkeypatch, qtbot
):
    tab = main_window.device_tab
    db1 = tab.db
    release = threading.Event()
    task = Task(lambda: release.wait(5))
    finished_when_closed: list[bool] = []
    close = db1.close

    def recording_close() -> None:
        finished_when_closed.append(task.isFinished())
        close()

    monkeypatch.setattr(db1, "close", recording_close)
    timer = threading.Timer(0.2, release.set)
    try:
        task.start()
        tab._poll_task = task
        timer.start()

        main_window.ui.device_tab_view.dbConnectRequested.emit("host=other")

        assert finished_when_closed == [True]
        assert tab.db is not db1
    finally:
        release.set()
        timer.cancel()
        task.wait()


# ----------------------------------------------------------------------
# G16: 시작할 때의 접속
# ----------------------------------------------------------------------


def test_a_failed_start_connect_shows_in_the_log_panel(start_window, store, dialogs, qtbot):
    store.fail_next("open_database", DbUnavailableError("down"))

    controller = start_window(store)
    qtbot.waitUntil(lambda: controller.device_tab.connected is not None)

    assert controller.device_tab.connected is False
    assert controller.device_tab.db is None
    assert "Database connect failed:" in log_text(controller)
    assert dialogs.shown == []


def test_a_failed_first_query_at_start_is_shown(start_window, store, dialogs, qtbot):
    store.fail_next("list_pairs", DbUnavailableError("down"))

    controller = start_window(store)
    qtbot.waitUntil(lambda: controller.device_tab.connected is not None)

    assert controller.device_tab.connected is True
    assert "Process List Failed" in titles(dialogs)
    assert "Process List Failed" in log_text(controller)


def test_a_successful_start_connect_is_logged_once(start_window, store, dialogs, qtbot):
    controller = start_window(store)
    changes: list = []
    controller.device_tab.dbChanged.connect(changes.append)
    qtbot.waitUntil(lambda: controller.device_tab.connected is not None)

    tab = controller.device_tab
    assert tab.connected is True
    assert changes == [tab.db]
    assert "Database connected:" in log_text(controller)
    assert tab._poll_timer.isActive()
    assert dialogs.shown == []


def test_reconnecting_after_a_failed_start_connects(start_window, store, dialogs, qtbot):
    store.fail_next("open_database", DbUnavailableError("down"))
    controller = start_window(store)
    qtbot.waitUntil(lambda: controller.device_tab.connected is not None)
    tab = controller.device_tab
    changes: list = []
    tab.dbChanged.connect(changes.append)

    controller.ui.device_tab_view.dbConnectRequested.emit("host=other")

    assert tab.connected is True
    assert changes == [tab.db]
    assert tab.db.cfg.dsn == "host=other"
    assert titles(dialogs) == ["Connected"]
    assert tab.device_table.current_process == "sf2p"
