from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import QApplication

THEMES = {
    "mist": {
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
    },
    "graphite": {
        "name": "Graphite",
        "window": "#22272e",
        "panel": "#22272e",
        "base": "#1c2128",
        "alternate": "#252b33",
        "text": "#c9d1d9",
        "muted": "#8b949e",
        "border": "#444c56",
        "header": "#2a3038",
        "button": "#2d333b",
        "button_hover": "#373e47",
        "button_pressed": "#444c56",
        "accent": "#539bf5",
        "accent_soft": "#2c4a72",
        "accent_text": "#1c2128",
        "good": "#6bc46d",
        "bad": "#f47067",
        "selection": "#2c4a72",
        "selection_text": "#f0f6fc",
        "dirty": "#3a3220",
        "unknown_name": "#f47067",
    },
}


def apply_theme(app, theme_name: str = "mist"):
    colors = THEMES.get(theme_name, THEMES["mist"])
    app.setProperty("themeName", theme_name)
    app.setFont(_compact_font(app.font()))
    app.setPalette(_build_palette(colors))
    app.setStyleSheet(_build_stylesheet(colors))


def current_colors() -> dict:
    """지금 앱 테마의 색 dict. 모델의 data() 가 부르므로 dict 조회만 한다.

    `apply_theme` 가 남긴 앱 속성 `themeName` 으로 고른다. 앱이 없거나, 속성이 없거나, 모르는
    이름이면 mist 다(`apply_theme` 의 기본값과 같다).
    """
    app = QApplication.instance()
    name = app.property("themeName") if app is not None else None
    return THEMES.get(name, THEMES["mist"])


def _compact_font(font: QFont) -> QFont:
    compact = QFont(font)
    compact.setPointSize(9)
    return compact


def _build_palette(colors: dict) -> QPalette:
    palette = QPalette()

    palette.setColor(QPalette.Window, QColor(colors["window"]))
    palette.setColor(QPalette.WindowText, QColor(colors["text"]))
    palette.setColor(QPalette.Base, QColor(colors["base"]))
    palette.setColor(QPalette.AlternateBase, QColor(colors["alternate"]))
    palette.setColor(QPalette.ToolTipBase, QColor(colors["base"]))
    palette.setColor(QPalette.ToolTipText, QColor(colors["text"]))
    palette.setColor(QPalette.Text, QColor(colors["text"]))
    palette.setColor(QPalette.Disabled, QPalette.Text, QColor(colors["muted"]))
    palette.setColor(QPalette.Button, QColor(colors["button"]))
    palette.setColor(QPalette.ButtonText, QColor(colors["text"]))
    palette.setColor(QPalette.Disabled, QPalette.ButtonText, QColor(colors["muted"]))
    palette.setColor(QPalette.Link, QColor(colors["accent"]))
    palette.setColor(QPalette.Highlight, QColor(colors["selection"]))
    palette.setColor(QPalette.HighlightedText, QColor(colors["selection_text"]))
    palette.setColor(QPalette.Mid, QColor(colors["border"]))
    palette.setColor(QPalette.Dark, QColor(colors["header"]))
    palette.setColor(QPalette.Light, QColor(colors["panel"]))

    return palette


