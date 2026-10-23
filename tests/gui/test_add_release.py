"""`+` 가 (이름, 버전) 쌍을 만들고, 원하면 기존 쌍에서 복제한다 (phase 19 step 9).

만들기 전에 저장 안 한 편집을 묻는다(기존 "Save Changes"). 저장이 취소·실패하면 아무것도 만들지
않는다(2026-10-21 승인한 변경. 예전에는 만들고 고르지만 않았다). 아니오면 만들기에 성공한 뒤,
새 쌍으로 넘어가기 전에 편집을 버린다. 그래서 질문은 한 번이고, 만들기가 실패하면 편집이 남는다.
만들기·복제는 `run_blocking` 의 워커에서 돈다.
"""

import threading

import pytest
from gui_support.fakes import FakeProcessRepository
from gui_support.helpers import edit_device_cell, edit_tab_cell, select_device_row

from genviewer.controllers.device_tab_toolbar import DeviceTabToolBarController
from genviewer.dialogs.add_process import AddProcessDialog
from genviewer.dialogs.conflict import CANCEL
from genviewer.service.errors import user_message
from genviewer.views.device_tab_toolbar import DeviceTabToolBar

V2 = "V2"
TAB = "InstTerm"
TABLE = "inst_terms"
COLUMN = "cds_inst_term_name"
EDITED_DESCRIPTION = "edited by tester"
EDITED_TAB = "dd"
SAVE_CHANGES = (
    "question",
    "Save Changes",
    "You have unsaved changes. Do you want to save them?",
)


def toolbar(ctrl):
    return ctrl.device_tab_toolbar.ui


def current(ctrl) -> tuple:
    dt = ctrl.device_table
    return (dt.current_process, dt.current_release, dt.current_process_id)


def device_names(ctrl) -> list[str]:
    return [d["name"] for d in ctrl.device_table.ui.model_safe().get_devices()]


def pid(store, name: str, release: str = "") -> int | None:
    found = [p for p, n in store.processes.items() if n == name and store.releases[p] == release]
    return found[0] if found else None


def pairs_of(store) -> list[tuple[str, str]]:
    return sorted((n, store.releases[p]) for p, n in store.processes.items())


def record_process_changes(ctrl) -> list[tuple[str, str]]:
    changes: list[tuple[str, str]] = []
    ctrl.device_tab_toolbar.processChanged.connect(
        lambda name, release: changes.append((name, release))
    )
    return changes


def record_logs(ctrl) -> list[str]:
    logs: list[str] = []
    ctrl.logRequested.connect(logs.append)
    return logs


def record_threads(monkeypatch, method: str) -> list[threading.Thread]:
    """가짜 ProcessRepository 의 method 가 돈 스레드를 모은다."""
    threads: list[threading.Thread] = []
    original = getattr(FakeProcessRepository, method)

    def spy(self, *args, **kwargs):
        threads.append(threading.current_thread())
        return original(self, *args, **kwargs)

    monkeypatch.setattr(FakeProcessRepository, method, spy)
    return threads


def call_names(store, since: int = 0) -> list[str]:
    return [name for name, _args in store.calls[since:]]


def made_calls(store, since: int = 0) -> list[str]:
    return [name for name in call_names(store, since) if name in ("add", "clone")]


def notices(dialogs, title: str) -> list[tuple[str, str, str]]:
    return [shown for shown in dialogs.shown if shown[1] == title]


def edit_nfet_a_description(ctrl) -> None:
    assert ctrl.device_table.ui.model_safe().get_device(0)["name"] == "nfet_a"
    edit_device_cell(ctrl, 0, "description", EDITED_DESCRIPTION)
    assert ctrl.device_table.is_dirty()


