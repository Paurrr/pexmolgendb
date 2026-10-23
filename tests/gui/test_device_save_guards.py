"""device 표에서 편집이 경고 없이 사라지는 두 경로 (phase 3 step 7).

G15a: save_all 은 CellType 이 delegate_config 목록에 없는 행을 저장하지 않는다(규칙은 그대로).
그 뒤의 다시 읽기가 그 행의 편집을 지우므로, 편집한 행이 있었으면 "Save Skipped" 경고로 이름을
알리고 False 를 돌려준다. 손대지 않은 목록 밖 행(CSV 로 들어온 옛 CellType)은 경고하지 않는다.

G15b: 붙여넣기는 바로 저장하고 목록을 다시 읽는다. device 표에 저장 안 한 편집이 있으면
붙여넣지 않고 "Unsaved Changes" 경고를 낸다.

K37 (phase 10 step 3, 승인): 붙여넣기는 탭을 붙여넣은 device 로 바꾼다. 탭에 저장 안 한 편집이
있으면 붙여넣지 않고 "Unsaved Changes"(탭 편집 본문) 경고를 낸다. device 편집 검사가 먼저다.

K38 (phase 10 step 2): 붙여넣은 device 의 탭 쓰기는 그 행의 device 저장이 돌려준 version 에
대고 쓴다(expected_version). 그 사이 남이 그 device 를 저장했으면 충돌로 묻는다.
"""

import pytest
from gui_support.helpers import edit_device_cell, edit_tab_cell, select_device_row, select_process

from genviewer.config.config import delegate_config
from genviewer.dialogs.conflict import CANCEL, RELOAD
from genviewer.service.errors import Conflict, StaleWriteError

EDITED = "edited by tester"
OFF_LIST = "nmos_rf"  # delegate_config 의 device.celltype.items 에 없다
TAB = "InstTerm"
COLUMN = "cds_inst_term_name"
ALL_SAVED = "All changes have been saved."


def record_notifications(ctrl) -> list[tuple[str, str, str]]:
    notes: list[tuple[str, str, str]] = []
    ctrl.notifyRequested.connect(lambda *args: notes.append(args))
    return notes


def titled(notes, title: str) -> list[tuple[str, str, str]]:
    return [n for n in notes if n[1] == title]


def model_of(ctrl):
    return ctrl.device_table.ui.model_safe()


def sent_names(store) -> list[list[str]]:
    return [[d["name"] for d in c["devices"]] for c in store.calls_of("upsert_devices")]


def open_sf2p(ctrl) -> None:
    select_process(ctrl, "sf2p")
    names = [d["name"] for d in model_of(ctrl).get_devices()]
    assert names == ["nfet_a", "nfet_b"]


def give_nfet_a_an_old_celltype(ctrl, store) -> None:
    """CSV 로 들어온 것처럼 nfet_a 의 CellType 이 DB 에서 이미 목록 밖이다(bob 의 저장)."""
    assert OFF_LIST not in delegate_config["device"]["celltype"]["items"]
    store.touch_device(store.find_device("nfet_a")["id"], actor="bob", celltype=OFF_LIST)
    ctrl.device_table.refresh_devices()
    assert model_of(ctrl).get_device(0)["celltype"] == OFF_LIST
    assert not ctrl.device_table.is_dirty()


# -- G15a: CellType 때문에 건너뛴 편집 --------------------------------------------


def test_an_edited_row_with_an_off_list_celltype_is_skipped_with_a_warning(
    device_tab_ctrl, store
):
    ctrl = device_tab_ctrl
    open_sf2p(ctrl)
    notes = record_notifications(ctrl)
    edit_device_cell(ctrl, 0, "celltype", OFF_LIST)
    edit_device_cell(ctrl, 1, "description", EDITED)

    assert ctrl.device_table.save_all() is False

    assert sent_names(store) == [["nfet_b"]]
    assert store.find_device("nfet_b")["description"] == EDITED
    assert store.find_device("nfet_a")["celltype"] == "NFET"
    assert titled(notes, "Save Complete") == [("info", "Save Complete", "1 updated.")]
    assert titled(notes, "Save Skipped") == [
        (
            "warn",
            "Save Skipped",
            "These devices were not saved because their CellType is not in the list "
            "(the edits were discarded on reload):\n - nfet_a",
        )
    ]
    # 건너뛴 행은 다시 읽으면서 DB 값으로 돌아갔다(경고가 그것을 알린다)
    assert model_of(ctrl).get_device(0)["celltype"] == "NFET"
    assert not ctrl.device_table.is_dirty()


