"""테마 색 (phase 22, ADR-019).

- Graphite 는 형제 저장소 pexqa 의 `gui/theme.py`("Dim slate") 토큰과 같다.
- Mist 는 바뀌지 않는다. 사용자가 밝은 테마는 그대로 두라고 했다. 그래서 dict 를 리터럴로,
  스타일시트를 phase 22 전 코드에서 잰 해시로, 팔레트 역할 색을 리터럴로 고정한다.
- 테마마다 다른 의미 색(`selection`, `selection_text`, `dirty`, `unknown_name`)은 THEMES 키이고,
  모델은 `current_colors()` 로 읽는다.

대비 기준(WCAG 4.5)은 Graphite 에만 건다. Mist 의 빨강 `#ff0000` 은 base 위에서 3.8 이지만
바꾸지 말라는 요청대로 둔다. `apply_theme` 를 부르는 테스트는 모두 `preserved_theme` 안에서 돈다.
"""

import hashlib
import subprocess
import sys

from gui_support.theme import preserved_theme
from PySide6.QtGui import QPalette

from genviewer.utils.palette import (
    THEMES,
    _build_palette,
    _build_stylesheet,
    apply_theme,
    current_colors,
)

MIST = {
    "name": "Mist",
    "window": "#dfe6ea",
    "panel": "#edf2f5",
    "base": "#f8fafb",
    "alternate": "#e8eef2",
    "text": "#20262d",
    "muted": "#58636f",
    "border": "#b7c1ca",
    "header": "#d3dde5",
    "button": "#e2e9ee",
    "button_hover": "#d5dfe6",
    "button_pressed": "#c8d5de",
    "accent": "#2f6f73",
    "accent_soft": "#c6dadd",
    "accent_text": "#ffffff",
    "good": "#1d6f52",
    "bad": "#9b3b42",
    "selection": "#2f6f73",
    "selection_text": "#ffffff",
    "dirty": "#fff9c4",
    "unknown_name": "#ff0000",
}

# pexqa `src/pexqa/gui/theme.py` 토큰 (2026-10-22 확인)
GRAPHITE = {
    "name": "Graphite",
    "window": "#22272e",  # WINDOW
    "panel": "#22272e",  # WINDOW. pexqa 는 패널도 창 색이고 경계는 border 로 그린다
    "base": "#1c2128",  # BASE
    "alternate": "#252b33",  # ALT_BASE
    "text": "#c9d1d9",  # TEXT
    "muted": "#8b949e",  # TEXT_MUTED
    "border": "#444c56",  # BORDER
    "header": "#2a3038",  # HEADER
    "button": "#2d333b",  # BUTTON
    "button_hover": "#373e47",  # BUTTON_HOVER
    "button_pressed": "#444c56",  # BUTTON_PRESSED
    "accent": "#539bf5",  # ACCENT
    "accent_soft": "#2c4a72",  # HIGHLIGHT
    "accent_text": "#1c2128",  # BASE. accent 로 채운 Connect 단추의 글자
    "good": "#6bc46d",  # 로그 SUCCESS
    "bad": "#f47067",  # 로그 ERROR
    "selection": "#2c4a72",  # HIGHLIGHT
    "selection_text": "#f0f6fc",  # HIGHLIGHTED_TEXT
    "dirty": "#3a3220",  # 상태 WAITING 배경
    "unknown_name": "#f47067",  # ERROR / PATH_MISSING
}

# phase 22 전 코드의 `_build_stylesheet(THEMES["mist"])` (5190 자) 의 UTF-8 sha256
MIST_STYLESHEET_SHA256 = "197584d4edacc5db5885de0023060c284caffb3496d20edd5e42c95751b48360"

# `_build_palette(THEMES["mist"])` 가 정하는 역할 색 (phase 22 전 코드에서 잰 값)
MIST_PALETTE = {
    QPalette.Window: "#dfe6ea",
    QPalette.WindowText: "#20262d",
    QPalette.Base: "#f8fafb",
    QPalette.AlternateBase: "#e8eef2",
    QPalette.ToolTipBase: "#f8fafb",
    QPalette.ToolTipText: "#20262d",
    QPalette.Text: "#20262d",
    QPalette.Button: "#e2e9ee",
    QPalette.ButtonText: "#20262d",
    QPalette.Link: "#2f6f73",
    QPalette.Highlight: "#2f6f73",
    QPalette.HighlightedText: "#ffffff",
    QPalette.Mid: "#b7c1ca",
    QPalette.Dark: "#d3dde5",
    QPalette.Light: "#edf2f5",
}
MIST_PALETTE_DISABLED = {
    QPalette.Text: "#58636f",
    QPalette.ButtonText: "#58636f",
}

