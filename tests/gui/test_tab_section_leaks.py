"""탭 섹션이 device 를 고를 때마다 Qt 객체를 쌓지 않는다 (phase 12 step 5, K22).

`TabSectionController.bind_model` 은 device 를 고를 때마다(섹션마다) `table_view.setModel` 을
부른다. Qt 의 `setModel` 은 새 `QItemSelectionModel` 을 표의 자식으로 만들고 옛 것을 지우지 않아서,
고른 횟수만큼 쌓였다. 새 device 모델을 만들 때마다 콤보 컬럼마다 `ComboBoxDelegate` 를 새로 만들어
같은 컬럼에 다시 설치해서, 밀려난 delegate 도 섹션의 자식으로 본 device 수만큼 남았다.

불변식: 지연 삭제를 처리한 뒤 섹션의 selection model 수는 고른 횟수와 상관없이 같고, delegate 수는
콤보 컬럼 수를 넘지 않는다. 표의 지금 selection model 은 지우지 않는다. 콤보 후보는 여전히 그 모델의
celltype 을 따르고, required 표시는 모델마다 붙는다.
"""

import pytest
from gui_support.helpers import seeded_store, select_device_row, select_process
from PySide6.QtCore import QCoreApplication, QEvent, QItemSelectionModel, Qt
from PySide6.QtWidgets import QStyleOptionViewItem

from genviewer.config.config import delegate_config
from genviewer.delegates.combo_box import ComboBoxDelegate
from genviewer.service.errors import DbUnavailableError
from genviewer.utils.validators import allowed_items

TAB = "InstTerm"  # 콤보 컬럼(reserved_key)과 시드 행이 있는 탭
NAME = 0
# sf2p 에 더하는 device. (이름, celltype, InstTerm 의 reserved_key 한 행)
EXTRA_DEVICES = (
    ("nfet_c", "NFET", "DRN"),
    ("pfet_c", "PFET", "GATE"),
    ("res_c", "RESISTOR", "IN"),
    ("vncap_c", "VNCAP", "PLUS"),
    ("inv_c", "INV", "A"),
)
SF2P_DEVICES = ["nfet_a", "nfet_b", *(name for name, _, _ in EXTRA_DEVICES)]


@pytest.fixture
def store():
    """시드의 sf2p 끝에 celltype 이 서로 다른 device 다섯 개(각각 InstTerm 행 하나)를 더한다."""
    s = seeded_store()
    sf2p = s.find_device("nfet_a")["process_id"]
    for order, (name, celltype, key) in enumerate(EXTRA_DEVICES, start=2):
        device = s.add_device(sf2p, name, celltype, order=order)
        s.set_rows("inst_terms", device["id"], [{"reserved_key": key, "cds_inst_term_name": "x"}])
    return s


def combo_columns(sec) -> list[str]:
    cfg = delegate_config.get(sec.table_name, {})
    return [
        c for c in sec.columns
        if c in cfg and (cfg[c].get("items") or cfg[c].get("items_by_celltype"))
    ]


def required_columns(sec) -> list[str]:
    cfg = delegate_config.get(sec.table_name, {})
    return [c for c in sec.columns if cfg.get(c, {}).get("required", False)]


def flush_deletes() -> None:
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def selection_models(ctrl) -> dict[str, int]:
    """섹션마다 표의 자식 QItemSelectionModel 수(지연 삭제를 처리한 뒤)."""
    flush_deletes()
    return {
        name: len(sec.ui.table_view.findChildren(QItemSelectionModel))
        for name, sec in ctrl.parameter_tab._sections.items()
    }


def delegates(ctrl) -> dict[str, int]:
    """섹션마다 자식 ComboBoxDelegate 수(지연 삭제를 처리한 뒤)."""
    flush_deletes()
    return {
        name: len(sec.ui.findChildren(ComboBoxDelegate))
        for name, sec in ctrl.parameter_tab._sections.items()
    }