def edit_nfet_b_tab(ctrl, store, qtbot) -> None:
    """sf2p 의 nfet_b(1행) InstTerm 0행을 고친다. device 행은 그대로다."""
    select_device_row(ctrl, 1)
    nfet_b = store.find_device("nfet_b")["id"]
    qtbot.waitUntil(lambda: ctrl.parameter_tab.section(TAB).device_id == nfet_b)
    qtbot.waitUntil(lambda: len(ctrl.parameter_tab.section(TAB).model.get_data()) == 2)
    edit_tab_cell(ctrl, TAB, 0, COLUMN, EDITED_TAB)
    assert ctrl.parameter_tab.is_dirty()


def assert_stayed_with_the_edits(ctrl, store, changes) -> None:
    """sf2p 빈 버전 그대로이고 nfet_a 의 Description 편집이 화면에 남아 있다."""
    assert toolbar(ctrl).current_pair() == ("sf2p", "")
    assert current(ctrl) == ("sf2p", "", pid(store, "sf2p"))
    assert ctrl.device_table.is_dirty()
    assert ctrl.device_table.ui.model_safe().get_device(0)["description"] == EDITED_DESCRIPTION
    assert changes == []


# -- 만들기 ----------------------------------------------------------------------------


def test_adding_a_release_makes_the_pair_and_moves_to_it(
    device_tab_ctrl, store, dialogs, qtbot, monkeypatch
):
    ctrl = device_tab_ctrl
    threads = record_threads(monkeypatch, "add")
    changes = record_process_changes(ctrl)
    logs = record_logs(ctrl)

    ctrl.device_tab_toolbar.add_process("sf2p", V2)

    v2 = pid(store, "sf2p", V2)
    assert v2 is not None
    assert store.calls_of("add") == [{"name": "sf2p", "release": V2, "actor": "tester"}]
    assert store.calls_of("clone") == []
    # 워커에서 돌았다(run_blocking).
    assert len(threads) == 1 and threads[0] is not threading.main_thread()
    qtbot.waitUntil(lambda: current(ctrl) == ("sf2p", V2, v2))
    assert toolbar(ctrl).current_pair() == ("sf2p", V2)
    assert ("sf2p", V2) in toolbar(ctrl).pairs()
    assert device_names(ctrl) == []
    assert changes == [("sf2p", V2)]
    assert notices(dialogs, "Success") == [("info", "Success", "Process 'sf2p V2' added.")]
    assert "Process added: sf2p V2." in logs
    assert SAVE_CHANGES not in dialogs.shown


def test_adding_without_a_release_keeps_the_old_lines(
    device_tab_ctrl, store, dialogs, qtbot
):
    ctrl = device_tab_ctrl
    logs = record_logs(ctrl)

    ctrl.device_tab_toolbar.add_process("new_p")

    assert store.calls_of("add") == [{"name": "new_p", "release": "", "actor": "tester"}]
    qtbot.waitUntil(lambda: ctrl.device_table.current_process == "new_p")
    assert toolbar(ctrl).current_pair() == ("new_p", "")
    assert notices(dialogs, "Success") == [("info", "Success", "Process 'new_p' added.")]
    assert "Process added: new_p." in logs