# (글자, 배경). Graphite 에서 대비가 4.5 이상이어야 하는 쌍
GRAPHITE_CONTRAST_PAIRS = [
    ("text", "base"),
    ("text", "alternate"),
    ("text", "dirty"),
    ("unknown_name", "base"),
    ("unknown_name", "alternate"),
    ("selection_text", "selection"),
    ("accent_text", "accent"),
    ("text", "accent_soft"),
    ("good", "panel"),
    ("bad", "panel"),
    ("muted", "panel"),
]


def _luminance(hex_color: str) -> float:
    """WCAG 2 상대 휘도."""
    channels = [int(hex_color[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [
        c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels
    ]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def _contrast(fg: str, bg: str) -> float:
    high, low = sorted((_luminance(fg), _luminance(bg)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def test_contrast_helper_matches_known_values():
    assert round(_contrast("#000000", "#ffffff"), 2) == 21.0
    assert round(_contrast("#ff0000", "#f8fafb"), 2) == 3.82


# --------------------------------------------------------------------------
# Mist 는 그대로
# --------------------------------------------------------------------------


def test_mist_colors_are_unchanged():
    assert THEMES["mist"] == MIST


def test_mist_stylesheet_is_byte_identical(qapp):
    text = _build_stylesheet(THEMES["mist"])
    assert hashlib.sha256(text.encode("utf-8")).hexdigest() == MIST_STYLESHEET_SHA256


def test_mist_palette_roles_are_unchanged(qapp):
    palette = _build_palette(THEMES["mist"])
    groups = (QPalette.Active, QPalette.Inactive, QPalette.Disabled)
    actual = {
        (group.name, role.name): palette.color(group, role).name()
        for group in groups
        for role in MIST_PALETTE
    }
    expected = {
        (group.name, role.name): (
            MIST_PALETTE_DISABLED.get(role, color)
            if group == QPalette.Disabled
            else color
        )
        for group in groups
        for role, color in MIST_PALETTE.items()
    }
    assert actual == expected


# --------------------------------------------------------------------------
# Graphite 는 pexqa 토큰
# --------------------------------------------------------------------------


def test_graphite_colors_are_pexqa_tokens():
    assert THEMES["graphite"] == GRAPHITE


def test_graphite_contrast_meets_wcag_aa():
    colors = THEMES["graphite"]
    low = {
        f"{fg}/{bg}": round(_contrast(colors[fg], colors[bg]), 2)
        for fg, bg in GRAPHITE_CONTRAST_PAIRS
        if _contrast(colors[fg], colors[bg]) < 4.5
    }
    assert low == {}


def test_selection_keys_drive_palette_and_stylesheet(qapp):
    colors = THEMES["graphite"]
    palette = _build_palette(colors)
    assert palette.color(QPalette.Highlight).name() == colors["selection"]
    assert palette.color(QPalette.HighlightedText).name() == colors["selection_text"]

    # 맨 위 `QWidget { … }` 규칙
    head = _build_stylesheet(colors).split("}", 1)[0]
    assert f"selection-background-color: {colors['selection']};" in head
    assert f"selection-color: {colors['selection_text']};" in head


# --------------------------------------------------------------------------
# current_colors()
# --------------------------------------------------------------------------


def test_current_colors_follows_applied_theme(qapp):
    with preserved_theme(qapp):
        apply_theme(qapp, "graphite")
        assert current_colors() == THEMES["graphite"]
        apply_theme(qapp, "mist")
        assert current_colors() == THEMES["mist"]


def test_current_colors_falls_back_to_mist(qapp):
    with preserved_theme(qapp):
        qapp.setProperty("themeName", None)
        assert current_colors() == THEMES["mist"]
        qapp.setProperty("themeName", "bogus")
        assert current_colors() == THEMES["mist"]


def test_current_colors_without_app_is_mist():
    """앱이 없는 인터프리터에서도 mist 를 돌려준다."""
    code = (
        "import sys\n"
        "from genviewer.utils.palette import THEMES, current_colors\n"
        "sys.exit(0 if current_colors() == THEMES['mist'] else 3)\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code],
        timeout=60,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert proc.returncode == 0, proc.stderr


def test_preserved_theme_restores_app_state(qapp):
    before = (
        qapp.font().toString(),
        qapp.palette().color(QPalette.Window).name(),
        qapp.styleSheet(),
        qapp.property("themeName"),
    )
    with preserved_theme(qapp):
        apply_theme(qapp, "graphite")
        assert qapp.property("themeName") == "graphite"
    after = (
        qapp.font().toString(),
        qapp.palette().color(QPalette.Window).name(),
        qapp.styleSheet(),
        qapp.property("themeName"),
    )
    assert after == before
