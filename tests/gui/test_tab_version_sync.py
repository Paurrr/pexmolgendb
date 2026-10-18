"""내 device 저장이 올린 version 을 탭이 따라간다 (phase 3 step 6).

device 표 저장(upsert_devices)도 값이 바뀐 device 의 version 을 +1 한다. 탭 컨트롤러가 그것을
모르면 바로 다음 탭 저장이 나 자신과 충돌한다. DeviceTableController 는 내 쓰기가 올린 행만
deviceVersionBumped(id, old, new) 로 알리고, 탭은 지금 열린 device 이고 old 가 자기 version 이며
정확히 한 번(old+1) 올린 것일 때만 받는다. 덮어쓰기로 남의 변경 위에 올린 것(+2 이상)이나 다시
읽은 version 은 받지 않는다. 남의 변경은 탭 저장에서 여전히 충돌로 보여야 한다(ADR-004).

K17: 모델 reset 뒤 같은 행을 다시 눌러도 탭이 그 device 를 보이고 dirty 면 다시 읽지 않는다(저장 안
한 탭 편집과 따라간 version 이 남는다). 깨끗한 탭과 비운 탭(Refresh 뒤)은 지금처럼 읽는다.
"""

import pytest
from gui_support.helpers import edit_device_cell, edit_tab_cell, select_device_row, select_process

from genviewer.dialogs.conflict import CANCEL, OVERWRITE, RELOAD

TAB = "InstTerm"
TABLE = "inst_terms"
COLUMN = "cds_inst_term_name"
SEED = "d"  # 시드에서 nfet_a 의 InstTerm 0행(DRN) 값
EDITED = "dd"
DESCRIPTION = "edited by tester"


def device_id(store, name: str) -> int:
    return store.find_device(name)["id"]


def version_of(ctrl, row: int) -> int:
    return ctrl.device_table.ui.model_safe().get_device(row)["version"]


def conflicts(dialogs) -> list[tuple[str, str, str]]:
    return [shown for shown in dialogs.shown if shown[0] == "conflict"]


def tab_value(ctrl) -> str:
    return ctrl.parameter_tab.section(TAB).model.get_data()[0][COLUMN]


def stored_value(store, name: str = "nfet_a") -> str:
    return store.rows(TABLE, device_id(store, name))[0][COLUMN]


def tab_saves(store) -> list[tuple[int, int | None]]:
    return [
        (c["device_id"], c["expected_version"])
        for c in store.calls_of("replace_many_for_device")
    ]


def record_bumps(ctrl) -> list[tuple[int, int, int]]:
    bumps: list[tuple[int, int, int]] = []
    ctrl.device_table.deviceVersionBumped.connect(lambda *args: bumps.append(args))
    return bumps


def open_nfet_a(ctrl, store, qtbot) -> None:
    """sf2p 의 nfet_a(0행)를 골라 탭이 그 device 를 읽을 때까지 기다린다."""
    select_process(ctrl, "sf2p")
    select_device_row(ctrl, 0)
    nfet_a = device_id(store, "nfet_a")
    qtbot.waitUntil(lambda: ctrl.parameter_tab.section(TAB).device_id == nfet_a)
    qtbot.waitUntil(lambda: len(ctrl.parameter_tab.section(TAB).model.get_data()) == 4)
    assert ctrl.parameter_tab.current_device_id == nfet_a
    assert ctrl.parameter_tab.current_version == version_of(ctrl, 0)


def edit_nfet_a_tab(ctrl) -> None:
    edit_tab_cell(ctrl, TAB, 0, COLUMN, EDITED)
    assert ctrl.parameter_tab.is_dirty()


def edit_description(ctrl, row: int) -> None:
    edit_device_cell(ctrl, row, "description", DESCRIPTION)
    assert ctrl.device_table.is_dirty()


def bob_saves_nfet_a(store) -> None:
    store.touch_device(device_id(store, "nfet_a"), actor="bob")


def assert_tab_edits_kept(ctrl, store) -> None:
    assert ctrl.parameter_tab.current_device_id == device_id(store, "nfet_a")
    assert ctrl.parameter_tab.is_dirty()
    assert tab_value(ctrl) == EDITED
    assert stored_value(store) == SEED


# -- 나 자신과 충돌하지 않는다 ---------------------------------------------------


