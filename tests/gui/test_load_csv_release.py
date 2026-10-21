"""GUI Load CSV 가 불러올 버전을 묻는다 (phase 19 step 10).

CSV 형식은 그대로다(버전 컬럼 없음). 파일을 고른 뒤 `DeviceTab._ask_release` 가 버전을 묻고, 모든
행이 (CdsLibName, 그 버전) 쌍으로 들어간다(2026-10-21 승인). 버전 묻기는 툴바가 이미 들고 있는
쌍 목록으로 끝나고 DB 를 부르지 않는다. 불러온 뒤에도 지금 쌍은 그대로다(자동으로 옮기지 않는다).
알림 문구와 Refresh 질문은 그대로이고, 로그 줄만 버전이 있으면 버전을 적는다.
"""

import pytest
from gui_support.helpers import select_process
from PySide6.QtWidgets import QInputDialog

import genviewer.views.device_tab as device_tab_view

CSV_TEXT = "CellType,CdsLibName,InstCellName,InstTerm\nNFET,sf2p,nfet_c,DRN d\n"
LOAD_CSV_NOTICE = (
    "info",
    "Load CSV",
    "device 1개를 새로 추가했다.\n"
    "CSV 는 불러올 때마다 새로 쌓인다 — 같은 파일을 다시 넣으면 중복된다.",
)


def toolbar(ctrl):
    return ctrl.device_tab_toolbar.ui


def current(ctrl) -> tuple:
    dt = ctrl.device_table
    return (dt.current_process, dt.current_release, dt.current_process_id)


def pid(store, name: str, release: str = "") -> int | None:
    found = [p for p, n in store.processes.items() if n == name and store.releases[p] == release]
    return found[0] if found else None


def device_names(ctrl) -> list[str]:
    return [d["name"] for d in ctrl.device_table.ui.model_safe().get_devices()]


def record_logs(ctrl) -> list[str]:
    logs: list[str] = []
    ctrl.logRequested.connect(logs.append)
    return logs


def write_csv(tmp_path) -> str:
    path = tmp_path / "in.csv"
    path.write_text(CSV_TEXT, encoding="utf-8", newline="")
    return str(path)


def give_file(monkeypatch, path: str) -> list[tuple]:
    """파일 열기 대화상자 대신 path 를 돌려준다. 받은 인자를 기록해 돌려준다."""
    asked: list[tuple] = []

    def fake(*args):
        asked.append(args)
        return path

    monkeypatch.setattr(device_tab_view, "open_file", fake)
    return asked


def give_release(monkeypatch, ctrl, release: str | None) -> list[str]:
    """`_ask_release` 대신 release 를 돌려준다. 불린 횟수를 기록한다."""
    asked: list[str] = []

    def fake():
        asked.append("asked")
        return release

    monkeypatch.setattr(ctrl.ui, "_ask_release", fake)
    return asked


# -- Load CSV --------------------------------------------------------------------------


def test_loading_a_csv_into_a_release_makes_the_pair_and_stays_on_the_current_one(
    device_tab_ctrl, store, dialogs, monkeypatch, tmp_path
):
    ctrl = device_tab_ctrl
    path = write_csv(tmp_path)
    give_file(monkeypatch, path)
    asked = give_release(monkeypatch, ctrl, "V1")
    logs = record_logs(ctrl)
    before = current(ctrl)
    assert before == ("sf2p", "", pid(store, "sf2p"))

    ctrl.ui._ask_load_csv()

    assert asked == ["asked"]
    assert store.calls_of("import_data")[-1] == {
        "input_path": path,
        "release": "V1",
        "actor": "tester",
    }
    v1 = pid(store, "sf2p", "V1")
    assert v1 is not None
    assert [d["name"] for d in store.devices.values() if d["process_id"] == v1] == ["nfet_c"]
    # 목록은 다시 읽지만 지금 쌍은 그대로다. 새 쌍은 사용자가 콤보로 고른다.
    assert ("sf2p", "V1") in toolbar(ctrl).pairs()
    assert toolbar(ctrl).current_pair() == ("sf2p", "")
    assert current(ctrl) == before
    assert device_names(ctrl) == ["nfet_a", "nfet_b"]
    assert dialogs.shown == [LOAD_CSV_NOTICE]
    assert logs[-1] == f"Imported CSV: {path} (version V1, device 1개 추가)."


def test_loading_a_csv_without_a_release_keeps_the_old_lines(
    device_tab_ctrl, store, dialogs, monkeypatch, tmp_path
):
    ctrl = device_tab_ctrl
    path = write_csv(tmp_path)
    give_file(monkeypatch, path)
    give_release(monkeypatch, ctrl, "")
    logs = record_logs(ctrl)

    ctrl.ui._ask_load_csv()

    assert store.calls_of("import_data")[-1]["release"] == ""
    assert sorted(store.releases.values()) == ["", ""]
    assert sorted(device_names(ctrl)) == ["nfet_a", "nfet_b", "nfet_c"]
    assert dialogs.shown == [LOAD_CSV_NOTICE]
    assert logs[-1] == f"Imported CSV: {path} (device 1개 추가)."


