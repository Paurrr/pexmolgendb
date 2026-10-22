"""device 표 Name 칸 글자색과 저장 안 한 셀 배경 (phase 22 step 1, ADR-019).

`DeviceTableModel.data` 가 테마와 상관없이 알려진 이름을 `Qt.black`, 저장 안 한 셀 배경을
`QColor(255, 249, 196)` 로 돌려주었다. `QTableView` QSS 는 `color` 만 정하므로 모델의
`ForegroundRole` 이 이긴다. 그래서 Graphite(어두움)에서 검정 글자가 어두운 base 위에(대비 약 1.6),
테마의 밝은 글자가 밝은 노랑 위에(약 1.13) 그려졌다.

고친 동작:
- 알려진 이름: `ForegroundRole` 이 None 이라 테마 글자색(다른 칸과 같은 색)을 따른다.
- 모르는 이름: `current_colors()["unknown_name"]` (Mist `#ff0000`, Graphite `#f47067`).
- dirty 배경: `current_colors()["dirty"]` (Mist `#fff9c4`, Graphite `#3a3220`).

"실제로 그려지는 색"은 모델이 None 을 돌려주면 테마의 `text`/`base` 로 본다. `apply_theme` 를
부르는 테스트는 모두 `preserved_theme` 안에서 돈다.
"""

from gui_support.theme import preserved_theme
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

from genviewer.models.device_table import DeviceTableModel
from genviewer.utils.palette import apply_theme, current_colors

NAME = 0
DESCRIPTION = 2
KNOWN = 0  # known_device_names 에 있는 이름의 행
UNKNOWN = 1  # Virtuoso 에 없는 이름의 행
EDITED = "edited by tester"


def _luminance(color: QColor) -> float:
    """WCAG 2 상대 휘도."""
    channels = [color.redF(), color.greenF(), color.blueF()]
    linear = [
        c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels
    ]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def _contrast(fg: QColor, bg: QColor) -> float:
    high, low = sorted((_luminance(fg), _luminance(bg)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def make_model() -> DeviceTableModel:
    """알려진 이름 하나, 모르는 이름 하나. 알려진 행의 Description 을 고쳐 dirty 로 만든다."""
    devices = [
        {"id": 1, "name": "nfet_a", "celltype": "NFET", "description": "", "version": 1},
        {"id": 2, "name": "nmos_x", "celltype": "NFET", "description": "", "version": 1},
    ]
    model = DeviceTableModel(devices, known_device_names={"nfet_a"})
    assert model.setData(model.index(KNOWN, DESCRIPTION), EDITED)
    return model


def drawn_foreground(model, row: int, col: int) -> QColor:
    color = model.index(row, col).data(Qt.ForegroundRole)
    return QColor(current_colors()["text"]) if color is None else QColor(color)


def drawn_background(model, row: int, col: int) -> QColor:
    color = model.index(row, col).data(Qt.BackgroundRole)
    return QColor(current_colors()["base"]) if color is None else QColor(color)


def drawn_contrast(model, row: int, col: int) -> float:
    return _contrast(drawn_foreground(model, row, col), drawn_background(model, row, col))


def test_known_device_name_is_readable_in_graphite(qapp):
    model = make_model()
    with preserved_theme(qapp):
        apply_theme(qapp, "graphite")
        assert drawn_contrast(model, KNOWN, NAME) >= 4.5


def test_dirty_cell_is_readable_in_graphite(qapp):
    model = make_model()
    with preserved_theme(qapp):
        apply_theme(qapp, "graphite")
        assert model.index(KNOWN, DESCRIPTION).data(Qt.ForegroundRole) is None
        assert drawn_contrast(model, KNOWN, DESCRIPTION) >= 4.5


def test_unknown_name_uses_the_theme_color(qapp):
    model = make_model()
    with preserved_theme(qapp):
        apply_theme(qapp, "graphite")
        assert drawn_foreground(model, UNKNOWN, NAME) == QColor("#f47067")
        apply_theme(qapp, "mist")
        assert drawn_foreground(model, UNKNOWN, NAME) == QColor("#ff0000")


def test_mist_dirty_background_is_unchanged(qapp):
    model = make_model()
    with preserved_theme(qapp):
        apply_theme(qapp, "mist")
        assert model.index(KNOWN, DESCRIPTION).data(Qt.BackgroundRole) == QColor(
            255, 249, 196
        )


def test_switching_theme_changes_model_colors(qapp):
    model = make_model()
    with preserved_theme(qapp):
        apply_theme(qapp, "mist")
        mist = (
            drawn_foreground(model, KNOWN, NAME),
            drawn_foreground(model, UNKNOWN, NAME),
            drawn_background(model, KNOWN, DESCRIPTION),
        )
        apply_theme(qapp, "graphite")
        graphite = (
            drawn_foreground(model, KNOWN, NAME),
            drawn_foreground(model, UNKNOWN, NAME),
            drawn_background(model, KNOWN, DESCRIPTION),
        )
    assert mist == (QColor("#20262d"), QColor("#ff0000"), QColor("#fff9c4"))
    assert graphite == (QColor("#c9d1d9"), QColor("#f47067"), QColor("#3a3220"))
