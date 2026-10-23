"""창을 줄여도 Device 탭 툴바의 위젯이 겹치지 않는다 (K57, phase 21).

툴바의 가로 정책이 `Ignored` 면 부모 레이아웃이 툴바의 최소 너비를 몰라 창이 툴바보다 좁아지고,
고정 너비 단추와 최소 너비가 있는 콤보가 서로 겹친다. 창은 툴바 최소 너비보다 좁아지지 않아야 한다.

`main_window` fixture 는 쓰지 않는다. 컨트롤러가 채운 Device Info·파라미터 탭 때문에 그 창은
이미 툴바보다 넓어서 수정 전에도 겹치지 않는다. 여기서는 컨트롤러 없이 `MainWindow` 를 직접
만든다(device 를 고르기 전의 실제 앱처럼 파라미터 탭이 비어 있다). 너비는 글꼴에 따라 달라서
픽셀 숫자를 박지 않는다.
"""

import pytest
from gui_support.theme import preserved_theme
from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QAbstractButton, QComboBox, QLabel, QPushButton, QWidget

from genviewer.utils.palette import apply_theme
from genviewer.views.device_tab import RefreshBanner
from genviewer.views.device_tab_toolbar import DeviceTabToolBar
from genviewer.views.main_window import MainWindow

LONG_NAME = "process_name_that_is_much_longer_than_thirty_characters"
LONG_RELEASE = "S00-V1.0.0.0-release-label-longer-than-thirty-chars"


@pytest.fixture
def window(qtbot) -> MainWindow:
    ui = MainWindow("localhost")
    qtbot.addWidget(ui)
    ui.show()
    qtbot.waitExposed(ui)
    return ui


def _settle() -> None:
    QCoreApplication.sendPostedEvents(None, QEvent.Type.LayoutRequest)


def _label(widget: QWidget) -> str:
    if isinstance(widget, (QLabel, QAbstractButton)):
        return f"{type(widget).__name__}({widget.text()!r})"
    if isinstance(widget, QComboBox):
        return f"QComboBox({widget.currentText()!r})"
    return type(widget).__name__


def _overlapping(toolbar: DeviceTabToolBar) -> list[tuple[str, str]]:
    """툴바 직계 자식 중 보이는 위젯끼리 겹치는 쌍."""
    children = [w for w in toolbar.children() if isinstance(w, QWidget) and w.isVisible()]
    return [
        (_label(a), _label(b))
        for i, a in enumerate(children)
        for b in children[i + 1 :]
        if a.geometry().intersects(b.geometry())
    ]


def test_toolbar_widgets_do_not_overlap_at_the_default_size(window):
    toolbar = window.device_tab_view.device_tab_toolbar_view
    _settle()

    assert _overlapping(toolbar) == []


def test_shrinking_the_window_keeps_toolbar_widgets_apart(window):
    toolbar = window.device_tab_view.device_tab_toolbar_view

    window.resize(800, 700)
    _settle()

    assert _overlapping(toolbar) == []
    assert toolbar.width() >= toolbar.layout().minimumSize().width()


def test_long_names_keep_toolbar_widgets_apart(window):
    toolbar = window.device_tab_view.device_tab_toolbar_view
    toolbar.set_pairs([("sf2p", ""), (LONG_NAME, LONG_RELEASE)])
    toolbar.process_selector.setCurrentIndex(toolbar.process_selector.findText(LONG_NAME))
    assert toolbar.current_pair() == (LONG_NAME, LONG_RELEASE)

    window.resize(800, 700)
    _settle()

    assert _overlapping(toolbar) == []


# -- Process / Version 콤보 너비 (phase 25) ------------------------------------------------
# 창을 최소 너비로 줄이면 두 콤보가 각자의 최소 너비로 눌린다. process 이름은 대개 짧고 버전
# (S00-V1.0.0.0 …)이 더 길어서 Version 콤보가 더 넓어야 한다.
#
# offscreen 플랫폼에는 글꼴이 없어 모든 글자가 같은 너비의 상자로 그려진다. 그래서 Windows 에서
# 잰 글자 수(10글자 이름, 16글자 버전)가 맞지 않는다. 아래 두 값은 offscreen sizeHint 로 고른
# 것이다. 이름은 바꾼 뒤의 Process 최소 너비에 들어가고, 버전은 바꾸기 전 Version 최소 너비에는
# 안 들어가고 바꾼 뒤에는 들어간다. 실제 글꼴은 상자보다 좁아서 수정 뒤에는 어디서든 들어간다.
SHORT_NAME = "sf2p_hv"
FITTING_RELEASE = "S00-V1.0.0"


def _shrink_to_minimum(window: MainWindow) -> None:
    """창을 최소 너비로 줄인다. 최소보다 작게 주면 최소로 맞춰진다."""
    _settle()
    window.resize(1, window.height())
    _settle()


@pytest.mark.parametrize("theme", ["graphite", "mist"])
def test_version_combo_is_wider_than_process_combo_at_minimum_width(window, qapp, theme):
    toolbar = window.device_tab_view.device_tab_toolbar_view
    toolbar.set_pairs([("sf2p", ""), ("sf2p", "S00-V1.0.0.0")])

    with preserved_theme(qapp):
        apply_theme(qapp, theme)
        _shrink_to_minimum(window)
        process = toolbar.process_selector.width()
        release = toolbar.release_selector.width()

    assert release > process


@pytest.mark.parametrize("theme", ["graphite", "mist"])
def test_a_short_name_and_a_long_version_fit_at_minimum_width(window, qapp, theme):
    toolbar = window.device_tab_view.device_tab_toolbar_view
    toolbar.set_pairs([(SHORT_NAME, FITTING_RELEASE)])
    assert toolbar.current_pair() == (SHORT_NAME, FITTING_RELEASE)

    with preserved_theme(qapp):
        apply_theme(qapp, theme)
        _shrink_to_minimum(window)
        cut = [
            (combo.currentText(), combo.width(), combo.sizeHint().width())
            for combo in (toolbar.process_selector, toolbar.release_selector)
            if combo.width() < combo.sizeHint().width()
        ]

    assert cut == []


# -- 변경 배너 단추 (phase 24 step 2) ------------------------------------------------------
# 배너 단추의 고정 너비는 한국어 글자(새로고침·닫기)에 맞춘 것이었다. 영어 글자가 그보다 넓으면
# 스타일시트의 padding 안에 다 들어가지 못해 양 끝 글자가 잘린다("Dismiss" 의 D 와 끝 s).


@pytest.mark.parametrize("theme", ["graphite", "mist"])
def test_refresh_banner_buttons_are_not_narrower_than_their_text(qtbot, qapp, theme):
    with preserved_theme(qapp):
        apply_theme(qapp, theme)
        banner = RefreshBanner()
        qtbot.addWidget(banner)
        banner.show_change("kim")
        qtbot.waitExposed(banner)
        _settle()

        narrow = [
            (button.text(), button.width(), button.sizeHint().width())
            for button in banner.findChildren(QPushButton)
            if button.width() < button.sizeHint().width()
        ]

    assert narrow == []
