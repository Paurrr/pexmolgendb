"""DeviceTableController.save_all 의 반환 계약 (phase 3 step 0).

True 는 "저장했다(덮어쓰기 포함) 또는 쓸 것이 없었다", False 는 "사용자가 저장하지 않기로
했다(충돌 대화상자의 취소·다시 읽기) 또는 접속 전" 이다. 예상 밖 예외는 그대로 올라간다.
호출부(save_db, Ctrl+S, process 전환)가 이 값을 보고 "Saved" 를 띄울지 정한다(step 2·5).
"""

import pytest
from gui_support.helpers import edit_device_cell, select_process

from genviewer.dialogs.conflict import CANCEL, OVERWRITE, RELOAD

EDITED = "edited by tester"


def save_complete(dialogs) -> list[tuple[str, str, str]]:
    return [shown for shown in dialogs.shown if shown[1] == "Save Complete"]


def screen_description(ctrl, row: int) -> str:
    return ctrl.device_table.ui.model_safe().get_device(row)["description"]


def edit_nfet_a(ctrl) -> None:
    """sf2p 의 nfet_a(0행) Description 을 고친다."""
    select_process(ctrl, "sf2p")
    assert ctrl.device_table.ui.model_safe().get_device(0)["name"] == "nfet_a"
    edit_device_cell(ctrl, 0, "description", EDITED)
    assert ctrl.device_table.is_dirty()


def test_a_successful_save_returns_true(device_tab_ctrl, store, dialogs):
    ctrl = device_tab_ctrl
    edit_nfet_a(ctrl)

    assert ctrl.device_table.save_all() is True

    assert len(store.calls_of("upsert_devices")) == 1
    assert store.find_device("nfet_a")["description"] == EDITED
    assert not ctrl.device_table.is_dirty()
    assert save_complete(dialogs) == [("info", "Save Complete", "1 updated.")]


def test_a_save_without_changed_rows_returns_true(device_tab_ctrl, store, dialogs):
    ctrl = device_tab_ctrl
    select_process(ctrl, "sf2p")

    assert ctrl.device_table.save_all() is True

    assert save_complete(dialogs) == [("info", "Save Complete", "No changes to save.")]


def test_a_process_without_devices_returns_true_without_writing(
    device_tab_ctrl, store, dialogs, qtbot
):
    ctrl = device_tab_ctrl
    ctrl.device_tab_toolbar.add_process("empty_p")
    qtbot.waitUntil(lambda: ctrl.device_table.current_process == "empty_p")
    assert ctrl.device_table.ui.model_safe().get_devices() == []

    assert ctrl.device_table.save_all() is True

    assert store.calls_of("upsert_devices") == []
    assert save_complete(dialogs) == [("info", "Save Complete", "No changes to save.")]


def test_overwriting_a_stale_save_returns_true(device_tab_ctrl, store, dialogs):
    ctrl = device_tab_ctrl
    edit_nfet_a(ctrl)
    store.touch_device(store.find_device("nfet_a")["id"], actor="bob")
    dialogs.answer_conflict(OVERWRITE)

    assert ctrl.device_table.save_all() is True

    calls = store.calls_of("upsert_devices")
    assert [c["force"] for c in calls] == [False, True]
    assert store.find_device("nfet_a")["description"] == EDITED
    assert [shown[0] for shown in dialogs.shown].count("conflict") == 1


def test_cancelling_a_stale_save_returns_false(device_tab_ctrl, store, dialogs):
    ctrl = device_tab_ctrl
    edit_nfet_a(ctrl)
    store.touch_device(store.find_device("nfet_a")["id"], actor="bob")
    dialogs.answer_conflict(CANCEL)

    assert ctrl.device_table.save_all() is False

    assert screen_description(ctrl, 0) == EDITED
    assert ctrl.device_table.is_dirty()
    assert save_complete(dialogs) == []
    assert len(store.calls_of("upsert_devices")) == 1
    assert store.find_device("nfet_a")["description"] == ""


def test_reloading_on_a_stale_save_returns_false(device_tab_ctrl, store, dialogs):
    ctrl = device_tab_ctrl
    edit_nfet_a(ctrl)
    store.touch_device(store.find_device("nfet_a")["id"], actor="bob", description="bob's")
    dialogs.answer_conflict(RELOAD)

    assert ctrl.device_table.save_all() is False

    assert screen_description(ctrl, 0) == "bob's"
    assert not ctrl.device_table.is_dirty()
    assert save_complete(dialogs) == []
    assert len(store.calls_of("upsert_devices")) == 1


def test_cancelling_after_another_user_deleted_the_device_returns_false(
    device_tab_ctrl, store, dialogs
):
    ctrl = device_tab_ctrl
    edit_nfet_a(ctrl)
    store.remove_device(store.find_device("nfet_a")["id"])
    dialogs.answer_conflict(CANCEL)

    assert ctrl.device_table.save_all() is False

    assert screen_description(ctrl, 0) == EDITED
    assert ctrl.device_table.is_dirty()
    assert save_complete(dialogs) == []


def test_saving_before_connecting_returns_false(device_tab_ctrl, store, dialogs):
    ctrl = device_tab_ctrl
    ctrl.device_table.repo = None
    before = len(store.calls)

    assert ctrl.device_table.save_all() is False

    assert store.calls[before:] == []
    assert save_complete(dialogs) == []


def test_an_unexpected_error_propagates(device_tab_ctrl, store, dialogs):
    ctrl = device_tab_ctrl
    edit_nfet_a(ctrl)
    store.fail_next("upsert_devices", RuntimeError("boom"))

    with pytest.raises(RuntimeError, match="boom"):
        ctrl.device_table.save_all()

    assert screen_description(ctrl, 0) == EDITED
    assert ctrl.device_table.is_dirty()
    assert save_complete(dialogs) == []
