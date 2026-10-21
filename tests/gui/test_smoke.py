"""컨트롤러 fixture smoke: 띄우고, 읽고, 고치고, 바뀐 것을 알리고, 닫는다.

phase 3/4 의 RED 테스트가 쓰는 `device_tab_ctrl`/`main_window` fixture 와 헬퍼가 지금 코드에서
도는지만 본다. 저장·충돌·접속 실패·창 닫기 중 경로는 여기서 단언하지 않는다(그쪽 phase 의 몫).
"""

import copy

from gui_support.fakes import FakeDatabase
from gui_support.helpers import (
    edit_device_cell,
    edit_tab_cell,
    select_device_row,
    select_process,
)

WRITES = ("upsert_device", "upsert_devices", "replace_many_for_device")


def device_names(ctrl) -> list[str]:
    """device 표의 이름. 화면에 보이는 순서(정렬 proxy)다."""
    proxy = ctrl.ui.device_table_view.model()
    return [proxy.index(row, 0).data() for row in range(proxy.rowCount())]


def tab_pairs(ctrl, tab_name: str) -> list[tuple[str, ...]] | None:
    """탭 섹션 모델의 행(컬럼 순서의 값 튜플). 모델이 아직 없으면 None."""
    sec = ctrl.parameter_tab.section(tab_name)
    if sec is None or sec.model is None:
        return None
    return [tuple(row[c] for c in sec.columns) for row in sec.model.get_data()]


def store_pairs(store, table: str, device_id: int, columns: list[str]) -> list[tuple[str, ...]]:
    return [tuple(row[c] for c in columns) for row in store.rows(table, device_id)]


def call_names(store) -> list[str]:
    return [name for name, _ in store.calls]


def test_connecting_fills_the_process_list(device_tab_ctrl, store):
    ctrl = device_tab_ctrl
    assert ctrl.connected is True

    combo = ctrl.device_tab_toolbar.ui.process_selector
    assert [combo.itemText(i) for i in range(combo.count())] == ["sf2p", "sf4u"]
    assert combo.currentText() == "sf2p"
    assert device_names(ctrl) == ["nfet_a", "nfet_b"]

    names = call_names(store)
    assert "list_pairs" in names
    assert "fetch_devices_by_process" in names
    assert isinstance(ctrl.db, FakeDatabase)
    assert not ctrl.db.closed


def test_selecting_a_device_loads_its_tab_rows(device_tab_ctrl, store, qtbot):
    ctrl = device_tab_ctrl
    nfet_a = store.find_device("nfet_a")["id"]

    select_device_row(ctrl, 0)

    qtbot.waitUntil(lambda: len(tab_pairs(ctrl, "InstTerm") or []) == 4)
    terms = ctrl.parameter_tab.section("InstTerm")
    assert terms.device_id == nfet_a
    assert tab_pairs(ctrl, "InstTerm") == store_pairs(store, "inst_terms", nfet_a, terms.columns)
    qtbot.waitUntil(lambda: len(tab_pairs(ctrl, "InstSchParam") or []) == 2)


def test_choosing_another_process_shows_its_devices(device_tab_ctrl, store, dialogs, qtbot):
    ctrl = device_tab_ctrl
    sf4u = store.find_device("pfet_a")["process_id"]

    select_process(ctrl, "sf4u")

    qtbot.waitUntil(lambda: device_names(ctrl) == ["pfet_a"])
    assert ctrl.device_table.current_process_id == sf4u
    assert [shown for shown in dialogs.shown if shown[0] == "question"] == []


def test_an_edit_marks_the_screen_dirty_without_writing(device_tab_ctrl, store, qtbot):
    ctrl = device_tab_ctrl
    select_device_row(ctrl, 0)
    qtbot.waitUntil(lambda: len(tab_pairs(ctrl, "InstTerm") or []) == 4)
    before = copy.deepcopy((store.processes, store.devices, store.tab_rows))

    edit_device_cell(ctrl, 0, "description", "edited")
    assert ctrl.device_table.is_dirty()

    edit_tab_cell(ctrl, "InstTerm", 0, "cds_inst_term_name", "dd")
    assert ctrl.parameter_tab.is_dirty()

    assert [name for name in call_names(store) if name in WRITES] == []
    assert (store.processes, store.devices, store.tab_rows) == before


def test_a_poll_without_changes_keeps_the_banner_hidden(device_tab_ctrl, store, qtbot):
    ctrl = device_tab_ctrl
    n = len(store.calls_of("etag"))

    ctrl._poll_remote_changes()

    # 워커 스레드의 폴링과 GUI 스레드의 결과 슬롯이 끝나기를 기다린다("아무 일도 없음"의 모양).
    qtbot.waitUntil(lambda: len(store.calls_of("etag")) == n + 1 and ctrl._poll_task is None)
    assert ctrl.ui.refresh_banner.isHidden()


def test_another_users_save_shows_the_banner(device_tab_ctrl, store, qtbot):
    ctrl = device_tab_ctrl
    nfet_a = store.find_device("nfet_a")["id"]
    fetches = len(store.calls_of("fetch_devices_by_process"))
    banner = ctrl.ui.refresh_banner

    store.touch_device(nfet_a, actor="kim")
    ctrl._poll_remote_changes()

    qtbot.waitUntil(lambda: not banner.isHidden() and ctrl._poll_task is None)
    assert "kim" in banner.label.text()
    # 자동으로 다시 읽지 않는다(ADR-004).
    assert len(store.calls_of("fetch_devices_by_process")) == fetches


def test_a_failing_call_is_reported(device_tab_ctrl, store, dialogs):
    ctrl = device_tab_ctrl
    store.fail_next("list_pairs", RuntimeError("boom"))

    ctrl.device_tab_toolbar.refresh_processes()

    kind, title, text = dialogs.shown[-1]
    assert (kind, title) == ("error", "Process List Failed")
    assert "boom" in text


def test_the_main_window_starts_and_shuts_down_cleanly(main_window, store, dialogs):
    tab = main_window.device_tab
    assert tab.connected is True
    assert dialogs.shown == []
    assert main_window.history_tab is None

    db = tab.db
    main_window.shutdown()

    assert db.closed
    assert tab.db is None
    assert tab.connected is False
    assert "db.close" in call_names(store)
