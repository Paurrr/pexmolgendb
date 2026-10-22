"""창을 줄여도 Device 탭 툴바의 위젯이 겹치지 않는다 (K57, phase 21).

툴바의 가로 정책이 `Ignored` 면 부모 레이아웃이 툴바의 최소 너비를 몰라 창이 툴바보다 좁아지고,
고정 너비 단추와 최소 너비가 있는 콤보가 서로 겹친다. 창은 툴바 최소 너비보다 좁아지지 않아야 한다.

`main_window` fixture 는 쓰지 않는다. 컨트롤러가 채운 Device Info·파라미터 탭 때문에 그 창은
이미 툴바보다 넓어서 수정 전에도 겹치지 않는다. 여기서는 컨트롤러 없이 `MainWindow` 를 직접
만든다(device 를 고르기 전의 실제 앱처럼 파라미터 탭이 비어 있다). 너비는 글꼴에 따라 달라서
픽셀 숫자를 박지 않는다.
"""

import pytest
from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QAbstractButton, QComboBox, QLabel, QWidget

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
