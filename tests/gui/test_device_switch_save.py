"""device 를 바꿀 때 묻는 "Save Changes?" 뒤의 탭 저장 (phase 3 step 3).

예로 답했는데 탭 저장이 충돌 대화상자의 취소로 끝나면 탭을 새 device 로 바꾸지 않고 이전
device 의 편집을 그대로 둔다(UI_GUIDE 원칙 2, 취소 툴팁 "편집 내용은 그대로 남는다").
다시 읽기는 편집이 이미 버려졌으므로 아니오처럼 새 device 로 넘어간다.
멈춰도 표의 선택은 새 행에 있다(이전 행을 코드로 다시 고르지 않는다). 다음에 다른 행을 누르면
다시 묻고, 그때 저장은 탭이 들고 있는 이전 device 로 간다.
"""

from gui_support.helpers import edit_tab_cell, select_device_row, select_process

from genviewer.dialogs.conflict import CANCEL, OVERWRITE, RELOAD

TAB = "InstTerm"
TABLE = "inst_terms"
COLUMN = "cds_inst_term_name"
SEED = "d"  # 시드에서 nfet_a 의 InstTerm 0행(DRN) 값
NFET_B_SEED = "d2"  # 시드에서 nfet_b 의 InstTerm 0행 값
EDITED = "dd"
SAVE_CHANGES = (
    "question",
    "Save Changes",
    "You have unsaved changes. Do you want to save them?",
)


def device_id(store, name: str) -> int:
    return store.find_device(name)["id"]


def saved(dialogs) -> list[tuple[str, str, str]]:
    return [shown for shown in dialogs.shown if shown[1] == "Saved"]


def tab_value(ctrl) -> str:
    return ctrl.parameter_tab.section(TAB).model.get_data()[0][COLUMN]


def tab_text(ctrl) -> str:
    ui = ctrl.parameter_tab.ui
    return ui.tabText(ui.find_tab(TAB))


def stored_value(store, name: str = "nfet_a") -> str:
    return store.rows(TABLE, device_id(store, name))[0][COLUMN]


def fetched_ids(store, since: int = 0) -> list[int]:
    return [c["device_id"] for c in store.calls_of("fetch_by_device")[since:]]


def tab_saves(store) -> list[dict]:
    return store.calls_of("replace_many_for_device")


def edit_nfet_a_tab(ctrl, store, qtbot) -> None:
    """sf2p 의 nfet_a(0행)를 골라 InstTerm 0행 값을 고친다."""
    select_process(ctrl, "sf2p")
    select_device_row(ctrl, 0)
    nfet_a = device_id(store, "nfet_a")
    qtbot.waitUntil(lambda: ctrl.parameter_tab.section(TAB).device_id == nfet_a)
    qtbot.waitUntil(lambda: len(ctrl.parameter_tab.section(TAB).model.get_data()) == 4)
    edit_tab_cell(ctrl, TAB, 0, COLUMN, EDITED)
    assert ctrl.parameter_tab.is_dirty()
    assert tab_text(ctrl) == f"{TAB} *"


def bob_saves_nfet_a(store) -> None:
    store.touch_device(device_id(store, "nfet_a"), actor="bob")


def click_nfet_b(ctrl) -> None:
    select_device_row(ctrl, 1)
    assert ctrl.device_table.last_selected_device()["name"] == "nfet_b"


def assert_on_nfet_b(ctrl, store) -> None:
    nfet_b = device_id(store, "nfet_b")
    assert ctrl.parameter_tab.current_device_id == nfet_b
    assert ctrl.parameter_tab.section(TAB).device_id == nfet_b
    assert not ctrl.parameter_tab.is_dirty()
    assert tab_value(ctrl) == NFET_B_SEED
    assert tab_text(ctrl) == TAB


def assert_still_on_edited_nfet_a(ctrl, store) -> None:
    nfet_a = device_id(store, "nfet_a")
    assert ctrl.parameter_tab.current_device_id == nfet_a
    assert ctrl.parameter_tab.section(TAB).device_id == nfet_a
    assert ctrl.parameter_tab.is_dirty()
    assert tab_value(ctrl) == EDITED
    assert tab_text(ctrl) == f"{TAB} *"
    # 표의 선택은 누른 행에 그대로 있다.
    assert ctrl.device_table.last_selected_device()["name"] == "nfet_b"


def test_cancelling_a_tab_conflict_keeps_the_previous_device_and_its_edits(
    device_tab_ctrl, store, dialogs, qtbot
):
    ctrl = device_tab_ctrl
    edit_nfet_a_tab(ctrl, store, qtbot)
    bob_saves_nfet_a(store)
    fetched = len(store.calls_of("fetch_by_device"))
    dialogs.answer_question(True)
    dialogs.answer_conflict(CANCEL)

    click_nfet_b(ctrl)

    qtbot.waitUntil(lambda: len(tab_saves(store)) == 1)
    assert SAVE_CHANGES in dialogs.shown
    assert_still_on_edited_nfet_a(ctrl, store)
    assert fetched_ids(store, fetched) == []
    assert device_id(store, "nfet_b") not in fetched_ids(store)
    assert stored_value(store) == SEED
    assert saved(dialogs) == []


