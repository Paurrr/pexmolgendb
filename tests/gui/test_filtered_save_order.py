"""Virtuoso 목록으로 걸러 본 채 저장할 때의 순서값 (phase 10 step 6, K19, 2026-10-17 승인).

Virtuoso device 목록을 받으면 device 표는 그 목록과 이름이 겹치는 행만 들고 있다(refresh_devices 의
필터). 예전 save_all 은 들고 있는 행에 0..k-1 을 매겼다. 그러면 숨은 행과 순서값이 겹쳐 전체 목록
(`ORDER BY "order", id`)과 내보내기 순서가 바뀌고, 편집 없이 저장해도 순서값이 바뀐 행의 version 이
올라 남에게 충돌이 났다.

승인된 동작: 걸러 본 채 저장할 때 보이는 행에 0..k-1 대신 그 행들이 원래 갖던 순서값을
다시 나눠 준다. 기준은 "마지막 refresh_devices 가 숨긴 행이 있었는가" 다. 없었으면(필터가
없거나 모두 보이면) 지금처럼 order = 화면 순서다.

한계(고치지 않음): refresh 때 이미 order 값이 겹친 행은 숨은 행을 쓰지 않고는 정리할 수 없다.

준비: sf2p 에 nfet_c(order 2)를 더하고 nfet_a·nfet_c 만 보이게 거른다. 숨은 행은 nfet_b(1)다.
"""

import pytest
from gui_support.helpers import edit_device_cell, seeded_store, select_process
from PySide6.QtCore import Qt

from genviewer.config.config import delegate_config
from genviewer.controllers.device_table import _filtered_orders
from genviewer.dialogs.conflict import CANCEL

NAME = 0
EDITED = "edited by tester"
OFF_LIST = "nmos_rf"  # delegate_config 의 device.celltype.items 에 없다
NEW_ROW = {"name": "nfet_new", "celltype": "NFET", "description": ""}


@pytest.fixture
def store():
    """시드의 sf2p 에 nfet_c(order 2)를 끝에 더한다. sf2p 는 nfet_a(0), nfet_b(1), nfet_c(2)."""
    s = seeded_store()
    sf2p = next(pid for pid, name in s.processes.items() if name == "sf2p")
    s.add_device(sf2p, "nfet_c", "NFET", order=2)
    return s


def model_of(ctrl):
    return ctrl.device_table.ui.model_safe()


def names(ctrl) -> list[str]:
    return [d["name"] for d in model_of(ctrl).get_devices()]


def show_only(ctrl, *shown: str) -> None:
    """Virtuoso 목록을 받은 것처럼 그 이름들만 보이게 다시 읽는다."""
    ctrl.device_table.device_state_data = {name: {"S": "O"} for name in shown}
    ctrl.device_table.refresh_devices()


def open_filtered(ctrl) -> None:
    """sf2p 를 열고 nfet_a·nfet_c 만 보이게 거른다(nfet_b 가 숨는다)."""
    select_process(ctrl, "sf2p")
    show_only(ctrl, "nfet_a", "nfet_c")
    assert names(ctrl) == ["nfet_a", "nfet_c"]
    assert not ctrl.device_table.is_dirty()


def sf2p_devices(store) -> list[dict]:
    """서버의 sf2p 전체 목록(숨은 행 포함). ORDER BY "order", id."""
    sf2p = next(pid for pid, name in store.processes.items() if name == "sf2p")
    found = [d for d in store.devices.values() if d["process_id"] == sf2p]
    return sorted(found, key=lambda d: (d["order"], d["id"]))


def server_names(store) -> list[str]:
    return [d["name"] for d in sf2p_devices(store)]


def orders(store) -> dict[str, int]:
    return {d["name"]: d["order"] for d in sf2p_devices(store)}


def versions(store) -> dict[str, int]:
    return {d["name"]: d["version"] for d in sf2p_devices(store)}


