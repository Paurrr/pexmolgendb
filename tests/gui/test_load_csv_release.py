"""GUI Load CSV 가 불러올 버전을 묻는다 (phase 19 step 10).

CSV 형식은 그대로다(버전 컬럼 없음). 파일을 고른 뒤 `DeviceTab._ask_release` 가 버전을 묻고, 모든
행이 (CdsLibName, 그 버전) 쌍으로 들어간다(2026-10-21 승인). 버전 묻기는 툴바가 이미 들고 있는
쌍 목록으로 끝나고 DB 를 부르지 않는다. 불러온 뒤에도 지금 쌍은 그대로다(자동으로 옮기지 않는다).
알림 문구와 Refresh 질문은 그대로이고, 로그 줄만 버전이 있으면 버전을 적는다.
"""

import pytest
from gui_support.helpers import select_process
from gui_support.keys import type_into
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication, QComboBox, QDialog, QInputDialog

import genviewer.views.device_tab as device_tab_view
from genviewer.views.device_tab import DeviceTab

# 진짜 모달 테스트(K56)가 되돌려 쓰는 진짜 함수. autouse dialogs fixture 가 테스트마다 둘을
# 막으므로 모듈 import(수집) 때 잡아 둔다.
REAL_GET_ITEM = QInputDialog.getItem
REAL_DIALOG_EXEC = QDialog.exec

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


def answer_exec(monkeypatch, text: str, accept: bool = True) -> list[dict]:
    """QInputDialog.exec 대신 창에 text 를 넣고 OK(accept) 또는 취소로 돌아온다.

    창이 뜰 때 본 것(부모, 제목, 라벨, 후보, 처음 글자, 편집 가능, 콤보 completer)을 기록해
    돌려준다. autouse dialogs fixture 가 QDialog.exec 를 막아 둔 것을 QInputDialog 에서 이긴다.
    """
    asked: list[dict] = []

    def fake(dialog, *_args):
        asked.append(
            {
                "parent": dialog.parentWidget(),
                "title": dialog.windowTitle(),
                "label": dialog.labelText(),
                "items": dialog.comboBoxItems(),
                "text": dialog.textValue(),
                "editable": dialog.isComboBoxEditable(),
                "completer": dialog.findChild(QComboBox).completer(),
            }
        )
        dialog.setTextValue(text)
        return QDialog.Accepted if accept else QDialog.Rejected

    monkeypatch.setattr(QInputDialog, "exec", fake)
    return asked


def test_the_release_question_lists_each_release_once_with_no_release_first(
    three_releases, store, monkeypatch
):
    ctrl = three_releases
    asked = answer_exec(monkeypatch, "V1")
    since = len(store.calls)

    assert ctrl.ui._ask_release() == "V1"

    (seen,) = asked
    assert seen.pop("parent") is ctrl.ui
    assert seen == {
        "title": "Load CSV",
        "label": "불러올 버전 (비우면 버전 없음):",
        "items": ["(none)", "V1", "V2"],
        "text": "V1",
        "editable": True,
        # 기본 completer 가 친 글자를 기존 버전으로 바꾼다(K56).
        "completer": None,
    }
    # 목록은 툴바가 들고 있다. 묻는 동안 DB 를 부르지 않는다.
    assert store.calls[since:] == []


def test_the_release_question_starts_on_no_release_when_the_current_pair_has_none(
    device_tab_ctrl, store, monkeypatch
):
    ctrl = device_tab_ctrl
    store.add_process("sf4u", release="V2")
    ctrl.device_tab_toolbar.refresh_processes()
    assert toolbar(ctrl).current_pair() == ("sf2p", "")
    asked = answer_exec(monkeypatch, "(none)")

    assert ctrl.ui._ask_release() == ""

    (seen,) = asked
    assert (seen["items"], seen["text"]) == (["(none)", "V2"], "(none)")


def test_the_release_question_is_asked_even_without_any_pair(qtbot, monkeypatch):
    view = DeviceTab()
    qtbot.addWidget(view)
    view.device_tab_toolbar_view.set_pairs([])
    asked = answer_exec(monkeypatch, "V1")

    assert view._ask_release() == "V1"

    (seen,) = asked
    assert (seen["items"], seen["text"]) == ([], "")


