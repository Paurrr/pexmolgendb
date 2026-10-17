"""저장 입구 두 곳: Database → Save(save_db)와 Ctrl+S(_on_save_triggered) (phase 3 step 2).

save_db 는 device 다음에 탭도 저장하고, 둘 다 저장됐을 때만 "All changes have been saved." 를
띄운다(UI_GUIDE 원칙 4). device 저장이 예외로 실패하면 탭 저장으로 가지 않는다.
Ctrl+S 의 상태 표시줄 문구도 저장 함수가 True 를 돌려줄 때만 낸다.

같은 device 의 device 행과 탭을 함께 고친 저장은 아직 나 자신과 충돌한다(step 6).
그래서 여기서는 둘을 같은 device 에서 함께 고치지 않는다.
"""

from gui_support.helpers import edit_device_cell, edit_tab_cell, select_device_row, select_process
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu

from genviewer.dialogs.conflict import CANCEL, OVERWRITE

TAB = "InstTerm"
COLUMN = "cds_inst_term_name"
ALL_SAVED = ("info", "Saved", "All changes have been saved.")


def all_saved_shown(dialogs) -> bool:
    return any(text == ALL_SAVED[2] for _kind, _title, text in dialogs.shown)


def status(main_window) -> str:
    return main_window.ui.statusBar().currentMessage()


def database_save_action(main_window) -> QAction:
    """메뉴 Database → Save. 창 전체의 Ctrl+S 도 텍스트가 "Save" 라서 메뉴 안에서 찾는다."""
    menus = [m for m in main_window.ui.menubar.findChildren(QMenu) if m.title() == "Database"]
    assert len(menus) == 1, "메뉴바에 Database 메뉴가 없다"
    actions = [a for a in menus[0].actions() if a.text() == "Save"]
    assert len(actions) == 1, "Database 메뉴에 Save 가 없다"
    return actions[0]


def edit_nfet_a_description(ctrl) -> None:
    """sf2p 의 nfet_a(0행) Description 을 고친다. 탭은 그대로다."""
    select_process(ctrl, "sf2p")
    assert ctrl.device_table.ui.model_safe().get_device(0)["name"] == "nfet_a"
    edit_device_cell(ctrl, 0, "description", "edited by tester")
    assert ctrl.device_table.is_dirty()


def edit_nfet_a_tab(ctrl, store, qtbot) -> None:
    """sf2p 의 nfet_a(0행)를 골라 InstTerm 0행 값을 고친다. device 행은 그대로다."""
    select_process(ctrl, "sf2p")
    select_device_row(ctrl, 0)
    nfet_a = store.find_device("nfet_a")["id"]
    qtbot.waitUntil(lambda: ctrl.parameter_tab.section(TAB).device_id == nfet_a)
    qtbot.waitUntil(lambda: len(ctrl.parameter_tab.section(TAB).model.get_data()) == 4)
    edit_tab_cell(ctrl, TAB, 0, COLUMN, "dd")
    assert ctrl.parameter_tab.is_dirty()
    assert not ctrl.device_table.is_dirty()


def bob_saves_nfet_a(store) -> None:
    store.touch_device(store.find_device("nfet_a")["id"], actor="bob")


# -- Database → Save ----------------------------------------------------------


def test_database_save_also_saves_tabs(main_window, store, dialogs, qtbot):
    ctrl = main_window.device_tab
    edit_nfet_a_tab(ctrl, store, qtbot)
    nfet_a = store.find_device("nfet_a")["id"]

    database_save_action(main_window).trigger()

    calls = store.calls_of("replace_many_for_device")
    assert [c["device_id"] for c in calls] == [nfet_a]
    assert store.rows("inst_terms", nfet_a)[0][COLUMN] == "dd"
    assert ALL_SAVED in dialogs.shown
    assert not ctrl.parameter_tab.is_dirty()


def test_cancelling_a_device_conflict_is_not_reported_as_saved(
    main_window, store, dialogs
):
    ctrl = main_window.device_tab
    edit_nfet_a_description(ctrl)
    bob_saves_nfet_a(store)
    dialogs.answer_conflict(CANCEL)

    assert ctrl.save_db() is False

    assert not all_saved_shown(dialogs)
    assert ctrl.device_table.is_dirty()