def save_notes(dialogs) -> list[tuple[str, str, str]]:
    return [s for s in dialogs.shown if s[1] in ("Save Complete", "Save Skipped")]


def sent_orders(call: dict) -> list[tuple[str, int]]:
    return [(d["name"], d["order"]) for d in call["devices"]]


# -- 숨긴 행이 있을 때 ------------------------------------------------------------------


def test_saving_a_filtered_view_without_edits_writes_nothing(device_tab_ctrl, store, dialogs):
    ctrl = device_tab_ctrl
    open_filtered(ctrl)
    before = versions(store)

    assert ctrl.device_table.save_all() is True

    assert orders(store) == {"nfet_a": 0, "nfet_b": 1, "nfet_c": 2}
    assert versions(store) == before
    assert save_notes(dialogs) == [("info", "Save Complete", "No changes to save.")]


def test_reordering_the_visible_rows_reuses_their_own_order_values(
    device_tab_ctrl, store, dialogs
):
    ctrl = device_tab_ctrl
    open_filtered(ctrl)
    before = versions(store)
    model_of(ctrl).sort_rows(NAME, Qt.DescendingOrder)
    assert names(ctrl) == ["nfet_c", "nfet_a"]

    assert ctrl.device_table.save_all() is True

    assert orders(store) == {"nfet_c": 0, "nfet_b": 1, "nfet_a": 2}
    assert server_names(store) == ["nfet_c", "nfet_b", "nfet_a"]
    assert versions(store) == {
        "nfet_a": before["nfet_a"] + 1,
        "nfet_b": before["nfet_b"],
        "nfet_c": before["nfet_c"] + 1,
    }
    assert save_notes(dialogs) == [("info", "Save Complete", "2 updated.")]
    # 다시 읽은 화면도 같은 필터, 새 순서다
    assert names(ctrl) == ["nfet_c", "nfet_a"]


def test_editing_one_visible_row_bumps_only_that_row(device_tab_ctrl, store, dialogs):
    ctrl = device_tab_ctrl
    open_filtered(ctrl)
    before = versions(store)
    edit_device_cell(ctrl, 1, "description", EDITED)

    assert ctrl.device_table.save_all() is True

    assert orders(store) == {"nfet_a": 0, "nfet_b": 1, "nfet_c": 2}
    assert versions(store) == {**before, "nfet_c": before["nfet_c"] + 1}
    assert store.find_device("nfet_c")["description"] == EDITED
    assert save_notes(dialogs) == [("info", "Save Complete", "1 updated.")]


def test_a_new_row_lands_right_after_the_id_row_above_it(device_tab_ctrl, store, dialogs):
    ctrl = device_tab_ctrl
    open_filtered(ctrl)
    before = versions(store)
    assert model_of(ctrl).insert_row(1, NEW_ROW)
    assert names(ctrl) == ["nfet_a", "nfet_new", "nfet_c"]

    assert ctrl.device_table.save_all() is True

    assert server_names(store) == ["nfet_a", "nfet_new", "nfet_b", "nfet_c"]
    assert orders(store)["nfet_b"] == 1
    assert {k: v for k, v in versions(store).items() if k != "nfet_new"} == before
    assert save_notes(dialogs) == [("info", "Save Complete", "1 added.")]


def test_a_new_row_on_top_lands_before_the_first_visible_row(device_tab_ctrl, store, dialogs):
    ctrl = device_tab_ctrl
    open_filtered(ctrl)
    before = versions(store)
    assert model_of(ctrl).insert_row(0, NEW_ROW)
    assert names(ctrl) == ["nfet_new", "nfet_a", "nfet_c"]

    assert ctrl.device_table.save_all() is True

    assert server_names(store) == ["nfet_new", "nfet_a", "nfet_b", "nfet_c"]
    assert orders(store) == {"nfet_new": -1, "nfet_a": 0, "nfet_b": 1, "nfet_c": 2}
    assert {k: v for k, v in versions(store).items() if k != "nfet_new"} == before