def test_cloning_a_release_copies_the_devices_and_their_tab_rows(
    device_tab_ctrl, store, dialogs, qtbot, monkeypatch
):
    ctrl = device_tab_ctrl
    threads = record_threads(monkeypatch, "clone")
    logs = record_logs(ctrl)
    originals = {d: store.find_device(d)["id"] for d in ("nfet_a", "nfet_b")}

    ctrl.device_tab_toolbar.add_process("sf2p", V2, ("sf2p", ""))

    assert store.calls_of("clone") == [
        {
            "src_name": "sf2p",
            "src_release": "",
            "name": "sf2p",
            "release": V2,
            "actor": "tester",
        }
    ]
    assert store.calls_of("add") == []
    assert len(threads) == 1 and threads[0] is not threading.main_thread()
    v2 = pid(store, "sf2p", V2)
    qtbot.waitUntil(lambda: current(ctrl) == ("sf2p", V2, v2))
    assert device_names(ctrl) == ["nfet_a", "nfet_b"]
    copies = {d["name"]: d["id"] for d in ctrl.device_table.ui.model_safe().get_devices()}
    assert set(copies.values()).isdisjoint(originals.values())
    for name, original in originals.items():
        for table in (TABLE, "inst_sch_params"):
            assert store.tab_rows[table][copies[name]] == store.tab_rows[table][original]
    assert notices(dialogs, "Success") == [
        ("info", "Success", "Process 'sf2p V2' added.\nsf2p 에서 device 2개를 복사했다.")
    ]
    assert "Process added: sf2p V2 (from sf2p, device 2)." in logs

    # 탭에도 복사한 행이 보인다.
    select_device_row(ctrl, 0)
    qtbot.waitUntil(lambda: ctrl.parameter_tab.section(TAB).device_id == copies["nfet_a"])
    qtbot.waitUntil(lambda: ctrl.parameter_tab.section(TAB).model is not None)
    rows = ctrl.parameter_tab.section(TAB).model.get_data()
    assert [r["reserved_key"] for r in rows] == ["DRN", "GATE", "SRC", "BULK"]


def test_cloning_from_a_release_names_it(device_tab_ctrl, store, dialogs, qtbot):
    ctrl = device_tab_ctrl
    src = store.add_process("sf2p", release=V2)
    store.add_device(src, "nfet_v2", "NFET", order=0)
    logs = record_logs(ctrl)

    ctrl.device_tab_toolbar.add_process("sf9x", "", ("sf2p", V2))

    qtbot.waitUntil(lambda: ctrl.device_table.current_process == "sf9x")
    assert toolbar(ctrl).current_pair() == ("sf9x", "")
    assert device_names(ctrl) == ["nfet_v2"]
    assert notices(dialogs, "Success") == [
        ("info", "Success", "Process 'sf9x' added.\nsf2p V2 에서 device 1개를 복사했다.")
    ]
    assert "Process added: sf9x (from sf2p V2, device 1)." in logs


@pytest.mark.parametrize("source", [None, ("sf2p", "")], ids=["add", "clone"])
def test_adding_an_existing_pair_warns_and_moves_to_it(
    device_tab_ctrl, store, dialogs, qtbot, source
):
    ctrl = device_tab_ctrl
    # 남이 먼저 만들었다. 이 창의 목록에는 아직 없다.
    v2 = store.add_process("sf2p", release=V2)
    store.add_device(v2, "theirs", "NFET", order=0)
    assert ("sf2p", V2) not in toolbar(ctrl).pairs()

    ctrl.device_tab_toolbar.add_process("sf2p", V2, source)

    assert dialogs.shown[-1] == ("warning", "Duplicate", "Process 'sf2p V2' already exists.")
    assert notices(dialogs, "Success") == []
    qtbot.waitUntil(lambda: current(ctrl) == ("sf2p", V2, v2))
    assert device_names(ctrl) == ["theirs"]
    assert [d["name"] for d in store.devices.values() if d["process_id"] == v2] == ["theirs"]


def test_without_a_database_nothing_is_asked_or_made(qtbot, dialogs):
    ui = DeviceTabToolBar()
    qtbot.addWidget(ui)
    ctrl = DeviceTabToolBarController(ui)
    asked: list[bool] = []
    ctrl.set_add_guard(lambda: asked.append(True) or True)
    ctrl.notifyRequested.connect(dialogs.record_notify)

    ctrl.add_process("sf2p", V2, ("sf2p", ""))

    assert dialogs.shown == [("warning", "Database Not Loaded", "먼저 DB를 Load 해야 합니다.")]
    assert asked == []


# -- 저장 안 한 편집 --------------------------------------------------------------------


