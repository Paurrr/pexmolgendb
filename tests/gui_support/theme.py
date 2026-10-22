"""앱 테마 상태 헬퍼. `from gui_support.theme import preserved_theme` 로 쓴다.

`apply_theme` 는 앱 전체의 글꼴·팔레트·스타일시트와 `themeName` 속성을 바꾼다. 그대로 두면 뒤
테스트의 글꼴(레이아웃 너비)과 `palette.current_colors()` 결과가 테스트 순서에 따라 달라진다.
`apply_theme` 를 부르는 테스트는 이 컨텍스트 안에서 돈다.
"""

from collections.abc import Iterator
from contextlib import contextmanager

from PySide6.QtGui import QFont, QPalette
from PySide6.QtWidgets import QApplication


@contextmanager
def preserved_theme(app: QApplication) -> Iterator[QApplication]:
    """들어갈 때의 글꼴·팔레트·스타일시트·`themeName` 을 나갈 때 그대로 되돌린다.

    `themeName` 이 없었으면 None 을 넣어 속성을 지운다(PySide6 는 None 을 빈 QVariant 로 넘긴다).
    """
    font = QFont(app.font())
    palette = QPalette(app.palette())
    style_sheet = app.styleSheet()
    theme_name = app.property("themeName")
    try:
        yield app
    finally:
        app.setStyleSheet(style_sheet)
        app.setPalette(palette)
        app.setFont(font)
        app.setProperty("themeName", theme_name)