def test_an_untouched_row_with_an_off_list_celltype_is_not_warned_about(device_tab_ctrl, store):
    ctrl = device_tab_ctrl
    open_sf2p(ctrl)
    give_nfet_a_an_old_celltype(ctrl, store)
    notes = record_notifications(ctrl)

    assert ctrl.device_table.save_all() is True

    assert titled(notes, "Save Skipped") == []
    assert titled(notes, "Save Complete") == [("info", "Save Complete", "No changes to save.")]


def test_editing_a_row_whose_celltype_came_off_list_from_the_db_is_warned_about(
    device_tab_ctrl, store
):
    ctrl = device_tab_ctrl
    open_sf2p(ctrl)
    give_nfet_a_an_old_celltype(ctrl, store)
    notes = record_notifications(ctrl)
    edit_device_cell(ctrl, 0, "description", EDITED)

    assert ctrl.device_table.save_all() is False

    assert sent_names(store) == [["nfet_b"]]
    assert store.find_device("nfet_a")["description"] == ""
    warnings = titled(notes, "Save Skipped")
    assert len(warnings) == 1
    assert " - nfet_a" in warnings[0][2]
    assert model_of(ctrl).get_device(0)["description"] == ""


def test_a_new_row_with_an_off_list_celltype_is_warned_about(device_tab_ctrl, store):
    # celltype 은 required 라 빈 CellType 으로는 insert_row 가 행을 넣지 않는다.
    ctrl = device_tab_ctrl
    open_sf2p(ctrl)
    notes = record_notifications(ctrl)
    assert model_of(ctrl).insert_row(2, {"name": "new1", "celltype": OFF_LIST, "description": ""})

    assert ctrl.device_table.save_all() is False

    assert sent_names(store) == [["nfet_a", "nfet_b"]]
    with pytest.raises(KeyError):
        store.find_device("new1")
    warnings = titled(notes, "Save Skipped")
    assert len(warnings) == 1
    assert " - new1" in warnings[0][2]
    assert [d["name"] for d in model_of(ctrl).get_devices()] == ["nfet_a", "nfet_b"]


@pytest.mark.parametrize("choice", [CANCEL, RELOAD])
def test_a_save_that_was_not_written_does_not_warn_about_skipped_rows(
    device_tab_ctrl, store, dialogs, choice
):
    ctrl = device_tab_ctrl
    open_sf2p(ctrl)
    notes = record_notifications(ctrl)
    edit_device_cell(ctrl, 0, "celltype", OFF_LIST)
    edit_device_cell(ctrl, 1, "description", EDITED)
    store.touch_device(store.find_device("nfet_b")["id"], actor="bob")
    dialogs.answer_conflict(choice)

    assert ctrl.device_table.save_all() is False

    assert len(store.calls_of("upsert_devices")) == 1
    assert titled(notes, "Save Skipped") == []
    assert titled(notes, "Save Complete") == []


def test_database_save_with_a_skipped_edit_is_not_reported_as_saved(
    device_tab_ctrl, store, dialogs, qtbot
):
    ctrl = device_tab_ctrl
    open_sf2p(ctrl)
    # nfet_b 의 탭을 고친다. device 행은 nfet_a 만 고치므로 탭 저장이 나 자신과 충돌하지 않는다.
    select_device_row(ctrl, 1)
    nfet_b = store.find_device("nfet_b")["id"]
    qtbot.waitUntil(lambda: ctrl.parameter_tab.section(TAB).device_id == nfet_b)
    qtbot.waitUntil(lambda: len(ctrl.parameter_tab.section(TAB).model.get_data()) == 2)
    edit_tab_cell(ctrl, TAB, 0, COLUMN, "dd")
    notes = record_notifications(ctrl)
    edit_device_cell(ctrl, 0, "celltype", OFF_LIST)

    assert ctrl.save_db() is False

    assert len(titled(notes, "Save Skipped")) == 1
    assert all(text != ALL_SAVED for _severity, _title, text in notes)
    calls = store.calls_of("replace_many_for_device")
    assert [c["device_id"] for c in calls] == [nfet_b]
    assert store.rows("inst_terms", nfet_b)[0][COLUMN] == "dd"
    assert not ctrl.parameter_tab.is_dirty()


# -- G15b: 저장 안 한 편집이 있을 때 붙여넣기 ----------------------------------------


def test_pasting_with_unsaved_device_edits_is_refused_with_a_warning(device_tab_ctrl, store):
    ctrl = device_tab_ctrl
    open_sf2p(ctrl)
    notes = record_notifications(ctrl)
    edit_device_cell(ctrl, 0, "description", EDITED)
    ctrl.device_table.copy_rows([1])

    ctrl.device_table.paste_rows([1])

    assert titled(notes, "Unsaved Changes") == [
        (
            "warn",
            "Unsaved Changes",
            "Not pasted: there are unsaved device changes.\n"
            "Pasting saves immediately and reloads the list, which would discard them. "
            "Save first.",
        )
    ]
    assert store.calls_of("upsert_device") == []
    assert model_of(ctrl).rowCount() == 2
    assert model_of(ctrl).get_device(0)["description"] == EDITED
    assert ctrl.device_table.is_dirty()


