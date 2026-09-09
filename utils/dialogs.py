from PySide6.QtWidgets import QMessageBox, QWidget


def info(parent: QWidget, title: str, message: str):
    QMessageBox.information(parent, title, message)


def warning(parent: QWidget, title: str, message: str):
    QMessageBox.warning(parent, title, message)


def critical(parent: QWidget, title: str, message: str):
    QMessageBox.critical(parent, title, message)


def error(parent: QWidget, title: str, message: str):
    # critical과 동일하게 동작하지만 이름만 별도로 유지하고 싶을 때
    QMessageBox.critical(parent, title, message)


def question(parent: QWidget, title: str, message: str) -> bool:
    reply = QMessageBox.question(
        parent, title, message, QMessageBox.Yes | QMessageBox.No
    )
    return reply == QMessageBox.Yes