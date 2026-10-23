"""덮어쓸 대상이 없는 충돌에서는 덮어쓰기를 내놓지 않는다 (phase 10 step 0, K20 승인 2026-10-17).

승인된 동작: "충돌이 전부 '삭제'면 충돌 대화상자에 덮어쓰기 버튼을 안 보인다(다시 읽기/취소만)."
예전에는 덮어쓰기를 고르면 device 저장은 사라진 행의 편집을 조용히 버리고 "Save Complete" 를
띄웠고, 탭 저장은 같은 충돌이 다시 나 오류 상자가 됐다.

내가 지운 행(device 저장의 deleted)의 "deleted" 충돌은 판단에서 뺀다(사용자 확인 2026-10-17).
남이 먼저 지운 행을 나도 지웠으면 덮어쓰기가 해가 없다. 지울 행이 이미 없다.
stale 과 deleted 가 섞인 충돌은 지금처럼 세 갈래다(덮어쓰면 사라진 행의 편집은 버려진다).
"""

import pytest
from gui_support.helpers import edit_device_cell, edit_tab_cell, select_device_row, select_process
from PySide6.QtWidgets import QPushButton, QWidget

from genviewer.dialogs.conflict import (
    CANCEL,
    OVERWRITE,
    RELOAD,
    ConflictDialog,
    can_overwrite,
)

# dialogs fixture 가 모듈의 ask_conflict 를 가짜로 바꾼다. 진짜는 수집 때(가짜를 깔기 전) 묶는다.
from genviewer.dialogs.conflict import ask_conflict as real_ask_conflict
from genviewer.service.errors import Conflict

TAB = "InstTerm"
TABLE = "inst_terms"
COLUMN = "cds_inst_term_name"
EDITED_TAB = "dd"
EDITED = "edited by tester"
RELOAD_BUTTON = "Reload"
OVERWRITE_BUTTON = "Overwrite with Mine"
CANCEL_BUTTON = "Cancel"
BOTH = (RELOAD, CANCEL)
ALL_THREE = (RELOAD, OVERWRITE, CANCEL)


def deleted(device_id: int) -> Conflict:
    return Conflict(device_id, "", "deleted")


def stale(device_id: int) -> Conflict:
    return Conflict(device_id, f"dev{device_id}", "stale", "bob")


def device_id(store, name: str) -> int:
    return store.find_device(name)["id"]


def record(signal) -> list[str]:
    lines: list[str] = []
    signal.connect(lines.append)
    return lines


def screen_names(ctrl) -> list[str]:
    return [d["name"] for d in ctrl.device_table.ui.model_safe().get_devices()]


def screen_description(ctrl, row: int) -> str:
    return ctrl.device_table.ui.model_safe().get_device(row)["description"]


def save_complete(dialogs) -> list[tuple[str, str, str]]:
    return [shown for shown in dialogs.shown if shown[1] == "Save Complete"]


def saved(dialogs) -> list[tuple[str, str, str]]:
    return [shown for shown in dialogs.shown if shown[1] == "Saved"]


def errors(dialogs) -> list[tuple[str, str, str]]:
    return [shown for shown in dialogs.shown if shown[0] in ("error", "critical")]


def tab_rows(ctrl) -> list[dict]:
    return ctrl.parameter_tab.section(TAB).model.get_data()


def edit_nfet_a(ctrl) -> None:
    """sf2p 의 nfet_a(0행) Description 을 고친다."""
    select_process(ctrl, "sf2p")
    assert screen_names(ctrl) == ["nfet_a", "nfet_b"]
    edit_device_cell(ctrl, 0, "description", EDITED)
    assert ctrl.device_table.is_dirty()


def edit_nfet_a_tab(ctrl, store, qtbot) -> None:
    """sf2p 의 nfet_a(0행)를 골라 InstTerm 0행 값을 고친다."""
    select_process(ctrl, "sf2p")
    select_device_row(ctrl, 0)
    nfet_a = device_id(store, "nfet_a")
    qtbot.waitUntil(lambda: ctrl.parameter_tab.section(TAB).device_id == nfet_a)
    qtbot.waitUntil(lambda: len(tab_rows(ctrl)) == 4)
    edit_tab_cell(ctrl, TAB, 0, COLUMN, EDITED_TAB)
    assert ctrl.parameter_tab.is_dirty()


def remove_nfet_b_on_screen(ctrl, store) -> None:
    """화면에서 nfet_b(1행)를 지운다(저장 전). 저장의 deleted 에 들어간다."""
    model = ctrl.device_table.ui.model_safe()
    assert model.remove_rows([1]) == 1
    assert set(model.deleted_devices()) == {device_id(store, "nfet_b")}


# -- can_overwrite ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("conflicts", "my_deletions", "expected"),
    [
        ([deleted(5)], (), False),
        ([stale(5)], (), True),
        ([stale(5), deleted(6)], (), True),
        ([deleted(5)], {5}, True),
        ([deleted(5), deleted(6)], {5}, False),
        ([], (), True),
    ],
    ids=[
        "deleted",
        "stale",
        "stale+deleted",
        "my-deletion-only",
        "my-deletion+deleted",
        "empty",
    ],
)
def test_can_overwrite(conflicts, my_deletions, expected):
    assert can_overwrite(conflicts, my_deletions) is expected


