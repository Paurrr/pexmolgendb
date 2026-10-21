"""컨트롤러가 process 를 (이름, 버전) 쌍으로 고르고, 되돌리고, 지운다 (phase 19 step 8).

process 행 하나가 (이름, 버전) 쌍이다(2026-10-21 승인). 툴바 컨트롤러는 view 의
`selectionChanged(이름, 버전)` 을 듣고 `list_pairs` 로 목록을 채운다. device·탭·저장·폴링은
지금처럼 그 쌍의 `process_id` 로 돈다. `current_process` 는 이름 그대로다(CSV `CdsLibName`,
Virtuoso payload). 저장이 취소돼 되돌릴 때는 두 콤보를 함께 되돌리고, Remove Process 가 편집을
버리는 것은 지운 쌍이 지금 쌍일 때뿐이다(K42).
"""

import pytest
from gui_support.helpers import edit_device_cell, select_device_row, select_process

from genviewer.dialogs.conflict import CANCEL

V2 = "V2"
TAB = "InstTerm"
EDITED_DESCRIPTION = "edited by tester"
SAVE_CHANGES = (
    "question",
    "Save Changes",
    "You have unsaved changes. Do you want to save them?",
)


def toolbar(ctrl):
    return ctrl.device_tab_toolbar.ui


def current(ctrl) -> tuple:
    dt = ctrl.device_table
    return (dt.current_process, dt.current_release, dt.current_process_id)


def shown_pair(ctrl) -> tuple[str, str]:
    """두 콤보에 보이는 글자."""
    ui = toolbar(ctrl)
    return (ui.process_selector.currentText(), ui.release_selector.currentText())


def device_names(ctrl) -> list[str]:
    return [d["name"] for d in ctrl.device_table.ui.model_safe().get_devices()]


def pid(store, name: str, release: str = "") -> int:
    (found,) = [
        p for p, n in store.processes.items() if n == name and store.releases[p] == release
    ]
    return found


def add_release(ctrl, store, name: str, release: str, device: str) -> int:
    """(name, release) 와 device 하나를 더하고 툴바가 목록을 다시 읽게 한다. 그 쌍의 id."""
    process_id = store.add_process(name, release=release)
    store.add_device(process_id, device, "NFET", order=0)
    ctrl.device_tab_toolbar.refresh_processes()
    return process_id


def add_v2(ctrl, store) -> int:
    """sf2p V2(nfet_v2). 지금 쌍 (sf2p, "") 은 그대로다."""
    return add_release(ctrl, store, "sf2p", V2, "nfet_v2")


def open_v2(ctrl, store, qtbot) -> int:
    v2 = add_v2(ctrl, store)
    select_process(ctrl, "sf2p", V2)
    qtbot.waitUntil(lambda: device_names(ctrl) == ["nfet_v2"])
    return v2


def edit_nfet_v2(ctrl, store, qtbot) -> int:
    """V2 를 열고 nfet_v2(0행) Description 을 고친다."""
    v2 = open_v2(ctrl, store, qtbot)
    edit_device_cell(ctrl, 0, "description", EDITED_DESCRIPTION)
    assert ctrl.device_table.is_dirty()
    return v2


def record_process_changes(ctrl) -> list[tuple[str, str]]:
    changes: list[tuple[str, str]] = []
    ctrl.device_tab_toolbar.processChanged.connect(
        lambda name, release: changes.append((name, release))
    )
    return changes


def record_logs(ctrl) -> list[str]:
    logs: list[str] = []
    ctrl.logRequested.connect(logs.append)
    return logs


def lookups_since(store, since: int) -> list[tuple[str, str]]:
    return [
        (args["name"], args["release"])
        for name, args in store.calls[since:]
        if name == "get_or_create_id"
    ]


def call_names(store, since: int = 0) -> list[str]:
    return [name for name, _args in store.calls[since:]]