def test_cancelling_the_release_question_loads_nothing(
    device_tab_ctrl, store, dialogs, monkeypatch, tmp_path
):
    ctrl = device_tab_ctrl
    give_file(monkeypatch, write_csv(tmp_path))
    asked = give_release(monkeypatch, ctrl, None)
    loads: list[tuple] = []
    ctrl.ui.loadCsvRequested.connect(lambda *args: loads.append(args))
    since = len(store.calls)

    ctrl.ui._ask_load_csv()

    assert asked == ["asked"]
    assert loads == []
    assert store.calls_of("import_data") == []
    assert store.calls[since:] == []
    assert dialogs.shown == []


def test_cancelling_the_file_question_does_not_ask_for_a_release(
    device_tab_ctrl, store, dialogs, monkeypatch
):
    ctrl = device_tab_ctrl
    files = give_file(monkeypatch, "")
    asked = give_release(monkeypatch, ctrl, "V1")

    ctrl.ui._ask_load_csv()

    assert files == [(ctrl.ui, "Load CSV", "csv file (*.csv)", "")]
    assert asked == []
    assert store.calls_of("import_data") == []
    assert dialogs.shown == []


def test_the_view_gives_the_path_and_the_release(device_tab_ctrl, monkeypatch, tmp_path):
    ctrl = device_tab_ctrl
    path = write_csv(tmp_path)
    give_file(monkeypatch, path)
    give_release(monkeypatch, ctrl, "V1")
    ctrl.ui.loadCsvRequested.disconnect(ctrl.on_load_csv_requested)
    loads: list[tuple] = []
    ctrl.ui.loadCsvRequested.connect(lambda *args: loads.append(args))

    ctrl.ui._ask_load_csv()

    assert loads == [(path, "V1")]


# -- 버전 묻기 ---------------------------------------------------------------------------


@pytest.fixture
def three_releases(device_tab_ctrl, store, qtbot):
    """툴바에 (sf2p,""),(sf2p,V1),(sf4u,""),(sf4u,V2) 가 있고 지금 쌍이 (sf2p,V1) 이다."""
    ctrl = device_tab_ctrl
    store.add_process("sf2p", release="V1")
    store.add_process("sf4u", release="V2")
    ctrl.device_tab_toolbar.refresh_processes()
    select_process(ctrl, "sf2p", "V1")
    qtbot.waitUntil(lambda: ctrl.device_table.current_release == "V1")
    return ctrl


def answer_get_item(monkeypatch, answer: tuple[str, bool]) -> list[tuple]:
    """QInputDialog.getItem 대신 answer 를 돌려준다. 받은 인자를 기록해 돌려준다.

    autouse dialogs fixture 가 막아 둔 것을 이 테스트 안에서 바꾼다(뒤에 바꾼 것이 이긴다).
    """
    asked: list[tuple] = []

    def fake(*args, **kwargs):
        asked.append((args, kwargs))
        return answer

    monkeypatch.setattr(QInputDialog, "getItem", staticmethod(fake))
    return asked


def test_the_release_question_lists_each_release_once_with_no_release_first(
    three_releases, store, monkeypatch
):
    ctrl = three_releases
    asked = answer_get_item(monkeypatch, ("V1", True))
    since = len(store.calls)

    assert ctrl.ui._ask_release() == "V1"

    ((args, kwargs),) = asked
    assert args == (
        ctrl.ui,
        "Load CSV",
        "불러올 버전 (비우면 버전 없음):",
        ["(없음)", "V1", "V2"],
        1,
    )
    assert kwargs == {"editable": True}
    # 목록은 툴바가 들고 있다. 묻는 동안 DB 를 부르지 않는다.
    assert store.calls[since:] == []


def test_the_release_question_starts_on_no_release_when_the_current_pair_has_none(
    device_tab_ctrl, store, monkeypatch
):
    ctrl = device_tab_ctrl
    store.add_process("sf4u", release="V2")
    ctrl.device_tab_toolbar.refresh_processes()
    assert toolbar(ctrl).current_pair() == ("sf2p", "")
    asked = answer_get_item(monkeypatch, ("(없음)", True))

    assert ctrl.ui._ask_release() == ""

    ((args, _kwargs),) = asked
    assert args[3:] == (["(없음)", "V2"], 0)


@pytest.mark.parametrize(
    ("answer", "expected"),
    [
        (("(없음)", True), ""),
        ((" (없음) ", True), ""),
        (("", True), ""),
        (("   ", True), ""),
        (("V2", True), "V2"),
        (("  V3 ", True), "V3"),
        (("V1", False), None),
        (("", False), None),
    ],
    ids=[
        "no-release",
        "padded-no-release",
        "empty",
        "blank",
        "listed",
        "typed",
        "cancel",
        "cancel-empty",
    ],
)
def test_the_release_answer_is_trimmed_and_no_release_is_empty(
    three_releases, monkeypatch, answer, expected
):
    answer_get_item(monkeypatch, answer)

    assert three_releases.ui._ask_release() == expected
