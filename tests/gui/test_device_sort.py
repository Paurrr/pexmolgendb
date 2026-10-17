"""device 표 머리글 메뉴의 "오름차순 정렬"/"내림차순 정렬" (phase 4 step 3).

정렬은 끌어 옮기기(moveRows)와 같은 "저장 안 한 변경" 이다. 모델의 모든 행을 정렬하고(필터에
가려진 device 도), 기준점(서버에서 읽은 상태)은 그대로 둔다. 그래서 저장 전에 지운 device 는
지울 목록에 남고, 고친 셀 표시와 undo 도 남는다. 프록시는 정렬된 채로 두지 않는다.

정렬은 메뉴 팝업 대신 `sort_and_commit(0, order)` 를 직접 부른다(메뉴 동작이 부르는 것과 같다).
"""

import pytest
from gui_support.helpers import edit_device_cell, seeded_store, select_process
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

NAME = 0
DESCRIPTION = 2
DIRTY = QColor(255, 249, 196)
EDITED = "edited by tester"
# sf2p 는 nfet_a(order 0), nfet_b(1), nfet_0(2) 순서다. 이름 순으로는 어느 방향도 아니다.
SEED_ORDER = ["nfet_a", "nfet_b", "nfet_0"]
ASCENDING = ["nfet_0", "nfet_a", "nfet_b"]
DESCENDING = ["nfet_b", "nfet_a", "nfet_0"]


@pytest.fixture
def store():
    """시드에 sf2p 의 device 하나(nfet_0, 이름 순으로 맨 앞)를 끝에 더한다."""
    s = seeded_store()
    sf2p = s.find_device("nfet_a")["process_id"]
    s.add_device(sf2p, "nfet_0", "NFET", order=2)
    return s


def model_of(ctrl):
    return ctrl.device_table.ui.model_safe()


def names(ctrl) -> list[str]:
    return [d["name"] for d in model_of(ctrl).get_devices()]


def visible_names(ctrl) -> list[str]:
    proxy = ctrl.device_table.ui.proxy_model
    return [proxy.index(r, NAME).data() for r in range(proxy.rowCount())]


def dirty_cells(model) -> set[tuple[int, int]]:
    return {
        (r, c)
        for r in range(model.rowCount())
        for c in range(model.columnCount())
        if model.index(r, c).data(Qt.BackgroundRole) == DIRTY
    }


def open_sf2p(ctrl) -> None:
    select_process(ctrl, "sf2p")
    assert names(ctrl) == SEED_ORDER
    assert not ctrl.device_table.is_dirty()


def last_save(store) -> list[dict]:
    saves = store.calls_of("upsert_devices")
    assert saves, "upsert_devices 가 불리지 않았다"
    return saves[-1]


# -- 필터 중 정렬 ------------------------------------------------------------------


def test_sorting_while_filtered_keeps_the_hidden_devices(device_tab_ctrl, store):
    ctrl = device_tab_ctrl
    open_sf2p(ctrl)
    ids_before = {d["id"] for d in model_of(ctrl).get_devices()}
    ctrl.device_table.ui.apply_filter("nfet_b")
    assert visible_names(ctrl) == ["nfet_b"]

    ctrl.device_table.sort_and_commit(NAME, Qt.DescendingOrder)

    assert {d["id"] for d in model_of(ctrl).get_devices()} == ids_before
    assert names(ctrl) == DESCENDING
    # 필터는 그대로다
    assert visible_names(ctrl) == ["nfet_b"]
    ctrl.device_table.ui.apply_filter("")
    assert visible_names(ctrl) == DESCENDING


def test_saving_after_sorting_while_filtered_sends_every_device_in_sorted_order(
    device_tab_ctrl, store
):
    ctrl = device_tab_ctrl
    open_sf2p(ctrl)
    ctrl.device_table.ui.apply_filter("nfet_b")

    ctrl.device_table.sort_and_commit(NAME, Qt.AscendingOrder)
    assert ctrl.device_table.save_all() is True

    sent = last_save(store)
    assert [(d["name"], d["order"]) for d in sent["devices"]] == [
        (name, i) for i, name in enumerate(ASCENDING)
    ]
    assert sent["deleted"] == {}
    assert [store.find_device(name)["order"] for name in ASCENDING] == [0, 1, 2]


# -- 기준점 유지: 지운 device, 고친 셀, undo ------------------------------------------


