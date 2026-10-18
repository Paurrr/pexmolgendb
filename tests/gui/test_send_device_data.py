"""Virtuoso 로 보내기에 저장 안 한 device 가 있으면 보내지 않는다 (phase 11 step 3, K21).

사용자 승인 2026-10-17: "Run Selected 등 보내기에 저장 안 한 새 행이 있으면 새 경고 문구로
알리고 보내지 않음. 지금은 'Send Failed: 'id''". 저장 안 한 새 행에는 id 가 없어서
send_device_data 가 device_info 를 만들다 KeyError('id') 를 냈고, @report 가 그것을
"Send Failed" 오류 상자(본문 'id')로 띄웠다.
"""

import pytest
from gui_support.helpers import select_device_row
from PySide6.QtCore import QItemSelectionModel

UNSAVED = (
    "warning",
    "Unsaved Devices",
    "저장하지 않은 device 가 있어 보내지 않았다. 먼저 저장할 것.",
)


@pytest.fixture
def sent(device_tab_ctrl) -> list[str]:
    """sendDataRequested 로 나간 문자열."""
    out: list[str] = []
    device_tab_ctrl.sendDataRequested.connect(out.append)
    return out


def add_unsaved_row(ctrl) -> int:
    """sf2p 목록 끝에 저장하지 않은 새 행(id 없음)을 넣고 그 행 번호를 돌려준다."""
    model = ctrl.device_table.ui.model_safe()
    row = model.rowCount()
    assert model.insert_row(row, {"name": "new_dev", "celltype": "NFET", "description": ""})
    assert model.get_device(row).get("id") is None
    return row


def also_select_row(ctrl, row: int) -> None:
    """화면 순서 row 행을 지금 선택에 더한다(Ctrl+클릭). current 는 바꾸지 않는다."""
    view = ctrl.ui.device_table_view
    index = view.model().index(row, 0)
    assert index.isValid(), f"device 표에 {row}번 행이 없다"
    view.selectionModel().select(
        index, QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows
    )


def selected_names(ctrl) -> list[str]:
    return [d["name"] for d in ctrl.device_table.get_selected_devices(fallback_to_all=False)]


def test_a_selected_unsaved_row_is_not_sent(device_tab_ctrl, store, dialogs, sent):
    ctrl = device_tab_ctrl
    row = add_unsaved_row(ctrl)
    select_device_row(ctrl, row)
    assert selected_names(ctrl) == ["new_dev"]

    ctrl.send_device_data("selected")

    assert sent == []
    assert store.calls_of("fetch_export_data") == []
    assert dialogs.shown == [UNSAVED]


def test_saved_and_unsaved_rows_selected_together_are_not_sent(
    device_tab_ctrl, store, dialogs, sent
):
    ctrl = device_tab_ctrl
    row = add_unsaved_row(ctrl)
    select_device_row(ctrl, 0)
    also_select_row(ctrl, row)
    assert selected_names(ctrl) == ["nfet_a", "new_dev"]

    ctrl.send_device_data("selected")

    assert sent == []
    assert store.calls_of("fetch_export_data") == []
    assert dialogs.shown == [UNSAVED]


def test_send_all_without_selection_is_not_sent_with_an_unsaved_row(
    device_tab_ctrl, store, dialogs, sent
):
    ctrl = device_tab_ctrl
    add_unsaved_row(ctrl)
    assert selected_names(ctrl) == []
    assert [d["name"] for d in ctrl.device_table.get_selected_devices()] == [
        "nfet_a",
        "nfet_b",
        "new_dev",
    ]

    ctrl.send_device_data("all")

    assert sent == []
    assert store.calls_of("fetch_export_data") == []
    assert dialogs.shown == [UNSAVED]


@pytest.mark.parametrize(
    "unsaved_elsewhere", [False, True], ids=["only-saved", "unsaved-unselected"]
)
def test_selected_saved_rows_are_sent(device_tab_ctrl, store, dialogs, sent, unsaved_elsewhere):
    ctrl = device_tab_ctrl
    if unsaved_elsewhere:
        add_unsaved_row(ctrl)  # 고르지 않은 새 행은 보낼 대상이 아니다
    select_device_row(ctrl, 0)
    assert selected_names(ctrl) == ["nfet_a"]

    ctrl.send_device_data("selected")

    assert len(sent) == 1
    assert sent[0].startswith("pydata = list(")
    assert len(store.calls_of("fetch_export_data")) == 1
    assert dialogs.shown == []


def test_nothing_selected_shows_the_status_message(device_tab_ctrl, store, dialogs, sent):
    ctrl = device_tab_ctrl
    status: list[tuple[str, int]] = []
    ctrl.statusMessageRequested.connect(lambda text, ms: status.append((text, ms)))
    add_unsaved_row(ctrl)  # 목록에 있어도 고르지 않았으면 대상이 없다
    assert selected_names(ctrl) == []

    ctrl.send_device_data("selected")

    assert status == [("No device selected", 2000)]
    assert sent == []
    assert store.calls_of("fetch_export_data") == []
    assert dialogs.shown == []
