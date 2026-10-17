"""탭 섹션의 Insert/Edit 입력 경로 (phase 4 step 1).

G10: `TabSection` 은 `device_id`·`device_celltype` 를 `on_device_changed` 에서 처음 만든다. 접속
직후(device 를 아직 고르지 않음) Insert(버튼, Ctrl+I, 메뉴)를 누르면 `open_insert_dialog` 가
`AttributeError` 로 죽어 "예기치 못한 오류" 가 됐다. 선택이 풀린 뒤에는 대화상자가 열리지만 OK 를
누르면 `insert_row` 가 모델이 없어 입력을 말없이 버렸다. device 가 없으면 Insert 는 아무것도 하지
않는다.

G12: Ctrl+E 만 빈 prefill 로 편집 창을 열어, OK 를 누르면 그 행이 빈 값(strict 콤보는 첫 항목)으로
덮였다. Ctrl+E 는 Edit 버튼과 같은 경로(행 값을 채운 편집 창)를 탄다.

진짜 `InsertDialog` 는 모달이라 띄우지 않는다. `FakeInsertDialog` 가 생성 인자를 기록하고 OK 를
누른 것처럼 돌려준다.
"""

from typing import ClassVar

import pytest
from gui_support.helpers import select_device_row, select_process
from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QDialog

from genviewer.controllers import tab_section as tab_section_module

TAB = "InstTerm"  # 시드에 행이 있는 탭 (nfet_a: DRN/d, GATE/g, SRC/s, BULK/b)
NFET_A_ROWS = [
    {"reserved_key": "DRN", "cds_inst_term_name": "d"},
    {"reserved_key": "GATE", "cds_inst_term_name": "g"},
    {"reserved_key": "SRC", "cds_inst_term_name": "s"},
    {"reserved_key": "BULK", "cds_inst_term_name": "b"},
]


class FakeInsertDialog:
    """`InsertDialog` 대역. 만들어진 것은 `created` 에 남고, `exec_` 는 OK 를 누른 것과 같다.

    `get_data()` 는 `reply` 가 있으면 그 사본, 없으면 `prefill` 사본(없으면 빈 dict)을 돌려준다.
    """

    created: ClassVar[list[dict]] = []
    reply: ClassVar[dict | None] = None

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
        self.prefill = prefill
        type(self).created.append(
            {
                "device_celltype": device_celltype,
                "table_name": table_name,
                "prefill": None if prefill is None else dict(prefill),
                "window_title": window_title,
            }
        )

    def exec_(self):
        return QDialog.Accepted

    exec = exec_

    def get_data(self):
        if type(self).reply is not None:
            return dict(type(self).reply)
        return dict(self.prefill or {})


@pytest.fixture
def insert_dialog(monkeypatch) -> type[FakeInsertDialog]:
    monkeypatch.setattr(FakeInsertDialog, "created", [])
    monkeypatch.setattr(FakeInsertDialog, "reply", None)
    monkeypatch.setattr("genviewer.views.tab_section.InsertDialog", FakeInsertDialog)
    return FakeInsertDialog


def open_nfet_a(ctrl, store, qtbot):
    """sf2p 의 nfet_a 를 골라 TAB 섹션이 그 행을 읽을 때까지 기다린다."""
    nfet_a = store.find_device("nfet_a")["id"]
    select_process(ctrl, "sf2p")
    select_device_row(ctrl, 0)
    sec = ctrl.parameter_tab.section(TAB)
    qtbot.waitUntil(lambda: sec.device_id == nfet_a and sec.model is not None)
    assert sec.model.get_data() == NFET_A_ROWS
    return sec


def choose_from_menu(monkeypatch, sec, action: str, rows: list[int]) -> None:
    """탭 섹션의 오른쪽 클릭 메뉴에서 action("insert"/"edit"/…)을 고른 것처럼 한다."""
    acts = {name: object() for name in ("insert", "edit", "delete", "clear", "copy", "paste")}

    class Menu:
        def exec(self, _pos):
            return acts[action]

    monkeypatch.setattr(
        tab_section_module, "build_parameter_table_menu", lambda parent, rows: (Menu(), acts)
    )
    sec.ui.contextMenuRequested.emit(rows, QPoint())


# -- G10: device 가 없을 때의 Insert -----------------------------------------


