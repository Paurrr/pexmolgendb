"""파라미터 탭 줄의 "+" 로 탭 추가 (phase 4 step 2).

탭 섹션은 DB 접속에 성공한 뒤 `apply_db` → `rebuild_all_sections()` 에서 만들어진다. DB 없이
떴거나(시작 접속 실패) 아직 붙지 않은 동안 "+" 를 누르면 탭 이름 14개가 전부 후보로 나오고,
하나를 고르면 `on_tab_clicked` 가 없는 `ParameterTab.add_tab` 을 불러 `AttributeError` 가 슬롯
밖으로 새어 "예기치 못한 오류" 가 떴다. 고른 탭은 다른 탭과 똑같이(같은 설정, 같은 dirty 표시,
같은 컨트롤러 연결) "+" 바로 앞에 생긴다. 접속한 뒤에는 탭이 다 있어 "+" 는 아무것도 하지 않는다.

진짜 `TabSelectorDialog` 는 모달이라 띄우지 않는다. `FakeTabSelector` 가 받은 후보를 기록하고
테스트가 정한 답을 돌려준다.
"""

from typing import ClassVar

import pytest
from PySide6.QtCore import Qt

from genviewer.config.config import tab_config
from genviewer.controllers.parameter_tab import ParameterTabController
from genviewer.views.parameter_tab import ParameterTab
from genviewer.views.tab_section import TabSection

# tab_config 순서상 가운데 있는 탭. 재구성하면 제자리(설정 순서)로 돌아가야 한다.
NAME = "AddLayer"
OTHER = "InstTerm"


class FakeTabSelector:
    """`TabSelectorDialog` 대역. 받은 후보는 `created` 에 남는다.

    `exec_()`/`exec()` 는 `accept` 를, `get_selected_tab()` 은 `choice` 를 돌려준다.
    """

    created: ClassVar[list[list[str]]] = []
    accept: ClassVar[bool] = True
    choice: ClassVar[str | None] = NAME

    def __init__(self, available_tabs, parent=None):
        type(self).created.append(list(available_tabs))

    def exec_(self):
        return type(self).accept

    exec = exec_

    def get_selected_tab(self):
        return type(self).choice


@pytest.fixture
def tab_selector(monkeypatch) -> type[FakeTabSelector]:
    monkeypatch.setattr(FakeTabSelector, "created", [])
    monkeypatch.setattr(FakeTabSelector, "accept", True)
    monkeypatch.setattr(FakeTabSelector, "choice", NAME)
    monkeypatch.setattr(
        "genviewer.controllers.parameter_tab.TabSelectorDialog", FakeTabSelector
    )
    return FakeTabSelector


@pytest.fixture
def offline(qtbot) -> ParameterTabController:
    """DB 없이 만든 파라미터 탭. 시작 접속이 실패해 섹션이 만들어지지 않은 상태와 같다."""
    ui = ParameterTab()
    qtbot.addWidget(ui)
    return ParameterTabController(ui)


def tab_texts(ui: ParameterTab) -> list[str]:
    return [ui.tabText(i) for i in range(ui.count())]


def press_plus(ctrl: ParameterTabController) -> None:
    plus = ctrl.ui.count() - 1
    assert ctrl.ui.tabText(plus) == "+"
    ctrl.on_tab_clicked(plus)


# -- "+" 로 탭 추가 ------------------------------------------------------------


def test_choosing_a_tab_from_plus_does_not_raise(offline, tab_selector):
    press_plus(offline)  # 수정 전: AttributeError: 'ParameterTab' object has no attribute 'add_tab'

    assert tab_selector.created == [list(tab_config)]
    assert offline.ui.find_tab(NAME) != -1


def test_clicking_plus_with_the_mouse_adds_the_chosen_tab(offline, tab_selector, qtbot):
    ui = offline.ui
    ui.show()
    qtbot.waitExposed(ui)
    bar = ui.tabBar()

    qtbot.mouseClick(bar, Qt.LeftButton, pos=bar.tabRect(ui.count() - 1).center())

    assert tab_texts(ui) == ["Summary", NAME, "+"]


def test_the_added_tab_sits_right_before_plus_and_becomes_current(offline, tab_selector):
    ui = offline.ui

    press_plus(offline)

    assert tab_texts(ui) == ["Summary", NAME, "+"]
    assert ui.find_tab(NAME) == ui.count() - 2
    assert ui.currentIndex() == ui.find_tab(NAME)


