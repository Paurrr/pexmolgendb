"""process 를 바꿀 때 묻는 "Save Changes?" 와 그 뒤의 저장 (phase 3 step 5).

device 표뿐 아니라 저장하지 않은 탭 편집도 묻는다. 예로 답하면 dirty 인 쪽만 저장한다(device 먼저,
탭 다음). 저장이 충돌 대화상자의 취소나 예외로 끝나 편집이 남아 있으면 넘어가지 않고 콤보를
이전 process 로 되돌린다(UI_GUIDE 원칙 2·4, 취소 툴팁 "편집 내용은 그대로 남는다"). 되돌릴 때는
processChanged 를 다시 내지 않는다. 다시 읽기는 편집이 이미 서버 내용이 됐으므로 넘어간다.

같은 device 의 행과 탭을 함께 고친 저장은 아직 나 자신과 충돌한다(step 6). 그래서 둘을 같은
device 에서 함께 고치지 않는다.
"""

from gui_support.helpers import edit_device_cell, edit_tab_cell, select_device_row, select_process

from genviewer.dialogs.conflict import CANCEL, RELOAD

TAB = "InstTerm"
TABLE = "inst_terms"
COLUMN = "cds_inst_term_name"
SEED_TAB = "d"  # 시드에서 nfet_a 의 InstTerm 0행(DRN) 값
EDITED_TAB = "dd"
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


def device_id(store, name: str) -> int:
    return store.find_device(name)["id"]


def record_process_changes(ctrl) -> list[str]:
    changes: list[str] = []
    ctrl.device_tab_toolbar.processChanged.connect(changes.append)
    return changes


def call_names(store, since: int = 0) -> list[str]:
    return [name for name, _args in store.calls[since:]]


def created_since(store, since: int) -> list[str]:
    """since 이후 get_or_create_id 에 넘어간 이름."""
    return [args["name"] for name, args in store.calls[since:] if name == "get_or_create_id"]


def errors(dialogs) -> list[str]:
    return [title for kind, title, _text in dialogs.shown if kind == "error"]


def tab_value(ctrl) -> str:
    return ctrl.parameter_tab.section(TAB).model.get_data()[0][COLUMN]


def tab_text(ctrl) -> str:
    ui = ctrl.parameter_tab.ui
    return ui.tabText(ui.find_tab(TAB))


def screen_description(ctrl, name: str) -> str:
    (found,) = [
        d["description"]
        for d in ctrl.device_table.ui.model_safe().get_devices()
        if d["name"] == name
    ]
    return found


def edit_nfet_a_tab(ctrl, store, qtbot) -> None:
    """sf2p 의 nfet_a(0행)를 골라 InstTerm 0행 값을 고친다. device 행은 그대로다."""
    select_device_row(ctrl, 0)
    nfet_a = device_id(store, "nfet_a")
    qtbot.waitUntil(lambda: ctrl.parameter_tab.section(TAB).device_id == nfet_a)
    qtbot.waitUntil(lambda: len(ctrl.parameter_tab.section(TAB).model.get_data()) == 4)
    edit_tab_cell(ctrl, TAB, 0, COLUMN, EDITED_TAB)
    assert ctrl.parameter_tab.is_dirty()
    assert not ctrl.device_table.is_dirty()


def edit_description(ctrl, row: int, name: str) -> None:
    """sf2p 의 row 행(name) Description 을 고친다. 탭은 그대로다."""
    assert ctrl.device_table.ui.model_safe().get_device(row)["name"] == name
    edit_device_cell(ctrl, row, "description", EDITED_DESCRIPTION)
    assert ctrl.device_table.is_dirty()


def bob_saves_nfet_a(store) -> None:
    store.touch_device(device_id(store, "nfet_a"), actor="bob")


def assert_moved_to_sf4u(ctrl, qtbot) -> None:
    qtbot.waitUntil(lambda: ctrl.device_table.current_process == "sf4u")
    assert combo(ctrl).currentText() == "sf4u"
    assert ctrl.device_table.ui.model_safe().get_devices()[0]["name"] == "pfet_a"


def assert_stayed_on_sf2p(ctrl, store, changes: list[str], since: int) -> None:
    """콤보·device 표가 sf2p 그대로이고, sf2p 를 다시 읽거나 새 process 를 찾지 않았다."""
    assert combo(ctrl).currentText() == "sf2p"
    assert ctrl.device_table.current_process == "sf2p"
    assert ctrl.device_table.current_process_id == store.find_device("nfet_a")["process_id"]
    # 되돌리는 동안 새 신호가 없다(select_process_silently).
    assert changes == ["sf4u"]
    assert created_since(store, since) == []
    assert "fetch_devices_by_process" not in call_names(store, since)


