"""device 표(Device Info)의 Insert/Edit 창 제목 (phase 23 step 0).

device 표의 `open_edit_dialog` 가 `InsertDialog` 에 `window_title` 을 넘기지 않아 Edit 창 제목이
기본값 "Insert" 로 떴다. 탭 표(`views/tab_section.py`)는 "Edit" 을 넘긴다. Edit 창은 "Edit",
Insert 창은 그대로 "Insert" 다.

진짜 `InsertDialog` 는 모달이라 띄우지 않는다. `FakeInsertDialog` 가 생성 인자를 기록하고 취소를
누른 것처럼 돌려준다(제목만 보므로 편집은 일으키지 않는다).
"""

from typing import ClassVar

import pytest
from gui_support.helpers import select_device_row, select_process
from PySide6.QtWidgets import QDialog

NFET_A = {"name": "nfet_a", "celltype": "NFET", "description": ""}  # sf2p 의 0번 행


class FakeInsertDialog:
    """`InsertDialog` 대역. 만들어진 것은 `created` 에 남고, `exec_` 는 취소를 누른 것과 같다."""

    created: ClassVar[list[dict]] = []

    def __init__(
        self,
        device_celltype,
        table_name,
        field_names,
        headers,
        parent=None,
        prefill=None,
        window_title="Insert",
    ):
        type(self).created.append(
            {
                "table_name": table_name,
                "prefill": None if prefill is None else dict(prefill),
                "window_title": window_title,
            }
        )

    def exec_(self):
        return QDialog.Rejected

    exec = exec_

    def get_data(self):
        raise AssertionError("취소한 대화상자의 값을 읽었다")


@pytest.fixture
def insert_dialog(monkeypatch) -> type[FakeInsertDialog]:
    monkeypatch.setattr(FakeInsertDialog, "created", [])
    monkeypatch.setattr("genviewer.views.device_table.InsertDialog", FakeInsertDialog)
    return FakeInsertDialog


@pytest.fixture
def device_view(device_tab_ctrl):
    """sf2p 를 고르고 device 표의 0번 행(nfet_a)을 고른 device 표 view."""
    select_process(device_tab_ctrl, "sf2p")
    select_device_row(device_tab_ctrl, 0)
    return device_tab_ctrl.ui.device_table_view


def test_device_edit_dialog_is_titled_edit(device_view, insert_dialog):
    device_view.open_edit_dialog(0)

    assert len(insert_dialog.created) == 1
    created = insert_dialog.created[0]
    assert created["window_title"] == "Edit"
    assert created["prefill"] == NFET_A


def test_device_insert_dialog_stays_titled_insert(device_view, insert_dialog):
    device_view.open_insert_dialog()

    assert len(insert_dialog.created) == 1
    created = insert_dialog.created[0]
    assert created["window_title"] == "Insert"
    assert created["prefill"] is None
