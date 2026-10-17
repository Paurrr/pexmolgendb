"""지금 process 가 지워졌을 때 process 전환이 저장 취소·실패로 멈추는 경우 (phase 4 step 7).

phase 3 step 5 부터 저장이 취소되거나 실패해 편집이 남으면 콤보를 이전 process 로 되돌리고
멈춘다. 그런데 이전 process 가 지워졌으면(다른 사용자, Remove Process) `set_processes` 가 콤보를
이미 첫 process 로 바꿨고 이전 이름은 목록에 없다. 되돌리지 못해 콤보는 "sf2p", device 표는
지워진 "sf4u" 를 가리켰다. 지금은 넘어간다(사용자 승인 2026-10-17). 그 편집은 저장할 곳이 없다.
이전 process 가 목록에 있으면 되돌린다(tests/gui/test_process_change_save.py 가 지킨다).
"""

from gui_support.helpers import edit_device_cell, edit_tab_cell, select_device_row, select_process

from genviewer.dialogs.conflict import CANCEL

TAB = "InstTerm"
COLUMN = "cds_inst_term_name"
EDITED_TAB = "pdd"  # 시드 pfet_a 의 InstTerm 0행 값은 "pd"
EDITED_DESCRIPTION = "edited by tester"
SAVE_CHANGES = (
    "question",
    "Save Changes",
    "You have unsaved changes. Do you want to save them?",
)


def combo(ctrl):
    return ctrl.device_tab_toolbar.ui.process_selector


def combo_items(ctrl) -> list[str]:
    box = combo(ctrl)
    return [box.itemText(i) for i in range(box.count())]


def process_id(store, name: str) -> int:
    (found,) = [pid for pid, process in store.processes.items() if process == name]
    return found


def record_process_changes(ctrl) -> list[str]:
    changes: list[str] = []
    ctrl.device_tab_toolbar.processChanged.connect(changes.append)
    return changes


def errors(dialogs) -> list[str]:
    return [title for kind, title, _text in dialogs.shown if kind == "error"]


def conflicts(dialogs) -> list[tuple]:
    return [shown for shown in dialogs.shown if shown[0] == "conflict"]


def open_sf4u(ctrl, qtbot) -> None:
    select_process(ctrl, "sf4u")
    qtbot.waitUntil(lambda: ctrl.device_table.current_process == "sf4u")
    qtbot.waitUntil(lambda: ctrl.device_table.ui.model_safe().rowCount() == 1)


def edit_pfet_a_description(ctrl, qtbot) -> None:
    """sf4u 를 열고 pfet_a(0행) Description 을 고친다. 탭은 그대로다."""
    open_sf4u(ctrl, qtbot)
    assert ctrl.device_table.ui.model_safe().get_device(0)["name"] == "pfet_a"
    edit_device_cell(ctrl, 0, "description", EDITED_DESCRIPTION)
    assert ctrl.device_table.is_dirty()


def edit_pfet_a_tab(ctrl, store, qtbot) -> None:
    """sf4u 의 pfet_a 를 골라 InstTerm 0행 값을 고친다. device 행은 그대로다."""
    open_sf4u(ctrl, qtbot)
    select_device_row(ctrl, 0)
    pfet_a = store.find_device("pfet_a")["id"]
    qtbot.waitUntil(lambda: ctrl.parameter_tab.section(TAB).device_id == pfet_a)
    qtbot.waitUntil(lambda: len(ctrl.parameter_tab.section(TAB).model.get_data()) == 2)
    edit_tab_cell(ctrl, TAB, 0, COLUMN, EDITED_TAB)
    assert ctrl.parameter_tab.is_dirty()
    assert not ctrl.device_table.is_dirty()


def bob_deletes_sf4u(ctrl) -> None:
    ctrl.device_tab_toolbar.repo.delete("sf4u", actor="bob")


def assert_moved_to_sf2p(ctrl, store) -> None:
    assert combo(ctrl).currentText() == "sf2p"
    assert ctrl.device_table.current_process == "sf2p"
    assert ctrl.device_table.current_process_id == process_id(store, "sf2p")
    names = [d["name"] for d in ctrl.device_table.ui.model_safe().get_devices()]
    assert names == ["nfet_a", "nfet_b"]
    assert ctrl.device_table.is_dirty() is False


# -- 다른 사용자가 지움 ----------------------------------------------------------------


def test_cancelling_after_another_user_deleted_the_process_moves_to_the_first_process(
    device_tab_ctrl, store, dialogs, qtbot
):
    ctrl = device_tab_ctrl
    edit_pfet_a_description(ctrl, qtbot)
    bob_deletes_sf4u(ctrl)
    changes = record_process_changes(ctrl)
    dialogs.answer_question(True)
    dialogs.answer_conflict(CANCEL)

    ctrl.device_tab_toolbar.refresh_processes()

    qtbot.waitUntil(lambda: len(store.calls_of("upsert_devices")) == 1)
    assert_moved_to_sf2p(ctrl, store)
    assert combo_items(ctrl) == ["sf2p"]
    assert changes == ["sf2p"]
    assert dialogs.shown.count(SAVE_CHANGES) == 1
    assert len(conflicts(dialogs)) == 1
    assert errors(dialogs) == []


