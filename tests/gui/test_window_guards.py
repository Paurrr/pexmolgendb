"""저장 안 한 편집이 말없이 사라지는 두 경로 (phase 4 step 5).

G6: 창을 닫을 때 device 표나 탭에 저장 안 한 편집이 있으면 "Save Changes" 를 묻는다. 예면
save_db() 가 True 일 때만 닫고, 아니오면 버리고 닫는다. 저장·접속 중(run_blocking 안)에는
묻지 않고 닫기를 무시한다. shutdown() 뒤에는 묻지 않는다.

G15c: Virtuoso 의 [DeviceList] 응답이 왔을 때 device 표에 저장 안 한 편집이 있으면 다시 읽기 전에
"Refresh" 를 묻는다. 아니오면 Virtuoso 목록 표와 device_state_data 만 갱신하고 device 표는 둔다.

Virtuoso 응답은 소켓 없이 `connection_controller.received` 로 넣는다.
"""

import threading

from gui_support.helpers import edit_device_cell, edit_tab_cell, select_device_row, select_process
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor

from genviewer.config.config import delegate_config
from genviewer.dialogs.conflict import CANCEL
from genviewer.service.errors import DbUnavailableError
from genviewer.utils.background import run_blocking
from genviewer.utils.palette import current_colors

EDITED = "edited by tester"
DESCRIPTION = 2
OFF_LIST = "nmos_rf"  # delegate_config 의 device.celltype.items 에 없다
TAB = "InstTerm"
COLUMN = "cds_inst_term_name"
SAVE_CHANGES = ("question", "Save Changes", "You have unsaved changes. Do you want to save them?")
REFRESH = (
    "question",
    "Refresh",
    "You have unsaved changes.\nReloading from the server discards them. Continue?",
)
DEVICE_LIST = "[DeviceList]nfet_a,O,O,lib"
NEW_STATE = {"nfet_a": {"S": "O", "L": "O", "library_name": "lib"}}


def model_of(ctrl):
    return ctrl.device_table.ui.model_safe()


def questions(dialogs) -> list[tuple[str, str, str]]:
    return [shown for shown in dialogs.shown if shown[0] == "question"]


def titles(dialogs) -> list[str]:
    return [title for _kind, title, _text in dialogs.shown]


def dirty_cells(model) -> set[tuple[int, int]]:
    dirty = QColor(current_colors()["dirty"])  # 지금 테마의 저장 안 한 셀 배경
    return {
        (r, c)
        for r in range(model.rowCount())
        for c in range(model.columnCount())
        if model.index(r, c).data(Qt.BackgroundRole) == dirty
    }


def edit_nfet_a_description(ctrl) -> None:
    """sf2p 의 nfet_a(0행) Description 을 고친다. 탭은 그대로다."""
    select_process(ctrl, "sf2p")
    assert model_of(ctrl).get_device(0)["name"] == "nfet_a"
    edit_device_cell(ctrl, 0, "description", EDITED)
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


def fetch_count(store) -> int:
    return len(store.calls_of("fetch_devices_by_process"))


# ----------------------------------------------------------------------
# G6: 창 닫기
# ----------------------------------------------------------------------


def test_closing_without_edits_does_not_ask(main_window, dialogs):
    assert main_window.ui.close() is True

    assert questions(dialogs) == []


def test_closing_with_a_device_edit_asks_and_no_closes_without_saving(
    main_window, store, dialogs
):
    edit_nfet_a_description(main_window.device_tab)
    dialogs.answer_question(False)

    assert main_window.ui.close() is True

    assert questions(dialogs) == [SAVE_CHANGES]
    assert store.calls_of("upsert_devices") == []
    assert store.find_device("nfet_a")["description"] == ""


def test_closing_with_a_device_edit_and_yes_saves_then_closes(main_window, store, dialogs):
    edit_nfet_a_description(main_window.device_tab)
    dialogs.answer_question(True)

    assert main_window.ui.close() is True

    assert questions(dialogs) == [SAVE_CHANGES]
    assert len(store.calls_of("upsert_devices")) == 1
    assert store.find_device("nfet_a")["description"] == EDITED
    assert not main_window.device_tab.device_table.is_dirty()


def test_a_failed_save_keeps_the_window_open(main_window, store, dialogs):
    ctrl = main_window.device_tab
    edit_nfet_a_description(ctrl)
    store.fail_next("upsert_devices", DbUnavailableError("down"))
    dialogs.answer_question(True)

    assert main_window.ui.close() is False

    assert questions(dialogs) == [SAVE_CHANGES]
    assert "Save Devices Failed" in titles(dialogs)
    assert model_of(ctrl).get_device(0)["description"] == EDITED
    assert ctrl.device_table.is_dirty()


def test_cancelling_the_conflict_keeps_the_window_open(main_window, store, dialogs):
    ctrl = main_window.device_tab
    edit_nfet_a_description(ctrl)
    store.touch_device(store.find_device("nfet_a")["id"], actor="bob")
    dialogs.answer_question(True)
    dialogs.answer_conflict(CANCEL)

    assert main_window.ui.close() is False

    assert questions(dialogs) == [SAVE_CHANGES]
    assert "Save Conflict" in titles(dialogs)
    assert model_of(ctrl).get_device(0)["description"] == EDITED
    assert ctrl.device_table.is_dirty()