def test_deleting_a_visible_row_keeps_the_others_order(device_tab_ctrl, store, dialogs):
    ctrl = device_tab_ctrl
    open_filtered(ctrl)
    before = versions(store)
    ctrl.device_table.remove_rows([0])
    assert names(ctrl) == ["nfet_c"]

    assert ctrl.device_table.save_all() is True

    assert orders(store) == {"nfet_b": 1, "nfet_c": 2}
    assert versions(store) == {"nfet_b": before["nfet_b"], "nfet_c": before["nfet_c"]}
    assert save_notes(dialogs) == [("info", "Save Complete", "1 deleted.")]


def test_new_rows_with_no_visible_id_row_go_after_every_row(device_tab_ctrl, store, dialogs):
    ctrl = device_tab_ctrl
    open_filtered(ctrl)
    ctrl.device_table.remove_rows([0, 1])
    assert model_of(ctrl).insert_row(0, NEW_ROW)
    assert names(ctrl) == ["nfet_new"]

    assert ctrl.device_table.save_all() is True

    # 숨은 nfet_b(1)까지 본 최댓값(지운 nfet_c 의 2)+1
    assert orders(store) == {"nfet_b": 1, "nfet_new": 3}
    assert save_notes(dialogs) == [("info", "Save Complete", "1 added, 2 deleted.")]


def test_an_off_list_row_keeps_its_order_value_to_itself(device_tab_ctrl, store, dialogs):
    """Save Skipped 행은 보내지 않는다. 슬롯은 보내는 행의 옛 값으로만 만든다.

    그래야 보내지 않는(그래서 DB 값이 그대로인) 행의 순서값을 다른 행이 받아 겹치지 않는다.
    """
    ctrl = device_tab_ctrl
    open_filtered(ctrl)
    before = versions(store)
    assert OFF_LIST not in delegate_config["device"]["celltype"]["items"]
    model_of(ctrl).sort_rows(NAME, Qt.DescendingOrder)
    assert names(ctrl) == ["nfet_c", "nfet_a"]
    edit_device_cell(ctrl, 0, "celltype", OFF_LIST)

    assert ctrl.device_table.save_all() is False

    sent = store.calls_of("upsert_devices")[-1]
    assert sent_orders(sent) == [("nfet_a", 0)]
    assert orders(store) == {"nfet_a": 0, "nfet_b": 1, "nfet_c": 2}
    assert versions(store) == before
    assert [title for _kind, title, _text in save_notes(dialogs)] == [
        "Save Complete",
        "Save Skipped",
    ]
    assert save_notes(dialogs)[0] == ("info", "Save Complete", "No changes to save.")


# -- 취소 뒤 다시 저장: 옛 값은 refresh 때 읽은 값이다 ------------------------------------


def test_saving_again_after_a_cancelled_conflict_sends_the_same_orders(
    device_tab_ctrl, store, dialogs
):
    ctrl = device_tab_ctrl
    open_filtered(ctrl)
    model_of(ctrl).sort_rows(NAME, Qt.DescendingOrder)
    store.touch_device(store.find_device("nfet_a")["id"], actor="bob", description="bob")
    dialogs.answer_conflict(CANCEL, CANCEL)

    assert ctrl.device_table.save_all() is False
    assert ctrl.device_table.save_all() is False

    first, second = store.calls_of("upsert_devices")
    assert sent_orders(first) == [("nfet_c", 0), ("nfet_a", 2)]
    assert sent_orders(second) == sent_orders(first)
    assert orders(store) == {"nfet_a": 0, "nfet_b": 1, "nfet_c": 2}


