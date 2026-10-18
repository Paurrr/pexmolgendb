"""파라미터 탭을 다시 만들 때 옛 페이지를 남기지 않는다 (phase 12 step 6, K22).

접속·재접속마다 `DeviceTabController.apply_db` → `rebuild_all_sections()` →
`ParameterTab.rebuild_tabs` 가 탭을 다시 만든다. `rebuild_tabs` 는 `QTabWidget.clear()` 로 페이지를
떼는데, `clear()` 는 페이지 위젯을 지우지 않는다. 그래서 다시 만들 때마다 옛 `TabSection` 14개(와
섹션을 부모로 둔 `TabSectionController`, 그 모델 캐시, 로그·알림 연결)와 옛 "+" 위젯이 숨은 자식으로
남았다.

불변식: 지연 삭제를 처리한 뒤 이 위젯 아래의 `TabSection`·`TabSectionController` 수는 지금 탭
페이지의 섹션 수와 같고, 옛 섹션·옛 "+" 는 지워진다. `summary_view` 는 지우지 않고 0번 페이지로 다시
쓴다. 탭 순서·현재 탭(섹션이 있으면 1번)은 그대로이고, `current_tab_section` 은 지워진 섹션을
가리키지 않는다.
"""

import shiboken6
from gui_support.helpers import select_device_row, select_process
from PySide6.QtCore import QCoreApplication, QEvent, Qt
from PySide6.QtWidgets import QStackedWidget, QWidget

from genviewer.config.config import tab_config
from genviewer.controllers.tab_section import TabSectionController
from genviewer.views.parameter_tab import ParameterTab
from genviewer.views.tab_section import TabSection

TAB = "InstTerm"  # 시드에 행이 있는 탭
NFET_B_ROWS = [
    {"reserved_key": "DRN", "cds_inst_term_name": "d2"},
    {"reserved_key": "GATE", "cds_inst_term_name": "g2"},
]


def flush_deletes() -> None:
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def tab_texts(view: ParameterTab) -> list[str]:
    return [view.tabText(i) for i in range(view.count())]


def rebuild(ctrl, times: int = 3) -> None:
    for _ in range(times):
        ctrl.parameter_tab.rebuild_all_sections()
    flush_deletes()


def stack_pages(view: ParameterTab) -> list[QWidget]:
    """탭 페이지를 담는 QStackedWidget 의 직계 자식 위젯(떼어 낸 페이지도 여기 남는다)."""
    stack = view.findChild(QStackedWidget)
    return stack.findChildren(QWidget, options=Qt.FindChildOption.FindDirectChildrenOnly)


def assert_no_leftover_pages(view: ParameterTab) -> None:
    sections = list(view.iter_sections())
    assert len(view.findChildren(TabSection)) == len(sections)
    assert len(view.findChildren(TabSectionController)) == len(sections)
    assert len(stack_pages(view)) == view.count()
    assert tab_texts(view).count("+") == 1


# -- 다시 만들기 ---------------------------------------------------------------


def test_rebuilding_deletes_the_old_sections_and_the_old_plus(device_tab_ctrl):
    view = device_tab_ctrl.ui.parameter_tab_view
    old_section = view.widget(1)
    old_plus = view.widget(view.count() - 1)
    assert isinstance(old_section, TabSection)
    assert view.tabText(view.count() - 1) == "+"

    rebuild(device_tab_ctrl)

    assert len(view.findChildren(TabSection)) == len(list(view.iter_sections()))
    assert len(list(view.iter_sections())) == len(tab_config)
    assert not shiboken6.isValid(old_section)
    assert not shiboken6.isValid(old_plus)


def test_rebuilding_leaves_one_plus_page(device_tab_ctrl):
    view = device_tab_ctrl.ui.parameter_tab_view

    rebuild(device_tab_ctrl)

    assert tab_texts(view).count("+") == 1
    assert len(stack_pages(view)) == view.count()


def test_rebuilding_deletes_the_old_section_controllers(device_tab_ctrl):
    view = device_tab_ctrl.ui.parameter_tab_view
    old_ctrl = device_tab_ctrl.parameter_tab.section(TAB)
    assert old_ctrl is not None

    rebuild(device_tab_ctrl)

    assert len(view.findChildren(TabSectionController)) == len(list(view.iter_sections()))
    assert not shiboken6.isValid(old_ctrl)
    # 컨트롤러가 들고 있는 것은 지금 섹션의 컨트롤러뿐이다.
    sections = list(view.iter_sections())
    assert [c.ui for c in device_tab_ctrl.parameter_tab._sections.values()] == sections


# -- 회귀 ----------------------------------------------------------------------


def test_the_summary_page_survives_rebuilding(device_tab_ctrl):
    view = device_tab_ctrl.ui.parameter_tab_view
    summary = view.summary_view

    rebuild(device_tab_ctrl)

    assert shiboken6.isValid(summary)
    assert view.summary_view is summary
    assert view.widget(0) is summary
    assert view.tabText(0) == "Summary"