def test_an_unanswered_release_question_is_blocked_by_the_fixture(qtbot, dialogs):
    view = DeviceTab()
    qtbot.addWidget(view)
    view.device_tab_toolbar_view.set_pairs([("sf2p", "")])

    # 진짜 창이 뜬다. dialogs fixture 가 답하지 않은 exec 를 막는다(정적 getItem 이 아니다).
    with pytest.raises(AssertionError, match="QInputDialog.exec: 'Load CSV'"):
        view._ask_release()
    dialogs.unexpected.clear()


@pytest.mark.parametrize(
    ("answer", "expected"),
    [
        (("(none)", True), ""),
        ((" (none) ", True), ""),
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
    answer_exec(monkeypatch, *answer)

    assert three_releases.ui._ask_release() == expected


# -- K56: 친 버전을 그대로 받는다 (진짜 모달) ------------------------------------------------
# 편집 가능한 콤보에 Qt 가 붙이는 기본 completer(대소문자 무시, inline 완성)가 친 글자를 앞부분이
# 같은 기존 버전으로 바꿨고, Enter 도 대소문자를 무시하고 기존 버전을 골랐다. completer 는 포커스를
# 가진 칸에서만 돌아서 진짜 모달 안에서 실제로 키를 친다(`type_into`).
TYPED_PAIRS = [("sf2p", ""), ("sf2p", "S00-V1.0.0.0")]


@pytest.fixture
def typed_view(qtbot, monkeypatch) -> DeviceTab:
    """툴바 쌍이 TYPED_PAIRS 인 view. 진짜 getItem·exec 를 되돌려 둔다(fixture 의 가짜를 이긴다)."""
    for real in (REAL_GET_ITEM, REAL_DIALOG_EXEC):
        assert getattr(real, "__module__", None) != "gui_support.dialogs"
    monkeypatch.setattr(QInputDialog, "getItem", REAL_GET_ITEM)
    monkeypatch.setattr(QDialog, "exec", REAL_DIALOG_EXEC)
    view = DeviceTab()
    qtbot.addWidget(view)
    view.device_tab_toolbar_view.set_pairs(TYPED_PAIRS)
    return view


def visible_input_dialog(view) -> QInputDialog | None:
    found = [d for d in view.findChildren(QInputDialog) if d.isVisible()]
    return found[0] if found else None


def ask_release_typing(qtbot, view, text: str, *, enter: bool = False) -> tuple[str | None, bool]:
    """진짜 모달로 `_ask_release` 를 부르고 뜬 창의 콤보에 text 를 친다. enter 면 Enter 를 누른다.

    (돌려받은 버전, 키가 창을 닫았는지)를 돌려준다. 치기는 모달 루프 안(`drive`)에서 돈다. drive 는
    단언하지 않고 예외를 기록만 한다. 떠 있는 모달은 finally 에서 반드시 닫는다(OK). 닫지 않으면
    테스트가 멈춘다. drive 의 예외는 `_ask_release` 가 돌아온 뒤 다시 낸다.
    """
    errors: list[BaseException] = []
    closed_by_keys: list[bool] = []

    def drive():
        dialog = None
        try:
            qtbot.waitUntil(lambda: visible_input_dialog(view) is not None)
            dialog = visible_input_dialog(view)
            line_edit = dialog.findChild(QComboBox).lineEdit()
            type_into(qtbot, line_edit, text)
            if enter:
                qtbot.keyClick(line_edit, Qt.Key_Return)
            closed_by_keys.append(not dialog.isVisible())
        except BaseException as exc:
            errors.append(exc)
        finally:
            modal = dialog or QApplication.activeModalWidget()
            if isinstance(modal, QDialog) and modal.isVisible():
                modal.accept()

    QTimer.singleShot(0, view, drive)
    answer = view._ask_release()
    if errors:
        raise errors[0]
    return answer, closed_by_keys == [True]


def test_typing_a_prefix_of_an_existing_release_keeps_what_was_typed(qtbot, typed_view):
    answer, _closed = ask_release_typing(qtbot, typed_view, "S00-V1.0")

    assert answer == "S00-V1.0"


def test_enter_on_a_release_differing_only_in_case_keeps_the_case(qtbot, typed_view):
    answer, closed = ask_release_typing(qtbot, typed_view, "s00-v1.0.0.0", enter=True)

    assert answer == "s00-v1.0.0.0"
    # Enter 가 OK(기본 버튼)를 누른다.
    assert closed


def test_enter_on_an_existing_release_typed_exactly_gives_that_release(qtbot, typed_view):
    answer, closed = ask_release_typing(qtbot, typed_view, "S00-V1.0.0.0", enter=True)

    assert answer == "S00-V1.0.0.0"
    assert closed
