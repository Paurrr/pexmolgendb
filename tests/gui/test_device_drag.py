"""device 표 끌어 옮기기와 이름 필터 (phase 11 step 5, K18, 사용자 승인 2026-10-17).

`dropEvent` 는 고른 proxy 행의 첫 행을 source 로 옮겨 그 자리부터 고른 개수만큼의 연속 구간을
옮긴다(`relocateRow`). 필터(`apply_filter`)가 사이 행을 숨기면 화면에서 이어진 두 행이 source
에서는 떨어져 있고, 그 연속 구간에 숨은 행이 끼어 함께 옮겨졌다. 승인된 동작은 "고른 행이 실제
목록에서 떨어져 있으면 놓기를 거부(아무 일 없음)" 다. 이어져 있으면 지금처럼 옮긴다.

drop 이벤트는 가짜다. `dropEvent` 가 부르는 것(source, dropAction, pos)만 흉내 내고 받은 처리를
`handled` 에 남긴다. 놓는 자리는 view 가 정한다(`indexAt(pos)`, `dropIndicatorPosition()`).
- "on-last-row": 마지막으로 보이는 행 가운데. 끌기가 지나간 적 없는 view 의 표시 위치는 OnItem
  이라 고른 행보다 아래 행이면 그 행 뒤(source 행 + 1)에 놓인다.
- "below-rows": 행 아래 빈 곳. 실제 끌기에서는 dragMoveEvent 가 표시 위치를 OnViewport 로 두고
  (가짜 이벤트로는 그 경로를 탈 수 없어 그 값만 대신 정한다) 모델 맨 끝에 놓인다.
"""

import pytest
from gui_support.helpers import seeded_store, select_process
from PySide6.QtCore import QItemSelection, QItemSelectionModel, QPoint, Qt
from PySide6.QtWidgets import QAbstractItemView

NAME = 0
# sf2p 는 nfet_a(order 0), nfet_b(1), nfet_0(2) 순서다.
SEED_ORDER = ["nfet_a", "nfet_b", "nfet_0"]
# 앞 두 행을 맨 끝으로 옮긴 순서(두 놓는 자리 모두 source 3 에 놓인다)
MOVED_TO_END = ["nfet_0", "nfet_a", "nfet_b"]
ACCEPTED = [("setDropAction", Qt.MoveAction), "acceptProposedAction"]
DROPS = ["on-last-row", "below-rows"]


@pytest.fixture
def store():
    """시드에 sf2p 의 device 하나(nfet_0)를 끝에 더한다(test_device_sort.py 와 같다)."""
    s = seeded_store()
    sf2p = s.find_device("nfet_a")["process_id"]
    s.add_device(sf2p, "nfet_0", "NFET", order=2)
    return s


class FakeDropEvent:
    """view 자신에서 시작한 MoveAction drop. 받은 처리를 `handled` 에 남긴다."""

    def __init__(self, view, pos: QPoint):
        self._view = view
        self._pos = pos
        self.handled: list = []

    def source(self):
        return self._view

    def dropAction(self):
        return Qt.MoveAction

    def pos(self) -> QPoint:
        return self._pos

    def ignore(self) -> None:
        self.handled.append("ignore")

    def acceptProposedAction(self) -> None:
        self.handled.append("acceptProposedAction")

    def setDropAction(self, action) -> None:
        self.handled.append(("setDropAction", action))


def model_of(ctrl):
    return ctrl.device_table.ui.model_safe()


def names(ctrl) -> list[str]:
    return [d["name"] for d in model_of(ctrl).get_devices()]


def visible_names(ctrl) -> list[str]:
    proxy = ctrl.device_table.ui.proxy_model
    return [proxy.index(r, NAME).data() for r in range(proxy.rowCount())]


def open_sf2p(ctrl) -> None:
    select_process(ctrl, "sf2p")
    assert names(ctrl) == SEED_ORDER
    assert not ctrl.device_table.is_dirty()


def select_visible_rows(ctrl, *rows: int) -> None:
    """화면(proxy) 순서의 rows 를 행 단위로 고른다(앞의 선택은 지운다)."""
    ui = ctrl.device_table.ui
    proxy = ui.proxy_model
    selection = QItemSelection()
    for row in rows:
        selection.select(proxy.index(row, NAME), proxy.index(row, NAME))
    ui.selectionModel().select(
        selection, QItemSelectionModel.ClearAndSelect | QItemSelectionModel.Rows
    )
    assert ui._selected_proxy_rows() == sorted(rows)


