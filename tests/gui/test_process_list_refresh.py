"""process 목록을 다시 채울 때와 process 를 지울 때의 콤보 (phase 3 step 4).

목록을 다시 채우면(CSV 불러오기, Add Process, 재접속) 지금 고른 process 를 그대로 둔다.
예전에는 `clear()` 가 "" 로, `addItems` 가 첫 process 로 두 번 바꾸면서 dirty 검사 없이 편집을
버렸다(UI_GUIDE 원칙 2). 지금 process 가 목록에 없을 때만(처음 접속, 지운 process) 첫 process 로
한 번 바뀐다. 지운 process 는 목록에서 사라진다. 남아 있으면 다시 고를 때
`get_or_create_id` 가 빈 process 를 새로 만든다.
"""

from gui_support.helpers import edit_device_cell, edit_tab_cell, select_device_row, select_process

TAB = "InstTerm"
COLUMN = "cds_inst_term_name"
EDITED_TAB = "pdd"  # 시드 pfet_a 의 InstTerm 0행 값은 "pd"
EDITED_DESCRIPTION = "edited by tester"
CSV_TEXT = (
    "CellType,CdsLibName,InstCellName,InstTerm\n"
    "PFET,sf9x,pfet_z,DRN d\n"
    "NFET,sf2p,nfet_c,DRN d\n"
)


def combo(ctrl):
    return ctrl.device_tab_toolbar.ui.process_selector


def combo_items(ctrl) -> list[str]:
    box = combo(ctrl)
    return [box.itemText(i) for i in range(box.count())]


def process_id(store, name: str) -> int:
    (found,) = [pid for pid, process in store.processes.items() if process == name]
    return found


def created_since(store, since: int) -> list[str]:
    """since 이후 get_or_create_id 에 넘어간 이름."""
    return [args["name"] for name, args in store.calls[since:] if name == "get_or_create_id"]


def record_process_changes(ctrl) -> list[tuple[str, str]]:
    changes: list[tuple[str, str]] = []
    ctrl.device_tab_toolbar.processChanged.connect(
        lambda name, release: changes.append((name, release))
    )
    return changes


def open_sf4u(ctrl, qtbot) -> None:
    select_process(ctrl, "sf4u")
    qtbot.waitUntil(lambda: ctrl.device_table.current_process == "sf4u")
    qtbot.waitUntil(lambda: ctrl.device_table.ui.model_safe().rowCount() == 1)


def edit_pfet_a_tab(ctrl, store, qtbot) -> None:
    """sf4u 의 pfet_a 를 골라 InstTerm 0행 값을 고친다."""
    open_sf4u(ctrl, qtbot)
    select_device_row(ctrl, 0)
    pfet_a = store.find_device("pfet_a")["id"]
    qtbot.waitUntil(lambda: ctrl.parameter_tab.section(TAB).device_id == pfet_a)
    qtbot.waitUntil(lambda: len(ctrl.parameter_tab.section(TAB).model.get_data()) == 2)
    edit_tab_cell(ctrl, TAB, 0, COLUMN, EDITED_TAB)
    assert ctrl.parameter_tab.is_dirty()


def test_loading_a_csv_keeps_the_current_process_and_its_tab_edits(
    device_tab_ctrl, store, dialogs, qtbot, tmp_path
):
    ctrl = device_tab_ctrl
    edit_pfet_a_tab(ctrl, store, qtbot)
    path = tmp_path / "in.csv"
    path.write_text(CSV_TEXT, encoding="utf-8", newline="")
    since = len(store.calls)

    ctrl.on_load_csv_requested(str(path))

    qtbot.waitUntil(lambda: any(shown[1] == "Load CSV" for shown in dialogs.shown))
    assert "sf9x" in combo_items(ctrl)
    assert combo(ctrl).currentText() == "sf4u"
    assert ctrl.device_table.current_process == "sf4u"
    assert ctrl.device_table.current_process_id == process_id(store, "sf4u")
    # device 편집은 단언하지 않는다. on_load_csv_requested 가 끝에서 refresh_devices 로 다시 읽는다.
    assert ctrl.parameter_tab.is_dirty()
    assert ctrl.parameter_tab.section(TAB).model.get_data()[0][COLUMN] == EDITED_TAB
    assert created_since(store, since) == []