# -- 대화상자 버튼 ----------------------------------------------------------------


def visible_buttons(dialog) -> list[str]:
    return [b.text() for b in dialog.findChildren(QPushButton) if b.isVisibleTo(dialog)]


@pytest.mark.parametrize(
    ("conflicts", "expected"),
    [
        ([deleted(5)], [RELOAD_BUTTON, CANCEL_BUTTON]),
        ([deleted(5), deleted(6)], [RELOAD_BUTTON, CANCEL_BUTTON]),
        ([stale(5)], [RELOAD_BUTTON, OVERWRITE_BUTTON, CANCEL_BUTTON]),
        ([stale(5), deleted(6)], [RELOAD_BUTTON, OVERWRITE_BUTTON, CANCEL_BUTTON]),
    ],
    ids=["deleted", "all-deleted", "stale", "stale+deleted"],
)
def test_conflict_dialog_buttons(qtbot, conflicts, expected):
    dialog = ConflictDialog(None, conflicts, allow_overwrite=can_overwrite(conflicts))
    qtbot.addWidget(dialog)

    assert visible_buttons(dialog) == expected


def press_in_real_dialog(monkeypatch, button: str) -> list[list[str]]:
    """진짜 ask_conflict 가 띄우는 대화상자의 버튼을 기록하고 button 을 누른다(exec 대신)."""
    seen: list[list[str]] = []

    def fake_exec(dialog, *_args, **_kwargs):
        seen.append(visible_buttons(dialog))
        pressed = [b for b in dialog.findChildren(QPushButton) if b.text() == button]
        assert len(pressed) == 1, f"{button!r} 버튼이 없다: {seen[-1]}"
        pressed[0].click()
        return dialog.result()

    monkeypatch.setattr(ConflictDialog, "exec", fake_exec)
    return seen


def test_real_ask_conflict_hides_overwrite_when_every_conflict_is_deleted(qtbot, monkeypatch):
    parent = QWidget()
    qtbot.addWidget(parent)
    seen = press_in_real_dialog(monkeypatch, CANCEL_BUTTON)

    assert real_ask_conflict(parent, [deleted(5), deleted(6)]) == CANCEL

    assert seen == [[RELOAD_BUTTON, CANCEL_BUTTON]]


def test_real_ask_conflict_offers_overwrite_when_only_my_deletion_was_deleted(
    qtbot, monkeypatch
):
    parent = QWidget()
    qtbot.addWidget(parent)
    seen = press_in_real_dialog(monkeypatch, OVERWRITE_BUTTON)

    assert real_ask_conflict(parent, [deleted(5)], my_deletions={5}) == OVERWRITE

    assert seen == [[RELOAD_BUTTON, OVERWRITE_BUTTON, CANCEL_BUTTON]]


# -- device 저장 ------------------------------------------------------------------


def test_reloading_a_device_save_after_another_user_deleted_the_edited_device(
    device_tab_ctrl, store, dialogs
):
    ctrl = device_tab_ctrl
    logs = record(ctrl.device_table.logRequested)
    edit_nfet_a(ctrl)
    store.remove_device(device_id(store, "nfet_a"))
    dialogs.answer_conflict(RELOAD)

    assert ctrl.device_table.save_all() is False

    assert dialogs.conflict_choices[-1] == BOTH
    assert screen_names(ctrl) == ["nfet_b"]
    assert not ctrl.device_table.is_dirty()
    assert "Save conflict: reloaded from the server." in logs
    assert save_complete(dialogs) == []
    assert [c["force"] for c in store.calls_of("upsert_devices")] == [False]


def test_cancelling_a_device_save_after_another_user_deleted_the_edited_device(
    device_tab_ctrl, store, dialogs
):
    ctrl = device_tab_ctrl
    logs = record(ctrl.device_table.logRequested)
    edit_nfet_a(ctrl)
    store.remove_device(device_id(store, "nfet_a"))
    dialogs.answer_conflict(CANCEL)

    assert ctrl.device_table.save_all() is False

    assert dialogs.conflict_choices[-1] == BOTH
    assert screen_names(ctrl) == ["nfet_a", "nfet_b"]
    assert screen_description(ctrl, 0) == EDITED
    assert ctrl.device_table.is_dirty()
    assert "Save conflict: save canceled." in logs
    assert save_complete(dialogs) == []
    assert [c["force"] for c in store.calls_of("upsert_devices")] == [False]


def test_overwrite_is_offered_when_another_user_deleted_only_the_device_i_deleted(
    device_tab_ctrl, store, dialogs
):
    ctrl = device_tab_ctrl
    select_process(ctrl, "sf2p")
    remove_nfet_b_on_screen(ctrl, store)
    edit_device_cell(ctrl, 0, "description", EDITED)
    store.remove_device(device_id(store, "nfet_b"))
    dialogs.answer_conflict(OVERWRITE)

    assert ctrl.device_table.save_all() is True

    assert dialogs.conflict_choices[-1] == ALL_THREE
    assert [c["force"] for c in store.calls_of("upsert_devices")] == [False, True]
    assert store.find_device("nfet_a")["description"] == EDITED
    assert not ctrl.device_table.is_dirty()
    assert len(save_complete(dialogs)) == 1