def errors(dialogs) -> list[str]:
    return [title for kind, title, _text in dialogs.shown if kind == "error"]


def conflicts(dialogs) -> list[tuple]:
    return [shown for shown in dialogs.shown if shown[0] == "conflict"]


def choose_release(ctrl, release: str) -> None:
    """version 콤보에서 지금 이름의 release 를 고른다(사용자 동작 한 번)."""
    ui = toolbar(ctrl)
    ui.release_selector.setCurrentIndex(ui.releases_of(ui.current_pair()[0]).index(release))


def choose_name(ctrl, name: str) -> None:
    """process 콤보에서 name 을 고른다(사용자 동작 한 번). 버전은 view 가 고른다."""
    ui = toolbar(ctrl)
    ui.process_selector.setCurrentIndex(ui.process_selector.findText(name))


# -- 고르기 --------------------------------------------------------------------------


def test_choosing_a_release_shows_only_its_devices(device_tab_ctrl, store, qtbot):
    ctrl = device_tab_ctrl
    v2 = add_v2(ctrl, store)
    changes = record_process_changes(ctrl)
    logs = record_logs(ctrl)
    since = len(store.calls)

    select_process(ctrl, "sf2p", V2)

    qtbot.waitUntil(lambda: device_names(ctrl) == ["nfet_v2"])
    assert current(ctrl) == ("sf2p", V2, v2)
    assert shown_pair(ctrl) == ("sf2p", V2)
    assert changes == [("sf2p", V2)]
    assert lookups_since(store, since) == [("sf2p", V2)]
    fetched = [a["process_id"] for n, a in store.calls[since:] if n == "fetch_devices_by_process"]
    assert fetched == [v2]
    assert [args["process_id"] for name, args in store.calls[since:] if name == "etag"] == [v2]
    assert "Selected process: sf2p V2." in logs
    assert ctrl.device_tab_toolbar.get_current_process() == "sf2p"
    assert ctrl.device_tab_toolbar.get_current_release() == V2
    # CSV CdsLibName·Virtuoso payload 로 가는 이름에 버전이 섞이지 않는다.
    assert [d["process_name"] for d in ctrl.device_table.get_selected_devices(True)] == ["sf2p"]


def test_choosing_no_release_again_keeps_the_old_log_line(device_tab_ctrl, store, qtbot):
    ctrl = device_tab_ctrl
    open_v2(ctrl, store, qtbot)
    changes = record_process_changes(ctrl)
    logs = record_logs(ctrl)

    choose_release(ctrl, "")

    qtbot.waitUntil(lambda: device_names(ctrl) == ["nfet_a", "nfet_b"])
    assert current(ctrl) == ("sf2p", "", pid(store, "sf2p"))
    assert shown_pair(ctrl) == ("sf2p", "(없음)")
    assert changes == [("sf2p", "")]
    assert "Selected process: sf2p." in logs


def test_choosing_a_release_hides_the_banner_and_clears_the_tabs(device_tab_ctrl, store, qtbot):
    ctrl = device_tab_ctrl
    add_v2(ctrl, store)
    select_device_row(ctrl, 0)
    nfet_a = store.find_device("nfet_a")["id"]
    qtbot.waitUntil(lambda: ctrl.parameter_tab.section(TAB).device_id == nfet_a)
    ctrl.ui.show_refresh_banner("kim")

    select_process(ctrl, "sf2p", V2)

    qtbot.waitUntil(lambda: device_names(ctrl) == ["nfet_v2"])
    assert ctrl.ui.refresh_banner.isHidden()
    assert ctrl.parameter_tab.section(TAB).device_id is None


def test_choosing_a_name_that_has_the_release_keeps_the_release(device_tab_ctrl, store, qtbot):
    ctrl = device_tab_ctrl
    sf4u_v2 = add_release(ctrl, store, "sf4u", V2, "pfet_v2")
    open_v2(ctrl, store, qtbot)
    changes = record_process_changes(ctrl)

    choose_name(ctrl, "sf4u")

    qtbot.waitUntil(lambda: device_names(ctrl) == ["pfet_v2"])
    assert current(ctrl) == ("sf4u", V2, sf4u_v2)
    assert shown_pair(ctrl) == ("sf4u", V2)
    assert changes == [("sf4u", V2)]