@pytest.mark.parametrize("source", [None, ("sf2p", "")], ids=["add", "clone"])
def test_cancelling_the_save_makes_nothing(device_tab_ctrl, store, dialogs, qtbot, source):
    ctrl = device_tab_ctrl
    edit_nfet_a_description(ctrl)
    store.touch_device(store.find_device("nfet_a")["id"], actor="bob")
    changes = record_process_changes(ctrl)
    since = len(store.calls)
    dialogs.answer_question(True)
    dialogs.answer_conflict(CANCEL)

    ctrl.device_tab_toolbar.add_process("sf2p", V2, source)

    assert store.calls_of("upsert_devices") != []
    assert made_calls(store, since) == []
    assert "list_pairs" not in call_names(store, since)
    assert pid(store, "sf2p", V2) is None
    assert ("sf2p", V2) not in toolbar(ctrl).pairs()
    assert_stayed_with_the_edits(ctrl, store, changes)
    # 질문 한 번, 충돌 한 번. 알림은 없다.
    assert [shown[0] for shown in dialogs.shown] == ["question", "conflict"]
    assert dialogs.shown[0] == SAVE_CHANGES


def test_a_failed_save_makes_nothing(device_tab_ctrl, store, dialogs, qtbot):
    ctrl = device_tab_ctrl
    edit_nfet_a_description(ctrl)
    store.fail_next("upsert_devices", RuntimeError("save broke"))
    changes = record_process_changes(ctrl)
    since = len(store.calls)
    dialogs.answer_question(True)

    ctrl.device_tab_toolbar.add_process("sf2p", V2, ("sf2p", ""))

    assert made_calls(store, since) == []
    assert pid(store, "sf2p", V2) is None
    assert_stayed_with_the_edits(ctrl, store, changes)
    assert [title for _kind, title, _text in dialogs.shown] == [
        "Save Changes",
        "Save Devices Failed",
    ]


def test_a_tab_conflict_cancelled_before_cloning_keeps_the_tab_edits(
    device_tab_ctrl, store, dialogs, qtbot
):
    ctrl = device_tab_ctrl
    edit_nfet_b_tab(ctrl, store, qtbot)
    store.touch_device(store.find_device("nfet_b")["id"], actor="bob")
    since = len(store.calls)
    dialogs.answer_question(True)
    dialogs.answer_conflict(CANCEL)

    ctrl.device_tab_toolbar.add_process("sf2p", V2, ("sf2p", ""))

    assert made_calls(store, since) == []
    assert ctrl.parameter_tab.is_dirty()
    assert ctrl.parameter_tab.section(TAB).model.get_data()[0][COLUMN] == EDITED_TAB
    assert toolbar(ctrl).current_pair() == ("sf2p", "")
    assert dialogs.shown.count(SAVE_CHANGES) == 1


def test_answering_yes_saves_before_cloning_so_the_copy_has_the_edit(
    device_tab_ctrl, store, dialogs, qtbot
):
    ctrl = device_tab_ctrl
    edit_nfet_a_description(ctrl)
    since = len(store.calls)
    dialogs.answer_question(True)

    ctrl.device_tab_toolbar.add_process("sf2p", V2, ("sf2p", ""))

    names = call_names(store, since)
    assert names.index("upsert_devices") < names.index("clone")
    v2 = pid(store, "sf2p", V2)
    qtbot.waitUntil(lambda: current(ctrl) == ("sf2p", V2, v2))
    copy = ctrl.device_table.ui.model_safe().get_device(0)
    assert (copy["name"], copy["description"]) == ("nfet_a", EDITED_DESCRIPTION)
    assert store.find_device("nfet_a")["description"] == EDITED_DESCRIPTION
    assert dialogs.shown.count(SAVE_CHANGES) == 1
    assert not ctrl.device_table.is_dirty()