def test_a_device_deleted_before_sorting_is_still_deleted_on_save(
    device_tab_ctrl, store, dialogs
):
    ctrl = device_tab_ctrl
    open_sf2p(ctrl)
    nfet_a = store.find_device("nfet_a")
    dialogs.answer_question(True)
    ctrl.device_table.ui.delete_rows([0])
    assert names(ctrl) == ["nfet_b", "nfet_0"]

    ctrl.device_table.sort_and_commit(NAME, Qt.AscendingOrder)

    assert names(ctrl) == ["nfet_0", "nfet_b"]
    assert model_of(ctrl).deleted_devices() == {nfet_a["id"]: nfet_a["version"]}

    assert ctrl.device_table.save_all() is True
    assert last_save(store)["deleted"] == {nfet_a["id"]: nfet_a["version"]}
    with pytest.raises(KeyError):
        store.find_device("nfet_a")
    assert names(ctrl) == ["nfet_0", "nfet_b"]


def test_an_edited_cell_stays_marked_after_sorting(device_tab_ctrl, store):
    ctrl = device_tab_ctrl
    open_sf2p(ctrl)
    model = model_of(ctrl)
    edit_device_cell(ctrl, 0, "description", EDITED)
    assert dirty_cells(model) == {(0, DESCRIPTION)}

    ctrl.device_table.sort_and_commit(NAME, Qt.DescendingOrder)

    assert names(ctrl) == DESCENDING
    # nfet_a 는 1행으로 옮겨 갔고 표시도 따라갔다
    assert model.get_device(1)["description"] == EDITED
    assert dirty_cells(model) == {(1, DESCRIPTION)}
    assert model.is_modified()
    assert ctrl.device_table.is_dirty()

    # undo 한 번이면 정렬만 되돌아가고 편집은 남는다
    assert model.undo()
    assert names(ctrl) == SEED_ORDER
    assert model.get_device(0)["description"] == EDITED
    assert dirty_cells(model) == {(0, DESCRIPTION)}
    assert ctrl.device_table.is_dirty()


# -- 정렬만 해도 저장 안 한 변경 ------------------------------------------------------


def test_sorting_alone_is_an_unsaved_change(device_tab_ctrl, store, qtbot):
    ctrl = device_tab_ctrl
    open_sf2p(ctrl)
    model = model_of(ctrl)

    with qtbot.waitSignal(model.modified, timeout=1000):
        ctrl.device_table.sort_and_commit(NAME, Qt.DescendingOrder)

    assert names(ctrl) == DESCENDING
    assert model.is_modified()
    assert ctrl.device_table.is_dirty()
    # 이름 순서만 바뀌었으므로 노란 셀은 없다(셀 값은 서버와 같다)
    assert dirty_cells(model) == set()


def test_sorting_into_the_order_it_already_has_changes_nothing(device_tab_ctrl, store):
    ctrl = device_tab_ctrl
    open_sf2p(ctrl)
    model = model_of(ctrl)
    ctrl.device_table.sort_and_commit(NAME, Qt.DescendingOrder)
    emitted: list[None] = []
    model.modified.connect(lambda: emitted.append(None))

    ctrl.device_table.sort_and_commit(NAME, Qt.DescendingOrder)

    assert emitted == []
    assert names(ctrl) == DESCENDING
    # 되돌릴 것은 첫 정렬 하나뿐이다
    assert model.undo()
    assert names(ctrl) == SEED_ORDER
    assert not model.undo()


# -- 회귀: 지금 프록시 정렬과 같은 순서 -------------------------------------------------


@pytest.mark.parametrize(
    ("order", "reverse"),
    [(Qt.AscendingOrder, False), (Qt.DescendingOrder, True)],
    ids=["ascending", "descending"],
)
def test_sorting_orders_the_names_like_before(device_tab_ctrl, store, order, reverse):
    ctrl = device_tab_ctrl
    open_sf2p(ctrl)

    ctrl.device_table.sort_and_commit(NAME, order)

    assert names(ctrl) == sorted(SEED_ORDER, reverse=reverse)
    # 프록시는 정렬된 채로 남지 않는다. 화면은 모델 순서 그대로다
    assert ctrl.device_table.ui.proxy_model.sortColumn() == -1
    assert visible_names(ctrl) == names(ctrl)


@pytest.mark.parametrize(
    "order", [Qt.AscendingOrder, Qt.DescendingOrder], ids=["ascending", "descending"]
)
def test_sorting_by_a_column_with_equal_values_keeps_the_order(device_tab_ctrl, store, order):
    # sf2p 의 CellType 은 모두 NFET 다. 같은 값끼리는 지금 순서를 지킨다(내림차순도)
    ctrl = device_tab_ctrl
    open_sf2p(ctrl)
    model = model_of(ctrl)
    emitted: list[None] = []
    model.modified.connect(lambda: emitted.append(None))

    ctrl.device_table.sort_and_commit(1, order)

    assert names(ctrl) == SEED_ORDER
    assert emitted == []
    assert not ctrl.device_table.is_dirty()
