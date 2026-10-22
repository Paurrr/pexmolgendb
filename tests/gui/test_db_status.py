"""상태 표시줄 오른쪽에 DB 접속 상태가 늘 보인다 (phase 23 step 2).

접속 결과는 상태 표시줄에 2초 뜨고 사라졌고, 로그 패널 줄은 스크롤되거나 Clear 로 지워졌다.
그래서 지금 어느 DB 에 붙어 편집하는지 알 수 없었다. Virtuoso 소켓처럼 영구 라벨 하나를 둔다.
2026-10-22 승인한 사용성 변경이다.

- 글자는 `DB: <target_summary(dsn)>` 또는 `DB: not connected` 다. `target_summary` 는 host·port·
  dbname·user 만 고르므로 비밀번호는 낄 수 없다.
- 색은 Virtuoso 상태 라벨과 같은 규칙이다(동적 속성 `connected` = "true"/"false", QSS good/bad).
- `DeviceTabController.dbChanged` 로만 바뀐다. 접속 실패는 그 신호를 내지 않으므로 재접속이
  실패하면 옛 대상이 그대로 남는다(옛 DB 를 계속 쓴다).
"""

from collections.abc import Callable, Iterator

import pytest
from gui_support.fakes import FakeStore
from gui_support.helpers import install_fake_db
from gui_support.theme import preserved_theme
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication

from genviewer.controllers.main_window import MainWindowController
from genviewer.service.errors import DbUnavailableError
from genviewer.utils.palette import apply_theme, current_colors
from genviewer.views.main_window import MainWindow

DSN = "host=db.example port=5433 dbname=gendb user=alice password=s3cret"
TARGET = "DB: host=db.example port=5433 dbname=gendb user=alice"
OTHER_DSN = "host=other.example port=5434 dbname=otherdb user=bob password=hunter2"
NOT_CONNECTED = "DB: not connected"


def status(ui: MainWindow) -> tuple[str, str]:
    label = ui.db_status_label
    return label.text(), label.property("connected")


@pytest.fixture
def start_window(qtbot, monkeypatch) -> Iterator[Callable[[FakeStore, str], MainWindowController]]:
    """store 를 손본 뒤 dsn 으로 첫 접속하는 창을 만든다. 첫 접속은 기다리지 않는다.

    정리 때 첫 접속이 끝나기를 기다린 뒤 shutdown 하고 닫는다.
    """
    made: list[MainWindowController] = []

    def start(store: FakeStore, dsn: str) -> MainWindowController:
        install_fake_db(monkeypatch, store)
        ui = MainWindow("localhost")
        qtbot.addWidget(ui, before_close_func=lambda _ui: [c.shutdown() for c in made])
        controller = MainWindowController(ui, dsn)
        made.append(controller)
        return controller

    yield start
    for controller in made:
        qtbot.waitUntil(lambda c=controller: c.device_tab.connected is not None)
        controller.shutdown()
        controller.ui.close()


def test_new_window_says_not_connected(qtbot):
    ui = MainWindow("localhost")
    qtbot.addWidget(ui)

    assert status(ui) == (NOT_CONNECTED, "false")
    assert ui.db_status_label.objectName() == "DbStatus"
    # 영구 위젯이라 showMessage 가 가리지 않는다.
    assert ui.db_status_label.parent() is not None
    assert ui.statusBar().isAncestorOf(ui.db_status_label)


def test_first_connect_shows_the_target(start_window, store, qtbot):
    controller = start_window(store, DSN)
    # 첫 접속은 생성자가 예약한다. 그 전에는 아직 붙지 않았다.
    assert status(controller.ui) == (NOT_CONNECTED, "false")

    qtbot.waitUntil(lambda: controller.device_tab.connected is not None)

    assert controller.device_tab.connected is True
    assert status(controller.ui) == (TARGET, "true")


def test_first_connect_failure_says_not_connected(start_window, store, dialogs, qtbot):
    store.fail_next("open_database", DbUnavailableError("down"))

    controller = start_window(store, DSN)
    qtbot.waitUntil(lambda: controller.device_tab.connected is not None)

    assert controller.device_tab.connected is False
    assert status(controller.ui) == (NOT_CONNECTED, "false")


def test_connect_shows_the_target_without_password(main_window, dialogs):
    assert main_window.device_tab.connect_db(DSN) is True

    text, connected = status(main_window.ui)
    assert text == TARGET
    assert "s3cret" not in text
    assert "password" not in text
    assert connected == "true"


def test_failed_reconnect_keeps_the_old_target(main_window, store, dialogs, qtbot):
    tab = main_window.device_tab
    assert tab.connect_db(DSN) is True
    before = len(store.calls_of("open_database"))
    store.fail_next("open_database", DbUnavailableError("down"))

    assert tab.connect_db(OTHER_DSN) is False

    # 실패한 시도는 calls 에 남는다(fail_next 가 낸 예외). 끝난 뒤에 본다.
    qtbot.waitUntil(lambda: len(store.calls_of("open_database")) == before + 1)
    assert tab.connected is True
    assert tab.db.cfg.dsn == DSN
    assert status(main_window.ui) == (TARGET, "true")


@pytest.mark.parametrize("close", ["close_db", "shutdown"])
def test_close_db_says_not_connected(main_window, dialogs, close):
    assert main_window.device_tab.connect_db(DSN) is True
    assert status(main_window.ui) == (TARGET, "true")

    if close == "close_db":
        main_window.device_tab.close_db()
    else:
        main_window.shutdown()

    assert main_window.device_tab.db is None
    assert status(main_window.ui) == (NOT_CONNECTED, "false")


@pytest.mark.parametrize("theme", ["graphite", "mist"])
def test_status_color_follows_the_theme(main_window, dialogs, theme):
    app = QApplication.instance()
    label = main_window.ui.db_status_label

    def color() -> QColor:
        return label.palette().color(label.foregroundRole())

    with preserved_theme(app):
        apply_theme(app, theme)
        colors = current_colors()
        assert QColor(colors["good"]) != QColor(colors["bad"])
        # fixture 의 첫 접속으로 붙어 있다.
        assert color() == QColor(colors["good"])

        main_window.device_tab.close_db()
        assert color() == QColor(colors["bad"])

        assert main_window.device_tab.connect_db(DSN) is True
        assert color() == QColor(colors["good"])
