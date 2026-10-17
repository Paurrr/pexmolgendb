"""탭 하나의 행 읽기가 실패했을 때 (phase 4 step 0).

device 를 바꿀 때 `TabSectionController.update_model` 의 `fetch_by_device` 가 실패하면 그 탭은
이전 device 의 모델을 붙인 채 새 device 의 탭으로 취급됐다. 그 상태로 고치고 저장하면 이전
device 의 행이 새 device 에 통째로 써진다.

불변식: `update_model()` 이 끝나면 `model` 은 지금 device 에 대해 이번에 새로 읽은 모델
(`model_by_device[device_id]`)이거나 None 이고, 표는 항상 `model` 과 같다. None 이면 dirty 가
아니라서 저장 대상에서 빠진다. 실패는 지금처럼 "Load Failed" 로 보인다.
"""

from gui_support.helpers import edit_tab_cell, select_device_row, select_process

from genviewer.dialogs.conflict import RELOAD
from genviewer.service.errors import DbUnavailableError

# 실패시킬 탭. `_sections` 순서상 첫 탭이라 fail_next 가 이 탭의 읽기를 친다.
FAILING = "SuffixCellName"
TABLE = "suffix_cell_name"
COLUMN = "suffix_cell_name"
ROWS_A = [{COLUMN: "_a"}]
ROWS_B = [{COLUMN: "_b1"}, {COLUMN: "_b2"}]


def device_id(store, name: str) -> int:
    return store.find_device(name)["id"]


def stored(store, sec, device: int) -> list[dict]:
    """store 에 있는 그 탭의 행을 화면 모델 모양(그 탭의 컬럼만)으로."""
    return [{c: r[c] for c in sec.columns} for r in store.rows(sec.table_name, device)]


def load_failures(dialogs) -> list[tuple[str, str, str]]:
    return [shown for shown in dialogs.shown if shown[:2] == ("error", "Load Failed")]


def seed_failing_tab(store) -> None:
    """실패시킬 탭에서 nfet_a 와 nfet_b 가 서로 다른 행을 갖게 한다(시드에는 이 탭 행이 없다)."""
    store.set_rows(TABLE, device_id(store, "nfet_a"), ROWS_A)
    store.set_rows(TABLE, device_id(store, "nfet_b"), ROWS_B)


def open_device(ctrl, store, qtbot, row: int, name: str) -> int:
    """device 표의 row 행(name)을 골라 모든 탭이 그 device 로 옮겨 갈 때까지 기다린다."""
    target = device_id(store, name)
    select_device_row(ctrl, row)
    sections = ctrl.parameter_tab._sections.values()
    qtbot.waitUntil(lambda: all(sec.device_id == target for sec in sections))
    return target


def open_nfet_a(ctrl, store, qtbot) -> int:
    seed_failing_tab(store)
    select_process(ctrl, "sf2p")
    assert next(iter(ctrl.parameter_tab._sections)) == FAILING
    return open_device(ctrl, store, qtbot, 0, "nfet_a")


def open_nfet_b_with_edit(ctrl, store, qtbot) -> int:
    """nfet_a → nfet_b 를 정상으로 읽고, nfet_b 의 실패시킬 탭 0행을 고친다."""
    open_nfet_a(ctrl, store, qtbot)
    nfet_b = open_device(ctrl, store, qtbot, 1, "nfet_b")
    sec = ctrl.parameter_tab.section(FAILING)
    assert sec.model.get_data() == ROWS_B
    edit_tab_cell(ctrl, FAILING, 0, COLUMN, "_edited")
    assert sec.is_dirty()
    return nfet_b


def assert_failed_section_is_empty(ctrl, device: int) -> None:
    sec = ctrl.parameter_tab.section(FAILING)
    assert sec.device_id == device
    assert sec.model is None
    assert sec.ui.table_view.model() is None
    assert sec.is_dirty() is False
    assert not ctrl.parameter_tab.is_dirty()
    tab = ctrl.parameter_tab.ui
    assert not tab.tabText(tab.find_tab(FAILING)).endswith(" *")


def test_a_failed_load_leaves_the_tab_empty_instead_of_the_previous_device(
    device_tab_ctrl, store, dialogs, qtbot
):
    ctrl = device_tab_ctrl
    open_nfet_a(ctrl, store, qtbot)
    nfet_b = device_id(store, "nfet_b")
    store.fail_next("fetch_by_device", DbUnavailableError("down"))

    open_device(ctrl, store, qtbot, 1, "nfet_b")

    for name, sec in ctrl.parameter_tab._sections.items():
        assert sec.device_id == nfet_b, name
        assert sec.model is None or sec.model is sec.model_by_device[nfet_b], name
        assert sec.ui.table_view.model() is sec.model, name
    failed = [n for n, sec in ctrl.parameter_tab._sections.items() if sec.model is None]
    assert failed == [FAILING]
    assert_failed_section_is_empty(ctrl, nfet_b)
    assert len(load_failures(dialogs)) == 1
    for name, sec in ctrl.parameter_tab._sections.items():
        if name != FAILING:
            assert sec.model.get_data() == stored(store, sec, nfet_b), name