def row_of(ctrl, name: str) -> int:
    proxy = ctrl.ui.device_table_view.model()
    names = [proxy.index(r, NAME).data() for r in range(proxy.rowCount())]
    assert name in names, f"device 표에 {name!r} 가 없다: {names}"
    return names.index(name)


def open_device(ctrl, store, qtbot, name: str) -> int:
    """device 표에서 name 을 골라 모든 탭이 그 device 를 읽을 때까지 기다린다."""
    target = store.find_device(name)["id"]
    sections = list(ctrl.parameter_tab._sections.values())
    before = len(store.calls_of("fetch_by_device"))
    select_device_row(ctrl, row_of(ctrl, name))
    qtbot.waitUntil(
        lambda: all(sec.device_id == target for sec in sections)
        and len(store.calls_of("fetch_by_device")) >= before + len(sections)
    )
    return target


def open_sf2p(ctrl, store, qtbot) -> None:
    """sf2p 의 nfet_a 를 연다. 같은 행을 다시 고르면 탭을 다시 읽지 않아서 다음은 다른 device다."""
    select_process(ctrl, "sf2p")
    assert combo_columns(ctrl.parameter_tab.section(TAB)) == ["reserved_key"]
    open_device(ctrl, store, qtbot, "nfet_a")


def visit_sf2p(ctrl, store, qtbot):
    """sf2p 의 device 를 nfet_a 부터 하나씩 열고, 열 때마다 (이름, id) 를 낸다."""
    open_sf2p(ctrl, store, qtbot)
    yield "nfet_a", store.find_device("nfet_a")["id"]
    for name in SF2P_DEVICES[1:]:
        yield name, open_device(ctrl, store, qtbot, name)


def editor_items(sec, column: str) -> list[str]:
    """그 컬럼 0행을 편집할 때 표의 delegate 가 내놓는 콤보 후보."""
    view = sec.ui.table_view
    col = sec.columns.index(column)
    delegate = view.itemDelegateForColumn(col)
    assert isinstance(delegate, ComboBoxDelegate), (sec.table_name, column, delegate)
    index = sec.model.index(0, col)
    assert index.isValid()
    editor = delegate.createEditor(view.viewport(), QStyleOptionViewItem(), index)
    try:
        return [editor.itemText(i) for i in range(editor.count())]
    finally:
        editor.deleteLater()


def assert_selection_works(sec) -> None:
    """표의 selection model 이 살아 있고 지금 모델을 보며, 행을 고를 수 있다."""
    view = sec.ui.table_view
    sel = view.selectionModel()
    assert sel is not None
    assert sel.model() is sec.model
    view.clearSelection()
    view.selectRow(0)
    assert view._selected_rows() == [0]
    view.clearSelection()


def test_switching_devices_does_not_pile_up_selection_models(device_tab_ctrl, store, qtbot):
    ctrl = device_tab_ctrl
    open_sf2p(ctrl, store, qtbot)
    first = selection_models(ctrl)

    for _ in range(10):
        open_device(ctrl, store, qtbot, "nfet_b")
        open_device(ctrl, store, qtbot, "nfet_a")

    assert selection_models(ctrl) == first
    assert_selection_works(ctrl.parameter_tab.section(TAB))


def test_seeing_many_devices_does_not_pile_up_combo_delegates(device_tab_ctrl, store, qtbot):
    ctrl = device_tab_ctrl
    seen = [name for name, _ in visit_sf2p(ctrl, store, qtbot)]
    assert seen == SF2P_DEVICES

    counts = delegates(ctrl)
    limits = {name: len(combo_columns(sec)) for name, sec in ctrl.parameter_tab._sections.items()}
    assert {n: c for n, c in counts.items() if c > limits[n]} == {}
    assert counts[TAB] >= 1