def test_the_added_tab_is_a_section_built_from_its_tab_config(offline, tab_selector):
    ui = offline.ui
    cfg = tab_config[NAME]

    press_plus(offline)

    widget = ui.widget(ui.find_tab(NAME))
    assert isinstance(widget, TabSection)
    assert (widget.columns, widget.headers, widget.table_name, widget.title) == (
        cfg["columns"],
        cfg["headers"],
        cfg["table"],
        NAME,
    )
    assert widget.objectName() == NAME
    assert offline.section(NAME) is not None
    assert offline.section(NAME).ui is widget
    assert ui.current_tab_section is widget


def test_the_added_tab_matches_the_tab_that_rebuilding_makes(qtbot, tab_selector):
    """같은 이름의 탭은 "+" 로 붙였든 재구성으로 만들었든 같은 값을 갖는다."""
    added = ParameterTab()
    qtbot.addWidget(added)
    press_plus(ParameterTabController(added))
    rebuilt = ParameterTab()
    qtbot.addWidget(rebuilt)
    ParameterTabController(rebuilt).rebuild_all_sections()

    def shape(ui):
        w = ui.widget(ui.find_tab(NAME))
        return (type(w), w.columns, w.headers, w.table_name, w.title, w.objectName())

    assert shape(added) == shape(rebuilt)


# -- 기존 섹션과 같은 연결 -----------------------------------------------------


def test_the_added_tab_shows_the_dirty_marker(offline, tab_selector):
    ui = offline.ui
    press_plus(offline)
    section = ui.widget(ui.find_tab(NAME))

    section.dirtyChanged.emit(True)
    assert ui.tabText(ui.find_tab(NAME)) == f"{NAME} *"

    section.dirtyChanged.emit(False)
    assert ui.tabText(ui.find_tab(NAME)) == NAME


def test_the_added_tab_reports_through_the_parameter_tab_controller(offline, tab_selector):
    logs: list[str] = []
    notes: list[tuple[str, str, str]] = []
    offline.logRequested.connect(logs.append)
    offline.notifyRequested.connect(lambda *a: notes.append(a))
    press_plus(offline)

    offline.section(NAME).logRequested.emit("hello")
    offline.section(NAME).notifyRequested.emit("info", "Title", "body")

    assert logs == ["hello"]
    assert notes == [("info", "Title", "body")]


# -- 후보, 취소, 중복 ----------------------------------------------------------


def test_the_added_tab_is_no_longer_offered(offline, tab_selector):
    press_plus(offline)
    tab_selector.choice = OTHER

    press_plus(offline)

    assert NAME not in tab_selector.created[1]
    assert tab_selector.created[1] == [n for n in tab_config if n != NAME]
    assert tab_texts(offline.ui) == ["Summary", NAME, OTHER, "+"]


def test_cancelling_the_selector_adds_nothing(offline, tab_selector):
    tab_selector.accept = False

    press_plus(offline)

    assert tab_texts(offline.ui) == ["Summary", "+"]
    assert offline.section(NAME) is None


def test_choosing_an_existing_tab_again_does_not_add_a_second_one(offline, tab_selector):
    press_plus(offline)
    first = offline.section(NAME)

    press_plus(offline)  # 가짜는 후보에 없어도 같은 이름을 돌려준다

    assert tab_texts(offline.ui) == ["Summary", NAME, "+"]
    assert offline.section(NAME) is first


def test_add_tab_returns_the_existing_section_for_a_name_already_shown(offline, tab_selector):
    ui = offline.ui
    press_plus(offline)
    existing = ui.widget(ui.find_tab(NAME))

    again = ui.add_tab(NAME, tab_config[NAME])

    assert again is existing
    assert tab_texts(ui) == ["Summary", NAME, "+"]


# -- 회귀 ----------------------------------------------------------------------


def test_rebuilding_after_adding_tabs_restores_the_config_order(offline, tab_selector):
    press_plus(offline)
    tab_selector.choice = OTHER
    press_plus(offline)
    assert tab_texts(offline.ui) == ["Summary", NAME, OTHER, "+"]

    offline.rebuild_all_sections()

    assert tab_texts(offline.ui) == ["Summary", *tab_config, "+"]
    assert list(offline._sections) == list(tab_config)
    assert offline.ui.currentIndex() == 1


def test_plus_after_connecting_offers_nothing(device_tab_ctrl, tab_selector):
    ui = device_tab_ctrl.parameter_tab.ui
    before = tab_texts(ui)
    assert before == ["Summary", *tab_config, "+"]

    press_plus(device_tab_ctrl.parameter_tab)

    assert tab_selector.created == []
    assert tab_texts(ui) == before