def assert_tab_edit_kept(ctrl, store) -> None:
    nfet_a = device_id(store, "nfet_a")
    assert ctrl.parameter_tab.current_device_id == nfet_a
    assert ctrl.parameter_tab.section(TAB).device_id == nfet_a
    assert ctrl.parameter_tab.is_dirty()
    assert tab_value(ctrl) == EDITED_TAB
    assert tab_text(ctrl) == f"{TAB} *"


# -- 탭만 편집 ------------------------------------------------------------------


def test_tab_edits_are_asked_about_and_saved_before_changing_process(
    device_tab_ctrl, store, dialogs, qtbot
):
    ctrl = device_tab_ctrl
    edit_nfet_a_tab(ctrl, store, qtbot)
    dialogs.answer_question(True)

    select_process(ctrl, "sf4u")

    assert_moved_to_sf4u(ctrl, qtbot)
    assert dialogs.shown.count(SAVE_CHANGES) == 1
    assert [c["device_id"] for c in store.calls_of("replace_many_for_device")] == [
        device_id(store, "nfet_a")
    ]
    assert store.rows(TABLE, device_id(store, "nfet_a"))[0][COLUMN] == EDITED_TAB
    assert store.calls_of("upsert_devices") == []
    assert [shown[1] for shown in dialogs.shown if shown[0] == "info"] == ["Saved"]
    assert not ctrl.parameter_tab.is_dirty()


def test_answering_no_discards_tab_edits_and_changes_process(
    device_tab_ctrl, store, dialogs, qtbot
):
    ctrl = device_tab_ctrl
    edit_nfet_a_tab(ctrl, store, qtbot)
    dialogs.answer_question(False)

    select_process(ctrl, "sf4u")

    assert_moved_to_sf4u(ctrl, qtbot)
    assert SAVE_CHANGES in dialogs.shown
    assert store.calls_of("replace_many_for_device") == []
    assert store.calls_of("upsert_devices") == []
    assert store.rows(TABLE, device_id(store, "nfet_a"))[0][COLUMN] == SEED_TAB
    assert not ctrl.parameter_tab.is_dirty()


# -- 저장이 취소·실패하면 이전 process 에 머문다 -----------------------------------


def test_cancelling_a_device_conflict_keeps_the_previous_process_and_its_edits(
    device_tab_ctrl, store, dialogs, qtbot
):
    ctrl = device_tab_ctrl
    edit_description(ctrl, 0, "nfet_a")
    bob_saves_nfet_a(store)
    changes = record_process_changes(ctrl)
    since = len(store.calls)
    dialogs.answer_question(True)
    dialogs.answer_conflict(CANCEL)

    select_process(ctrl, "sf4u")

    qtbot.waitUntil(lambda: len(store.calls_of("upsert_devices")) == 1)
    assert_stayed_on_sf2p(ctrl, store, changes, since)
    assert ctrl.device_table.is_dirty()
    assert screen_description(ctrl, "nfet_a") == EDITED_DESCRIPTION
    assert store.find_device("nfet_a")["description"] != EDITED_DESCRIPTION
    assert dialogs.shown.count(SAVE_CHANGES) == 1
    assert errors(dialogs) == []


def test_cancelling_a_tab_conflict_keeps_the_previous_process_and_its_tab_edits(
    device_tab_ctrl, store, dialogs, qtbot
):
    ctrl = device_tab_ctrl
    edit_nfet_a_tab(ctrl, store, qtbot)
    bob_saves_nfet_a(store)
    changes = record_process_changes(ctrl)
    since = len(store.calls)
    dialogs.answer_question(True)
    dialogs.answer_conflict(CANCEL)

    select_process(ctrl, "sf4u")

    qtbot.waitUntil(lambda: len(store.calls_of("replace_many_for_device")) == 1)
    assert_stayed_on_sf2p(ctrl, store, changes, since)
    assert_tab_edit_kept(ctrl, store)
    assert "fetch_by_device" not in call_names(store, since)
    # device 는 dirty 가 아니라 저장하지 않는다.
    assert store.calls_of("upsert_devices") == []
    assert store.rows(TABLE, device_id(store, "nfet_a"))[0][COLUMN] == SEED_TAB
    assert dialogs.shown.count(SAVE_CHANGES) == 1
    assert errors(dialogs) == []


def test_a_device_save_error_keeps_the_previous_process_and_its_edits(
    device_tab_ctrl, store, dialogs, qtbot
):
    ctrl = device_tab_ctrl
    edit_description(ctrl, 0, "nfet_a")
    store.fail_next("upsert_devices", RuntimeError("boom"))
    changes = record_process_changes(ctrl)
    since = len(store.calls)
    dialogs.answer_question(True)

    select_process(ctrl, "sf4u")

    qtbot.waitUntil(lambda: len(store.calls_of("upsert_devices")) == 1)
    assert errors(dialogs) == ["Save Devices Failed"]
    assert_stayed_on_sf2p(ctrl, store, changes, since)
    assert ctrl.device_table.is_dirty()
    assert screen_description(ctrl, "nfet_a") == EDITED_DESCRIPTION