def test_a_save_error_after_another_user_deleted_the_process_moves_to_the_first_process(
    device_tab_ctrl, store, dialogs, qtbot
):
    ctrl = device_tab_ctrl
    edit_pfet_a_description(ctrl, qtbot)
    bob_deletes_sf4u(ctrl)
    store.fail_next("upsert_devices", RuntimeError("boom"))
    changes = record_process_changes(ctrl)
    dialogs.answer_question(True)

    ctrl.device_tab_toolbar.refresh_processes()

    qtbot.waitUntil(lambda: len(store.calls_of("upsert_devices")) == 1)
    assert errors(dialogs) == ["Save Devices Failed"]
    assert_moved_to_sf2p(ctrl, store)
    assert changes == ["sf2p"]
    assert conflicts(dialogs) == []


def test_cancelling_a_tab_save_after_another_user_deleted_the_process_moves_on(
    device_tab_ctrl, store, dialogs, qtbot
):
    ctrl = device_tab_ctrl
    edit_pfet_a_tab(ctrl, store, qtbot)
    bob_deletes_sf4u(ctrl)
    changes = record_process_changes(ctrl)
    dialogs.answer_question(True)
    # 가짜도 실제도 잠글 device 행이 없으면 "deleted" 충돌을 낸다.
    dialogs.answer_conflict(CANCEL)

    ctrl.device_tab_toolbar.refresh_processes()

    qtbot.waitUntil(lambda: len(store.calls_of("replace_many_for_device")) == 1)
    assert_moved_to_sf2p(ctrl, store)
    assert ctrl.parameter_tab.is_dirty() is False
    assert changes == ["sf2p"]
    assert store.calls_of("upsert_devices") == []
    assert len(conflicts(dialogs)) == 1
    assert errors(dialogs) == []


def test_answering_no_after_another_user_deleted_the_process_moves_on(
    device_tab_ctrl, store, dialogs, qtbot
):
    ctrl = device_tab_ctrl
    edit_pfet_a_description(ctrl, qtbot)
    bob_deletes_sf4u(ctrl)
    changes = record_process_changes(ctrl)
    dialogs.answer_question(False)

    ctrl.device_tab_toolbar.refresh_processes()

    qtbot.waitUntil(lambda: ctrl.device_table.current_process == "sf2p")
    assert_moved_to_sf2p(ctrl, store)
    assert changes == ["sf2p"]
    assert store.calls_of("upsert_devices") == []
    assert dialogs.shown.count(SAVE_CHANGES) == 1


# -- 내가 지움 ------------------------------------------------------------------------


def test_cancelling_after_removing_the_process_moves_to_the_first_process(
    device_tab_ctrl, store, dialogs, qtbot
):
    ctrl = device_tab_ctrl
    edit_pfet_a_description(ctrl, qtbot)
    changes = record_process_changes(ctrl)
    dialogs.answer_question(True, True)  # Remove Process, Save Changes
    dialogs.answer_conflict(CANCEL)

    ctrl.device_tab_toolbar.remove_process("sf4u")

    qtbot.waitUntil(lambda: len(store.calls_of("upsert_devices")) == 1)
    assert len(store.calls_of("delete")) == 1
    assert_moved_to_sf2p(ctrl, store)
    assert "sf4u" not in combo_items(ctrl)
    assert "sf4u" not in ctrl.device_tab_toolbar.repo.list_all()
    assert changes == ["sf2p"]
    assert len(conflicts(dialogs)) == 1
    assert errors(dialogs) == []


# -- select_process_silently ----------------------------------------------------------


def test_select_process_silently_reports_whether_it_found_the_name(device_tab_ctrl):
    ctrl = device_tab_ctrl
    changes = record_process_changes(ctrl)

    assert ctrl.device_tab_toolbar.select_process_silently("sf4u") is True
    assert combo(ctrl).currentText() == "sf4u"
    assert ctrl.device_tab_toolbar.select_process_silently("nope") is False
    assert combo(ctrl).currentText() == "sf4u"
    assert combo_items(ctrl) == ["sf2p", "sf4u"]
    # view 도 같은 값을 돌려준다.
    assert ctrl.device_tab_toolbar.ui.select_process_silently("sf2p") is True
    assert ctrl.device_tab_toolbar.ui.select_process_silently("nope") is False
    assert combo(ctrl).currentText() == "sf2p"
    assert changes == []
    assert ctrl.device_table.current_process == "sf2p"