def test_pasting_without_unsaved_edits_saves_the_pasted_row(device_tab_ctrl, store):
    ctrl = device_tab_ctrl
    open_sf2p(ctrl)
    notes = record_notifications(ctrl)
    ctrl.device_table.copy_rows([1])

    ctrl.device_table.paste_rows([1])

    assert len(store.calls_of("upsert_device")) == 1
    assert model_of(ctrl).rowCount() == 3
    assert [d["name"] for d in model_of(ctrl).get_devices()].count("nfet_b") == 2
    assert titled(notes, "Unsaved Changes") == []


def edit_nfet_a_tab(ctrl, store, qtbot) -> int:
    """nfet_a(0행)를 골라 탭이 그것을 읽은 뒤 InstTerm 0행을 "dd" 로 고친다. nfet_a 의 id."""
    select_device_row(ctrl, 0)
    nfet_a = store.find_device("nfet_a")["id"]
    qtbot.waitUntil(lambda: ctrl.parameter_tab.section(TAB).device_id == nfet_a)
    qtbot.waitUntil(lambda: len(ctrl.parameter_tab.section(TAB).model.get_data()) == 4)
    edit_tab_cell(ctrl, TAB, 0, COLUMN, "dd")
    assert ctrl.parameter_tab.is_dirty()
    return nfet_a


def test_pasting_with_unsaved_tab_edits_is_refused_with_a_warning(
    device_tab_ctrl, store, qtbot
):
    ctrl = device_tab_ctrl
    open_sf2p(ctrl)
    nfet_a = edit_nfet_a_tab(ctrl, store, qtbot)
    notes = record_notifications(ctrl)
    ctrl.device_table.copy_rows([1])

    ctrl.device_table.paste_rows([1])

    assert store.calls_of("upsert_device") == []
    assert store.calls_of("replace_many_for_device") == []
    assert titled(notes, "Unsaved Changes") == [
        (
            "warn",
            "Unsaved Changes",
            "Not pasted: there are unsaved tab changes.\n"
            "Pasting saves immediately and reloads the tabs, which would discard them. "
            "Save first.",
        )
    ]
    assert model_of(ctrl).rowCount() == 2
    assert ctrl.parameter_tab.current_device_id == nfet_a
    assert ctrl.parameter_tab.section(TAB).device_id == nfet_a
    assert ctrl.parameter_tab.is_dirty()
    assert ctrl.parameter_tab.section(TAB).model.get_data()[0][COLUMN] == "dd"


def test_pasting_with_unsaved_device_and_tab_edits_warns_only_about_device_edits(
    device_tab_ctrl, store, qtbot
):
    ctrl = device_tab_ctrl
    open_sf2p(ctrl)
    edit_nfet_a_tab(ctrl, store, qtbot)
    edit_device_cell(ctrl, 0, "description", EDITED)
    notes = record_notifications(ctrl)
    ctrl.device_table.copy_rows([1])

    ctrl.device_table.paste_rows([1])

    assert titled(notes, "Unsaved Changes") == [
        (
            "warn",
            "Unsaved Changes",
            "Not pasted: there are unsaved device changes.\n"
            "Pasting saves immediately and reloads the list, which would discard them. "
            "Save first.",
        )
    ]
    assert store.calls_of("upsert_device") == []
    assert ctrl.device_table.is_dirty()
    assert ctrl.parameter_tab.is_dirty()


# -- K38: 붙여넣은 device 의 탭 쓰기는 저장된 version 에 대고 쓴다 ----------------------


def new_device_ids(store, before: set[int]) -> list[int]:
    return sorted(set(store.devices) - before)


def spy_saved_versions(monkeypatch, ctrl, after_save=None) -> list[tuple[int, int]]:
    """붙여넣기의 device 저장(upsert_device)이 돌려준 (id, version) 을 차례로 모은다."""
    repo = ctrl.device_table.repo
    save = repo.upsert_device
    saved_versions: list[tuple[int, int]] = []

    def spy(*args, **kwargs):
        saved = save(*args, **kwargs)
        saved_versions.append((saved["id"], saved["version"]))
        if after_save is not None:
            after_save(saved)
        return saved

    monkeypatch.setattr(repo, "upsert_device", spy)
    return saved_versions