def test_cancelling_a_tab_conflict_is_not_reported_as_saved(
    main_window, store, dialogs, qtbot
):
    ctrl = main_window.device_tab
    edit_nfet_a_tab(ctrl, store, qtbot)
    bob_saves_nfet_a(store)
    # device 저장이 화면의 device 전부의 version 을 보므로 먼저 충돌한다. 덮어써도 nfet_a 값이
    # 같아 version 은 그대로이고, 이어지는 탭 저장이 bob 과 충돌해 취소를 받는다.
    dialogs.answer_conflict(OVERWRITE, CANCEL)

    assert ctrl.save_db() is False

    assert [kind for kind, _title, _text in dialogs.shown].count("conflict") == 2
    assert len(store.calls_of("replace_many_for_device")) == 1
    assert not all_saved_shown(dialogs)
    assert ctrl.parameter_tab.is_dirty()


def test_a_device_save_error_stops_before_the_tabs(main_window, store, dialogs, qtbot):
    ctrl = main_window.device_tab
    edit_nfet_a_tab(ctrl, store, qtbot)
    store.fail_next("upsert_devices", RuntimeError("boom"))

    assert ctrl.save_db() is False

    assert [title for kind, title, _text in dialogs.shown if kind == "error"] == [
        "Save Devices Failed"
    ]
    assert store.calls_of("replace_many_for_device") == []
    assert not all_saved_shown(dialogs)
    assert ctrl.parameter_tab.is_dirty()


# -- Ctrl+S ---------------------------------------------------------------------


def focus_on(monkeypatch, main_window, widget) -> None:
    # offscreen 에서 실제 포커스는 창 활성화에 달려 있어 불안정하다.
    # isAncestorOf 는 자기 자신에도 참이다.
    monkeypatch.setattr(main_window.ui, "focusWidget", lambda: widget)


def test_ctrl_s_on_the_device_table_reports_a_save(main_window, store, dialogs, monkeypatch):
    ctrl = main_window.device_tab
    edit_nfet_a_description(ctrl)
    focus_on(monkeypatch, main_window, ctrl.ui.device_table_view)

    main_window._on_save_triggered()

    assert status(main_window) == "Device table saved"
    assert not ctrl.device_table.is_dirty()


def test_ctrl_s_on_the_device_table_after_cancel_reports_nothing(
    main_window, store, dialogs, monkeypatch
):
    ctrl = main_window.device_tab
    edit_nfet_a_description(ctrl)
    bob_saves_nfet_a(store)
    dialogs.answer_conflict(CANCEL)
    focus_on(monkeypatch, main_window, ctrl.ui.device_table_view)

    main_window._on_save_triggered()

    assert status(main_window) != "Device table saved"
    assert ctrl.device_table.is_dirty()


def test_ctrl_s_on_the_tabs_after_cancel_reports_nothing(
    main_window, store, dialogs, qtbot, monkeypatch
):
    ctrl = main_window.device_tab
    edit_nfet_a_tab(ctrl, store, qtbot)
    bob_saves_nfet_a(store)
    dialogs.answer_conflict(CANCEL)
    focus_on(monkeypatch, main_window, ctrl.ui.parameter_tab_view)

    main_window._on_save_triggered()

    assert len(store.calls_of("replace_many_for_device")) == 1
    assert status(main_window) != "Tab section data saved"
    assert ctrl.parameter_tab.is_dirty()


def test_ctrl_s_elsewhere_saves_devices_and_tabs(
    main_window, store, dialogs, qtbot, monkeypatch
):
    ctrl = main_window.device_tab
    edit_nfet_a_tab(ctrl, store, qtbot)
    focus_on(monkeypatch, main_window, None)

    main_window._on_save_triggered()

    assert status(main_window) == "All device and tab data saved"
    assert ALL_SAVED in dialogs.shown
    assert not ctrl.parameter_tab.is_dirty()


def test_ctrl_s_elsewhere_after_a_device_save_error_reports_nothing(
    main_window, store, dialogs, monkeypatch
):
    ctrl = main_window.device_tab
    edit_nfet_a_description(ctrl)
    store.fail_next("upsert_devices", RuntimeError("boom"))
    focus_on(monkeypatch, main_window, None)

    main_window._on_save_triggered()

    assert [title for kind, title, _text in dialogs.shown if kind == "error"] == [
        "Save Devices Failed"
    ]
    assert status(main_window) != "All device and tab data saved"
