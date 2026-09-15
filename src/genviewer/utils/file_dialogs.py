from PySide6.QtWidgets import QFileDialog, QWidget


def open_file(
    parent: QWidget, title: str, filter_str: str = "", start_dir: str = ""
) -> str:
    """단일 파일 열기 다이얼로그"""
    options = QFileDialog.Options()
    options |= QFileDialog.DontUseNativeDialog
    path, _ = QFileDialog.getOpenFileName(
        parent, title, start_dir, filter_str, options=options
    )
    return path or ""


def save_file(
    parent: QWidget, title: str, filter_str: str = "", start_dir: str = ""
) -> str:
    """파일 저장 다이얼로그"""
    options = QFileDialog.Options()
    options |= QFileDialog.DontUseNativeDialog
    path, _ = QFileDialog.getSaveFileName(
        parent, title, start_dir, filter_str, options=options
    )
    return path or ""