@pytest.mark.parametrize("source", [None, ("sf2p", "")], ids=["add", "clone"])
def test_answering_no_makes_the_pair_drops_the_edits_and_asks_once(
    device_tab_ctrl, store, dialogs, qtbot, source
):
    ctrl = device_tab_ctrl
    edit_nfet_b_tab(ctrl, store, qtbot)
    edit_nfet_a_description(ctrl)
    changes = record_process_changes(ctrl)
    since = len(store.calls)
    dialogs.answer_question(False)

    ctrl.device_tab_toolbar.add_process("sf2p", V2, source)

    v2 = pid(store, "sf2p", V2)
    assert v2 is not None
    qtbot.waitUntil(lambda: current(ctrl) == ("sf2p", V2, v2))
    assert changes == [("sf2p", V2)]
    assert dialogs.shown.count(SAVE_CHANGES) == 1
    assert "upsert_devices" not in call_names(store, since)
    assert "replace_many_for_device" not in call_names(store, since)
    assert store.find_device("nfet_a")["description"] == ""
    assert not ctrl.device_table.is_dirty()
    assert not ctrl.parameter_tab.is_dirty()
    # 복제는 저장된 내용(편집 전)을 복사했다.
    if source is not None:
        assert device_names(ctrl) == ["nfet_a", "nfet_b"]
        assert ctrl.device_table.ui.model_safe().get_device(0)["description"] == ""

    # 돌아가도 묻지 않는다. 버린 편집은 남아 있지 않다.
    toolbar(ctrl).select_pair("sf2p", "")
    qtbot.waitUntil(lambda: current(ctrl) == ("sf2p", "", pid(store, "sf2p")))
    assert dialogs.shown.count(SAVE_CHANGES) == 1
    assert ctrl.device_table.ui.model_safe().get_device(0)["description"] == ""


@pytest.mark.parametrize(
    ("source", "method", "exc"),
    [
        (None, "add", RuntimeError("add broke")),
        (("sf2p", ""), "clone", RuntimeError("clone broke")),
        (("sf2p", ""), "clone", LookupError("Source process not found: sf2p")),
    ],
    ids=["add", "clone", "missing-source"],
)
def test_answering_no_keeps_the_edits_when_making_fails(
    device_tab_ctrl, store, dialogs, qtbot, source, method, exc
):
    ctrl = device_tab_ctrl
    edit_nfet_a_description(ctrl)
    store.fail_next(method, exc)
    changes = record_process_changes(ctrl)
    since = len(store.calls)
    dialogs.answer_question(False)

    ctrl.device_tab_toolbar.add_process("sf2p", V2, source)

    assert made_calls(store, since) == [method]
    assert pid(store, "sf2p", V2) is None
    assert notices(dialogs, "Process Add Failed") == [
        ("error", "Process Add Failed", user_message(exc))
    ]
    assert notices(dialogs, "Success") == []
    assert ("sf2p", V2) not in toolbar(ctrl).pairs()
    assert_stayed_with_the_edits(ctrl, store, changes)
    assert dialogs.shown.count(SAVE_CHANGES) == 1


def test_a_missing_source_reports_and_makes_nothing(device_tab_ctrl, store, dialogs, qtbot):
    ctrl = device_tab_ctrl

    ctrl.device_tab_toolbar.add_process("sf2p", V2, ("sf9q", "V1"))

    assert pid(store, "sf2p", V2) is None
    missing = LookupError("Source process not found: sf9q V1")
    assert notices(dialogs, "Process Add Failed") == [
        ("error", "Process Add Failed", user_message(missing))
    ]
    assert toolbar(ctrl).current_pair() == ("sf2p", "")