def test_choosing_a_name_without_the_release_takes_its_first_release(
    device_tab_ctrl, store, qtbot
):
    ctrl = device_tab_ctrl
    open_v2(ctrl, store, qtbot)
    changes = record_process_changes(ctrl)

    choose_name(ctrl, "sf4u")

    qtbot.waitUntil(lambda: device_names(ctrl) == ["pfet_a"])
    assert current(ctrl) == ("sf4u", "", pid(store, "sf4u"))
    assert shown_pair(ctrl) == ("sf4u", "(없음)")
    assert changes == [("sf4u", "")]


def test_a_failed_lookup_of_a_release_leaves_no_process_id(
    device_tab_ctrl, store, dialogs, qtbot
):
    ctrl = device_tab_ctrl
    add_v2(ctrl, store)
    since = len(store.calls)
    store.fail_next("get_or_create_id", RuntimeError("boom"))

    select_process(ctrl, "sf2p", V2)

    qtbot.waitUntil(lambda: lookups_since(store, since) == [("sf2p", V2)])
    assert errors(dialogs) == ["Process Lookup Failed"]
    assert current(ctrl) == ("sf2p", V2, None)
    assert shown_pair(ctrl) == ("sf2p", V2)
    assert ctrl.device_table.is_dirty() is False


# -- 저장 안 한 편집이 있을 때 ------------------------------------------------------------


def test_answering_no_drops_the_release_edits_and_moves(device_tab_ctrl, store, dialogs, qtbot):
    ctrl = device_tab_ctrl
    edit_nfet_v2(ctrl, store, qtbot)
    changes = record_process_changes(ctrl)
    dialogs.answer_question(False)

    choose_release(ctrl, "")

    qtbot.waitUntil(lambda: device_names(ctrl) == ["nfet_a", "nfet_b"])
    assert current(ctrl) == ("sf2p", "", pid(store, "sf2p"))
    assert ctrl.device_table.is_dirty() is False
    assert changes == [("sf2p", "")]
    assert store.calls_of("upsert_devices") == []
    assert store.find_device("nfet_v2")["description"] == ""
    assert dialogs.shown.count(SAVE_CHANGES) == 1


def test_answering_yes_saves_into_the_release_and_moves(device_tab_ctrl, store, dialogs, qtbot):
    ctrl = device_tab_ctrl
    v2 = edit_nfet_v2(ctrl, store, qtbot)
    dialogs.answer_question(True)

    choose_release(ctrl, "")

    qtbot.waitUntil(lambda: device_names(ctrl) == ["nfet_a", "nfet_b"])
    (call,) = store.calls_of("upsert_devices")
    assert call["process_id"] == v2
    assert store.find_device("nfet_v2")["description"] == EDITED_DESCRIPTION
    assert current(ctrl) == ("sf2p", "", pid(store, "sf2p"))
    assert ctrl.device_table.is_dirty() is False
    assert errors(dialogs) == []


@pytest.mark.parametrize("target", ["release", "name"])
def test_cancelling_a_conflict_puts_both_combos_back_on_the_release(
    device_tab_ctrl, store, dialogs, qtbot, target
):
    ctrl = device_tab_ctrl
    v2 = edit_nfet_v2(ctrl, store, qtbot)
    store.touch_device(store.find_device("nfet_v2")["id"], actor="bob")
    changes = record_process_changes(ctrl)
    since = len(store.calls)
    dialogs.answer_question(True)
    dialogs.answer_conflict(CANCEL)

    if target == "release":
        choose_release(ctrl, "")
    else:
        choose_name(ctrl, "sf4u")

    qtbot.waitUntil(lambda: len(store.calls_of("upsert_devices")) == 1)
    assert shown_pair(ctrl) == ("sf2p", V2)
    assert toolbar(ctrl).current_pair() == ("sf2p", V2)
    assert current(ctrl) == ("sf2p", V2, v2)
    assert ctrl.device_table.is_dirty()
    assert ctrl.device_table.ui.model_safe().get_device(0)["description"] == EDITED_DESCRIPTION
    assert changes == [("sf2p", "") if target == "release" else ("sf4u", "")]
    assert lookups_since(store, since) == []
    assert "fetch_devices_by_process" not in call_names(store, since)
    assert len(conflicts(dialogs)) == 1