def test_editing_and_saving_after_a_failed_load_does_not_write_the_previous_device_rows(
    device_tab_ctrl, store, dialogs, qtbot
):
    ctrl = device_tab_ctrl
    nfet_a = open_nfet_a(ctrl, store, qtbot)
    nfet_b = device_id(store, "nfet_b")
    store.fail_next("fetch_by_device", DbUnavailableError("down"))
    open_device(ctrl, store, qtbot, 1, "nfet_b")
    sec = ctrl.parameter_tab.section(FAILING)

    # 수정 전에는 표에 nfet_a 의 모델이 붙어 있어 고칠 수 있었다. 수정 뒤에는 표가 비어 있다.
    if sec.ui.table_view.model() is not None:
        edit_tab_cell(ctrl, FAILING, 0, COLUMN, "_edited")

    assert ctrl.parameter_tab.save_all() is True

    assert store.rows(TABLE, nfet_b) == ROWS_B
    assert store.rows(TABLE, nfet_a) == ROWS_A
    written = [
        c for c in store.calls_of("replace_many_for_device") if TABLE in c["payload"]
    ]
    assert written == []
    assert len(load_failures(dialogs)) == 1


def test_a_failed_reload_after_a_conflict_drops_the_edits_instead_of_keeping_them(
    device_tab_ctrl, store, dialogs, qtbot
):
    ctrl = device_tab_ctrl
    nfet_b = open_nfet_b_with_edit(ctrl, store, qtbot)
    store.touch_device(nfet_b, actor="bob")
    dialogs.answer_conflict(RELOAD)
    store.fail_next("fetch_by_device", DbUnavailableError("down"))

    assert ctrl.parameter_tab.save_all() is False

    assert [shown[0] for shown in dialogs.shown].count("conflict") == 1
    assert len(load_failures(dialogs)) == 1
    assert_failed_section_is_empty(ctrl, nfet_b)
    # 다시 저장해도 None.get_data() 로 죽지 않고, 쓸 것이 없다.
    assert ctrl.parameter_tab.save_all() is True
    assert len(store.calls_of("replace_many_for_device")) == 1
    assert store.rows(TABLE, nfet_b) == ROWS_B


def test_a_failed_reload_while_discarding_drops_the_edits_instead_of_keeping_them(
    device_tab_ctrl, store, dialogs, qtbot
):
    ctrl = device_tab_ctrl
    nfet_b = open_nfet_b_with_edit(ctrl, store, qtbot)
    store.fail_next("fetch_by_device", DbUnavailableError("down"))

    ctrl.parameter_tab.discard_all()

    assert len(load_failures(dialogs)) == 1
    assert_failed_section_is_empty(ctrl, nfet_b)
    assert ctrl.parameter_tab.save_all() is True
    assert store.calls_of("replace_many_for_device") == []
    assert store.rows(TABLE, nfet_b) == ROWS_B


def test_pasting_into_a_device_whose_tab_failed_to_load_skips_only_that_tab(
    device_tab_ctrl, store, dialogs, qtbot
):
    ctrl = device_tab_ctrl
    nfet_a = open_nfet_a(ctrl, store, qtbot)
    nfet_b = device_id(store, "nfet_b")
    terms_before = store.rows("inst_terms", nfet_b)
    pasted_terms = [{"reserved_key": "BULK", "cds_inst_term_name": "b2"}]
    store.fail_next("fetch_by_device", DbUnavailableError("down"))

    ctrl.parameter_tab.paste_payload(
        nfet_b,
        "NFET",
        {FAILING: [{COLUMN: "_pasted"}], "InstTerm": pasted_terms},
        store.find_device("nfet_b")["version"],
    )

    assert len(load_failures(dialogs)) == 1
    assert store.rows(TABLE, nfet_b) == ROWS_B
    assert store.rows(TABLE, nfet_a) == ROWS_A
    assert store.rows("inst_terms", nfet_b) == pasted_terms + terms_before
    calls = store.calls_of("replace_many_for_device")
    assert [(c["device_id"], sorted(c["payload"])) for c in calls] == [
        (nfet_b, ["inst_terms"])
    ]
    assert_failed_section_is_empty(ctrl, nfet_b)


def test_choosing_the_device_again_after_a_failed_load_reads_it(
    device_tab_ctrl, store, dialogs, qtbot
):
    ctrl = device_tab_ctrl
    open_nfet_a(ctrl, store, qtbot)
    store.fail_next("fetch_by_device", DbUnavailableError("down"))
    nfet_b = open_device(ctrl, store, qtbot, 1, "nfet_b")
    assert len(load_failures(dialogs)) == 1

    open_device(ctrl, store, qtbot, 0, "nfet_a")
    open_device(ctrl, store, qtbot, 1, "nfet_b")

    sec = ctrl.parameter_tab.section(FAILING)
    assert sec.model is sec.model_by_device[nfet_b]
    assert sec.ui.table_view.model() is sec.model
    assert sec.model.get_data() == ROWS_B == stored(store, sec, nfet_b)
    assert not sec.is_dirty()
    assert len(load_failures(dialogs)) == 1


def test_switching_devices_without_failures_loads_every_tab_of_the_new_device(
    device_tab_ctrl, store, dialogs, qtbot
):
    ctrl = device_tab_ctrl
    open_nfet_a(ctrl, store, qtbot)

    for row, name in ((1, "nfet_b"), (0, "nfet_a")):
        target = open_device(ctrl, store, qtbot, row, name)
        for tab, sec in ctrl.parameter_tab._sections.items():
            assert sec.model is sec.model_by_device[target], (name, tab)
            assert sec.ui.table_view.model() is sec.model, (name, tab)
            assert sec.model.get_data() == stored(store, sec, target), (name, tab)
            assert not sec.is_dirty(), (name, tab)
    assert ctrl.parameter_tab.section(FAILING).model.get_data() == ROWS_A
    assert load_failures(dialogs) == []
