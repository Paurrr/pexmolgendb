"""`+` 의 추가 창 `AddProcessDialog` (phase 19 step 9).

창은 (이름, 버전) 쌍 하나와 복사 원본(없으면 None)을 고른다. repo 도 메시지 상자도 모른다.
잘못된 입력은 OK 를 끄고 그 이유를 창 안의 한 줄로 보인다. 모달이라 테스트는 `exec` 없이 만들어
위젯을 채운다(답하지 않은 `QDialog.exec` 는 dialogs fixture 가 막는다).
"""

import pytest
from gui_support.keys import type_into
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QDialog, QDialogButtonBox, QLabel, QLineEdit

from genviewer.dialogs.add_process import AddProcessDialog

PAIRS = [("sf2p", ""), ("sf2p", "V1"), ("sf4u", "")]
EXISTS = "이미 있는 process 다."
NO_RELEASE = "(없음) 은 버전 이름으로 쓸 수 없다."


@pytest.fixture
def dialog(qtbot) -> AddProcessDialog:
    dlg = AddProcessDialog(PAIRS, ("sf2p", ""))
    qtbot.addWidget(dlg)
    return dlg


def items(box: QComboBox) -> list[str]:
    return [box.itemText(i) for i in range(box.count())]


def ok_enabled(dlg: AddProcessDialog) -> bool:
    return dlg.buttons.button(QDialogButtonBox.Ok).isEnabled()


def fill(dlg: AddProcessDialog, name: str, release: str) -> None:
    dlg.name_box.setEditText(name)
    dlg.release_edit.setText(release)


def test_the_window_has_the_old_title_and_three_fields(dialog):
    assert dialog.windowTitle() == "Add Process"
    labels = [label.text() for label in dialog.findChildren(QLabel)]
    for text in ("Process", "Version", "Copy from"):
        assert text in labels
    assert isinstance(dialog.release_edit, QLineEdit)
    assert dialog.name_box.isEditable()


def test_it_starts_on_the_current_name_with_a_blank_version_and_no_copy(dialog):
    assert items(dialog.name_box) == ["sf2p", "sf4u"]
    assert dialog.name_box.currentText() == "sf2p"
    assert dialog.release_edit.text() == ""
    assert items(dialog.source_box) == ["(복사 안 함)", "sf2p", "sf2p V1", "sf4u"]
    # 지금 쌍이 아니라 "(복사 안 함)" 이 기본이다. 모르고 device 를 복사하지 않게.
    assert dialog.source_box.currentIndex() == 0
    assert dialog.values() == ("sf2p", "", None)


def test_a_new_release_of_the_current_name_enables_ok(dialog):
    fill(dialog, "sf2p", "V2")

    assert ok_enabled(dialog)
    assert dialog.reason_label.text() == ""
    assert dialog.values() == ("sf2p", "V2", None)


@pytest.mark.parametrize(("name", "release"), [("sf2p", ""), ("sf2p", "V1"), ("  sf2p ", " V1  ")])
def test_an_existing_pair_disables_ok_and_says_why(dialog, name, release):
    fill(dialog, "sf2p", "V2")
    assert ok_enabled(dialog)

    fill(dialog, name, release)

    assert not ok_enabled(dialog)
    assert dialog.reason_label.text() == EXISTS


def test_the_initial_existing_pair_disables_ok(dialog):
    # 지금 쌍 ("sf2p", "") 그대로 열린다. 이미 있다.
    assert not ok_enabled(dialog)
    assert dialog.reason_label.text() == EXISTS


@pytest.mark.parametrize("name", ["", "   "])
def test_a_blank_name_disables_ok(dialog, name):
    fill(dialog, name, "V2")

    assert not ok_enabled(dialog)


@pytest.mark.parametrize("release", ["(없음)", "  (없음) "])
def test_the_no_release_text_cannot_be_a_version(dialog, release):
    fill(dialog, "sf9x", release)

    assert not ok_enabled(dialog)
    assert dialog.reason_label.text() == NO_RELEASE


def test_a_new_name_without_a_version_enables_ok(dialog):
    fill(dialog, "sf9x", "")

    assert ok_enabled(dialog)
    assert dialog.values() == ("sf9x", "", None)


def test_values_trims_the_name_and_the_version(dialog):
    fill(dialog, "  sf9x  ", "  S00-V1.0.0.0 ")

    assert ok_enabled(dialog)
    assert dialog.values() == ("sf9x", "S00-V1.0.0.0", None)


