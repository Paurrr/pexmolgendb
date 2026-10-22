"""툴바 view 의 Process·Version 콤보 두 개 (phase 19 step 7).

process 행 하나가 (이름, 버전) 쌍이다. view 는 두 콤보를 묶어 쌍을 다루고, 사용자 동작 한 번이나
실제로 바뀐 선택 한 번에 `selectionChanged(이름, 버전)` 을 정확히 한 번 낸다. 빈 버전은
`(없음)` 으로 보이지만 값은 `""` 이다. 컨트롤러가 쌍으로 옮긴 뒤(step 8) 옛 이름 API
(`set_processes`, `select_process`, `select_process_silently`)는 없다. Remove 는 지금 쌍을
묻고 낸다.
"""

import pytest
from PySide6.QtWidgets import QComboBox, QSizePolicy

from genviewer.views.device_tab_toolbar import DeviceTabToolBar

PAIRS = [("sf2p", ""), ("sf2p", "V1"), ("sf4u", "")]
# 같은 버전이 이름마다 다른 자리에 있다. 자리(index)를 그대로 옮기는 구현을 가려낸다.
MANY = [
    ("sf2p", ""),
    ("sf2p", "V1"),
    ("sf4u", ""),
    ("sf4u", "U0"),
    ("sf4u", "V1"),
    ("sf9x", "V2"),
    ("sf9x", "V3"),
]


@pytest.fixture
def view(qtbot) -> DeviceTabToolBar:
    ui = DeviceTabToolBar()
    qtbot.addWidget(ui)
    return ui


def record(view: DeviceTabToolBar) -> list[tuple[str, str]]:
    got: list[tuple[str, str]] = []
    view.selectionChanged.connect(lambda name, release: got.append((name, release)))
    return got


def items(box: QComboBox) -> list[str]:
    return [box.itemText(i) for i in range(box.count())]


def shown(view: DeviceTabToolBar) -> tuple[list[str], str, list[str], str]:
    """두 콤보의 항목과 지금 글자."""
    return (
        items(view.process_selector),
        view.process_selector.currentText(),
        items(view.release_selector),
        view.release_selector.currentText(),
    )


def at(view: DeviceTabToolBar, pairs, name: str, release: str) -> list[tuple[str, str]]:
    """pairs 를 채우고 (name, release) 를 고른 뒤, 그 뒤의 시그널만 모은다."""
    view.set_pairs(pairs)
    assert view.select_silently(name, release) is True
    return record(view)


def test_set_pairs_fills_the_names_and_the_releases_of_the_first_name(view):
    got = record(view)

    view.set_pairs(PAIRS)

    assert items(view.process_selector) == ["sf2p", "sf4u"]
    assert items(view.release_selector) == ["(없음)", "V1"]
    assert view.current_pair() == ("sf2p", "")
    assert got == [("sf2p", "")]


def test_the_same_pairs_again_emit_nothing(view):
    view.set_pairs(PAIRS)
    got = record(view)

    view.set_pairs(list(PAIRS))

    assert got == []
    assert view.current_pair() == ("sf2p", "")


def test_set_pairs_keeps_the_current_pair_when_it_is_still_there(view):
    got = at(view, PAIRS, "sf2p", "V1")

    view.set_pairs([*PAIRS, ("sf9x", "")])

    assert got == []
    assert view.current_pair() == ("sf2p", "V1")
    assert shown(view) == (["sf2p", "sf4u", "sf9x"], "sf2p", ["(없음)", "V1"], "V1")


def test_a_dropped_release_falls_back_to_the_first_release_of_the_name(view):
    got = at(view, MANY, "sf4u", "V1")

    view.set_pairs([p for p in MANY if p != ("sf4u", "V1")])

    assert got == [("sf4u", "")]
    assert view.current_pair() == ("sf4u", "")
    assert items(view.release_selector) == ["(없음)", "U0"]


def test_a_dropped_release_of_the_spec_example_goes_to_no_release(view):
    got = at(view, PAIRS, "sf2p", "V1")

    view.set_pairs([("sf2p", ""), ("sf4u", "")])

    assert got == [("sf2p", "")]
    assert view.current_pair() == ("sf2p", "")


def test_a_dropped_name_falls_back_to_the_first_pair(view):
    got = at(view, PAIRS, "sf2p", "V1")

    view.set_pairs([("sf4u", "V7"), ("sf4u", "V8"), ("sf9x", "")])

    assert got == [("sf4u", "V7")]
    assert view.current_pair() == ("sf4u", "V7")
    assert shown(view) == (["sf4u", "sf9x"], "sf4u", ["V7", "V8"], "V7")


def test_an_empty_list_empties_both_combos_once(view):
    got = at(view, PAIRS, "sf2p", "V1")

    view.set_pairs([])

    assert got == [("", "")]
    assert view.current_pair() == ("", "")
    assert shown(view) == ([], "", [], "")
    assert view.pairs() == []

    view.set_pairs([])

    assert got == [("", "")]


def test_choosing_a_release_gives_the_pair_once(view):
    view.set_pairs(PAIRS)
    got = record(view)

    view.release_selector.setCurrentIndex(1)

    assert got == [("sf2p", "V1")]
    assert view.current_pair() == ("sf2p", "V1")