def test_a_skipped_save_keeps_the_window_open_once(main_window, store, dialogs):
    """Save Skipped 는 저장 실패다. 다시 읽기로 편집이 지워졌으므로 다음 닫기는 묻지 않는다."""
    ctrl = main_window.device_tab
    select_process(ctrl, "sf2p")
    assert OFF_LIST not in delegate_config["device"]["celltype"]["items"]
    edit_device_cell(ctrl, 0, "celltype", OFF_LIST)
    dialogs.answer_question(True)

    assert main_window.ui.close() is False

    assert questions(dialogs) == [SAVE_CHANGES]
    assert "Save Skipped" in titles(dialogs)
    assert not ctrl.device_table.is_dirty()

    assert main_window.ui.close() is True
    assert questions(dialogs) == [SAVE_CHANGES]


def test_closing_with_only_a_tab_edit_saves_the_tab(main_window, store, dialogs, qtbot):
    ctrl = main_window.device_tab
    edit_nfet_a_tab(ctrl, store, qtbot)
    nfet_a = store.find_device("nfet_a")["id"]
    dialogs.answer_question(True)

    assert main_window.ui.close() is True

    assert questions(dialogs) == [SAVE_CHANGES]
    assert [c["device_id"] for c in store.calls_of("replace_many_for_device")] == [nfet_a]
    assert store.rows("inst_terms", nfet_a)[0][COLUMN] == "dd"
    assert not ctrl.parameter_tab.is_dirty()


def test_closing_while_busy_is_ignored(main_window, store, dialogs):
    """run_blocking 은 사용자 입력만 막는다. 그 안에서 온 닫기 요청은 묻지 않고 무시한다."""
    edit_nfet_a_description(main_window.device_tab)
    closed: list[bool] = []
    asked = threading.Event()

    def close_now() -> None:
        closed.append(main_window.ui.close())
        asked.set()

    QTimer.singleShot(0, close_now)
    run_blocking(lambda: asked.wait(5), main_window.ui)

    assert closed == [False]
    assert questions(dialogs) == []
    assert store.calls_of("upsert_devices") == []
    assert main_window.device_tab.device_table.is_dirty()


def test_closing_after_shutdown_does_not_ask(main_window, dialogs):
    edit_nfet_a_description(main_window.device_tab)
    main_window.shutdown()

    assert main_window.ui.close() is True

    assert questions(dialogs) == []


# ----------------------------------------------------------------------
# G15c: Virtuoso [DeviceList] 응답
# ----------------------------------------------------------------------


def test_a_device_list_without_edits_reloads_the_device_table(main_window, store, dialogs):
    ctrl = main_window.device_tab
    select_process(ctrl, "sf2p")
    before = fetch_count(store)

    main_window.connection_controller.received.emit(DEVICE_LIST)

    assert questions(dialogs) == []
    assert fetch_count(store) == before + 1
    assert ctrl.device_table.device_state_data == NEW_STATE
    assert [d["name"] for d in model_of(ctrl).get_devices()] == ["nfet_a"]


def test_a_device_list_keeps_device_edits_when_the_user_says_no(main_window, store, dialogs):
    ctrl = main_window.device_tab
    edit_nfet_a_description(ctrl)
    before = fetch_count(store)
    dialogs.answer_question(False)

    main_window.connection_controller.received.emit(DEVICE_LIST)

    model = model_of(ctrl)
    assert model.get_device(0)["description"] == EDITED
    assert model.is_modified()
    assert dirty_cells(model) == {(0, DESCRIPTION)}
    assert ctrl.device_table.is_dirty()
    assert [d["name"] for d in model.get_devices()] == ["nfet_a", "nfet_b"]
    assert questions(dialogs) == [REFRESH]
    # 목록은 받은 것이 맞다. 지킨 것은 device 표의 편집뿐이다.
    assert ctrl.device_table.device_state_data == NEW_STATE
    assert ctrl.ui.virtuoso_device_table.get_devices() == NEW_STATE
    assert ctrl.ui.filtered_device_table.get_devices() == NEW_STATE
    assert fetch_count(store) == before
    assert "Received Virtuoso device list: 1 item(s)." in main_window.ui.log_te.toPlainText()


def test_a_device_list_keeps_a_deleted_device_when_the_user_says_no(
    main_window, store, dialogs
):
    ctrl = main_window.device_tab
    select_process(ctrl, "sf2p")
    nfet_b = store.find_device("nfet_b")
    model = model_of(ctrl)
    ctrl.device_table.remove_rows([1])
    assert [d["name"] for d in model.get_devices()] == ["nfet_a"]
    assert ctrl.device_table.is_dirty()
    dialogs.answer_question(False)

    main_window.connection_controller.received.emit(DEVICE_LIST)

    assert model.deleted_devices() == {nfet_b["id"]: nfet_b["version"]}
    assert questions(dialogs) == [REFRESH]


def test_a_device_list_drops_device_edits_when_the_user_says_yes(main_window, store, dialogs):
    ctrl = main_window.device_tab
    edit_nfet_a_description(ctrl)
    before = fetch_count(store)
    dialogs.answer_question(True)

    main_window.connection_controller.received.emit(DEVICE_LIST)

    assert questions(dialogs) == [REFRESH]
    assert fetch_count(store) == before + 1
    model = model_of(ctrl)
    assert not model.is_modified()
    assert model.get_device(0)["description"] == ""
    assert not ctrl.device_table.is_dirty()
    assert ctrl.device_table.device_state_data == NEW_STATE


def test_a_device_list_does_not_ask_about_tab_edits(main_window, store, dialogs, qtbot):
    """탭 편집은 device 표를 다시 읽어도 사라지지 않는다. device 표의 dirty 만 본다."""
    ctrl = main_window.device_tab
    edit_nfet_a_tab(ctrl, store, qtbot)
    before = fetch_count(store)

    main_window.connection_controller.received.emit(DEVICE_LIST)

    assert questions(dialogs) == []
    assert fetch_count(store) == before + 1
    assert ctrl.parameter_tab.is_dirty()