@pytest.mark.parametrize(
    ("index", "source"), [(1, ("sf2p", "")), (2, ("sf2p", "V1")), (3, ("sf4u", ""))]
)
def test_copy_from_gives_the_chosen_pair(dialog, index, source):
    fill(dialog, "sf2p", "V2")

    dialog.source_box.setCurrentIndex(index)

    assert dialog.values() == ("sf2p", "V2", source)
    assert ok_enabled(dialog)


def test_choosing_no_copy_again_gives_none(dialog):
    fill(dialog, "sf2p", "V2")
    dialog.source_box.setCurrentIndex(2)

    dialog.source_box.setCurrentIndex(0)

    assert dialog.values() == ("sf2p", "V2", None)


def test_a_release_name_starts_on_its_name(qtbot):
    dlg = AddProcessDialog(PAIRS, ("sf2p", "V1"))
    qtbot.addWidget(dlg)

    assert dlg.name_box.currentText() == "sf2p"
    assert dlg.release_edit.text() == ""
    assert dlg.source_box.currentIndex() == 0


def test_without_any_process_it_starts_empty_and_ok_is_off(qtbot):
    dlg = AddProcessDialog([], ("", ""))
    qtbot.addWidget(dlg)

    assert items(dlg.name_box) == []
    assert dlg.name_box.currentText() == ""
    assert items(dlg.source_box) == ["(복사 안 함)"]
    assert not ok_enabled(dlg)

    fill(dlg, "sf2p", "")

    assert ok_enabled(dlg)
    assert dlg.values() == ("sf2p", "", None)


def test_the_window_shows_no_message_box(dialog, dialogs):
    fill(dialog, "sf2p", "")
    fill(dialog, "sf9x", "(없음)")
    fill(dialog, "", "")

    assert dialogs.shown == []


def test_cancel_rejects(dialog):
    dialog.buttons.button(QDialogButtonBox.Cancel).click()

    assert dialog.result() == QDialog.Rejected


def test_ok_accepts_only_when_enabled(dialog):
    accepted: list[bool] = []
    dialog.accepted.connect(lambda: accepted.append(True))
    ok = dialog.buttons.button(QDialogButtonBox.Ok)

    ok.click()  # ("sf2p", "") 은 이미 있다. 꺼진 버튼은 눌리지 않는다
    assert accepted == []

    fill(dialog, "sf2p", "V2")
    ok.click()

    assert accepted == [True]
    assert dialog.result() == QDialog.Accepted


# K56: 편집 가능한 콤보에 Qt 가 붙이는 기본 completer(대소문자 무시, inline 완성)가 친 글자를
# 앞부분이 같은 기존 이름으로 바꿨다. `fill` 의 `setEditText` 는 completer 를 거치지 않으므로
# 아래는 포커스를 가진 칸에 실제로 키를 친다(`type_into`). 모달 `exec` 없이 `show` 로 재현된다.
TYPED_PAIRS = [("sf2p", ""), ("sf4u", "")]


@pytest.fixture
def typed_dialog(qtbot) -> AddProcessDialog:
    dlg = AddProcessDialog(TYPED_PAIRS, ("sf2p", ""))
    qtbot.addWidget(dlg)
    dlg.release_edit.setText("V9")
    return dlg


def test_typing_a_prefix_of_an_existing_name_keeps_what_was_typed(qtbot, typed_dialog):
    line_edit = typed_dialog.name_box.lineEdit()

    type_into(qtbot, line_edit, "sf2")

    assert line_edit.text() == "sf2"
    assert typed_dialog.values() == ("sf2", "V9", None)
    assert ok_enabled(typed_dialog)


def test_enter_on_a_name_differing_only_in_case_keeps_the_case(qtbot, typed_dialog):
    line_edit = typed_dialog.name_box.lineEdit()

    type_into(qtbot, line_edit, "SF4U")
    qtbot.keyClick(line_edit, Qt.Key_Return)

    # Enter 가 OK(기본 버튼)를 누른다.
    assert typed_dialog.result() == QDialog.Accepted
    assert typed_dialog.values() == ("SF4U", "V9", None)


def test_enter_on_an_existing_name_typed_exactly_gives_that_name(qtbot, typed_dialog):
    line_edit = typed_dialog.name_box.lineEdit()

    type_into(qtbot, line_edit, "sf4u")
    qtbot.keyClick(line_edit, Qt.Key_Return)

    assert typed_dialog.result() == QDialog.Accepted
    assert typed_dialog.values() == ("sf4u", "V9", None)


def test_choosing_from_the_list_still_gives_that_name(typed_dialog):
    typed_dialog.name_box.setCurrentIndex(1)

    assert typed_dialog.values()[0] == "sf4u"