def test_a_deleted_release_is_not_restored_after_a_cancel(device_tab_ctrl, store, dialogs, qtbot):
    ctrl = device_tab_ctrl
    edit_nfet_v2(ctrl, store, qtbot)
    ctrl.device_tab_toolbar.repo.delete("sf2p", release=V2, actor="bob")
    changes = record_process_changes(ctrl)
    dialogs.answer_question(True)
    # 지워진 device 라 "deleted" 충돌이다. 덮어쓰기는 내놓지 않는다.
    dialogs.answer_conflict(CANCEL)

    ctrl.device_tab_toolbar.refresh_processes()

    qtbot.waitUntil(lambda: len(store.calls_of("upsert_devices")) == 1)
    qtbot.waitUntil(lambda: device_names(ctrl) == ["nfet_a", "nfet_b"])
    assert toolbar(ctrl).pairs() == [("sf2p", ""), ("sf4u", "")]
    assert shown_pair(ctrl) == ("sf2p", "(없음)")
    assert current(ctrl) == ("sf2p", "", pid(store, "sf2p"))
    assert ctrl.device_table.is_dirty() is False
    assert changes == [("sf2p", "")]
    assert len(conflicts(dialogs)) == 1
    assert errors(dialogs) == []


# -- 목록 다시 읽기 --------------------------------------------------------------------


def test_when_the_current_release_is_deleted_the_first_release_of_the_name_is_selected_once(
    device_tab_ctrl, store, qtbot
):
    ctrl = device_tab_ctrl
    add_release(ctrl, store, "sf4u", V2, "pfet_v2")
    add_release(ctrl, store, "sf4u", "V3", "pfet_v3")
    select_process(ctrl, "sf4u", "V3")
    qtbot.waitUntil(lambda: device_names(ctrl) == ["pfet_v3"])
    ctrl.device_tab_toolbar.repo.delete("sf4u", release="V3", actor="bob")
    changes = record_process_changes(ctrl)
    since = len(store.calls)

    ctrl.device_tab_toolbar.refresh_processes()

    qtbot.waitUntil(lambda: device_names(ctrl) == ["pfet_a"])
    assert current(ctrl) == ("sf4u", "", pid(store, "sf4u"))
    assert shown_pair(ctrl) == ("sf4u", "(없음)")
    assert changes == [("sf4u", "")]
    assert lookups_since(store, since) == [("sf4u", "")]


def test_when_every_process_is_deleted_the_selection_is_emptied_without_asking(
    device_tab_ctrl, store, dialogs, qtbot
):
    ctrl = device_tab_ctrl
    edit_nfet_v2(ctrl, store, qtbot)
    for name, release in (("sf2p", ""), ("sf2p", V2), ("sf4u", "")):
        ctrl.device_tab_toolbar.repo.delete(name, release=release, actor="bob")
    changes = record_process_changes(ctrl)
    since = len(store.calls)

    ctrl.device_tab_toolbar.refresh_processes()

    qtbot.waitUntil(lambda: changes != [])
    assert changes == [("", "")]
    assert current(ctrl) == ("", "", None)
    assert toolbar(ctrl).current_pair() == ("", "")
    assert toolbar(ctrl).pairs() == []
    assert lookups_since(store, since) == []
    assert SAVE_CHANGES not in dialogs.shown