def test_a_tab_save_error_keeps_the_previous_process_and_its_tab_edits(
    device_tab_ctrl, store, dialogs, qtbot
):
    ctrl = device_tab_ctrl
    edit_nfet_a_tab(ctrl, store, qtbot)
    store.fail_next("replace_many_for_device", RuntimeError("boom"))
    changes = record_process_changes(ctrl)
    since = len(store.calls)
    dialogs.answer_question(True)

    select_process(ctrl, "sf4u")

    qtbot.waitUntil(lambda: len(store.calls_of("replace_many_for_device")) == 1)
    assert errors(dialogs) == ["Save Tabs Failed"]
    assert_stayed_on_sf2p(ctrl, store, changes, since)
    assert_tab_edit_kept(ctrl, store)
    assert store.rows(TABLE, device_id(store, "nfet_a"))[0][COLUMN] == SEED_TAB


def test_reloading_on_a_device_conflict_changes_process(
    device_tab_ctrl, store, dialogs, qtbot
):
    ctrl = device_tab_ctrl
    edit_description(ctrl, 0, "nfet_a")
    bob_saves_nfet_a(store)
    dialogs.answer_question(True)
    dialogs.answer_conflict(RELOAD)

    select_process(ctrl, "sf4u")

    assert_moved_to_sf4u(ctrl, qtbot)
    assert len(store.calls_of("upsert_devices")) == 1
    assert store.find_device("nfet_a")["description"] != EDITED_DESCRIPTION
    assert not ctrl.device_table.is_dirty()
    assert errors(dialogs) == []


def test_reloading_on_a_tab_conflict_changes_process(device_tab_ctrl, store, dialogs, qtbot):
    ctrl = device_tab_ctrl
    edit_nfet_a_tab(ctrl, store, qtbot)
    bob_saves_nfet_a(store)
    dialogs.answer_question(True)
    dialogs.answer_conflict(RELOAD)

    select_process(ctrl, "sf4u")

    assert_moved_to_sf4u(ctrl, qtbot)
    assert len(store.calls_of("replace_many_for_device")) == 1
    assert store.rows(TABLE, device_id(store, "nfet_a"))[0][COLUMN] == SEED_TAB
    assert not ctrl.parameter_tab.is_dirty()
    assert errors(dialogs) == []


# -- 둘 다 편집 -------------------------------------------------------------------


def test_device_and_tab_edits_are_both_saved_before_changing_process(
    device_tab_ctrl, store, dialogs, qtbot
):
    ctrl = device_tab_ctrl
    edit_nfet_a_tab(ctrl, store, qtbot)
    edit_description(ctrl, 1, "nfet_b")
    dialogs.answer_question(True)

    select_process(ctrl, "sf4u")

    assert_moved_to_sf4u(ctrl, qtbot)
    assert dialogs.shown.count(SAVE_CHANGES) == 1
    saves = [
        name
        for name in call_names(store)
        if name in ("upsert_devices", "replace_many_for_device")
    ]
    assert saves == ["upsert_devices", "replace_many_for_device"]
    assert store.find_device("nfet_b")["description"] == EDITED_DESCRIPTION
    assert store.rows(TABLE, device_id(store, "nfet_a"))[0][COLUMN] == EDITED_TAB
    assert [shown[0] for shown in dialogs.shown].count("conflict") == 0
    assert errors(dialogs) == []


# -- Add Process ------------------------------------------------------------------


def test_adding_a_process_after_cancelling_a_tab_conflict_keeps_the_tab_edits(
    device_tab_ctrl, store, dialogs, qtbot
):
    ctrl = device_tab_ctrl
    edit_nfet_a_tab(ctrl, store, qtbot)
    bob_saves_nfet_a(store)
    changes = record_process_changes(ctrl)
    since = len(store.calls)
    dialogs.answer_question(True)
    dialogs.answer_conflict(CANCEL)

    ctrl.device_tab_toolbar.add_process("new_p")

    qtbot.waitUntil(lambda: len(store.calls_of("replace_many_for_device")) == 1)
    # process 는 만들어졌다. 고르지만 않았다.
    assert "new_p" in combo_items(ctrl)
    assert combo(ctrl).currentText() == "sf2p"
    assert ctrl.device_table.current_process == "sf2p"
    assert changes == ["new_p"]
    assert created_since(store, since) == []
    assert_tab_edit_kept(ctrl, store)
    assert dialogs.shown.count(SAVE_CHANGES) == 1