def drop(ctrl, monkeypatch, where: str) -> FakeDropEvent:
    ui = ctrl.device_table.ui
    proxy = ui.proxy_model
    last = ui.visualRect(proxy.index(proxy.rowCount() - 1, NAME))
    if where == "on-last-row":
        pos = last.center()
        assert ui.dropIndicatorPosition() == QAbstractItemView.OnItem
    else:
        pos = QPoint(last.center().x(), last.bottom() + 30)
        monkeypatch.setattr(
            ui, "dropIndicatorPosition", lambda: QAbstractItemView.OnViewport
        )
    event = FakeDropEvent(ui, pos)
    ui.dropEvent(event)
    return event


def assert_nothing_happened(ctrl, event: FakeDropEvent) -> None:
    assert names(ctrl) == SEED_ORDER
    assert event.handled == ["ignore"]
    assert not ctrl.device_table.is_dirty()
    assert not model_of(ctrl).is_modified()
    assert not model_of(ctrl).undo()


# -- 필터가 사이 행을 숨김: 거부 ----------------------------------------------------------


@pytest.mark.parametrize("where", DROPS)
def test_rows_apart_in_the_model_are_not_dropped(device_tab_ctrl, monkeypatch, where):
    ctrl = device_tab_ctrl
    open_sf2p(ctrl)
    ctrl.device_table.ui.apply_filter("nfet_a|nfet_0")
    assert visible_names(ctrl) == ["nfet_a", "nfet_0"]
    # 화면에서는 이어진 두 행이고 source 에서는 0 과 2 다(사이의 nfet_b 가 숨어 있다)
    select_visible_rows(ctrl, 0, 1)
    assert ctrl.device_table.ui._selected_source_rows() == [0, 2]

    event = drop(ctrl, monkeypatch, where)

    assert_nothing_happened(ctrl, event)
    assert visible_names(ctrl) == ["nfet_a", "nfet_0"]


# -- 회귀: source 에서도 이어져 있으면 지금처럼 옮긴다 --------------------------------------


@pytest.mark.parametrize("where", DROPS)
def test_adjacent_rows_without_a_filter_are_moved(device_tab_ctrl, monkeypatch, where):
    ctrl = device_tab_ctrl
    open_sf2p(ctrl)
    select_visible_rows(ctrl, 0, 1)

    event = drop(ctrl, monkeypatch, where)

    assert event.handled == ACCEPTED
    assert names(ctrl) == MOVED_TO_END
    assert ctrl.device_table.is_dirty()
    assert model_of(ctrl).undo()
    assert names(ctrl) == SEED_ORDER


def test_adjacent_rows_with_a_filter_hiding_nothing_between_are_moved(
    device_tab_ctrl, monkeypatch
):
    # 보이는 행이 고른 두 행뿐이라 행 위에 놓으면 제자리다. 행 아래 빈 곳에 놓는다
    ctrl = device_tab_ctrl
    open_sf2p(ctrl)
    ctrl.device_table.ui.apply_filter("nfet_a|nfet_b")
    assert visible_names(ctrl) == ["nfet_a", "nfet_b"]
    select_visible_rows(ctrl, 0, 1)
    assert ctrl.device_table.ui._selected_source_rows() == [0, 1]

    event = drop(ctrl, monkeypatch, "below-rows")

    assert event.handled == ACCEPTED
    assert names(ctrl) == MOVED_TO_END
    assert ctrl.device_table.is_dirty()
    assert visible_names(ctrl) == ["nfet_a", "nfet_b"]


# -- 회귀: 화면에서 떨어진 행은 지금도 거부한다 --------------------------------------------


@pytest.mark.parametrize("where", DROPS)
def test_rows_apart_on_screen_are_not_dropped(device_tab_ctrl, monkeypatch, where):
    ctrl = device_tab_ctrl
    open_sf2p(ctrl)
    select_visible_rows(ctrl, 0, 2)

    event = drop(ctrl, monkeypatch, where)

    assert_nothing_happened(ctrl, event)