# -- + 버튼 ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("answer", "made"),
    [
        (("sf2p", V2, None), {"add": [{"name": "sf2p", "release": V2, "actor": "tester"}]}),
        (
            ("sf9x", "", ("sf2p", "")),
            {
                "clone": [
                    {
                        "src_name": "sf2p",
                        "src_release": "",
                        "name": "sf9x",
                        "release": "",
                        "actor": "tester",
                    }
                ]
            },
        ),
    ],
    ids=["add", "clone"],
)
def test_the_plus_button_makes_what_the_window_gives(
    device_tab_ctrl, store, qtbot, monkeypatch, answer, made
):
    ctrl = device_tab_ctrl
    monkeypatch.setattr(toolbar(ctrl), "_ask_add_pair", lambda: answer)

    toolbar(ctrl).add_process_btn.click()

    for method, calls in made.items():
        assert store.calls_of(method) == calls
    qtbot.waitUntil(lambda: toolbar(ctrl).current_pair() == answer[:2])
    assert current(ctrl)[:2] == answer[:2]


def test_the_plus_button_does_nothing_when_the_window_is_cancelled(
    device_tab_ctrl, store, dialogs, monkeypatch
):
    ctrl = device_tab_ctrl
    monkeypatch.setattr(toolbar(ctrl), "_ask_add_pair", lambda: None)
    since = len(store.calls)
    shown = list(dialogs.shown)

    toolbar(ctrl).add_process_btn.click()

    assert store.calls[since:] == []
    assert dialogs.shown == shown
    assert toolbar(ctrl).current_pair() == ("sf2p", "")


def test_the_window_gets_the_pairs_and_the_current_pair(qtbot, monkeypatch):
    ui = DeviceTabToolBar()
    qtbot.addWidget(ui)
    ui.set_pairs([("sf2p", ""), ("sf2p", "V1"), ("sf4u", "")])
    ui.select_pair("sf2p", "V1")
    seen: list[tuple] = []

    def accept(dlg):
        seen.append(
            (
                dlg.windowTitle(),
                [dlg.name_box.itemText(i) for i in range(dlg.name_box.count())],
                dlg.name_box.currentText(),
                [dlg.source_box.itemText(i) for i in range(dlg.source_box.count())],
            )
        )
        dlg.release_edit.setText(" V2 ")
        dlg.source_box.setCurrentIndex(2)
        return AddProcessDialog.Accepted

    monkeypatch.setattr(AddProcessDialog, "exec", accept)

    assert ui._ask_add_pair() == ("sf2p", "V2", ("sf2p", "V1"))
    assert seen == [
        (
            "Add Process",
            ["sf2p", "sf4u"],
            "sf2p",
            ["(복사 안 함)", "sf2p", "sf2p V1", "sf4u"],
        )
    ]


def test_a_cancelled_window_gives_none(qtbot, monkeypatch):
    ui = DeviceTabToolBar()
    qtbot.addWidget(ui)
    ui.set_pairs([("sf2p", "")])

    def cancel(dlg):
        dlg.release_edit.setText("V2")
        return AddProcessDialog.Rejected

    monkeypatch.setattr(AddProcessDialog, "exec", cancel)

    assert ui._ask_add_pair() is None


def test_the_plus_button_opens_the_add_process_window(qtbot, dialogs):
    ui = DeviceTabToolBar()
    qtbot.addWidget(ui)

    # 진짜 창이 뜬다. dialogs fixture 가 답하지 않은 exec 를 막는다(예전 QInputDialog 가 아니다).
    with pytest.raises(AssertionError, match="AddProcessDialog.exec: 'Add Process'"):
        ui._ask_add_pair()
    dialogs.unexpected.clear()


def test_the_view_gives_the_pair_and_the_source(qtbot, monkeypatch):
    ui = DeviceTabToolBar()
    qtbot.addWidget(ui)
    got: list[tuple] = []
    ui.addProcessRequested.connect(
        lambda name, release, source: got.append((name, release, source))
    )
    answers = iter([("sf2p", V2, ("sf2p", "")), ("sf9x", "", None), None])
    monkeypatch.setattr(ui, "_ask_add_pair", lambda: next(answers))

    for _ in range(3):
        ui.open_add_process_dialog()

    assert got == [("sf2p", V2, ("sf2p", "")), ("sf9x", "", None)]
