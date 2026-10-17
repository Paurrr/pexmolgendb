"""ParameterTabController.save_all 의 반환 계약 (phase 3 step 1).

True 는 "저장했다(덮어쓰기 포함) 또는 dirty 탭이 없었다", False 는 "사용자가 저장하지 않기로
했다(충돌 대화상자의 취소·다시 읽기) 또는 접속 전" 이다. 예상 밖 예외는 그대로 올라간다.
호출부(save_db, device 전환, Ctrl+S)가 이 값을 보고 넘어갈지·"Saved" 를 띄울지 정한다(step 2·3·5).
"""

import pytest
from gui_support.helpers import edit_tab_cell, select_device_row, select_process

from genviewer.dialogs.conflict import CANCEL, OVERWRITE, RELOAD

TAB = "InstTerm"
TABLE = "inst_terms"
COLUMN = "cds_inst_term_name"
SEED = "d"  # 시드에서 nfet_a 의 InstTerm 0행(DRN) 값
EDITED = "dd"


def saved(dialogs) -> list[tuple[str, str, str]]:
    return [shown for shown in dialogs.shown if shown[1] == "Saved"]


def tab_value(ctrl) -> str:
    return ctrl.parameter_tab.section(TAB).model.get_data()[0][COLUMN]


def stored_value(store) -> str:
    return store.rows(TABLE, store.find_device("nfet_a")["id"])[0][COLUMN]


def screen_version(ctrl) -> int:
    return ctrl.device_table.ui.model_safe().get_device(0)["version"]


def open_nfet_a(ctrl, store, qtbot) -> None:
    """sf2p 의 nfet_a(0행)를 골라 탭을 읽는다."""
    select_process(ctrl, "sf2p")
    select_device_row(ctrl, 0)
    nfet_a = store.find_device("nfet_a")["id"]
    qtbot.waitUntil(lambda: ctrl.parameter_tab.section(TAB).device_id == nfet_a)
    qtbot.waitUntil(lambda: len(ctrl.parameter_tab.section(TAB).model.get_data()) == 4)
    assert ctrl.parameter_tab.current_device_id == nfet_a


def edit_nfet_a_tab(ctrl, store, qtbot) -> None:
    """nfet_a 의 InstTerm 0행 값을 고친다."""
    open_nfet_a(ctrl, store, qtbot)
    edit_tab_cell(ctrl, TAB, 0, COLUMN, EDITED)
    assert ctrl.parameter_tab.is_dirty()


def test_saving_without_dirty_tabs_returns_true_without_writing(
    device_tab_ctrl, store, dialogs, qtbot
):
    ctrl = device_tab_ctrl
    open_nfet_a(ctrl, store, qtbot)
    shown = list(dialogs.shown)

    assert ctrl.parameter_tab.save_all() is True

    assert store.calls_of("replace_many_for_device") == []
    assert dialogs.shown == shown


def test_a_successful_save_returns_true(device_tab_ctrl, store, dialogs, qtbot):
    ctrl = device_tab_ctrl
    edit_nfet_a_tab(ctrl, store, qtbot)
    nfet_a = store.find_device("nfet_a")["id"]
    version = screen_version(ctrl)
    versions = []
    ctrl.parameter_tab.deviceVersionChanged.connect(lambda *args: versions.append(args))

    assert ctrl.parameter_tab.save_all() is True

    calls = store.calls_of("replace_many_for_device")
    assert [(c["device_id"], c["expected_version"], c["force"]) for c in calls] == [
        (nfet_a, version, False)
    ]
    new_version = store.find_device("nfet_a")["version"]
    assert new_version == version + 1
    assert stored_value(store) == EDITED
    assert not ctrl.parameter_tab.is_dirty()
    assert ctrl.parameter_tab.current_version == new_version
    assert versions == [(nfet_a, new_version)]
    assert len(saved(dialogs)) == 1


def test_overwriting_a_stale_save_returns_true(device_tab_ctrl, store, dialogs, qtbot):
    ctrl = device_tab_ctrl
    edit_nfet_a_tab(ctrl, store, qtbot)
    store.touch_device(store.find_device("nfet_a")["id"], actor="bob")
    dialogs.answer_conflict(OVERWRITE)

    assert ctrl.parameter_tab.save_all() is True

    calls = store.calls_of("replace_many_for_device")
    assert [c["force"] for c in calls] == [False, True]
    assert stored_value(store) == EDITED
    assert not ctrl.parameter_tab.is_dirty()
    assert [shown[0] for shown in dialogs.shown].count("conflict") == 1
    assert len(saved(dialogs)) == 1


def test_cancelling_a_stale_save_returns_false(device_tab_ctrl, store, dialogs, qtbot):
    ctrl = device_tab_ctrl
    edit_nfet_a_tab(ctrl, store, qtbot)
    store.touch_device(store.find_device("nfet_a")["id"], actor="bob")
    dialogs.answer_conflict(CANCEL)

    assert ctrl.parameter_tab.save_all() is False

    assert tab_value(ctrl) == EDITED
    assert ctrl.parameter_tab.is_dirty()
    assert saved(dialogs) == []
    assert len(store.calls_of("replace_many_for_device")) == 1
    assert stored_value(store) == SEED


def test_reloading_on_a_stale_save_returns_false(device_tab_ctrl, store, dialogs, qtbot):
    ctrl = device_tab_ctrl
    edit_nfet_a_tab(ctrl, store, qtbot)
    store.touch_device(store.find_device("nfet_a")["id"], actor="bob")
    dialogs.answer_conflict(RELOAD)

    assert ctrl.parameter_tab.save_all() is False

    assert tab_value(ctrl) == SEED
    assert not ctrl.parameter_tab.is_dirty()
    assert saved(dialogs) == []
    assert len(store.calls_of("replace_many_for_device")) == 1


def test_saving_before_connecting_returns_false(device_tab_ctrl, store, dialogs, qtbot):
    ctrl = device_tab_ctrl
    edit_nfet_a_tab(ctrl, store, qtbot)
    ctrl.parameter_tab.repo = None
    before = len(store.calls)

    assert ctrl.parameter_tab.save_all() is False

    assert store.calls[before:] == []
    assert tab_value(ctrl) == EDITED
    assert ctrl.parameter_tab.is_dirty()
    assert saved(dialogs) == []


def test_an_unexpected_error_propagates(device_tab_ctrl, store, dialogs, qtbot):
    ctrl = device_tab_ctrl
    edit_nfet_a_tab(ctrl, store, qtbot)
    store.fail_next("replace_many_for_device", RuntimeError("boom"))

    with pytest.raises(RuntimeError, match="boom"):
        ctrl.parameter_tab.save_all()

    assert tab_value(ctrl) == EDITED
    assert ctrl.parameter_tab.is_dirty()
    assert saved(dialogs) == []
    assert stored_value(store) == SEED