def test_overwrite_is_hidden_when_another_user_also_deleted_my_edited_device(
    device_tab_ctrl, store, dialogs
):
    """내가 지운 nfet_b 를 빼면 남은 충돌(편집한 nfet_a 삭제)은 전부 deleted 다."""
    ctrl = device_tab_ctrl
    select_process(ctrl, "sf2p")
    remove_nfet_b_on_screen(ctrl, store)
    edit_device_cell(ctrl, 0, "description", EDITED)
    store.remove_device(device_id(store, "nfet_a"))
    store.remove_device(device_id(store, "nfet_b"))
    dialogs.answer_conflict(CANCEL)

    assert ctrl.device_table.save_all() is False

    assert len(dialogs.shown[-1][2].splitlines()) == 2  # 두 충돌이 다 보인다
    assert dialogs.conflict_choices[-1] == BOTH
    assert ctrl.device_table.is_dirty()


def test_a_stale_and_deleted_conflict_still_offers_overwrite(device_tab_ctrl, store, dialogs):
    """특성 테스트. 덮어쓰면 nfet_b 의 편집은 조용히 버려진다(고치지 않은 새 known-issue)."""
    ctrl = device_tab_ctrl
    edit_nfet_a(ctrl)
    edit_device_cell(ctrl, 1, "description", EDITED)
    store.touch_device(device_id(store, "nfet_a"), actor="bob")
    store.remove_device(device_id(store, "nfet_b"))
    dialogs.answer_conflict(CANCEL)

    assert ctrl.device_table.save_all() is False

    assert dialogs.conflict_choices[-1] == ALL_THREE


# -- 탭 저장 ----------------------------------------------------------------------


def test_reloading_a_tab_save_after_another_user_deleted_the_device(
    device_tab_ctrl, store, dialogs, qtbot
):
    ctrl = device_tab_ctrl
    logs = record(ctrl.parameter_tab.logRequested)
    edit_nfet_a_tab(ctrl, store, qtbot)
    store.remove_device(device_id(store, "nfet_a"))
    dialogs.answer_conflict(RELOAD)

    assert ctrl.parameter_tab.save_all() is False

    assert dialogs.conflict_choices[-1] == BOTH
    assert tab_rows(ctrl) == []
    assert not ctrl.parameter_tab.is_dirty()
    assert "Tab conflict: reloaded from the server." in logs
    assert saved(dialogs) == []
    assert [c["force"] for c in store.calls_of("replace_many_for_device")] == [False]


def test_cancelling_a_tab_save_after_another_user_deleted_the_device(
    device_tab_ctrl, store, dialogs, qtbot
):
    ctrl = device_tab_ctrl
    logs = record(ctrl.parameter_tab.logRequested)
    edit_nfet_a_tab(ctrl, store, qtbot)
    store.remove_device(device_id(store, "nfet_a"))
    dialogs.answer_conflict(CANCEL)

    assert ctrl.parameter_tab.save_all() is False

    assert dialogs.conflict_choices[-1] == BOTH
    assert tab_rows(ctrl)[0][COLUMN] == EDITED_TAB
    assert ctrl.parameter_tab.is_dirty()
    assert "Tab conflict: save canceled." in logs
    assert saved(dialogs) == []
    assert [c["force"] for c in store.calls_of("replace_many_for_device")] == [False]


@pytest.mark.parametrize("choice", [RELOAD, CANCEL])
def test_switching_device_after_the_edited_device_was_deleted(
    device_tab_ctrl, store, dialogs, qtbot, choice
):
    """탭 편집 중 남이 그 device 를 지웠다. 다른 행을 누르고 "Save Changes" 에 예."""
    ctrl = device_tab_ctrl
    edit_nfet_a_tab(ctrl, store, qtbot)
    nfet_a = device_id(store, "nfet_a")
    nfet_b = device_id(store, "nfet_b")
    store.remove_device(nfet_a)
    dialogs.answer_question(True)
    dialogs.answer_conflict(choice)

    select_device_row(ctrl, 1)

    qtbot.waitUntil(lambda: store.calls_of("replace_many_for_device") != [])
    if choice == RELOAD:
        qtbot.waitUntil(lambda: ctrl.parameter_tab.current_device_id == nfet_b)
        assert not ctrl.parameter_tab.is_dirty()
    else:
        # 취소는 머문다(phase 3). 편집은 그대로다.
        assert ctrl.parameter_tab.current_device_id == nfet_a
        assert ctrl.parameter_tab.is_dirty()
    assert dialogs.conflict_choices == [BOTH]
    assert errors(dialogs) == []
    assert [c["force"] for c in store.calls_of("replace_many_for_device")] == [False]
