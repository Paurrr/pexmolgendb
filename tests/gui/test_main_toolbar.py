"""창 위 툴바는 Virtuoso 소켓 묶음이고, 테마는 View 메뉴에서 바꾼다 (phase 23 step 1).

위 툴바의 Server·Port·Connect 는 Virtuoso 소켓인데 화면 어디에도 "Virtuoso" 가 없어서 메뉴
Database → Connect... (DB 접속)와 헷갈렸다. 그래서 Server 앞에 굵은 "Virtuoso" 라벨을 두고
Connect 에 툴팁을 단다. 상관없는 Theme 단추는 빼고 View → Dark Theme(체크 = graphite)로 옮긴다.
2026-10-22 승인한 사용성 변경이다.

툴바 순서는 컨트롤러 없이 `MainWindow` 를 직접 만들어 본다. 메뉴는 컨트롤러가 만들므로
`main_window` fixture 로 본다. `apply_theme` 를 부르는 테스트는 `preserved_theme` 안에서 돈다.
"""

import pytest
from gui_support.theme import preserved_theme
from PySide6.QtGui import QAction, QTextDocumentFragment
from PySide6.QtWidgets import QLabel, QMenu, QSizePolicy, QToolBar, QWidget, QWidgetAction

from genviewer.views.main_window import MainWindow


@pytest.fixture
def window(qtbot) -> MainWindow:
    ui = MainWindow("localhost")
    qtbot.addWidget(ui)
    return ui


def main_toolbar_widgets(ui: MainWindow) -> list[QWidget]:
    """창 위 툴바("Main Toolbar")에 놓인 위젯을 놓인 순서대로."""
    bars = [t for t in ui.findChildren(QToolBar) if t.windowTitle() == "Main Toolbar"]
    assert len(bars) == 1, "Main Toolbar 가 없다"
    actions = bars[0].actions()
    assert all(isinstance(a, QWidgetAction) for a in actions)
    return [a.defaultWidget() for a in actions]


def plain_text(label: QLabel) -> str:
    return QTextDocumentFragment.fromHtml(label.text()).toPlainText()


def view_menu(main_window) -> QMenu:
    menus = [m for m in main_window.ui.menubar.findChildren(QMenu) if m.title() == "View"]
    assert len(menus) == 1, "메뉴바에 View 메뉴가 없다"
    return menus[0]


def dark_theme_action(main_window) -> QAction:
    actions = [a for a in view_menu(main_window).actions() if a.text() == "Dark Theme"]
    assert len(actions) == 1, "View 메뉴에 Dark Theme 가 없다"
    return actions[0]


def last_log_line(main_window) -> str:
    return main_window.ui.log_te.toPlainText().splitlines()[-1]


# --------------------------------------------------------------------------
# 위 툴바
# --------------------------------------------------------------------------


def test_main_toolbar_is_the_virtuoso_group(window):
    widgets = main_toolbar_widgets(window)

    assert len(widgets) == 8
    spacer, label, *rest = widgets
    assert type(spacer) is QWidget
    assert spacer.sizePolicy().horizontalPolicy() == QSizePolicy.Expanding
    assert isinstance(label, QLabel)
    assert plain_text(label) == "Virtuoso"
    assert rest == [
        window.server_input,
        window.server_field,
        window.port_input,
        window.port_field,
        window.connect_btn,
        window.status_label,
    ]
    assert window.server_input.text() == "Server:"
    assert window.port_input.text() == "Port:"


def test_virtuoso_label_is_bold(window):
    label = main_toolbar_widgets(window)[1]

    assert label.font().bold() or label.text() == "<b>Virtuoso</b>"


def test_theme_button_is_gone(window):
    assert not hasattr(window, "theme_btn")


def test_connect_button_tooltip_names_virtuoso(window):
    assert window.connect_btn.toolTip() == "Connect to the Virtuoso socket"


# --------------------------------------------------------------------------
# View → Dark Theme
# --------------------------------------------------------------------------


def test_view_menu_comes_after_database(main_window):
    titles = [a.text() for a in main_window.ui.menubar.actions()]

    assert "View" in titles
    assert titles.index("View") > titles.index("Database")


def test_dark_theme_starts_checked(main_window):
    action = dark_theme_action(main_window)

    assert action.isCheckable()
    assert action.isChecked()
    assert main_window.theme_name == "graphite"


def test_dark_theme_toggles_between_mist_and_graphite(main_window, qapp):
    action = dark_theme_action(main_window)

    with preserved_theme(qapp):
        action.trigger()
        assert qapp.property("themeName") == "mist"
        assert not action.isChecked()
        assert main_window.theme_name == "mist"
        assert last_log_line(main_window).endswith("Theme changed to Mist.")

        action.trigger()
        assert qapp.property("themeName") == "graphite"
        assert action.isChecked()
        assert main_window.theme_name == "graphite"
        assert last_log_line(main_window).endswith("Theme changed to Graphite.")
