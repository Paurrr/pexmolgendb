"""재접속·CSV 불러오기 전에 저장 안 한 편집을 묻는다 (phase 10 step 4, K36 승인).

재접속(Database → Connect…)은 `apply_db` 가 device 표를 다시 읽고 탭 섹션을 다시 만들어 device 표
편집도 탭 편집도 버린다. 그래서 둘 중 하나라도 dirty 면 새 DB 를 열기 전에 기존 "Refresh" 질문을
한다. CSV 불러오기는 끝에서 device 표만 다시 읽으므로 device 표가 dirty 일 때만 묻는다(탭 편집은
남는다, `test_process_list_refresh.py` 가 고정한다). 아니오면 아무것도 하지 않는다. DB 호출도 알림도
없고 지금 DB·repo·폴링·화면·편집이 그대로다.

질문은 `_on_connect`(Connect… 창의 입구)에서 한다. `connect_db` 는 첫 접속과 테스트가 직접 부르므로
묻지 않는다.
"""

from gui_support.helpers import edit_device_cell, edit_tab_cell, select_device_row

from genviewer.service.errors import DbUnavailableError

EDITED = "edited by tester"
TAB = "InstTerm"
COLUMN = "cds_inst_term_name"
EDITED_TAB = "dd"  # 시드 nfet_a 의 InstTerm 0행 값은 "d"
REFRESH = (
    "question",
    "Refresh",
    "You have unsaved changes.\nReloading from the server discards them. Continue?",
)
CSV_TEXT = (
    "CellType,CdsLibName,InstCellName,InstTerm\n"
    "PFET,sf9x,pfet_z,DRN d\n"
    "NFET,sf2p,nfet_c,DRN d\n"
)


def model_of(ctrl):
    return ctrl.device_table.ui.model_safe()


def edit_nfet_a_description(ctrl) -> None:
    """sf2p(접속하면 골라져 있다)의 nfet_a(0행) Description 을 고친다."""
    assert ctrl.device_table.current_process == "sf2p"
    assert model_of(ctrl).get_device(0)["name"] == "nfet_a"
    edit_device_cell(ctrl, 0, "description", EDITED)
    assert ctrl.device_table.is_dirty()


def edit_nfet_a_tab(ctrl, store, qtbot) -> None:
    """sf2p 의 nfet_a(0행)를 골라 InstTerm 0행 값을 고친다. device 행은 그대로다."""
    select_device_row(ctrl, 0)
    nfet_a = store.find_device("nfet_a")["id"]
    qtbot.waitUntil(lambda: ctrl.parameter_tab.section(TAB).device_id == nfet_a)
    qtbot.waitUntil(lambda: len(ctrl.parameter_tab.section(TAB).model.get_data()) == 4)
    edit_tab_cell(ctrl, TAB, 0, COLUMN, EDITED_TAB)
    assert ctrl.parameter_tab.is_dirty()
    assert not ctrl.device_table.is_dirty()


def tab_value(ctrl) -> str:
    return ctrl.parameter_tab.section(TAB).model.get_data()[0][COLUMN]


def write_csv(tmp_path) -> str:
    path = tmp_path / "in.csv"
    path.write_text(CSV_TEXT, encoding="utf-8", newline="")
    return str(path)


def reconnect(ctrl) -> None:
    """Connect… 창에서 확인한 것처럼 재접속을 요청한다."""
    ctrl.ui.dbConnectRequested.emit("")


# ----------------------------------------------------------------------
# 재접속
# ----------------------------------------------------------------------


def test_declining_a_reconnect_with_device_edits_keeps_everything(
    device_tab_ctrl, store, dialogs
):
    ctrl = device_tab_ctrl
    edit_nfet_a_description(ctrl)
    db1 = ctrl.db
    since = len(store.calls)
    shown = len(dialogs.shown)
    dialogs.answer_question(False)

    reconnect(ctrl)

    assert dialogs.shown[shown:] == [REFRESH]
    assert store.calls[since:] == []
    assert ctrl.db is db1
    assert ctrl.device_table.repo.db is db1
    assert ctrl._poll_timer.isActive()
    assert ctrl.device_table.is_dirty()
    assert model_of(ctrl).get_device(0)["description"] == EDITED


def test_declining_a_reconnect_with_only_tab_edits_keeps_them(
    device_tab_ctrl, store, dialogs, qtbot
):
    ctrl = device_tab_ctrl
    edit_nfet_a_tab(ctrl, store, qtbot)
    db1 = ctrl.db
    since = len(store.calls)
    shown = len(dialogs.shown)
    dialogs.answer_question(False)

    reconnect(ctrl)

    assert dialogs.shown[shown:] == [REFRESH]
    assert store.calls[since:] == []
    assert ctrl.db is db1
    assert ctrl.parameter_tab.repo.db is db1
    assert ctrl._poll_timer.isActive()
    assert ctrl.parameter_tab.is_dirty()
    assert tab_value(ctrl) == EDITED_TAB