def test_database_save_does_not_conflict_with_my_own_device_save(
    device_tab_ctrl, store, dialogs, qtbot
):
    ctrl = device_tab_ctrl
    open_nfet_a(ctrl, store, qtbot)
    nfet_a = device_id(store, "nfet_a")
    v = version_of(ctrl, 0)
    edit_description(ctrl, 0)
    edit_nfet_a_tab(ctrl)

    assert ctrl.save_db() is True

    assert conflicts(dialogs) == []
    assert tab_saves(store) == [(nfet_a, v + 1)]
    assert not ctrl.parameter_tab.is_dirty()
    assert stored_value(store) == EDITED
    assert store.find_device("nfet_a")["description"] == DESCRIPTION
    # 탭 저장이 한 번 더 올렸다. device 표도 그 version 을 들고 있어 다음 저장이 충돌하지 않는다.
    assert store.find_device("nfet_a")["version"] == v + 2
    assert ctrl.parameter_tab.current_version == v + 2
    assert version_of(ctrl, 0) == v + 2


def test_switching_device_after_a_device_save_saves_the_tabs_without_a_conflict(
    device_tab_ctrl, store, dialogs, qtbot
):
    ctrl = device_tab_ctrl
    open_nfet_a(ctrl, store, qtbot)
    nfet_a = device_id(store, "nfet_a")
    nfet_b = device_id(store, "nfet_b")
    v = version_of(ctrl, 0)
    edit_description(ctrl, 0)
    edit_nfet_a_tab(ctrl)
    assert ctrl.device_table.save_all() is True
    dialogs.answer_question(True)

    select_device_row(ctrl, 1)

    qtbot.waitUntil(lambda: len(tab_saves(store)) == 1)
    assert conflicts(dialogs) == []
    assert tab_saves(store) == [(nfet_a, v + 1)]
    assert stored_value(store) == EDITED
    qtbot.waitUntil(lambda: ctrl.parameter_tab.section(TAB).device_id == nfet_b)
    assert ctrl.parameter_tab.current_device_id == nfet_b
    assert not ctrl.parameter_tab.is_dirty()


# -- deviceVersionBumped 는 내 쓰기가 올린 행만 ------------------------------------


def test_a_device_save_signals_only_the_rows_it_bumped(device_tab_ctrl, store, qtbot):
    ctrl = device_tab_ctrl
    open_nfet_a(ctrl, store, qtbot)
    nfet_b = device_id(store, "nfet_b")
    v = version_of(ctrl, 1)
    bumps = record_bumps(ctrl)
    edit_description(ctrl, 1)

    assert ctrl.device_table.save_all() is True

    # nfet_a 도 같이 보냈지만 값이 같아 오르지 않았다.
    sent = store.calls_of("upsert_devices")[0]["devices"]
    assert [d["name"] for d in sent] == ["nfet_a", "nfet_b"]
    assert bumps == [(nfet_b, v, v + 1)]


def test_inserted_and_deleted_rows_are_not_signalled(device_tab_ctrl, store, qtbot):
    ctrl = device_tab_ctrl
    open_nfet_a(ctrl, store, qtbot)
    nfet_b = device_id(store, "nfet_b")
    bumps = record_bumps(ctrl)
    model = ctrl.device_table.ui.model_safe()
    # nfet_b 를 지우고 끝(1행)에 새 행을 넣는다. nfet_a 의 순서는 그대로라 nfet_a 는 쓰이지 않는다.
    assert model.remove_rows([1]) == 1
    assert model.insert_row(1, {"name": "nfet_c", "celltype": "NFET", "description": ""})

    assert ctrl.device_table.save_all() is True

    saves = store.calls_of("upsert_devices")
    assert len(saves) == 1
    assert list(saves[0]["deleted"]) == [nfet_b]
    assert nfet_b not in store.devices
    assert store.find_device("nfet_c")["version"] == 1
    assert bumps == []


@pytest.mark.parametrize("choice", [CANCEL, RELOAD])
def test_a_device_save_that_was_not_written_signals_nothing(
    device_tab_ctrl, store, dialogs, qtbot, choice
):
    ctrl = device_tab_ctrl
    open_nfet_a(ctrl, store, qtbot)
    bumps = record_bumps(ctrl)
    bob_saves_nfet_a(store)
    edit_description(ctrl, 1)
    dialogs.answer_conflict(choice)

    assert ctrl.device_table.save_all() is False

    assert len(conflicts(dialogs)) == 1
    assert bumps == []