def test_every_device_gets_the_combo_delegate_with_its_own_celltype_items(
    device_tab_ctrl, store, qtbot
):
    ctrl = device_tab_ctrl
    sec = ctrl.parameter_tab.section(TAB)
    cfg = delegate_config[sec.table_name]["reserved_key"]
    seen = {}

    for name, _ in visit_sf2p(ctrl, store, qtbot):
        celltype = store.find_device(name)["celltype"]
        for name_, other in ctrl.parameter_tab._sections.items():
            for column in combo_columns(other):
                col = other.columns.index(column)
                assert isinstance(
                    other.ui.table_view.itemDelegateForColumn(col), ComboBoxDelegate
                ), (name, name_, column)
        items = editor_items(sec, "reserved_key")
        assert items == allowed_items(cfg, celltype), name
        seen[celltype] = items

    # 섹션당 delegate 하나를 같이 써도 후보는 모델(device)마다 다르다.
    assert seen["NFET"] != seen["RESISTOR"]


def test_every_device_model_marks_its_required_columns(device_tab_ctrl, store, qtbot):
    ctrl = device_tab_ctrl

    for name, device in visit_sf2p(ctrl, store, qtbot):
        for tab, sec in ctrl.parameter_tab._sections.items():
            assert sec.model is sec.model_by_device[device], (name, tab)
            assert set(required_columns(sec)) <= sec.model.required_columns, (name, tab)

    sec = ctrl.parameter_tab.section(TAB)
    assert {"reserved_key", "cds_inst_term_name"} <= sec.model.required_columns


def test_reloading_the_same_device_keeps_the_current_selection_model(
    device_tab_ctrl, store, qtbot
):
    """같은 모델을 다시 붙이면 Qt 는 selection model 을 바꾸지 않는다. 그것은 지우면 안 된다."""
    ctrl = device_tab_ctrl
    open_sf2p(ctrl, store, qtbot)
    sec = ctrl.parameter_tab.section(TAB)
    current = sec.ui.table_view.selectionModel()
    first = selection_models(ctrl)

    sec.update_model()
    sec.update_model()

    assert selection_models(ctrl) == first
    assert sec.ui.table_view.selectionModel() is current
    assert_selection_works(sec)


def test_a_failed_load_and_a_good_one_after_it_do_not_pile_up_selection_models(
    device_tab_ctrl, store, dialogs, qtbot
):
    ctrl = device_tab_ctrl
    open_sf2p(ctrl, store, qtbot)
    first = selection_models(ctrl)
    store.fail_next("fetch_by_device", DbUnavailableError("down"))

    open_device(ctrl, store, qtbot, "nfet_b")
    failed = [n for n, sec in ctrl.parameter_tab._sections.items() if sec.model is None]
    assert len(failed) == 1
    assert ctrl.parameter_tab.section(failed[0]).ui.table_view.model() is None
    assert [s for s in dialogs.shown if s[:2] == ("error", "Load Failed")] != []
    after_failure = selection_models(ctrl)

    open_device(ctrl, store, qtbot, "nfet_a")

    assert after_failure == first
    assert selection_models(ctrl) == first
    sec = ctrl.parameter_tab.section(failed[0])
    assert sec.model is sec.model_by_device[store.find_device("nfet_a")["id"]]
    assert sec.ui.table_view.selectionModel() is not None
    assert sec.ui.table_view.selectionModel().model() is sec.model


def test_editing_a_combo_cell_still_goes_through_the_shared_delegate(
    device_tab_ctrl, store, qtbot
):
    """delegate 를 섹션마다 한 번만 둬도 편집 결과는 지금 모델에 들어가고 dirty 가 선다."""
    ctrl = device_tab_ctrl
    open_sf2p(ctrl, store, qtbot)
    open_device(ctrl, store, qtbot, "res_c")
    sec = ctrl.parameter_tab.section(TAB)
    view = sec.ui.table_view
    col = sec.columns.index("reserved_key")
    index = sec.model.index(0, col)
    delegate = view.itemDelegateForColumn(col)
    editor = delegate.createEditor(view.viewport(), QStyleOptionViewItem(), index)
    try:
        delegate.setEditorData(editor, index)
        editor.setCurrentText("OUT")
        delegate.setModelData(editor, sec.model, index)
    finally:
        editor.deleteLater()

    assert sec.model.data(index, Qt.EditRole) == "OUT"
    assert sec.is_dirty()