def test_deleting_a_row_after_a_cancelled_conflict_keeps_the_old_order_values(
    device_tab_ctrl, store, dialogs
):
    """취소된 저장은 모델 행의 order 를 그 자리에서 바꿔 두었다. 그 값을 옛 값으로 쓰면 안 된다.

    정렬로 nfet_c=0, nfet_a=2 를 보냈다가 취소하고 nfet_a 를 지우면, nfet_c 의 옛 값은 refresh 때
    읽은 2 다(모델 행에 남은 0 이 아니다). 0 을 보내면 nfet_c 가 숨은 nfet_b 앞으로 온다.
    """
    ctrl = device_tab_ctrl
    open_filtered(ctrl)
    nfet_a = store.find_device("nfet_a")
    model_of(ctrl).sort_rows(NAME, Qt.DescendingOrder)
    store.touch_device(nfet_a["id"], actor="bob", description="bob")
    dialogs.answer_conflict(CANCEL, CANCEL)
    assert ctrl.device_table.save_all() is False

    ctrl.device_table.remove_rows([1])
    assert names(ctrl) == ["nfet_c"]
    assert ctrl.device_table.save_all() is False

    second = store.calls_of("upsert_devices")[-1]
    assert sent_orders(second) == [("nfet_c", 2)]
    assert second["deleted"] == {nfet_a["id"]: nfet_a["version"]}


# -- 숨긴 행이 없을 때: 지금처럼 order = 화면 순서 (특성 테스트) ----------------------------


def test_saving_without_a_filter_renumbers_every_row(device_tab_ctrl, store, dialogs):
    ctrl = device_tab_ctrl
    store.devices[store.find_device("nfet_c")["id"]]["order"] = 7
    select_process(ctrl, "sf2p")
    show_only(ctrl)  # device_state_data = {}
    assert names(ctrl) == ["nfet_a", "nfet_b", "nfet_c"]

    assert ctrl.device_table.save_all() is True

    assert orders(store) == {"nfet_a": 0, "nfet_b": 1, "nfet_c": 2}
    assert save_notes(dialogs) == [("info", "Save Complete", "1 updated.")]


def test_a_filter_that_shows_every_row_still_renumbers_every_row(
    device_tab_ctrl, store, dialogs
):
    ctrl = device_tab_ctrl
    store.devices[store.find_device("nfet_c")["id"]]["order"] = 7
    select_process(ctrl, "sf2p")
    show_only(ctrl, "nfet_a", "nfet_b", "nfet_c")
    assert names(ctrl) == ["nfet_a", "nfet_b", "nfet_c"]

    assert ctrl.device_table.save_all() is True

    assert orders(store) == {"nfet_a": 0, "nfet_b": 1, "nfet_c": 2}
    assert save_notes(dialogs) == [("info", "Save Complete", "1 updated.")]


# -- _filtered_orders (Qt 없는 계산) -------------------------------------------------------

# refresh 때 읽은 모든 행: id 1(0), 2(5, 숨음), 4(2). 화면 행은 id 목록, None 은 새 행이다.
OLD_ORDERS = {1: 0, 2: 5, 4: 2}


@pytest.mark.parametrize(
    ("ids", "old_orders", "expected"),
    [
        pytest.param([1, 4], OLD_ORDERS, [0, 2], id="unchanged"),
        pytest.param([4, 1], OLD_ORDERS, [0, 2], id="swapped"),
        pytest.param([4], OLD_ORDERS, [2], id="deleted-row-drops-its-value"),
        pytest.param([1, None, None, 4], OLD_ORDERS, [0, 0, 0, 2], id="new-after-id-row"),
        pytest.param([None, 4, 1], OLD_ORDERS, [-1, 0, 2], id="new-on-top"),
        pytest.param([None, None], OLD_ORDERS, [6, 6], id="no-id-row-goes-after-max"),
        pytest.param([None], {}, [0], id="nothing-read"),
        pytest.param([1, 99], OLD_ORDERS, [0, 0], id="id-not-read-is-new"),
        pytest.param([4, 1], {1: 3, 4: 3}, [3, 3], id="overlapping-old-values"),
    ],
)
def test_filtered_orders(ids, old_orders, expected):
    devices = [{} if i is None else {"id": i} for i in ids]

    assert _filtered_orders(devices, old_orders) == expected