def test_choosing_a_name_that_has_the_release_keeps_the_release(view):
    got = at(view, MANY, "sf2p", "V1")

    view.process_selector.setCurrentIndex(1)  # sf4u: "", U0, V1

    assert got == [("sf4u", "V1")]
    assert view.current_pair() == ("sf4u", "V1")
    assert shown(view) == (["sf2p", "sf4u", "sf9x"], "sf4u", ["(없음)", "U0", "V1"], "V1")


def test_choosing_a_name_without_the_release_takes_its_first_release(view):
    got = at(view, MANY, "sf2p", "V1")

    view.process_selector.setCurrentIndex(2)  # sf9x: V2, V3

    assert got == [("sf9x", "V2")]
    assert view.current_pair() == ("sf9x", "V2")
    assert items(view.release_selector) == ["V2", "V3"]


def test_choosing_a_name_from_no_release_keeps_no_release(view):
    got = at(view, MANY, "sf4u", "")

    view.process_selector.setCurrentIndex(0)  # sf2p: "", V1

    assert got == [("sf2p", "")]


def test_select_silently_changes_the_pair_without_a_signal(view):
    view.set_pairs(PAIRS)
    got = record(view)

    assert view.select_silently("sf4u", "") is True

    assert got == []
    assert view.current_pair() == ("sf4u", "")
    assert shown(view) == (["sf2p", "sf4u"], "sf4u", ["(없음)"], "(없음)")

    # 조용히 고른 쌍이 다음 비교의 기준이다. 사용자가 원래 쌍으로 돌아가면 그것도 바뀐 것이다.
    view.process_selector.setCurrentIndex(0)

    assert got == [("sf2p", "")]


@pytest.mark.parametrize("pair", [("sf9x", ""), ("sf2p", "V9"), ("", "")])
def test_select_silently_leaves_everything_for_an_unknown_pair(view, pair):
    got = at(view, PAIRS, "sf2p", "V1")
    before = shown(view)

    assert view.select_silently(*pair) is False

    assert shown(view) == before
    assert view.current_pair() == ("sf2p", "V1")
    assert got == []


def test_select_pair_gives_the_pair_only_when_it_changes(view):
    view.set_pairs(MANY)
    got = record(view)

    view.select_pair("sf4u", "V1")
    view.select_pair("sf4u", "V1")
    view.select_pair("sf9x", "")  # 없는 쌍
    view.select_pair("sf4u", "U0")

    assert got == [("sf4u", "V1"), ("sf4u", "U0")]
    assert view.current_pair() == ("sf4u", "U0")
    assert items(view.release_selector) == ["(없음)", "U0", "V1"]


def test_no_release_shows_as_its_text_but_reads_as_an_empty_string(view):
    got = record(view)
    view.set_pairs([("sf2p", ""), ("sf2p", "V1")])

    assert view.release_selector.currentText() == "(없음)"
    assert view.current_pair() == ("sf2p", "")
    assert got == [("sf2p", "")]

    view.release_selector.setCurrentIndex(1)
    view.release_selector.setCurrentIndex(0)

    assert got == [("sf2p", ""), ("sf2p", "V1"), ("sf2p", "")]
    assert view.current_pair()[1] == ""


def test_pairs_and_releases_of_give_the_current_list(view):
    view.set_pairs(MANY)

    assert view.pairs() == MANY
    assert view.releases_of("sf4u") == ["", "U0", "V1"]
    assert view.releases_of("sf9x") == ["V2", "V3"]
    assert view.releases_of("nope") == []

    view.pairs().append(("sf0z", ""))

    assert view.pairs() == MANY


def test_an_empty_view_has_no_pair(view):
    assert view.current_pair() == ("", "")
    assert view.pairs() == []
    assert items(view.release_selector) == []


def test_the_version_combo_sits_between_the_process_combo_and_its_buttons(view):
    layout = view.layout()
    order = [layout.itemAt(i).widget() for i in range(layout.count())]

    assert order[:7] == [
        view.process_selector_label,
        view.process_selector,
        view.release_selector_label,
        view.release_selector,
        view.add_process_btn,
        view.remove_process_btn,
        view.load_virtuoso_btn,
    ]
    assert view.release_selector_label.text() == "Version"
    assert view.release_selector_label.sizePolicy().horizontalPolicy() == QSizePolicy.Fixed
    assert view.release_selector.sizePolicy().horizontalPolicy() == QSizePolicy.Preferred
    assert (
        view.release_selector.sizeAdjustPolicy()
        == QComboBox.SizeAdjustPolicy.AdjustToContents
    )


def test_the_old_process_api_is_gone(view):
    for name in ("set_processes", "select_process", "select_process_silently"):
        assert not hasattr(view, name), name


def test_remove_gives_the_current_pair_without_asking(view, dialogs):
    # 확인은 controller 의 Remove Process 질문 하나다(device 수를 알려 준다).
    got: list[tuple[str, str]] = []
    view.removeProcessRequested.connect(lambda name, release: got.append((name, release)))
    view.set_pairs(PAIRS)
    view.select_pair("sf2p", "V1")

    view.open_remove_process_dialog()

    assert dialogs.shown == []
    assert got == [("sf2p", "V1")]


def test_remove_without_a_pair_does_nothing(view, dialogs):
    got: list[tuple[str, str]] = []
    view.removeProcessRequested.connect(lambda name, release: got.append((name, release)))

    view.open_remove_process_dialog()

    assert dialogs.shown == []
    assert got == []