def test_accepting_a_reconnect_drops_device_and_tab_edits(
    device_tab_ctrl, store, dialogs, qtbot
):
    ctrl = device_tab_ctrl
    edit_nfet_a_tab(ctrl, store, qtbot)
    edit_device_cell(ctrl, 0, "description", EDITED)
    assert ctrl.device_table.is_dirty()
    db1 = ctrl.db
    shown = len(dialogs.shown)
    dialogs.answer_question(True)

    reconnect(ctrl)

    assert dialogs.shown[shown:] == [
        REFRESH,
        ("info", "Connected", "Connected to the database."),
    ]
    assert ctrl.db is not db1
    assert ctrl.device_table.repo.db is ctrl.db
    assert not ctrl.device_table.is_dirty()
    assert not ctrl.parameter_tab.is_dirty()
    assert model_of(ctrl).get_device(0)["description"] == store.find_device("nfet_a")[
        "description"
    ]


def test_a_failed_reconnect_after_accepting_keeps_the_edits(device_tab_ctrl, store, dialogs):
    ctrl = device_tab_ctrl
    edit_nfet_a_description(ctrl)
    db1 = ctrl.db
    shown = len(dialogs.shown)
    store.fail_next("open_database", DbUnavailableError("boom"))
    dialogs.answer_question(True)

    reconnect(ctrl)

    assert dialogs.shown[shown:] == [
        REFRESH,
        ("error", "Connect Failed", "Could not connect to the database."),
    ]
    assert len(store.calls_of("open_database")) == 2  # 첫 접속 + 실패한 재접속
    assert ctrl.db is db1
    assert ctrl.device_table.repo.db is db1
    assert ctrl.device_table.is_dirty()
    assert model_of(ctrl).get_device(0)["description"] == EDITED


def test_a_reconnect_without_edits_does_not_ask(device_tab_ctrl, store, dialogs):
    ctrl = device_tab_ctrl
    db1 = ctrl.db
    shown = len(dialogs.shown)

    reconnect(ctrl)

    assert dialogs.shown[shown:] == [("info", "Connected", "Connected to the database.")]
    assert ctrl.db is not db1


# ----------------------------------------------------------------------
# CSV 불러오기
# ----------------------------------------------------------------------


def test_declining_a_csv_load_with_device_edits_keeps_them(
    device_tab_ctrl, store, dialogs, tmp_path
):
    ctrl = device_tab_ctrl
    edit_nfet_a_description(ctrl)
    path = write_csv(tmp_path)
    since = len(store.calls)
    shown = len(dialogs.shown)
    dialogs.answer_question(False)

    ctrl.on_load_csv_requested(path)

    assert dialogs.shown[shown:] == [REFRESH]
    assert store.calls[since:] == []
    assert store.calls_of("import_data") == []
    assert ctrl.device_table.is_dirty()
    assert model_of(ctrl).get_device(0)["description"] == EDITED
    assert [d["name"] for d in model_of(ctrl).get_devices()] == ["nfet_a", "nfet_b"]


def test_accepting_a_csv_load_rereads_the_device_table(
    device_tab_ctrl, store, dialogs, tmp_path
):
    ctrl = device_tab_ctrl
    edit_nfet_a_description(ctrl)
    path = write_csv(tmp_path)
    shown = len(dialogs.shown)
    dialogs.answer_question(True)

    ctrl.on_load_csv_requested(path)

    assert [title for _kind, title, _text in dialogs.shown[shown:]] == ["Refresh", "Load CSV"]
    assert dialogs.shown[-1][0] == "info"
    assert len(store.calls_of("import_data")) == 1
    assert not ctrl.device_table.is_dirty()
    devices = {d["name"]: d for d in model_of(ctrl).get_devices()}
    assert sorted(devices) == ["nfet_a", "nfet_b", "nfet_c"]
    assert devices["nfet_a"]["description"] == store.find_device("nfet_a")["description"]


def test_a_failed_csv_load_after_accepting_keeps_the_device_edits(
    device_tab_ctrl, store, dialogs, tmp_path
):
    ctrl = device_tab_ctrl
    edit_nfet_a_description(ctrl)
    path = write_csv(tmp_path)
    shown = len(dialogs.shown)
    store.fail_next("import_data", RuntimeError("boom"))
    dialogs.answer_question(True)

    ctrl.on_load_csv_requested(path)

    assert [(kind, title) for kind, title, _text in dialogs.shown[shown:]] == [
        ("question", "Refresh"),
        ("error", "Load CSV Failed"),
    ]
    assert dialogs.shown[shown] == REFRESH
    assert ctrl.device_table.is_dirty()
    assert model_of(ctrl).get_device(0)["description"] == EDITED


def test_a_csv_load_without_a_database_warns_before_asking(
    device_tab_ctrl, store, dialogs, tmp_path
):
    ctrl = device_tab_ctrl
    edit_nfet_a_description(ctrl)
    path = write_csv(tmp_path)
    ctrl.close_db()
    since = len(store.calls)
    shown = len(dialogs.shown)

    ctrl.on_load_csv_requested(path)

    assert dialogs.shown[shown:] == [
        ("warning", "Database Not Loaded", "Connect to the database first.")
    ]
    assert store.calls[since:] == []
