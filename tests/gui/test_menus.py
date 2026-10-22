"""메뉴 줄은 Database | Edit | View 다 (phase 23 step 4).

메뉴에 Database(Connect... / Save / Load CSV) 하나만 있었다. Undo·Redo 는 단축키로만, 내보내기는
device 표 오른쪽 클릭으로만 닿았다. 그래서 Database 에 `Export Selected Devices...` 를 더하고
(오른쪽 클릭 Export 와 같은 `export_selected_devices`), 대화상자를 여는 `Load CSV` 에 `...` 를
붙이고, Edit 메뉴에 창 동작 Undo·Redo 를 그대로 넣는다(단축키와 메뉴가 같은 동작이고, 지금처럼
포커스를 따른다). 메뉴 Save 는 device 표와 탭을 다 저장하고 Ctrl+S 는 포커스 쪽만 저장하므로
메뉴 Save 에는 단축키를 보이지 않는다. 2026-10-22 승인한 사용성 변경이다.
"""

import csv
from pathlib import Path

from gui_support.helpers import edit_device_cell, select_device_row, select_process
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QMenu

EDITED = "edited by tester"


def menu(main_window, title: str) -> QMenu:
    menus = [m for m in main_window.ui.menubar.findChildren(QMenu) if m.title() == title]
    assert len(menus) == 1, f"메뉴바에 {title} 메뉴가 없다"
    return menus[0]


def menu_action(main_window, title: str, text: str) -> QAction:
    actions = [a for a in menu(main_window, title).actions() if a.text() == text]
    assert len(actions) == 1, f"{title} 메뉴에 {text} 가 없다"
    return actions[0]


def ask_path(main_window, path: Path) -> list[str]:
    """저장 경로 대화상자 대신 path 를 돌려준다. 제안된 파일 이름을 기록해 돌려준다."""
    suggested: list[str] = []

    def fake(name: str) -> str:
        suggested.append(name)
        return str(path)

    main_window.device_tab.device_table.ui._ask_export_path = fake
    return suggested


def focus_device_table(main_window, qtbot) -> None:
    ui = main_window.ui
    ui.show()
    qtbot.waitExposed(ui)
    ui.activateWindow()
    qtbot.waitUntil(ui.isActiveWindow)
    view = main_window.device_tab.ui.device_table_view
    view.setFocus()
    qtbot.waitUntil(view.hasFocus)


# --------------------------------------------------------------------------
# 메뉴 줄과 Database
# --------------------------------------------------------------------------


def test_menu_bar_order(main_window):
    titles = [a.menu().title() for a in main_window.ui.menubar.actions()]

    assert titles == ["Database", "Edit", "View"]


def test_database_menu_items(main_window):
    items = [
        "-" if a.isSeparator() else a.text() for a in menu(main_window, "Database").actions()
    ]

    assert items == ["Connect...", "-", "Save", "-", "Load CSV...", "Export Selected Devices..."]


def test_save_menu_item_shows_no_shortcut(main_window):
    assert menu_action(main_window, "Database", "Save").shortcut().isEmpty()


def test_load_csv_menu_text(main_window, monkeypatch):
    calls: list[tuple] = []
    monkeypatch.setattr(
        main_window.ui.device_tab_view, "_ask_load_csv", lambda *args: calls.append(args)
    )

    menu_action(main_window, "Database", "Load CSV...").trigger()

    assert len(calls) == 1


# --------------------------------------------------------------------------
# Database → Export Selected Devices...
# --------------------------------------------------------------------------


def test_export_menu_exports_selected_devices(main_window, dialogs, tmp_path):
    ctrl = main_window.device_tab
    select_process(ctrl, "sf2p")
    select_device_row(ctrl, 1)
    assert ctrl.device_table.ui.model_safe().get_device(1)["name"] == "nfet_b"
    path = tmp_path / "out.csv"
    suggested = ask_path(main_window, path)

    menu_action(main_window, "Database", "Export Selected Devices...").trigger()

    assert suggested == ["sf2p.csv"]
    with open(path, newline="", encoding="utf-8") as f:
        header, *rows = list(csv.reader(f))
    assert header[:3] == ["CellType", "CdsLibName", "InstCellName"]
    assert [row[2] for row in rows] == ["nfet_b"]  # 고른 행만. 선택이 없을 때의 "전체" 가 아니다
    assert dialogs.shown == [("info", "Save CSV", "Success!\n - out.csv")]


def test_export_menu_without_selection_warns(main_window, store, dialogs, qtbot):
    """선택이 없으면 오른쪽 클릭 Export 처럼 표의 모든 device 를 낸다. 표가 비면 경고다."""
    ctrl = main_window.device_tab
    store.add_process("empty")
    ctrl.device_tab_toolbar.refresh_processes()
    select_process(ctrl, "empty")
    qtbot.waitUntil(lambda: ctrl.device_table.current_process == "empty")
    assert ctrl.device_table.ui.model_safe().rowCount() == 0
    suggested = ask_path(main_window, Path("unused.csv"))

    menu_action(main_window, "Database", "Export Selected Devices...").trigger()

    assert dialogs.shown == [("warning", "Export", "No device selected.")]
    assert suggested == []  # 파일 창을 열지 않았다


# --------------------------------------------------------------------------
# Edit → Undo / Redo
# --------------------------------------------------------------------------


def test_edit_menu_holds_the_window_undo_redo(main_window):
    window_actions = main_window.ui.actions()
    undo, redo = menu(main_window, "Edit").actions()

    assert [undo.text(), redo.text()] == ["Undo", "Redo"]
    assert any(undo is a for a in window_actions)
    assert any(redo is a for a in window_actions)
    assert undo.shortcut() == QKeySequence(QKeySequence.Undo)
    assert redo.shortcut() == QKeySequence(QKeySequence.Redo)


def test_edit_menu_undo_reverts_the_focused_device_table(main_window, qtbot):
    ctrl = main_window.device_tab
    model = ctrl.device_table.ui.model_safe()
    before = model.get_device(0)["description"]
    edit_device_cell(ctrl, 0, "description", EDITED)
    assert ctrl.device_table.is_dirty()
    focus_device_table(main_window, qtbot)

    menu_action(main_window, "Edit", "Undo").trigger()

    assert model.get_device(0)["description"] == before
    assert not ctrl.device_table.is_dirty()

    menu_action(main_window, "Edit", "Redo").trigger()

    assert model.get_device(0)["description"] == EDITED
    assert ctrl.device_table.is_dirty()