def _build_stylesheet(colors: dict) -> str:
    return f"""
        QWidget {{
            color: {colors["text"]};
            selection-background-color: {colors["selection"]};
            selection-color: {colors["selection_text"]};
        }}

        QMainWindow,
        QStackedWidget,
        QDialog {{
            background-color: {colors["window"]};
        }}

        QToolBar {{
            background-color: {colors["panel"]};
            border-bottom: 1px solid {colors["border"]};
            spacing: 3px;
            padding: 1px 3px;
        }}

        QMenuBar,
        QMenu {{
            background-color: {colors["panel"]};
            color: {colors["text"]};
            border: 1px solid {colors["border"]};
        }}

        QMenuBar::item:selected,
        QMenu::item:selected {{
            background-color: {colors["accent_soft"]};
        }}

        QListWidget {{
            border: none;
            background-color: {colors["panel"]};
            outline: 0;
        }}

        QListWidget::item {{
            padding: 5px 7px;
            min-height: 24px;
            border-bottom: 1px solid {colors["border"]};
            color: {colors["muted"]};
        }}

        QListWidget::item:selected {{
            background-color: {colors["base"]};
            border-left: 3px solid {colors["accent"]};
            color: {colors["text"]};
            font-weight: 600;
        }}

        QWidget#LabeledTablePanel,
        QWidget#TabSectionHeader,
        QWidget#DeviceTabControlToolBar {{
            background-color: {colors["panel"]};
            border: 1px solid {colors["border"]};
        }}

        QWidget#DeviceTabControlToolBar {{
            border-left: none;
            border-right: none;
            border-top: none;
        }}

        QLabel#PanelTitle,
        QLabel#TabSectionTitle {{
            color: {colors["text"]};
        }}

        QLineEdit,
        QComboBox,
        QTextEdit {{
            background-color: {colors["base"]};
            color: {colors["text"]};
            border: 1px solid {colors["border"]};
            border-radius: 3px;
            padding: 1px 4px;
            min-height: 19px;
        }}

        QLineEdit[requiredField="true"],
        QComboBox[requiredField="true"] {{
            border-left: 3px solid {colors["accent"]};
        }}

        QComboBox::drop-down {{
            width: 18px;
            border-left: 1px solid {colors["border"]};
        }}

        QPushButton {{
            background-color: {colors["button"]};
            color: {colors["text"]};
            border: 1px solid {colors["border"]};
            border-radius: 3px;
            padding: 2px 7px;
            min-height: 19px;
        }}

        QPushButton:hover {{
            background-color: {colors["button_hover"]};
        }}

        QPushButton:pressed,
        QPushButton:checked {{
            background-color: {colors["accent_soft"]};
            border-color: {colors["accent"]};
        }}

        QPushButton#ConnectButton {{
            background-color: {colors["accent"]};
            border-color: {colors["accent"]};
            color: {colors["accent_text"]};
            font-weight: 600;
        }}

        QLabel#ConnectionStatus[connected="true"] {{
            color: {colors["good"]};
            font-weight: 600;
        }}

        QLabel#ConnectionStatus[connected="false"] {{
            color: {colors["bad"]};
            font-weight: 600;
        }}

        QLabel#ErrorLabel {{
            color: {colors["bad"]};
            font-weight: 600;
        }}

        QFrame#RefreshBanner {{
            background-color: {colors["accent_soft"]};
            border-top: 1px solid {colors["accent"]};
            border-bottom: 1px solid {colors["accent"]};
        }}

        QLabel#RefreshBannerText {{
            color: {colors["text"]};
            font-weight: 600;
        }}

        QTableView {{
            background-color: {colors["base"]};
            alternate-background-color: {colors["alternate"]};
            color: {colors["text"]};
            border: 1px solid {colors["border"]};
            gridline-color: {colors["border"]};
            selection-background-color: {colors["accent_soft"]};
            selection-color: {colors["text"]};
        }}

        QTableView::item {{
            padding: 0px 3px;
        }}

        QHeaderView::section {{
            background-color: {colors["header"]};
            color: {colors["text"]};
            padding: 2px 4px;
            border: none;
            border-right: 1px solid {colors["border"]};
            border-bottom: 1px solid {colors["border"]};
            min-height: 18px;
        }}

        QTabWidget::pane {{
            border: 1px solid {colors["border"]};
            background-color: {colors["panel"]};
            top: -1px;
        }}

        QTabBar::tab {{
            background-color: {colors["button"]};
            color: {colors["muted"]};
            padding: 3px 8px;
            min-height: 18px;
            border: 1px solid {colors["border"]};
            border-bottom: none;
            border-top-left-radius: 3px;
            border-top-right-radius: 3px;
            margin-right: 1px;
        }}

        QTabBar::tab:selected {{
            background-color: {colors["accent_soft"]};
            color: {colors["text"]};
            border-color: {colors["accent"]};
            font-weight: 600;
        }}

        QTabBar::tab:hover {{
            background-color: {colors["button_hover"]};
            color: {colors["text"]};
        }}

        QSplitter::handle {{
            background-color: {colors["border"]};
        }}

        QStatusBar {{
            background-color: {colors["panel"]};
            color: {colors["muted"]};
            border-top: 1px solid {colors["border"]};
        }}
    """