def test_a_pasted_row_writes_its_tabs_against_the_saved_version(device_tab_ctrl, store):
    ctrl = device_tab_ctrl
    open_sf2p(ctrl)
    before = set(store.devices)
    ctrl.device_table.copy_rows([1])

    ctrl.device_table.paste_rows([1])

    [new_id] = new_device_ids(store, before)
    call = store.calls_of("replace_many_for_device")[-1]
    assert call["device_id"] == new_id
    assert call["expected_version"] is not None
    # 탭 쓰기가 한 번 올렸다
    assert call["expected_version"] + 1 == store.devices[new_id]["version"]


def test_each_pasted_row_writes_its_tabs_against_its_own_saved_version(
    device_tab_ctrl, store, monkeypatch
):
    ctrl = device_tab_ctrl
    open_sf2p(ctrl)
    before = set(store.devices)
    ctrl.device_table.copy_rows([0, 1])
    saved_versions = spy_saved_versions(monkeypatch, ctrl)

    ctrl.device_table.paste_rows([1])

    new_ids = new_device_ids(store, before)
    assert [device_id for device_id, _ in saved_versions] == new_ids
    calls = store.calls_of("replace_many_for_device")
    assert [(c["device_id"], c["expected_version"]) for c in calls] == saved_versions
    assert [store.devices[i]["version"] for i in new_ids] == [v + 1 for _, v in saved_versions]


def test_another_users_save_between_paste_and_tab_write_is_a_conflict(
    device_tab_ctrl, store, dialogs, monkeypatch
):
    # 내 붙여넣기가 device 행을 저장한 바로 뒤, 탭을 쓰기 전에 bob 이 그 device 를 저장했다.
    ctrl = device_tab_ctrl
    open_sf2p(ctrl)
    before = set(store.devices)
    ctrl.device_table.copy_rows([1])
    spy_saved_versions(
        monkeypatch,
        ctrl,
        after_save=lambda saved: store.touch_device(saved["id"], actor="bob", description="bob"),
    )
    dialogs.answer_conflict(CANCEL)

    ctrl.device_table.paste_rows([1])

    [new_id] = new_device_ids(store, before)
    bob_saved_at = store.devices[new_id]["updated_at"]
    assert [s for s in dialogs.shown if s[0] == "conflict"] == [
        ("conflict", "Save Conflict", f"nfet_b: modified by bob ({bob_saved_at:%Y-%m-%d %H:%M})")
    ]
    # 취소했으므로 붙여넣은 탭 행은 쓰이지 않았고 bob 의 저장이 그대로다
    assert store.rows("inst_terms", new_id) == []
    assert store.devices[new_id]["updated_by"] == "bob"
    section = ctrl.parameter_tab.section(TAB)
    assert section.device_id == new_id
    assert section.is_dirty()


def test_a_stale_tab_write_after_paste_asks_and_cancel_keeps_the_pasted_rows_dirty(
    device_tab_ctrl, store, dialogs
):
    ctrl = device_tab_ctrl
    open_sf2p(ctrl)
    before = set(store.devices)
    ctrl.device_table.copy_rows([1])
    store.fail_next(
        "replace_many_for_device",
        StaleWriteError([Conflict(0, "nfet_b", "stale", "bob", None)]),
    )
    dialogs.answer_conflict(CANCEL)

    ctrl.device_table.paste_rows([1])

    [new_id] = new_device_ids(store, before)
    assert [s for s in dialogs.shown if s[0] == "conflict"] == [
        ("conflict", "Save Conflict", "nfet_b: modified by bob")
    ]
    assert [s for s in dialogs.shown if s[0] == "error"] == []
    # device 행은 저장됐고 목록을 다시 읽었다. 탭 행은 쓰이지 않고 dirty 로 남았다
    assert model_of(ctrl).rowCount() == 3
    assert store.rows("inst_terms", new_id) == []
    section = ctrl.parameter_tab.section(TAB)
    assert section.device_id == new_id
    assert section.is_dirty()


# -- DeviceTableModel.is_row_changed ---------------------------------------------


def test_is_row_changed_follows_the_loaded_values(device_tab_ctrl):
    ctrl = device_tab_ctrl
    open_sf2p(ctrl)
    model = model_of(ctrl)
    assert not model.is_row_changed(0)
    assert not model.is_row_changed(1)

    edit_device_cell(ctrl, 0, "description", EDITED)
    assert model.is_row_changed(0)
    assert not model.is_row_changed(1)

    edit_device_cell(ctrl, 0, "description", "")
    assert not model.is_row_changed(0)

    assert model.insert_row(2, {"name": "new1", "celltype": "NFET", "description": ""})
    assert model.is_row_changed(2)
    assert not model.is_row_changed(3)