def press_insert(how: str, sec, qtbot, monkeypatch) -> None:
    """Insert 를 누르는 길 넷. 모두 `TabSection.open_insert_dialog` 를 지난다."""
    if how == "call":
        sec.ui.open_insert_dialog()
    elif how == "ctrl_i":
        qtbot.keyClick(sec.ui, Qt.Key_I, Qt.ControlModifier)
    elif how == "button":
        sec.ui.insert_btn.click()
    else:
        choose_from_menu(monkeypatch, sec, "insert", [])


INSERT_PATHS = ("call", "ctrl_i", "button", "menu")


@pytest.mark.parametrize("how", INSERT_PATHS)
def test_insert_right_after_connect_does_nothing(
    device_tab_ctrl, insert_dialog, qtbot, monkeypatch, how
):
    sec = device_tab_ctrl.parameter_tab.section(TAB)
    assert sec.device_id is None  # 아직 device 를 고르지 않았다

    press_insert(how, sec, qtbot, monkeypatch)

    assert insert_dialog.created == []
    assert sec.ui.device_id is None
    assert sec.ui.device_celltype is None
    assert sec.model is None


@pytest.mark.parametrize("how", INSERT_PATHS)
def test_insert_after_the_selection_is_cleared_does_not_open_the_dialog(
    device_tab_ctrl, store, insert_dialog, qtbot, monkeypatch, how
):
    ctrl = device_tab_ctrl
    sec = open_nfet_a(ctrl, store, qtbot)
    ctrl.parameter_tab._clear_tabs()
    assert sec.device_id is None and sec.model is None

    press_insert(how, sec, qtbot, monkeypatch)

    assert insert_dialog.created == []
    assert sec.ui.device_id is None
    assert sec.ui.device_celltype is None


@pytest.mark.parametrize("how", INSERT_PATHS)
def test_insert_with_a_device_opens_the_dialog_and_adds_the_row(
    device_tab_ctrl, store, insert_dialog, qtbot, monkeypatch, how
):
    sec = open_nfet_a(device_tab_ctrl, store, qtbot)
    insert_dialog.reply = {"reserved_key": "GATE", "cds_inst_term_name": "g_new"}

    press_insert(how, sec, qtbot, monkeypatch)

    assert insert_dialog.created == [
        {
            "device_celltype": "NFET",
            "table_name": "inst_terms",
            "prefill": None,
            "window_title": "Insert",
        }
    ]
    assert sec.model.get_data() == [
        *NFET_A_ROWS,
        {"reserved_key": "GATE", "cds_inst_term_name": "g_new"},
    ]
    assert sec.is_dirty()


# -- G12: Ctrl+E 는 Edit 버튼과 같은 경로 --------------------------------------


def test_ctrl_e_opens_the_edit_dialog_with_the_row_values(
    device_tab_ctrl, store, insert_dialog, qtbot
):
    sec = open_nfet_a(device_tab_ctrl, store, qtbot)
    sec.ui.table_view.selectRow(0)

    qtbot.keyClick(sec.ui, Qt.Key_E, Qt.ControlModifier)

    assert [(d["prefill"], d["window_title"]) for d in insert_dialog.created] == [
        ({"reserved_key": "DRN", "cds_inst_term_name": "d"}, "Edit")
    ]
    # 편집 창이 받은 값을 그대로 OK 하면 아무것도 바뀌지 않는다.
    assert sec.model.get_data() == NFET_A_ROWS
    assert not sec.is_dirty()


def test_ctrl_e_and_the_edit_button_open_the_same_dialog(
    device_tab_ctrl, store, insert_dialog, qtbot
):
    sec = open_nfet_a(device_tab_ctrl, store, qtbot)
    sec.ui.table_view.selectRow(1)

    qtbot.keyClick(sec.ui, Qt.Key_E, Qt.ControlModifier)
    sec.ui.edit_btn.click()

    by_key, by_button = insert_dialog.created
    assert by_key == by_button
    assert by_key["prefill"] == {"reserved_key": "GATE", "cds_inst_term_name": "g"}
    assert by_key["device_celltype"] == "NFET"


def test_ctrl_e_without_a_selection_does_nothing(
    device_tab_ctrl, store, insert_dialog, qtbot
):
    sec = open_nfet_a(device_tab_ctrl, store, qtbot)
    sec.ui.table_view.clearSelection()

    qtbot.keyClick(sec.ui, Qt.Key_E, Qt.ControlModifier)

    assert insert_dialog.created == []