def test_adding_a_process_asks_to_save_the_current_process_edits(
    device_tab_ctrl, store, dialogs, qtbot
):
    ctrl = device_tab_ctrl
    open_sf4u(ctrl, qtbot)
    edit_device_cell(ctrl, 0, "description", EDITED_DESCRIPTION)
    assert ctrl.device_table.is_dirty()
    dialogs.answer_question(True)

    ctrl.device_tab_toolbar.add_process("new_p")

    qtbot.waitUntil(lambda: len(store.calls_of("upsert_devices")) == 1)
    (call,) = store.calls_of("upsert_devices")
    assert call["process_id"] == process_id(store, "sf4u")
    assert [d["description"] for d in call["devices"]] == [EDITED_DESCRIPTION]
    assert store.find_device("pfet_a")["description"] == EDITED_DESCRIPTION
    assert ("question", "Save Changes", "You have unsaved changes. Do you want to save them?") in (
        dialogs.shown
    )
    qtbot.waitUntil(lambda: ctrl.device_table.current_process == "new_p")
    assert combo(ctrl).currentText() == "new_p"
    assert ctrl.device_table.current_process_id == process_id(store, "new_p")


def test_reconnecting_keeps_the_current_process(device_tab_ctrl, store, qtbot):
    ctrl = device_tab_ctrl
    open_sf4u(ctrl, qtbot)
    since = len(store.calls)

    assert ctrl.connect_db("") is True

    qtbot.waitUntil(lambda: "list_pairs" in [name for name, _ in store.calls[since:]])
    assert combo(ctrl).currentText() == "sf4u"
    assert ctrl.device_table.current_process == "sf4u"
    assert ctrl.device_table.current_process_id == process_id(store, "sf4u")
    assert created_since(store, since) == []


def test_first_connect_selects_the_first_process_once(device_tab_ctrl, store):
    ctrl = device_tab_ctrl

    assert combo(ctrl).currentText() == "sf2p"
    assert ctrl.device_table.current_process == "sf2p"
    assert created_since(store, 0) == ["sf2p"]


def test_when_another_user_deletes_the_current_process_the_first_one_is_selected_once(
    device_tab_ctrl, store, qtbot
):
    ctrl = device_tab_ctrl
    open_sf4u(ctrl, qtbot)
    ctrl.device_tab_toolbar.repo.delete("sf4u", actor="bob")
    changes = record_process_changes(ctrl)
    since = len(store.calls)

    ctrl.device_tab_toolbar.refresh_processes()

    qtbot.waitUntil(lambda: ctrl.device_table.current_process == "sf2p")
    assert combo_items(ctrl) == ["sf2p"]
    assert combo(ctrl).currentText() == "sf2p"
    assert changes == [("sf2p", "")]
    assert created_since(store, since) == ["sf2p"]


def test_removing_a_process_drops_it_from_the_list(device_tab_ctrl, store, dialogs, qtbot):
    ctrl = device_tab_ctrl
    open_sf4u(ctrl, qtbot)
    dialogs.answer_question(True)

    ctrl.device_tab_toolbar.remove_process("sf4u")

    qtbot.waitUntil(lambda: len(store.calls_of("delete")) == 1)
    assert ("info", "Removed", "Process 'sf4u' removed.") in dialogs.shown
    assert combo(ctrl).findText("sf4u") == -1
    assert combo(ctrl).currentText() == "sf2p"
    assert ctrl.device_table.current_process == "sf2p"


def test_a_removed_process_is_not_recreated_by_selecting_again(
    device_tab_ctrl, store, dialogs, qtbot
):
    ctrl = device_tab_ctrl
    open_sf4u(ctrl, qtbot)
    dialogs.answer_question(True)
    ctrl.device_tab_toolbar.remove_process("sf4u")
    qtbot.waitUntil(lambda: len(store.calls_of("delete")) == 1)
    since = len(store.calls)

    combo(ctrl).setCurrentText("sf2p")
    combo(ctrl).setCurrentText("sf4u")

    assert "sf4u" not in created_since(store, since)
    assert "sf4u" not in ctrl.device_tab_toolbar.repo.list_all()


def test_select_process_silently_changes_only_the_combo(device_tab_ctrl, store, qtbot):
    ctrl = device_tab_ctrl
    changes = record_process_changes(ctrl)
    since = len(store.calls)

    ctrl.device_tab_toolbar.select_process_silently("sf4u")

    qtbot.waitUntil(lambda: combo(ctrl).currentText() == "sf4u")
    assert changes == []
    assert created_since(store, since) == []
    assert ctrl.device_table.current_process == "sf2p"
    assert ctrl.device_table.current_process_id == process_id(store, "sf2p")


def test_select_process_silently_ignores_an_unknown_name(device_tab_ctrl, store):
    ctrl = device_tab_ctrl
    changes = record_process_changes(ctrl)

    ctrl.device_tab_toolbar.select_process_silently("nope")

    assert combo(ctrl).currentText() == "sf2p"
    assert combo_items(ctrl) == ["sf2p", "sf4u"]
    assert changes == []