def test_the_summary_still_opens_its_source_cell_after_rebuilding(device_tab_ctrl):
    """`summarySourceActivated` 는 생성자에서 한 번만 잇는다. 다시 만든 뒤에도 그 연결이 산다."""
    view = device_tab_ctrl.ui.parameter_tab_view
    logs: list[str] = []
    device_tab_ctrl.parameter_tab.logRequested.connect(logs.append)
    rebuild(device_tab_ctrl)

    view.summary_view.sourceActivated.emit(TAB, 0, 0)

    assert view.currentIndex() == view.find_tab(TAB)
    assert logs == [f"Summary: opened {TAB} row 1, column 1."]


def test_rebuilding_keeps_the_tab_order_and_the_current_tab(device_tab_ctrl):
    view = device_tab_ctrl.ui.parameter_tab_view

    rebuild(device_tab_ctrl)

    assert tab_texts(view) == ["Summary", *tab_config, "+"]
    assert view.currentIndex() == 1
    assert view.current_tab_section is view.widget(1)


def test_selecting_a_device_after_rebuilding_reads_the_tab_rows(device_tab_ctrl, store, qtbot):
    nfet_b = store.find_device("nfet_b")["id"]
    select_process(device_tab_ctrl, "sf2p")
    rebuild(device_tab_ctrl)
    since = len(store.calls_of("fetch_by_device"))

    select_device_row(device_tab_ctrl, 1)

    sec = device_tab_ctrl.parameter_tab.section(TAB)
    qtbot.waitUntil(lambda: sec.device_id == nfet_b and sec.model is not None)
    assert sec.model.get_data() == NFET_B_ROWS
    fetched = store.calls_of("fetch_by_device")[since:]
    assert {c["device_id"] for c in fetched} == {nfet_b}
    assert len(fetched) == len(tab_config)
    assert sec.ui.table_view.model() is sec.model


def test_the_current_section_after_rebuilding_is_alive(device_tab_ctrl):
    view = device_tab_ctrl.ui.parameter_tab_view
    view.setCurrentIndex(view.find_tab(TAB))

    rebuild(device_tab_ctrl)

    current = getattr(view, "current_tab_section", None)
    assert current is None or (
        shiboken6.isValid(current) and current in list(view.iter_sections())
    )


def test_rebuilding_with_no_tabs_leaves_no_section_behind(device_tab_ctrl, monkeypatch):
    view = device_tab_ctrl.ui.parameter_tab_view
    view.setCurrentIndex(view.find_tab(TAB))
    monkeypatch.setattr("genviewer.controllers.parameter_tab.tab_config", {})

    rebuild(device_tab_ctrl, times=1)

    assert tab_texts(view) == ["Summary", "+"]
    assert view.currentIndex() == 0
    assert getattr(view, "current_tab_section", None) is None
    assert view.findChildren(TabSection) == []
    assert view.findChildren(TabSectionController) == []
    assert len(stack_pages(view)) == view.count()


def test_the_view_drops_a_current_section_it_deletes(qtbot):
    """컨트롤러 없이 쓴 view 도 지운 섹션을 `current_tab_section` 으로 들고 있지 않는다.

    컨트롤러가 붙어 있으면 `clear()` 가 마지막 페이지를 뗄 때 `currentChanged(-1)` →
    `on_tab_changed` 가 먼저 비운다. 이 테스트는 그 연결 없이도 view 가 스스로 비우는지 본다.
    """
    view = ParameterTab()
    qtbot.addWidget(view)
    view.rebuild_tabs(tab_config)
    view.on_tab_changed(view.currentIndex())
    old = view.current_tab_section
    assert isinstance(old, TabSection)

    view.rebuild_tabs({})
    flush_deletes()

    assert view.current_tab_section is None
    assert not shiboken6.isValid(old)
    assert view.findChildren(TabSection) == []


# -- 재접속 경로 ---------------------------------------------------------------


def test_reconnecting_does_not_pile_up_pages(main_window, dialogs):
    view = main_window.ui.device_tab_view.parameter_tab_view
    old_section = view.widget(1)
    old_ctrl = main_window.device_tab.parameter_tab.section(TAB)
    old_plus = view.widget(view.count() - 1)

    main_window.ui.device_tab_view.dbConnectRequested.emit("host=other")
    main_window.ui.device_tab_view.dbConnectRequested.emit("host=other")
    flush_deletes()

    assert [title for _, title, _ in dialogs.shown] == ["Connected", "Connected"]
    assert_no_leftover_pages(view)
    assert len(list(view.iter_sections())) == len(tab_config)
    assert not shiboken6.isValid(old_section)
    assert not shiboken6.isValid(old_ctrl)
    assert not shiboken6.isValid(old_plus)
    assert tab_texts(view) == ["Summary", *tab_config, "+"]
    assert view.widget(0) is view.summary_view