# -- 남의 변경은 여전히 충돌로 보인다 ---------------------------------------------


def test_another_users_save_still_conflicts_with_the_tabs(
    device_tab_ctrl, store, dialogs, qtbot
):
    ctrl = device_tab_ctrl
    open_nfet_a(ctrl, store, qtbot)
    v = version_of(ctrl, 0)
    edit_nfet_a_tab(ctrl)
    bob_saves_nfet_a(store)
    edit_description(ctrl, 1)
    dialogs.answer_conflict(OVERWRITE, CANCEL)

    # device 충돌(nfet_a, bob)을 덮어쓴다. nfet_a 는 값이 같아 오르지 않는다.
    assert ctrl.device_table.save_all() is True
    assert store.find_device("nfet_a")["version"] == v + 1
    # 다시 읽은 표는 bob 의 version 을 들고 있지만 탭은 그것을 받지 않는다.
    assert version_of(ctrl, 0) == v + 1
    assert ctrl.parameter_tab.current_version == v

    assert ctrl.parameter_tab.save_all() is False

    assert len(conflicts(dialogs)) == 2
    assert "bob" in conflicts(dialogs)[1][2]
    assert tab_saves(store) == [(device_id(store, "nfet_a"), v)]
    assert_tab_edits_kept(ctrl, store)


def test_overwriting_another_users_save_does_not_carry_over_to_the_tabs(
    device_tab_ctrl, store, dialogs, qtbot
):
    ctrl = device_tab_ctrl
    open_nfet_a(ctrl, store, qtbot)
    nfet_a = device_id(store, "nfet_a")
    v = version_of(ctrl, 0)
    bumps = record_bumps(ctrl)
    edit_description(ctrl, 0)
    edit_nfet_a_tab(ctrl)
    bob_saves_nfet_a(store)
    dialogs.answer_conflict(OVERWRITE, CANCEL)

    # force 가 bob 의 변경 위에 한 번 더 올려 v+2 가 된다.
    assert ctrl.device_table.save_all() is True
    assert store.find_device("nfet_a")["version"] == v + 2
    assert bumps == [(nfet_a, v, v + 2)]
    assert ctrl.parameter_tab.current_version == v

    assert ctrl.parameter_tab.save_all() is False

    # 충돌 문구는 마지막 수정자(덮어쓴 나)를 보여 준다. 탭은 bob 이전의 v 로 저장하려 했다.
    assert len(conflicts(dialogs)) == 2
    assert tab_saves(store) == [(nfet_a, v)]
    assert_tab_edits_kept(ctrl, store)


def test_a_bump_from_a_version_the_tabs_never_saw_is_not_adopted(
    device_tab_ctrl, store, dialogs, qtbot
):
    ctrl = device_tab_ctrl
    open_nfet_a(ctrl, store, qtbot)
    nfet_a = device_id(store, "nfet_a")
    v = version_of(ctrl, 0)
    bumps = record_bumps(ctrl)
    edit_nfet_a_tab(ctrl)
    bob_saves_nfet_a(store)
    edit_description(ctrl, 1)
    dialogs.answer_conflict(OVERWRITE, CANCEL)
    # 덮어쓴 뒤 다시 읽은 표는 bob 의 v+1 을 들고 있다. 탭은 아직 v 다.
    assert ctrl.device_table.save_all() is True
    assert version_of(ctrl, 0) == v + 1

    edit_description(ctrl, 0)
    assert ctrl.device_table.save_all() is True

    # 내 쓰기가 한 번 올렸지만 출발점이 탭이 본 적 없는 bob 의 version 이다.
    assert bumps[-1] == (nfet_a, v + 1, v + 2)
    assert ctrl.parameter_tab.current_version == v
    assert ctrl.parameter_tab.save_all() is False
    assert len(conflicts(dialogs)) == 2
    assert tab_saves(store) == [(nfet_a, v)]
    assert_tab_edits_kept(ctrl, store)


# -- adopt_device_version ---------------------------------------------------------