def test_reconnecting_keeps_the_current_release(device_tab_ctrl, store, qtbot):
    ctrl = device_tab_ctrl
    v2 = open_v2(ctrl, store, qtbot)
    since = len(store.calls)

    assert ctrl.connect_db("") is True

    qtbot.waitUntil(lambda: "list_pairs" in call_names(store, since))
    assert current(ctrl) == ("sf2p", V2, v2)
    assert shown_pair(ctrl) == ("sf2p", V2)
    assert lookups_since(store, since) == []


def test_first_connect_selects_the_first_pair_once(device_tab_ctrl, store):
    ctrl = device_tab_ctrl

    assert current(ctrl) == ("sf2p", "", pid(store, "sf2p"))
    assert shown_pair(ctrl) == ("sf2p", "(없음)")
    assert lookups_since(store, 0) == [("sf2p", "")]
    assert "list_pairs" in call_names(store)
    # History 를 만들지 않았다. 툴바는 이름 목록(list_all)을 읽지 않는다.
    assert "list_all" not in call_names(store)


# -- Remove Process ------------------------------------------------------------------


def test_removing_another_release_of_the_same_name_keeps_the_edits(
    device_tab_ctrl, store, dialogs, qtbot
):
    ctrl = device_tab_ctrl
    v2 = edit_nfet_v2(ctrl, store, qtbot)
    changes = record_process_changes(ctrl)
    dialogs.answer_question(True)  # Remove Process 만

    ctrl.device_tab_toolbar.remove_process("sf2p", "")

    qtbot.waitUntil(lambda: store.calls_of("delete") != [])
    (call,) = store.calls_of("delete")
    assert (call["name"], call["release"]) == ("sf2p", "")
    assert toolbar(ctrl).pairs() == [("sf2p", V2), ("sf4u", "")]
    assert shown_pair(ctrl) == ("sf2p", V2)
    assert current(ctrl) == ("sf2p", V2, v2)
    assert ctrl.device_table.is_dirty()
    assert ctrl.device_table.ui.model_safe().get_device(0)["description"] == EDITED_DESCRIPTION
    assert changes == []
    assert ("info", "Removed", "Process 'sf2p' removed.") in dialogs.shown
    assert SAVE_CHANGES not in dialogs.shown
    assert store.calls_of("upsert_devices") == []


def test_removing_the_current_release_moves_to_the_other_release_without_asking(
    device_tab_ctrl, store, dialogs, qtbot
):
    ctrl = device_tab_ctrl
    edit_nfet_v2(ctrl, store, qtbot)
    changes = record_process_changes(ctrl)
    logs: list[str] = []
    ctrl.device_tab_toolbar.logRequested.connect(logs.append)
    dialogs.answer_question(True)

    ctrl.device_tab_toolbar.remove_process("sf2p", V2)

    qtbot.waitUntil(lambda: device_names(ctrl) == ["nfet_a", "nfet_b"])
    assert current(ctrl) == ("sf2p", "", pid(store, "sf2p"))
    assert shown_pair(ctrl) == ("sf2p", "(없음)")
    assert ctrl.device_table.is_dirty() is False
    assert changes == [("sf2p", "")]
    assert sorted(d["name"] for d in store.devices.values()) == ["nfet_a", "nfet_b", "pfet_a"]
    assert ("info", "Removed", "Process 'sf2p V2' removed.") in dialogs.shown
    assert "Process removed: sf2p V2." in logs
    assert SAVE_CHANGES not in dialogs.shown
    assert conflicts(dialogs) == []
    assert store.calls_of("upsert_devices") == []