def test_after_cancelling_the_next_switch_asks_again_and_saves_the_tabs_device(
    device_tab_ctrl, store, dialogs, qtbot
):
    ctrl = device_tab_ctrl
    edit_nfet_a_tab(ctrl, store, qtbot)
    bob_saves_nfet_a(store)
    dialogs.answer_question(True)
    dialogs.answer_conflict(CANCEL)
    click_nfet_b(ctrl)
    qtbot.waitUntil(lambda: len(tab_saves(store)) == 1)
    dialogs.answer_question(True)
    dialogs.answer_conflict(OVERWRITE)

    select_device_row(ctrl, 0)

    qtbot.waitUntil(lambda: len(tab_saves(store)) == 3)
    nfet_a = device_id(store, "nfet_a")
    assert [(c["device_id"], c["force"]) for c in tab_saves(store)] == [
        (nfet_a, False),
        (nfet_a, False),
        (nfet_a, True),
    ]
    assert dialogs.shown.count(SAVE_CHANGES) == 2
    assert stored_value(store) == EDITED
    assert ctrl.parameter_tab.current_device_id == nfet_a
    assert not ctrl.parameter_tab.is_dirty()
    assert tab_value(ctrl) == EDITED
    assert len(saved(dialogs)) == 1


def test_reloading_on_a_tab_conflict_moves_to_the_new_device(
    device_tab_ctrl, store, dialogs, qtbot
):
    ctrl = device_tab_ctrl
    edit_nfet_a_tab(ctrl, store, qtbot)
    bob_saves_nfet_a(store)
    dialogs.answer_question(True)
    dialogs.answer_conflict(RELOAD)

    click_nfet_b(ctrl)

    nfet_b = device_id(store, "nfet_b")
    qtbot.waitUntil(lambda: ctrl.parameter_tab.current_device_id == nfet_b)
    assert_on_nfet_b(ctrl, store)
    assert len(tab_saves(store)) == 1
    assert stored_value(store) == SEED
    # nfet_a 의 편집은 다시 읽기로 이미 서버 내용이 됐다.
    cached = ctrl.parameter_tab.section(TAB).model_by_device[device_id(store, "nfet_a")]
    assert cached.get_data()[0][COLUMN] == SEED
    assert saved(dialogs) == []


def test_overwriting_a_tab_conflict_moves_to_the_new_device(
    device_tab_ctrl, store, dialogs, qtbot
):
    ctrl = device_tab_ctrl
    edit_nfet_a_tab(ctrl, store, qtbot)
    bob_saves_nfet_a(store)
    dialogs.answer_question(True)
    dialogs.answer_conflict(OVERWRITE)

    click_nfet_b(ctrl)

    qtbot.waitUntil(lambda: len(tab_saves(store)) == 2)
    nfet_a = device_id(store, "nfet_a")
    assert [(c["device_id"], c["force"]) for c in tab_saves(store)] == [
        (nfet_a, False),
        (nfet_a, True),
    ]
    assert_on_nfet_b(ctrl, store)
    assert stored_value(store) == EDITED
    assert len(saved(dialogs)) == 1


def test_saving_without_a_conflict_moves_to_the_new_device(
    device_tab_ctrl, store, dialogs, qtbot
):
    ctrl = device_tab_ctrl
    edit_nfet_a_tab(ctrl, store, qtbot)
    version = ctrl.parameter_tab.current_version
    dialogs.answer_question(True)

    click_nfet_b(ctrl)

    qtbot.waitUntil(lambda: len(tab_saves(store)) == 1)
    nfet_a = device_id(store, "nfet_a")
    assert [(c["device_id"], c["expected_version"], c["force"]) for c in tab_saves(store)] == [
        (nfet_a, version, False)
    ]
    assert_on_nfet_b(ctrl, store)
    assert stored_value(store) == EDITED
    assert len(saved(dialogs)) == 1
    assert [shown[0] for shown in dialogs.shown].count("conflict") == 0


def test_answering_no_discards_the_edits_and_moves_to_the_new_device(
    device_tab_ctrl, store, dialogs, qtbot
):
    ctrl = device_tab_ctrl
    edit_nfet_a_tab(ctrl, store, qtbot)
    dialogs.answer_question(False)

    click_nfet_b(ctrl)

    nfet_b = device_id(store, "nfet_b")
    qtbot.waitUntil(lambda: ctrl.parameter_tab.current_device_id == nfet_b)
    assert SAVE_CHANGES in dialogs.shown
    assert_on_nfet_b(ctrl, store)
    assert tab_saves(store) == []
    assert stored_value(store) == SEED
    cached = ctrl.parameter_tab.section(TAB).model_by_device[device_id(store, "nfet_a")]
    assert cached.get_data()[0][COLUMN] == SEED
    assert saved(dialogs) == []


def test_a_tab_save_error_keeps_the_previous_device_and_its_edits(
    device_tab_ctrl, store, dialogs, qtbot
):
    ctrl = device_tab_ctrl
    edit_nfet_a_tab(ctrl, store, qtbot)
    store.fail_next("replace_many_for_device", RuntimeError("boom"))
    fetched = len(store.calls_of("fetch_by_device"))
    dialogs.answer_question(True)

    click_nfet_b(ctrl)

    qtbot.waitUntil(lambda: len(tab_saves(store)) == 1)
    errors = [shown for shown in dialogs.shown if shown[:2] == ("error", "Load Failed")]
    assert len(errors) == 1
    assert_still_on_edited_nfet_a(ctrl, store)
    assert fetched_ids(store, fetched) == []
    assert stored_value(store) == SEED
    assert saved(dialogs) == []