def test_adopt_device_version_accepts_only_one_step_on_the_open_device(
    device_tab_ctrl, store, qtbot
):
    ctrl = device_tab_ctrl
    open_nfet_a(ctrl, store, qtbot)
    edit_nfet_a_tab(ctrl)
    tab = ctrl.parameter_tab
    a = device_id(store, "nfet_a")
    b = device_id(store, "nfet_b")
    v = tab.current_version
    calls = len(store.calls)

    tab.adopt_device_version(b, v, v + 1)  # 다른 device
    assert tab.current_version == v
    tab.adopt_device_version(a, v, v + 2)  # 남의 변경 위에 덮어씀
    assert tab.current_version == v
    tab.adopt_device_version(a, v + 1, v + 2)  # 탭이 들고 있는 version 에서 출발하지 않음
    assert tab.current_version == v

    tab.adopt_device_version(a, v, v + 1)
    assert tab.current_version == v + 1

    # 탭 모델·dirty·화면은 그대로이고 DB 를 다시 읽지 않는다.
    assert tab.current_device_id == a
    assert tab.is_dirty()
    assert tab_value(ctrl) == EDITED
    assert store.calls[calls:] == []


# -- K17 ---------------------------------------------------------------------------


def test_clicking_the_same_row_after_a_device_save_keeps_the_tab_edits(
    device_tab_ctrl, store, qtbot
):
    ctrl = device_tab_ctrl
    open_nfet_a(ctrl, store, qtbot)
    edit_nfet_a_tab(ctrl)
    # device 편집 없이도 refresh_devices 가 모델을 reset 한다.
    assert ctrl.device_table.save_all() is True

    select_device_row(ctrl, 0)

    assert tab_value(ctrl) == EDITED
    assert ctrl.parameter_tab.is_dirty()


def test_tab_save_after_clicking_the_same_row_does_not_conflict_with_my_device_save(
    device_tab_ctrl, store, dialogs, qtbot
):
    ctrl = device_tab_ctrl
    open_nfet_a(ctrl, store, qtbot)
    nfet_a = device_id(store, "nfet_a")
    v = version_of(ctrl, 0)
    edit_description(ctrl, 0)
    edit_nfet_a_tab(ctrl)
    assert ctrl.device_table.save_all() is True
    assert ctrl.parameter_tab.current_version == v + 1

    select_device_row(ctrl, 0)

    # 따라간 version 이 남아 있어 탭 저장이 내 device 저장과 충돌하지 않는다.
    assert ctrl.parameter_tab.current_version == v + 1
    assert ctrl.parameter_tab.save_all() is True
    assert conflicts(dialogs) == []
    assert tab_saves(store) == [(nfet_a, v + 1)]
    assert stored_value(store) == EDITED


def test_clicking_the_same_row_after_a_device_save_reloads_clean_tabs(
    device_tab_ctrl, store, qtbot
):
    ctrl = device_tab_ctrl
    open_nfet_a(ctrl, store, qtbot)
    assert ctrl.device_table.save_all() is True
    reads = len(store.calls_of("fetch_by_device"))

    select_device_row(ctrl, 0)

    # 깨끗한 탭은 지금처럼 다시 읽는다(잃는 것이 없다).
    qtbot.waitUntil(lambda: len(store.calls_of("fetch_by_device")) > reads)
    assert ctrl.parameter_tab.current_device_id == device_id(store, "nfet_a")
    assert not ctrl.parameter_tab.is_dirty()
    assert tab_value(ctrl) == SEED


def test_clicking_the_row_after_refresh_reads_the_server_tabs(
    device_tab_ctrl, store, dialogs, qtbot
):
    ctrl = device_tab_ctrl
    open_nfet_a(ctrl, store, qtbot)
    nfet_a = device_id(store, "nfet_a")
    edit_nfet_a_tab(ctrl)
    store.set_rows(TABLE, nfet_a, [{"reserved_key": "DRN", COLUMN: "d3"}])
    dialogs.answer_question(True)

    ctrl.ui.refresh_banner.refreshRequested.emit()
    # 다시 읽기가 탭을 비운다. current_device_id 는 옛 값(nfet_a)으로 남아 있다.
    assert ctrl.parameter_tab.section(TAB).device_id is None
    assert ctrl.parameter_tab.current_device_id == nfet_a

    select_device_row(ctrl, 0)

    qtbot.waitUntil(lambda: ctrl.parameter_tab.section(TAB).device_id == nfet_a)
    qtbot.waitUntil(lambda: len(ctrl.parameter_tab.section(TAB).model.get_data()) == 1)
    assert tab_value(ctrl) == "d3"
    assert not ctrl.parameter_tab.is_dirty()