@pytest.mark.parametrize(
    ("release", "label", "n"), [(V2, "sf2p V2", 1), ("", "sf2p", 2)], ids=["V2", "no-release"]
)
def test_the_remove_question_names_the_release(
    device_tab_ctrl, store, dialogs, release, label, n
):
    ctrl = device_tab_ctrl
    add_v2(ctrl, store)
    dialogs.answer_question(False)

    ctrl.device_tab_toolbar.remove_process("sf2p", release)

    assert dialogs.shown == [
        (
            "question",
            "Remove Process",
            f"Process '{label}' 을(를) 삭제하면 device {n}개와 그 파라미터가\n"
            "모두 함께 삭제됩니다. 계속할까요?",
        )
    ]
    (counted,) = store.calls_of("count_devices")
    assert (counted["name"], counted["release"]) == ("sf2p", release)
    assert store.calls_of("delete") == []


def test_removing_a_missing_release_says_it_is_not_found(device_tab_ctrl, store, dialogs):
    ctrl = device_tab_ctrl

    ctrl.device_tab_toolbar.remove_process("sf2p", "V9")

    assert dialogs.shown == [("warning", "Not Found", "Process 'sf2p V9' does not exist.")]
    assert store.calls_of("delete") == []


def test_a_failed_remove_of_a_release_names_it_and_keeps_the_edits(
    device_tab_ctrl, store, dialogs, qtbot
):
    ctrl = device_tab_ctrl
    v2 = edit_nfet_v2(ctrl, store, qtbot)
    store.fail_next("delete", RuntimeError("boom"))
    dialogs.answer_question(True)

    ctrl.device_tab_toolbar.remove_process("sf2p", V2)

    qtbot.waitUntil(lambda: store.calls_of("delete") != [])
    assert errors(dialogs) == ["Remove Failed: sf2p V2"]
    assert current(ctrl) == ("sf2p", V2, v2)
    assert ctrl.device_table.is_dirty()
    assert ("sf2p", V2) in toolbar(ctrl).pairs()


def test_the_minus_button_confirms_and_removes_the_current_pair(
    device_tab_ctrl, store, dialogs, qtbot
):
    ctrl = device_tab_ctrl
    open_v2(ctrl, store, qtbot)
    dialogs.answer_question(True, True)  # Confirm Delete, Remove Process

    toolbar(ctrl).remove_process_btn.click()

    qtbot.waitUntil(lambda: device_names(ctrl) == ["nfet_a", "nfet_b"])
    assert dialogs.shown[0] == (
        "question",
        "Confirm Delete",
        "Are you sure you want to delete the process:\n'sf2p V2'?",
    )
    (call,) = store.calls_of("delete")
    assert (call["name"], call["release"]) == ("sf2p", V2)
    assert toolbar(ctrl).pairs() == [("sf2p", ""), ("sf4u", "")]


def test_the_minus_button_question_without_a_release_is_the_old_one(device_tab_ctrl, dialogs):
    ctrl = device_tab_ctrl
    dialogs.answer_question(False)

    toolbar(ctrl).remove_process_btn.click()

    assert dialogs.shown == [
        ("question", "Confirm Delete", "Are you sure you want to delete the process:\n'sf2p'?")
    ]


# -- 변경 감지 ------------------------------------------------------------------------


def test_a_change_in_another_release_does_not_show_the_banner(device_tab_ctrl, store, qtbot):
    ctrl = device_tab_ctrl
    v2 = open_v2(ctrl, store, qtbot)
    banner = ctrl.ui.refresh_banner
    n = len(store.calls_of("etag"))

    store.touch_device(store.find_device("nfet_a")["id"], actor="kim")
    ctrl._poll_remote_changes()

    qtbot.waitUntil(lambda: len(store.calls_of("etag")) == n + 1 and ctrl._poll_task is None)
    assert store.calls_of("etag")[-1]["process_id"] == v2
    assert banner.isHidden()

    store.touch_device(store.find_device("nfet_v2")["id"], actor="kim")
    ctrl._poll_remote_changes()

    qtbot.waitUntil(lambda: not banner.isHidden() and ctrl._poll_task is None)
    assert "kim" in banner.label.text()
